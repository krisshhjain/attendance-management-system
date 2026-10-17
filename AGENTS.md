# Codex Code Review Instructions

## 1. Project overview

Dailoqa is an attendance and HR management system. Review the component affected by a change and follow its data flow into related services before reporting a finding. The repository includes:

- A Django 5.2 and Django REST Framework backend, using Python 3.10 in an Alpine Linux backend container.
- PostgreSQL, Django migrations, Celery, and RabbitMQ.
- HR Copilot services for AI-assisted queries and actions.
- A separate facial-recognition service with sensitive biometric data and model assets.
- A React 19 and JavaScript frontend built with Vite; frontend tests use Vitest.
- Docker and Docker Compose for local services and backend deployment packaging.
- GitHub Actions CI and SonarQube Cloud (also referred to as SonarCloud) analysis.

Use the repository's current code, tests, configuration, and documented specifications as evidence. Do not assume business requirements that those sources do not support.

## 2. Code review priorities

Review every pull request for correctness, security, data integrity, regressions, and adequate tests. Understand the relevant component and its callers before raising findings. Trace inputs through authorization, validation, persistence, and output where applicable.

Check for incorrect calculations or conditions; behavior changes and regressions; missing edge-case handling; incorrect exception handling; race conditions and concurrency issues; database transaction problems; timezone, date, and calendar errors; incomplete input validation; and incompatible API contract changes.

Pay particular attention to attendance rules, shift assignments, check-in and check-out, working days, weekends, holidays, location verification, and regularization. Confirm conclusions against existing behavior and documented requirements.

Follow Development Standards & Guidelines v1.0 (9 October 2026) where applicable. Review new or modified Python for PEP 8, clear naming, focused functions, meaningful docstrings and comments where required, appropriate type hints, specific exception handling, useful logging, consistent imports, separation of concerns, and maintainability. Consider SOLID principles where they fit. Do not request broad stylistic refactoring without a concrete impact. Honor the existing ESLint and Prettier configuration for frontend changes.

## 3. Security and authorization checks

Check authentication and authorization at the server boundary, including organization, department, manager, and employee scoping. Look for cross-tenant data exposure, privilege escalation, unauthorized employee-data access, unsafe raw SQL or SQL injection, hardcoded credentials or secrets, sensitive data in logs or errors, unsafe network requests or missing timeouts, insecure file handling, and unsafe dependency or container changes.

Verify that permissions are enforced by the backend rather than relying on frontend visibility or route guards. Follow identifiers and filters through query construction and object access to confirm that a caller cannot access another tenant's or employee's data. Report a security concern only when the code shows a plausible execution path and explain the required conditions.

## 4. Backend and HR Copilot considerations

For Django and DRF changes, review serializers and validation, permission classes, queryset scoping, transaction boundaries, migration safety, API response compatibility, and error handling. Inspect how values are normalized and persisted, including dates, timezones, decimals, and concurrent updates.

For HR Copilot, inspect the full path from user request and model output through intent normalization, query planning, authorization, execution, audit logging, and response. Confirm that AI-generated SQL or other database operations are constrained and validated server-side. Check read/write permissions, employee-data privacy, organization scope, and approval or explicit confirmation workflows for write actions. Treat prompts and SQL strings as behaviorally significant; do not suggest changing them without understanding their execution effects.

## 5. Facial-recognition considerations

Review identity verification, service-to-service authentication, access controls, error handling, and the collection, storage, transmission, logging, and retention of biometric data. Check that failures do not silently authenticate a person or expose sensitive images, embeddings, or identifiers. Consider model and asset loading, input validation, and the boundary between the facial-recognition service and the Django backend. Support findings with a concrete data flow or failure path.

## 6. Frontend considerations

For React and JavaScript changes, check hook dependencies, state-management behavior, authentication and route-guard behavior, organization scoping, unsafe rendering or injection, API integration and response handling, and component behavior. Review loading and error states when their absence causes a functional or security problem. Report accessibility issues when the user impact is meaningful. Check whether frontend regression tests cover changed behavior.

