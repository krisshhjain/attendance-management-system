#!/usr/bin/env python3
"""Collect SonarQube PR measures and summarize local coverage.py JSON.

Writes reports outside the repository by default. Sonar credentials, when
needed, are read only from SONAR_TOKEN and sent in an HTTP Authorization
header; they are never persisted or printed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

METRICS = (
    "new_coverage",
    "new_uncovered_lines",
    "new_uncovered_conditions",
    "new_lines_to_cover",
    "new_conditions_to_cover",
    "coverage",
)
PRIORITY_PATHS = {
    "backend/hr_copilot/services/write_actions.py": 1,
    "backend/attendance/views.py": 2,
    "backend/hr_copilot/services/pipeline.py": 3,
    "backend/hr_copilot/views.py": 4,
    "backend/hr_copilot/services/write_executor.py": 5,
}
DEFAULT_PROJECT = "krisshhjain_attendance-management-system"
DEFAULT_ORG = "krisshhjain"
DEFAULT_SONAR = "https://sonarcloud.io"
DEFAULT_REPOSITORY = "krisshhjain/attendance-management-system"


def gh_json(args: list[str], root: Path) -> dict:
    """Call gh using its existing credential store; never print command output on errors."""
    proc = subprocess.run(["gh", "api", *args], cwd=root, text=True,
                          capture_output=True, encoding="utf-8", errors="replace")
    if proc.returncode:
        raise RuntimeError("GitHub CLI API request failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub CLI returned invalid JSON") from exc


def github_artifact_coverage(root: Path, repo: str, pr: str, output_dir: Path) -> dict:
    """Find the successful Actions run for the PR head and download its coverage artifact."""
    result = {"status": "unavailable", "repository": repo, "pull_request": pr}
    try:
        pull = gh_json([f"repos/{repo}/pulls/{pr}"], root)
        head = pull["head"]["sha"]
        result["head"] = head
        runs = gh_json([f"repos/{repo}/actions/runs?head_sha={head}&per_page=100"], root).get("workflow_runs", [])
        successful = [run for run in runs if run.get("head_sha") == head and run.get("status") == "completed" and run.get("conclusion") == "success"]
        if not successful:
            result["reason"] = "No successful Actions run was found for the current PR head"
            return result
        run = max(successful, key=lambda item: item.get("run_number", 0))
        artifacts = gh_json([f"repos/{repo}/actions/runs/{run['id']}/artifacts?per_page=100"], root).get("artifacts", [])
        artifact = next((item for item in artifacts if item.get("name") == "backend-coverage" and not item.get("expired")), None)
        if artifact is None:
            result["reason"] = "Successful run has no unexpired backend-coverage artifact"
            return result
        destination = output_dir / "github-artifacts"
        destination.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(["gh", "run", "download", str(run["id"]), "--repo", repo,
                               "--name", "backend-coverage", "--dir", str(destination)],
                              cwd=root, text=True, capture_output=True, encoding="utf-8", errors="replace")
        if proc.returncode:
            result["reason"] = "GitHub CLI could not download backend-coverage"
            return result
        candidates = list(destination.rglob("coverage.json"))
        if not candidates:
            result["reason"] = "Downloaded artifact did not contain coverage.json"
            return result
        result.update(status="available", run_id=run["id"], run_number=run.get("run_number"),
                      artifact_id=artifact.get("id"), coverage_json=str(candidates[0]))
        return result
    except (OSError, KeyError, RuntimeError, json.JSONDecodeError):
        result["reason"] = "GitHub CLI unavailable or authenticated API request failed"
        return result


def github_sonar_gate(root: Path, repo: str, head: str | None) -> dict:
    if not head:
        return {"status": "unavailable", "reason": "PR head SHA unavailable"}
    try:
        data = gh_json([f"repos/{repo}/commits/{head}/check-runs?per_page=100"], root)
        checks = [item for item in data.get("check_runs", [])
                  if "sonar" in item.get("name", "").lower() or "quality gate" in item.get("name", "").lower()]
        checks.sort(key=lambda item: item.get("completed_at") or item.get("started_at") or "", reverse=True)
        if checks:
            item = checks[0]
            return {"status": "available", "name": item.get("name"), "conclusion": item.get("conclusion"),
                    "status_text": item.get("status"), "completed_at": item.get("completed_at"),
                    "details_url": item.get("details_url"), "summary": item.get("output", {}).get("summary", "")}
        return {"status": "unavailable", "reason": "No Sonar quality-gate check found on current PR head"}
    except (OSError, KeyError, RuntimeError, json.JSONDecodeError):
        return {"status": "unavailable", "reason": "GitHub CLI unavailable or authenticated API request failed"}


def request_json(url: str, token: str | None = None) -> dict:
    headers = {"Accept": "application/json", "User-Agent": "coverage-triage/1.0"}
    if token:
        import base64

        encoded = base64.b64encode((token + ":").encode()).decode("ascii")
        headers["Authorization"] = "Basic " + encoded
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def sonar_measures(base_url: str, project: str, pr: str, token: str | None) -> dict:
    result: dict = {"status": "unavailable", "project": project, "pull_request": pr, "measures": [], "files": [], "errors": []}
    base_url = base_url.rstrip("/")
    params = urllib.parse.urlencode({"component": project, "pullRequest": pr, "metricKeys": ",".join(METRICS)})
    try:
        data = request_json(f"{base_url}/api/measures/component?{params}", token)
        result["measures"] = data.get("component", {}).get("measures", [])
        result["status"] = "available"
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        code = getattr(exc, "code", None)
        result["errors"].append({"endpoint": "component measures", "http_status": code, "message": str(exc)})
        # An unauthenticated public project may allow measures but deny file
        # detail; retry with the authorized token if one was supplied.
        if not token:
            token = os.environ.get("SONAR_TOKEN") or None
            if token:
                try:
                    data = request_json(f"{base_url}/api/measures/component?{params}", token)
                    result["measures"] = data.get("component", {}).get("measures", [])
                    result["status"] = "available_authenticated"
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as retry_exc:
                    result["errors"].append({"endpoint": "component measures (authenticated)", "http_status": getattr(retry_exc, "code", None), "message": str(retry_exc)})

    # Page through file-level measures when the server supports this endpoint.
    page = 1
    while True:
        query = urllib.parse.urlencode({
            "component": project,
            "pullRequest": pr,
            "metricKeys": ",".join(METRICS),
            "qualifiers": "FIL",
            "ps": 500,
            "p": page,
        })
        try:
            data = request_json(f"{base_url}/api/measures/component_tree?{query}", token)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            result["errors"].append({"endpoint": "component tree", "http_status": getattr(exc, "code", None), "message": str(exc)})
            break
        result["files"].extend(data.get("components", []))
        paging = data.get("paging", {})
        if page * int(paging.get("pageSize", 500)) >= int(paging.get("total", 0)):
            break
        page += 1
    return result


def changed_lines(root: Path, base: str) -> dict[str, set[int]]:
    proc = subprocess.run(
        ["git", "diff", "--unified=0", f"{base}...HEAD", "--", "*.py"],
        cwd=root, check=True, text=True, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    changed: dict[str, set[int]] = {}
    path = None
    line = 0
    for row in proc.stdout.splitlines():
        if row.startswith("+++ b/"):
            path = row[6:]
            changed.setdefault(path, set())
        elif row.startswith("@@"):
            import re

            match = re.search(r"\+(\d+)(?:,(\d+))?", row)
            if match:
                line = int(match.group(1))
        elif path and row.startswith("+") and not row.startswith("+++"):
            changed[path].add(line)
            line += 1
        elif path and not row.startswith("-"):
            line += 1
    return changed


def local_summary(path: Path, root: Path, changed: dict[str, set[int]]) -> dict:
    if not path.exists():
        return {"available": False, "reason": f"coverage JSON not found: {path}", "files": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    files = []
    for filename, details in data.get("files", {}).items():
        normalized = Path(filename).as_posix()
        try:
            relative = Path(filename).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            relative = normalized.lstrip("/")
            remote_backend = "/backend/"
            if remote_backend in "/" + normalized:
                relative = "backend/" + normalized.split(remote_backend, 1)[1]
        if not (root / relative).exists() and (root / "backend" / relative).exists():
            relative = "backend/" + relative
        if relative not in changed and (root / "backend" / relative).exists():
            relative = "backend/" + relative
        missing = details.get("missing_lines", [])
        missing_branches = details.get("missing_branches", [])
        changed_set = changed.get(relative, set())
        changed_branches = [arc for arc in missing_branches
                            if isinstance(arc, (list, tuple)) and arc and arc[0] in changed_set]
        business_terms = ("auth", "permission", "scope", "validate", "write", "execute",
                          "attendance", "leave", "transaction", "approval", "security", "pipeline")
        business_score = sum(term in relative.lower() for term in business_terms)
        files.append({
            "path": relative,
            "priority": PRIORITY_PATHS.get(relative),
            "reachable_business_logic_score": business_score,
            "executed_statements": details.get("executed_lines", []),
            "executed_statement_count": details.get("summary", {}).get("covered_lines"),
            "missing_statements": missing,
            "missing_branches": missing_branches,
            "missing_changed_branches": changed_branches,
            "changed_lines": sorted(changed_set),
            "missing_changed_statements": sorted(set(missing) & changed_set),
            "missing_statement_count": len(missing),
            "missing_branch_count": len(missing_branches),
        })
    for item in files:
        item["sonar_new_uncovered_lines"] = None
        item["sonar_new_uncovered_conditions"] = None
        item["uncovered_new_code_impact"] = len(item["missing_changed_statements"]) + len(item["missing_changed_branches"])
    files.sort(key=lambda item: (-item["uncovered_new_code_impact"],
                                -item["reachable_business_logic_score"],
                                -(item["missing_statement_count"] + item["missing_branch_count"]),
                                item["path"]))
    return {"available": True, "totals": data.get("totals", {}), "files": files}


def apply_sonar_file_metrics(local: dict, sonar: dict) -> None:
    if not local.get("available"):
        return
    metrics = {item["path"]: {entry.get("metric"): entry.get("value")
                               for entry in item.get("measures", [])}
               for item in sonar.get("files", [])}
    for file in local["files"]:
        candidates = (file["path"], file["path"].removeprefix("backend/"))
        values = next((metrics[key] for key in metrics
                       if any(key.endswith(candidate) for candidate in candidates)), {})
        try:
            file["sonar_new_uncovered_lines"] = int(values["new_uncovered_lines"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            file["sonar_new_uncovered_conditions"] = int(values["new_uncovered_conditions"])
        except (KeyError, TypeError, ValueError):
            pass
        if file["sonar_new_uncovered_lines"] is not None or file["sonar_new_uncovered_conditions"] is not None:
            file["uncovered_new_code_impact"] = (file["sonar_new_uncovered_lines"] or 0) + 2 * (file["sonar_new_uncovered_conditions"] or 0)
    local["files"].sort(key=lambda item: (-item["uncovered_new_code_impact"],
                                         -item["reachable_business_logic_score"],
                                         -(item["missing_statement_count"] + item["missing_branch_count"]),
                                         item["path"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--coverage-json", type=Path, default=Path("backend/coverage.json"))
    parser.add_argument("--base", default="origin/develop")
    parser.add_argument("--sonar-url", default=os.environ.get("SONAR_URL", DEFAULT_SONAR))
    parser.add_argument("--organization", default=os.environ.get("SONAR_ORGANIZATION", DEFAULT_ORG))
    parser.add_argument("--project", default=os.environ.get("SONAR_PROJECT_KEY", DEFAULT_PROJECT))
    parser.add_argument("--pull-request", default=os.environ.get("SONAR_PULL_REQUEST", "15"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--output-dir", type=Path, default=Path(os.environ.get("TEMP", "/tmp")) / "attendance-coverage-triage")
    parser.add_argument("--no-sonar", action="store_true", help="Only summarize local coverage data")
    parser.add_argument("--no-github", action="store_true", help="Skip GitHub run discovery and artifact download")
    args = parser.parse_args()

    root = args.root.resolve()
    coverage_path = args.coverage_json if args.coverage_json.is_absolute() else root / args.coverage_json
    github = {"status": "skipped", "reason": "--no-github"} if args.no_github else github_artifact_coverage(root, args.repo, args.pull_request, args.output_dir)
    if github.get("status") == "available":
        coverage_path = Path(github["coverage_json"])
    changed = changed_lines(root, args.base)
    local = local_summary(coverage_path, root, changed)
    sonar = {"status": "skipped", "reason": "--no-sonar"} if args.no_sonar else sonar_measures(args.sonar_url, args.project, args.pull_request, os.environ.get("SONAR_TOKEN") or None)
    apply_sonar_file_metrics(local, sonar)
    head = github.get("head") or subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True).stdout.strip()
    sonar_gate = github_sonar_gate(root, args.repo, head) if sonar.get("status") == "unavailable" else {"status": "not_needed"}
    report = {
        "organization": args.organization,
        "base": args.base,
        "head": head,
        "github_coverage_artifact": github,
        "sonar": sonar,
        "sonar_quality_gate_fallback": sonar_gate,
        "local_coverage": local,
        "mapping_caveat": "coverage.py local execution and changed-line mapping are not equivalent to SonarQube new-code coverage; Sonar's own PR measures are authoritative.",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "coverage-triage.json"
    if local.get("available") and report_path.exists():
        try:
            previous = json.loads(report_path.read_text(encoding="utf-8"))
            previous_local = previous.get("local_coverage", {})
            if previous_local.get("available"):
                previous_files = {item["path"]: item for item in previous_local.get("files", [])}
                comparison = {}
                for item in local["files"]:
                    old = previous_files.get(item["path"])
                    if old is not None:
                        comparison[item["path"]] = {
                            "missing_statements_before": old["missing_statement_count"],
                            "missing_statements_after": item["missing_statement_count"],
                            "missing_branches_before": old["missing_branch_count"],
                            "missing_branches_after": item["missing_branch_count"],
                        }
                report["coverage_comparison"] = {
                    "baseline_head": previous.get("head"),
                    "line_coverage_before": previous_local.get("totals", {}).get("percent_covered"),
                    "line_coverage_after": local.get("totals", {}).get("percent_covered"),
                    "files": comparison,
                }
        except (OSError, json.JSONDecodeError):
            pass
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Coverage triage", "", f"- Head: `{report['head']}`", f"- Base: `{args.base}`", f"- GitHub coverage artifact: `{github.get('status')}`", f"- Sonar PR measures: `{sonar.get('status')}`"]
    measures = {entry.get("metric"): entry.get("value") for entry in sonar.get("measures", [])}
    if measures:
        lines.extend([f"- Sonar new coverage: {measures.get('new_coverage', 'unavailable')}%", f"- New uncovered lines: {measures.get('new_uncovered_lines', 'unavailable')}"])
    if sonar_gate.get("status") == "available":
        lines.append(f"- Sonar GitHub quality gate: {sonar_gate.get('conclusion')} ({sonar_gate.get('name')})")
    lines.append(f"- Local coverage JSON: {'available' if local.get('available') else local.get('reason')}")
    if local.get("available"):
        lines.extend(["", "## Priority target gaps", ""])
        for item in local["files"][:15]:
            lines.append(f"- `{item['path']}`: impact {item['uncovered_new_code_impact']}, Sonar uncovered lines/conditions {item['sonar_new_uncovered_lines']}/{item['sonar_new_uncovered_conditions']}; {item['missing_statement_count']} missing statements, {item['missing_branch_count']} missing branch arcs; {len(item['missing_changed_statements'])} missed changed statements and {len(item['missing_changed_branches'])} missed changed branch arcs; business-logic score {item['reachable_business_logic_score']}")
    lines.extend(["", f"> {report['mapping_caveat']}", ""])
    (args.output_dir / "coverage-triage.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote coverage triage reports to {args.output_dir}")
    if sonar.get("errors"):
        print(f"Sonar data unavailable or partial ({len(sonar['errors'])} API issue(s)); see report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
