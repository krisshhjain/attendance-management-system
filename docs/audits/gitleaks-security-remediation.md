# Gitleaks security audit and remediation

## Scope and baseline

The user's original Gitleaks 8.30.1 Windows working-directory report was available at scan time and contained 72 findings. The entry-by-entry redacted inventory is in [gitleaks-working-directory-inventory.md](gitleaks-working-directory-inventory.md). No detected credential values or match excerpts are recorded in that inventory or this report.

Every entry used `generic-api-key`. The 72 path/rule/line fingerprints represent 9 distinct exact scanner match groups. The original report breaks down as follows:

| Category | Findings | Assessment |
| --- | ---: | --- |
| Root `.env` | 1 | Local RabbitMQ password; can authenticate to the local Compose RabbitMQ instance. Production reuse is unknown and requires owner verification. |
| Tracked test fixtures | 8 | Synthetic Django auth, log redaction, and frontend password dialog data; no external service capability. |
| Duplicate test fixtures in nested worktrees | 48 | Copies of tracked test values across ignored local worktrees. |
| Generated Trivy reports in a nested worktree | 8 | Generated dependency report metadata, outside the active source tree. |
| Local virtual environment dependency | 1 | Third-party setuptools code under ignored `.venv`. |
| Generated Bandit report | 6 | Untracked report excerpts repeating fixture content. |
| **Total** | **72** | **9 exact detector match groups after deduplication.** |

## Remediation

- Replaced the flagged test-only passwords in `backend/accounts/test_auth_views.py`, `backend/system_logs/tests.py`, and `frontend/tests/passwordDialogs.test.jsx` with explicit synthetic values while preserving the test inputs and assertions.
- Added `.gitleaks.toml`, which extends Gitleaks' default rules and excludes only local dependencies (`.venv`, `node_modules`), duplicate worktree roots (`.worktrees`, `.kilo/worktrees`), and the exact root `bandit-results.json` output from the project source scan. The root `.env`, source code, and tracked SBOM files are not excluded.
- Existing `.gitleaksignore` entries remain limited to specific historical fixture fingerprints. There is no global `generic-api-key` suppression and no `.env` allowlist.
- `.env` and `bandit-results.json` are untracked. The audit does not stage either file.

## Credential decision and remaining risk

The root `.env` value is used by `docker-compose.yml` for the local RabbitMQ service and local Celery broker URLs. The repository documentation says production credentials are supplied by the deployment platform. Repository evidence cannot establish whether this local value is reused in production. No production credential exposure was found in tracked source or Git history. The deployment owner must confirm that the local value is not reused; rotate the production RabbitMQ credential only if it is shared or production-bound. No rotation is claimed.

## Validation

Gitleaks 8.30.1 results:

- Git-history scan: **0 findings**.
- Working-directory scan using `.gitleaks.toml`: **1 finding**, the expected root `.env` local RabbitMQ password. No finding remained in tracked source, tracked tests, or tracked SBOMs. The scan did not exclude `.env`.
- The original 72 entries are accounted for by the inventory. After deduplicating exact scanner matches, 9 match groups remain: 1 local `.env` value, 5 synthetic test-fixture values, and 3 generated/dependency artifact groups.
- `.env` and `bandit-results.json` are not tracked. Only the audit inventory, audit summary, Gitleaks config, and fixture changes are intended for this branch.
- `git diff --check`: passed.
- A focused Gitleaks scan of the changed Django auth fixture: passed with 0 findings.
- Backend test execution was attempted but could not complete: the test process stalled on its first database-backed test, and the configured local PostgreSQL endpoint (`127.0.0.1:5434`) is not listening. The process was stopped. The repository `.venv` does not contain pytest.
- Frontend test execution was attempted but could not start because Vitest is not installed in `frontend/node_modules` or the root `node_modules`.
- Bandit, CI, and Sonar configuration were not changed. CI and Sonar Quality Gate results require the PR workflow and are pending.

## Review checkpoint

No secret rotation is claimed. The deployment owner still needs to confirm whether the local `.env` RabbitMQ password is reused by production. Do not merge until that answer is recorded and the PR's required human review, GitHub Actions, and Sonar Quality Gate have completed.