Do not treat client-side checks as authorization. Confirm that server-side access controls remain effective. Follow existing ESLint and Prettier configuration and avoid duplicating routine linter or formatter output as review comments.

## 7. Testing and quality gates

Assess whether changed behavior has suitable tests, including regression, negative, and authorization tests. Look for weakened or deleted assertions, tests skipped in a way that hides failures, and flaky tests dependent on the actual current date, timezone, environment, or execution order. Use the repository's existing test frameworks: Django tests and pytest for backend areas, unittest for the facial-recognition service, and Vitest for the frontend.

Development Standards v1.0 requires Sonar coverage above 80%. Distinguish overall project coverage from new-code coverage: a passing pull-request Quality Gate or a new-code coverage percentage does not by itself establish that overall project coverage is above 80%. Evaluate the relevant reports and configured thresholds rather than inferring a percentage from a passing gate.

Consider applicable evidence from Flake8, isort, Bandit, Gitleaks, Trivy, ESLint, Prettier, Django tests, pytest, Vitest, SonarQube Cloud, Docker builds, and SBOM generation or review. Tool output is evidence to evaluate, not proof by itself. Do not repeat automated lint findings unless they reveal an important correctness or security problem. Check that CI results correspond to the pull request's current commit when relying on them.

## 8. Docker and infrastructure considerations

Review container build regressions, Alpine Linux compatibility, dependency vulnerabilities, environment-variable handling, container permissions, PostgreSQL persistence, migration safety, Celery and RabbitMQ configuration, secrets in image layers, and deployment compatibility. The backend image uses Python 3.10 on Alpine Linux; assess package availability and native dependency behavior in that environment. Do not recommend changing from Alpine to Debian without demonstrated technical justification.

Review dependency and lockfile changes for provenance, pinning or hash policy, compatibility, and meaningful security impact. Treat SBOM and vulnerability scan results in context, including whether the affected component is present and reachable; do not dismiss or assert a vulnerability based on package presence alone.

## 9. Documentation-only PR review

When a pull request claims to change only comments or documentation, verify the diff contains no executable code, import or export changes, application-logic changes, or unexpected formatting and line-ending changes. Check carefully that existing strings, SQL queries, and AI prompts were not changed. Python docstrings can affect runtime introspection and are not automatically behavior-free.

Confirm that comments accurately describe the existing behavior and that documentation does not claim unsupported security or business guarantees. Report only issues introduced by the documentation change; do not request unrelated implementation work in a documentation-only pull request.

## 10. Finding severity and response format

Report only actionable findings introduced by the pull request. Do not invent defects, assume undocumented requirements, or report speculative vulnerabilities without a plausible execution path. Prefer a small number of accurate findings over low-confidence comments. If no substantive issue is found, say so clearly and do not manufacture review comments.

Classify each finding as:

- **P0 — Critical:** Immediate security exposure, severe data loss, or another release-blocking failure.
- **P1 — High:** Demonstrable security vulnerability, significant functional regression, broken permissions, or serious data-integrity defect.
- **P2 — Medium:** Reproducible edge-case failure, maintainability problem with concrete impact, or missing essential regression test.
- **P3 — Low:** Minor but actionable issue. Avoid cosmetic comments already handled by linters.

For each finding, provide the severity, exact file and relevant line range, description of the problem, why it matters, conditions required to reproduce it, and a concise recommended correction. Keep the explanation specific to the changed code and avoid bundling unrelated concerns into one finding.

## 11. Repository workflow and human approval

All feature work belongs on separate branches. Never push directly to `main` or `develop`. Pull requests target `develop` unless an authorized repository instruction says otherwise. Require CI checks and the SonarQube Cloud Quality Gate to pass, and require human review before merging. Codex reviews are advisory and do not replace human approval. Never merge pull requests automatically or enable auto-merge.

Recognize the repository's documented tool choices: it uses GitHub Actions rather than GitLab CI/CD, Django migrations rather than Alembic, and its existing dependency-management workflows rather than Poetry. Do not report these choices as defects unless a pull request introduces a concrete regression or an approved standards change requires a migration.
