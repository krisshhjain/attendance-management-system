#!/usr/bin/env python3
"""Report uncovered frontend production code from Vitest and Sonar artifacts."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

REPOSITORY = "krisshhjain/attendance-management-system"
PROJECT_KEY = "krisshhjain_attendance-management-system"
METRICS = (
    "coverage",
    "lines_to_cover",
    "uncovered_lines",
    "branch_coverage",
    "conditions_to_cover",
    "uncovered_conditions",
    "functions",
    "uncovered_functions",
    "new_coverage",
    "new_uncovered_lines",
    "new_uncovered_conditions",
)


def gh_json(root: Path, endpoint: str) -> dict:
    result = subprocess.run(
        ["gh", "api", endpoint], cwd=root, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise RuntimeError("GitHub CLI request failed")
    return json.loads(result.stdout)


def download_frontend_artifact(root: Path, repo: str, pr: str, output: Path) -> dict:
    result = {"status": "unavailable", "repository": repo, "pull_request": pr}
    try:
        pull = gh_json(root, f"repos/{repo}/pulls/{pr}")
        head = pull["head"]["sha"]
        result["head"] = head
        runs = gh_json(root, f"repos/{repo}/actions/runs?head_sha={head}&per_page=100").get("workflow_runs", [])
        completed = [
            run for run in runs
            if run.get("head_sha") == head and run.get("status") == "completed" and run.get("conclusion") == "success"
        ]
        if not completed:
            result["reason"] = "No successful Actions run exists for the exact PR head"
            return result
        run = max(completed, key=lambda item: (item.get("run_number", 0), item.get("id", 0)))
        artifacts = gh_json(root, f"repos/{repo}/actions/runs/{run['id']}/artifacts?per_page=100").get("artifacts", [])
        artifact = next((item for item in artifacts if item.get("name") == "frontend-coverage" and not item.get("expired")), None)
        if artifact is None:
            result["reason"] = "Successful exact-head run has no unexpired frontend-coverage artifact"
            return result
        destination = output / "github-artifacts" / f"{run['id']}-{uuid.uuid4().hex}"
        destination.mkdir(parents=True, exist_ok=True)
        download = subprocess.run(
            ["gh", "run", "download", str(run["id"]), "--repo", repo, "--name", "frontend-coverage", "--dir", str(destination)],
            cwd=root, capture_output=True, text=True, encoding="utf-8",
        )
        if download.returncode:
            result["reason"] = "GitHub CLI could not download frontend-coverage"
            return result
        lcov = next(destination.rglob("lcov.info"), None)
        coverage_json = next(destination.rglob("coverage-final.json"), None)
        if not lcov or not coverage_json:
            result["reason"] = "Artifact must contain lcov.info and coverage-final.json"
            return result
        result.update(status="available", run_id=run["id"], run_number=run.get("run_number"), artifact_id=artifact.get("id"))
        result["lcov_path"] = str(lcov)
        result["coverage_json"] = str(coverage_json)
        return result
    except (OSError, KeyError, RuntimeError, json.JSONDecodeError):
        result["reason"] = "GitHub CLI unavailable or authenticated request failed"
        return result


def parse_lcov(path: Path, root: Path) -> dict[str, dict]:
    files: dict[str, dict] = {}
    current = None
    for row in path.read_text(encoding="utf-8").splitlines():
        if row.startswith("SF:"):
            source = row[3:].replace("\\", "/")
            if source.startswith("frontend/"):
                current = source
            else:
                current = f"frontend/{source.lstrip('./')}"
            files[current] = {"missing_lines": [], "missing_functions": [], "missing_branches": []}
        elif current and row.startswith("DA:"):
            line, count, *_ = row[3:].split(",")
            if int(count) == 0:
                files[current]["missing_lines"].append(int(line))
        elif current and row.startswith("FNDA:"):
            count, name = row[5:].split(",", 1)
            if int(count) == 0:
                files[current]["missing_functions"].append(name)
        elif current and row.startswith("BRDA:"):
            line, block, branch, count = row[5:].split(",")
            if count == "0":
                files[current]["missing_branches"].append({"line": int(line), "block": block, "branch": branch})
    for item in files.values():
        item["missing_lines"] = sorted(set(item["missing_lines"]))
    return files


def normalized_source(filename: str, root: Path) -> tuple[str, Path] | None:
    path = Path(filename).resolve()
    try:
        relative = path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    if not relative.startswith("frontend/src/") or not path.is_file():
        return None
    return relative, path


def source_priority(path: str) -> int:
    value = path.lower()
    if any(term in value for term in ("auth", "requireauth", "permission", "login")):
        return 5
    if any(term in value for term in ("attendance", "regularization", "geofence", "location")):
        return 5
    if any(term in value for term in ("leave", "hr-copilot", "organization", "api.js")):
        return 4
    if any(term in value for term in ("admin", "employee", "webcam", "face", "kiosk")):
        return 3
    return 1


def local_coverage(path: Path, root: Path, lcov_path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    lcov = parse_lcov(lcov_path, root)
    files = []
    for filename, data in raw.items():
        normalized = normalized_source(filename, root)
        if not normalized:
            continue
        relative, source_path = normalized
        missing_lines = set()
        for key, location in data.get("statementMap", {}).items():
            if data.get("s", {}).get(key, 0) == 0:
                missing_lines.add(location["start"]["line"])
        missing_functions = []
        for key, function in data.get("fnMap", {}).items():
            if data.get("f", {}).get(key, 0) == 0:
                missing_functions.append({"name": function.get("name", "anonymous"), "line": function["loc"]["start"]["line"]})
        missing_branches = []
        for key, branch in data.get("branchMap", {}).items():
            counts = data.get("b", {}).get(key, [])
            locations = branch.get("locations", [])
            for index, count in enumerate(counts):
                if count == 0:
                    location = locations[index] if index < len(locations) else branch["loc"]
                    line = location.get("start", {}).get("line") or branch.get("line")
                    missing_branches.append({"line": line, "branch": index})
        source_lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
        statement_counts = data.get("s", {})
        function_counts = data.get("f", {})
        branch_counts = data.get("b", {})
        statement_total = len(statement_counts)
        statement_covered = sum(count > 0 for count in statement_counts.values())
        function_total = len(function_counts)
        function_covered = sum(count > 0 for count in function_counts.values())
        branch_total = sum(len(counts) for counts in branch_counts.values())
        branch_covered = sum(count > 0 for counts in branch_counts.values() for count in counts)
        source_lines_total = {location["start"]["line"] for location in data.get("statementMap", {}).values()}
        source_lines_covered = {
            data["statementMap"][key]["start"]["line"]
            for key, count in statement_counts.items()
            if count > 0 and key in data.get("statementMap", {})
        }
        examples = [
            {"line": line, "source": source_lines[line - 1].strip()[:240]}
            for line in sorted(missing_lines)[:5]
            if 0 < line <= len(source_lines)
        ]
        priority = source_priority(relative)
        impact = priority * (len(missing_lines) + 2 * len(missing_branches) + 3 * len(missing_functions))
        lcov_record = lcov.get(relative, {})
        files.append({
            "path": relative,
            "priority": priority,
            "impact_score": impact,
            "source_exists": True,
            "source_lines": len(source_lines),
            "coverage": {
                "statements_covered": statement_covered,
                "statements_total": statement_total,
                "branches_covered": branch_covered,
                "branches_total": branch_total,
                "functions_covered": function_covered,
                "functions_total": function_total,
                "lines_covered": len(source_lines_covered),
                "lines_total": len(source_lines_total),
            },
            "missing_lines": sorted(missing_lines),
            "missing_branches": missing_branches,
            "missing_functions": missing_functions,
            "source_examples": examples,
            "lcov_missing_line_count": len(lcov_record.get("missing_lines", [])),
            "lcov_missing_branch_count": len(lcov_record.get("missing_branches", [])),
            "lcov_missing_function_count": len(lcov_record.get("missing_functions", [])),
        })
    files.sort(key=lambda item: (-item["impact_score"], -len(item["missing_lines"]), item["path"]))
    totals = {
        key: sum(item["coverage"][key] for item in files)
        for key in (
            "statements_covered", "statements_total", "branches_covered", "branches_total",
            "functions_covered", "functions_total", "lines_covered", "lines_total",
        )
    }
    for unit in ("statements", "branches", "functions", "lines"):
        numerator = totals[f"{unit}_covered"]
        denominator = totals[f"{unit}_total"]
        totals[f"{unit}_coverage"] = round(100 * numerator / denominator, 2) if denominator else None
    return {
        "files": files,
        "source_file_count": len(files),
        "uncovered_line_count": sum(len(item["missing_lines"]) for item in files),
        "totals": totals,
    }


def sonar_file_measures(url: str, project: str, pr: str | None, token: str | None) -> dict:
    params = {"component": project, "metricKeys": ",".join(METRICS), "qualifiers": "FIL", "ps": 500}
    if pr:
        params["pullRequest"] = pr
    query = urllib.parse.urlencode(params)
    headers = {"Accept": "application/json", "User-Agent": "frontend-coverage-triage/1.0"}
    if token:
        encoded = base64.b64encode((token + ":").encode()).decode("ascii")
        headers["Authorization"] = "Basic " + encoded
    request = urllib.request.Request(f"{url.rstrip('/')}/api/measures/component_tree?{query}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
        return {"status": "available", "files": data.get("components", [])}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
        return {"status": "unavailable", "reason": str(error), "files": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--coverage-json", type=Path, default=Path("frontend/coverage/coverage-final.json"))
    parser.add_argument("--lcov", type=Path, default=Path("frontend/coverage/lcov.info"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", REPOSITORY))
    parser.add_argument("--pull-request", default=os.environ.get("GITHUB_PR_NUMBER"))
    parser.add_argument("--sonar-url", default=os.environ.get("SONAR_URL", "https://sonarcloud.io"))
    parser.add_argument("--project", default=os.environ.get("SONAR_PROJECT_KEY", PROJECT_KEY))
    parser.add_argument("--no-github", action="store_true", help="Use the local coverage artifacts")
    parser.add_argument("--no-sonar", action="store_true", help="Skip Sonar file-level measures")
    parser.add_argument("--output-dir", type=Path, default=Path(os.environ.get("TEMP", "/tmp")) / "frontend-coverage-triage")
    args = parser.parse_args()

    root = args.root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    github = {"status": "skipped", "reason": "--no-github"}
    coverage_path = args.coverage_json if args.coverage_json.is_absolute() else root / args.coverage_json
    lcov_path = args.lcov if args.lcov.is_absolute() else root / args.lcov
    if not args.no_github and args.pull_request:
        github = download_frontend_artifact(root, args.repo, args.pull_request, args.output_dir)
        if github.get("status") == "available":
            coverage_path = Path(github["coverage_json"])
            lcov_path = Path(github["lcov_path"])

    local = local_coverage(coverage_path, root, lcov_path)
    sonar = {"status": "skipped", "files": []} if args.no_sonar else sonar_file_measures(
        args.sonar_url, args.project, args.pull_request, os.environ.get("SONAR_TOKEN") or None
    )
    sonar_files = {item.get("path", ""): item.get("measures", []) for item in sonar.get("files", [])}
    for item in local["files"]:
        item["sonar_measures"] = sonar_files.get(item["path"], [])
    report = {
        "repository": args.repo,
        "pull_request": args.pull_request,
        "github_artifact": github,
        "sonar": {"status": sonar.get("status"), "reason": sonar.get("reason")},
        "local_coverage": local,
        "coverage_json": str(coverage_path),
        "lcov": str(lcov_path),
    }
    (args.output_dir / "frontend-coverage-triage.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Frontend coverage triage", "",
        f"- Repository: `{args.repo}`", f"- PR: `{args.pull_request or 'not specified'}`",
        f"- Exact-head GitHub artifact: `{github.get('status')}` (run `{github.get('run_id', 'n/a')}`, artifact `{github.get('artifact_id', 'n/a')}`)",
        f"- Sonar file measures: `{sonar.get('status')}`",
        f"- Local source files measured: {local['source_file_count']}",
        f"- Missing executable lines: {local['uncovered_line_count']}", "",
        f"- Statement / branch / function / line coverage: {local['totals']['statements_coverage']}% / "
        f"{local['totals']['branches_coverage']}% / {local['totals']['functions_coverage']}% / "
        f"{local['totals']['lines_coverage']}%", "",
        "## Highest impact source gaps", "",
    ]
    for item in local["files"][:20]:
        lines.append(
            f"- `{item['path']}` (priority {item['priority']}, impact {item['impact_score']}): "
            f"{len(item['missing_lines'])} missing lines, {len(item['missing_branches'])} branches, "
            f"{len(item['missing_functions'])} functions. Source present: {item['source_exists']}."
        )
        for example in item["source_examples"][:2]:
            lines.append(f"  - L{example['line']}: `{example['source']}`")
    (args.output_dir / "frontend-coverage-triage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote frontend triage reports to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
