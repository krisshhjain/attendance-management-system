# Combined Phase 0 + Phase 1 Development Standards Audit

**Audit date:** 2026-10-15<br>
**Base:** `origin/develop` at `088a7bbdebe52a7ecf8c6a3aa17428ecd932c5fc`<br>
**Implementation commit:** `321193cbb35250245dba14f32ea7c658f8a30131`<br>
**Branch:** `feature/final-standards-security-audit`<br>
**PR:** [#19](https://github.com/krisshhjain/attendance-management-system/pull/19), targeting `develop`<br>
**Standards:** Development Standards & Guidelines, Version 1.0 (09 Oct 2026)

## Assessment

**BLOCKED pending explicit security-risk acceptance.** The final backend image still contains eight distinct Trivy High Debian advisories, and Debian does not currently provide Trixie fixes for these package versions. No broad Trivy suppression, unsupported backport, or risky removal of base packages was used. A security owner must accept the residual risk or approve a supported base-image change before this PR is merge-ready.

The application-level Phase 0/1 remediation is otherwise in place. The remaining 936 Flake8 E501 findings are long lines inside string literals. Prompt, SQL, and runtime string values were not rewritten or blanket-suppressed.

## Backend image security review

The final image was rebuilt from the pinned Python 3.10-slim Debian Trixie base. Trivy 0.76.0, using the refreshed database downloaded 2026-10-15, reports **165 package-vulnerability records across 71 distinct advisory IDs**: 0 Critical, 44 High, 58 Medium, and 61 Low. The High records represent eight distinct advisories. The final CycloneDX image SBOM is [sboms/backend-image.cdx.json](sboms/backend-image.cdx.json), with 135 image components and 71 vulnerability entries.

| Image scan | Total records | Critical records | High records | Distinct High advisories |
|---|---:|---:|---:|---:|
| Before runtime pip removal, same Trivy version/database | 170 | 0 | 48 | 12 |
| After pip removal, same Trivy version/database | 165 | 0 | 44 | 8 |
| Final image after runtime-home fix, refreshed database | 165 | 0 | 44 | 8 |

The older committed SBOM had reported 2 Critical and 19 High records. That result used an earlier scan/database and different severity aggregation; it is not directly comparable to the current Debian-aware Trivy JSON counts. The same-database before/after JSON comparison is the relevant remediation comparison. The current scan has zero Critical records, but it does **not** have zero vulnerabilities.

Four distinct High advisories present before the runtime change disappeared from the final image: CVE-2025-47273 (old pip-vendored setuptools), CVE-2026-97687 and CVE-2026-97689 (old pip-vendored urllib3), and GHSA-6v7p-g79w-8964 (old pip-vendored msgpack). The locked application runtime already uses setuptools 84.0.0 and urllib3 2.8.0. Removing pip also removed its bundled vulnerable copies. The final image does not contain pip or ensurepip.

All eight remaining High advisories are Debian OS-package findings, not the locked Python application packages. The installed versions below are present in the final image. The Trivy scan reports no fixed version in Debian Trixie; the listed upstream/unstable versions are not a safe drop-in Trixie remediation.

| Advisory and affected package(s) | Trigger and observed runtime reachability | Fix availability and disposition |
|---|---|---|
| [CVE-2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720) — ncurses: `libncursesw6`, `libtinfo6`, `ncurses-base`, `ncurses-bin` `6.5+20250216-2` | Stack overflow in `infocmp` with crafted terminal data. `/usr/bin/infocmp` is present. The application startup and routes do not invoke it; execution inside the container remains possible. | Debian marks Trixie no-DSA/minor; fixed upstream in ncurses 6.6 and packaged in newer unstable suites. No Trixie patch. Keep package; wait for supported Debian update or assess a supported base migration. Residual local-execution risk remains. |
| [CVE-2026-16742](https://security-tracker.debian.org/tracker/CVE-2026-16742) — systemd: `libsystemd0`, `libudev1` `257.13-1~deb13u1` | Local privilege escalation in systemd-homed. `systemd-homed` is absent from the image and the container does not run systemd-homed. The vulnerable shared-library packages are present. | Debian marks Trixie no-DSA/minor; upstream fix is in later systemd releases (including 258.10/261.2). No Trixie patch. Specific service path is absent, but package-level finding remains pending vendor remediation or risk acceptance. |
| [CVE-2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369) — acl: `libacl1` `2.3.2-2+b1` | Symlink traversal in pathname-based libacl APIs. The library is present. No application call path to these APIs was identified in this review; package presence alone does not prove unreachability. | Debian lists 2.4.0-1 in unstable and says the fix is not individually backportable to Trixie. No safe removal/backport was made. Residual package risk requires vendor update or security acceptance. |
| [CVE-2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642) — util-linux package family, version `2.41.5-0+deb13u1` (nine package records, including `mount`, `util-linux`, `libmount1`, `libblkid1`, `libuuid1`, `libsmartcols1`, `bsdutils`, `login`, `liblastlog2-2`) | Failed mount-helper status can still trigger privileged X-mount hooks. `/usr/bin/mount` is present and setuid; the application does not invoke mount. Exploitation depends on privileged mount configuration and local invocation. | Trixie is marked no-DSA/minor; fixed in newer util-linux (2.42.3-1 upstream/unstable). Do not mix unstable packages into this base. Residual risk remains if an attacker can execute locally and satisfy mount configuration requirements. |
| [CVE-2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408) — same util-linux package family and versions above | `nsenter --join-cgroup` can retain root cgroup-migration authority across namespace/credential changes. `/usr/bin/nsenter` is present as a regular 0755 binary. The advisory requires a privileged operator to invoke the option against an attacker-controlled target; no application path does so. | Trixie remains vulnerable; Debian lists a fix in util-linux 2.42.4-1. No stable patch. Runtime user is `nobody`; this reduces ordinary reachability but does not erase the package finding or risk from privileged in-container operations. |
| [CVE-2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409) — same util-linux package family and versions above | `X-mount.subdir` can follow an intermediate symlink outside an authorized mount. Requires a configured fstab `X-mount.subdir` entry and local mount invocation. The application does not configure or invoke it. | Trixie is marked no-DSA/minor; fix is in util-linux 2.42.3-1 upstream/unstable. No Trixie patch. Avoid unsupported package replacement; residual risk requires vendor update or acceptance. |
| [CVE-2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410) — same util-linux package family and versions above | Restricted bind mount can redirect a privileged mount to a replaceable source path; impact depends on an fstab-authorized entry and local invocation. `mount` is present; the application does not invoke it. | Trixie is marked no-DSA/minor; fix is in util-linux 2.42.3-1 upstream/unstable. No Trixie patch. No package suppression or unsafe removal; residual risk requires vendor update or acceptance. |
| [CVE-2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) — perl: `perl-base` `5.40.1-6+deb13u1` | Archive::Tar can allocate unbounded memory from an attacker-controlled tar size. The vulnerable `Archive::Tar` module file is absent from the final image, and the application does not invoke Perl archive processing. | Debian postpones the Trixie fix; upstream Archive::Tar 3.10 / Perl 5.42.3-1 contains the fix in newer suites. No Trixie patch. Module absence lowers this specific path, but the Perl package finding remains. |

The util-linux advisories are not classified as resolved based on the current container account. The final runtime runs as UID 65534 and has no application code path that invokes these tools, but the affected binaries/packages remain in the image. A future untrusted code-execution foothold or a privileged operational command could change reachability. Removing essential/dependency-heavy OS packages or importing unstable Debian packages was judged unsafe without compatibility and regression work.

## Dockerfile and runtime validation

The final [backend/Dockerfile](../../backend/Dockerfile) now:

- Installs locked dependencies, then removes unused pip, its bundled packages, ensurepip, and pip executables from the runtime layer.
- Creates `/home/app` owned by `nobody:nogroup` with mode 0700 and sets `HOME=/home/app`. This corrects Gunicorn's prior control-socket permission error under the base image's nonexistent `/nonexistent` home.
- Keeps the service on the unprivileged `nobody:nogroup` user.

Built image: `pr19-validation-backend:checkpoint`, image ID `sha256:e56cc18d81d6731d861a9a2d64932ebabfa1f8428b08076994ae59d90d840a00`.

Validation used a unique disposable Compose project with no published ports, separate volumes and random temporary credentials. Existing user-owned containers and volumes were not touched. PostgreSQL and RabbitMQ became healthy; backend startup applied migrations and seeded default leave data; backend health was healthy. Django `manage.py check` passed; `migrate --check` passed; `/healthz/` returned 200; `/api/auth/me/` returned its expected unauthenticated 401. The container ran as UID 65534, `HOME` was writable at `/home/app`, pip import was absent, and Gunicorn started without the prior control-socket error. The disposable project, database, broker, and volumes were removed afterward.

A focused Django test invocation inside the final runtime image was unavailable because the production Docker build deliberately excludes test modules via `backend/.dockerignore`. The full Django and other test suites below are reused from the previous validated revision; application source files and dependency locks are unchanged in this checkpoint.

## Scanner results and evidence

| Check | Final disposition |
|---|---|
| Trivy 0.76.0 backend image | 165 raw package records; 0 Critical, 44 High, 58 Medium, 61 Low; 71 distinct advisory IDs. The 44 High records are eight distinct Debian advisories documented above. |
| Trivy filesystem, full worktree | Completed: 0 package vulnerability findings and 0 secret matches across Python/npm manifests. The only later source change was the Dockerfile runtime-home setting; a final targeted scan of that Dockerfile also found 0 vulnerabilities and 0 secrets. |
| Trivy configuration | Previous full repository scan reported 0 misconfigurations. A repeated full-repository scan exceeded the bounded five-minute window; the changed backend Dockerfile was scanned separately after its final edit and had 0 failures / 27 successful checks. Other configuration files are unchanged. |
| Gitleaks 8.30.1 | Prior full-history scan passed with the 12 exact historical test-fixture fingerprints in `.gitleaksignore`; Git history is unchanged, so that evidence is reused. A current full working-tree scan reported 16 detector matches: eight synthetic password literals in existing tests and eight public base-image `GPG_KEY` values in local raw Trivy JSON reports. These were inspected; no actual credentials were found. A separate Gitleaks scan of the PR-intended Dockerfile, audit markdown, and CycloneDX SBOM found no leaks. The temporary Compose passwords were deleted and are not in the current scan. Raw image Trivy JSON is retained locally but not committed; the committed CycloneDX SBOM and this CVE review contain the reviewable results. |
| Bandit 1.9.4 | Reused unchanged-source result: 0 HIGH, 5 MEDIUM, 562 LOW. The MEDIUM findings were reviewed previously; request calls include explicit timeouts, fixed-column SQL is plan-validated, and the bind finding is test-only. |
| Frontend container | Reused: 0 vulnerabilities after pinned Nginx update and Alpine package upgrade. |
| npm production audit | Reused unchanged manifest/lock result: 0 vulnerabilities. |
| SBOMs | Refreshed backend image SBOM: [sboms/backend-image.cdx.json](sboms/backend-image.cdx.json). Python lock SBOMs and frontend SBOMs are unchanged-input evidence from the previous audit. |

Generated local evidence files in `docs/audits/sboms/` include `backend-image-trivy-before.json`, `backend-image-trivy-after.json`, `backend-image-trivy-final.json`, `trivy-filesystem-final.json`, `trivy-backend-dockerfile-config-final.json`, `trivy-backend-dockerfile-filesystem-final.json`, and redacted Gitleaks working-tree reports. Raw image Trivy JSON includes public Python-base `GPG_KEY` values that trigger Gitleaks' generic-key rule; these scan outputs are intentionally not part of the PR diff.

## Standards, tests, and build evidence

| Area | Result |
|---|---|
| Flake8 | 936 E501 findings remain; 770 single-quoted and 166 multiline literal lines. All non-E501 findings were resolved. No prompt/SQL/runtime string content was rewritten and no blanket E501 ignore was added. |
| isort / compileall | Reused pass on unchanged Python source. |
| Django | 511 passed, 1 skipped (previous validated run; source unchanged). |
| HR Copilot pytest | 241 passed (previous validated run; source/dependencies unchanged). |
| Facial-recognition unittest | 66 passed (previous validated run; source/dependencies unchanged). |
| Frontend Vitest | 230 passed; prior ESLint, Prettier and Vite build passed with existing warnings. |
| Docker Compose | Isolated Compose config validation passed; runtime/migration/health checks described above passed. |

Flake8's remaining E501 lines are message, prompt, SQL, and test literals whose byte-for-byte behavior was intentionally preserved. Safe wrapping of executable code and comments is complete. No Sonar exclusions, thresholds, or coverage instrumentation were changed.

## Hosted checks and review gate

At PR head `0980f694497afda972092122b695200c03649dc2`, GitHub Actions run [38685175105](https://github.com/krisshhjain/attendance-management-system/actions/runs/38685175105) passed all four jobs: backend checks, frontend build/tests, facial-recognition checks, and the SonarQube Cloud analysis action. The SonarQube Cloud bot's [PR comment](https://github.com/krisshhjain/attendance-management-system/pull/19#issuecomment-6184994703) independently reports **Quality Gate passed**, 0 new issues, 0 security hotspots, and 84.4% coverage on new code. This check covered implementation commit `321193cbb35250245dba14f32ea7c658f8a30131` and the report version then on the branch. This follow-up changes only the report to record the results; the resulting PR head must receive its own automated rerun before merge.

## Remaining approval and merge decision

1. Security owner must accept the eight remaining High Debian image advisories or authorize a supported base-image remediation. The PR must remain unmerged until this decision and exact-head CI/Sonar checks are recorded.
2. The 936 string-literal E501 findings remain for human disposition; their values must be preserved, especially HR Copilot prompts and SQL.
3. Repeated full-repository Trivy configuration scanning timed out; only the changed Dockerfile received a fresh targeted scan. The unchanged configuration files retain the previous full-scan evidence.

**Merge recommendation: do not merge pending item 1 and final-head CI/Sonar verification.** No merge or deployment was performed.
