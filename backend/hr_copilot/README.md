# HR Copilot ADI (Phase 1)

This feature answers a bounded set of questions about structured employee, attendance, and leave records. It does not implement document search or RAG.

## Tests

Install development dependencies with `python -m pip install --require-hashes -r backend/requirements-dev.lock`, then run `pytest` from the repository root. The Copilot suite mocks database access and does not need PostgreSQL.

The database integration cases use Django's isolated test database. Run them from `backend/` with `python manage.py test hr_copilot.test_database_operations` to verify scoped employee, attendance, and leave reads plus approved attendance and leave changes. They do not modify the development database.

## Data dictionary

- `Employee` (`employees_employee`): `id`, `user_id`, `department`, `employment_type`, `date_joined`, `is_active`, `section`, `subsection`.
- `User` (`accounts_user`): `id`, `first_name`, `last_name`, `email`.
- `Attendance` (`attendance_attendance`): `employee_id`, `date`, `status`, `check_in`, `check_out`, `working_duration`. Stored statuses are `PRESENT`, `INCOMPLETE`, and `LEAVE`; absence is not recorded as a status.
- `LeaveRequest` (`leave_management_leaverequest`): `employee_id`, `leave_type_id`, `start_date`, `end_date`, `duration_days`, `status`, `reason`, review/cancellation timestamps and users.
- `LeaveType` (`leave_management_leavetype`): `id`, `name`, `code` and policy metadata.
- No BR field or BR relationship exists in the current schema. BR questions are rejected rather than inferred.

## Scope assignment

Apply migrations, then use Django Admin at `/admin/` to edit a System Admin user’s **HR Copilot scope** fields. `hr_copilot_sections` and `hr_copilot_subsections` are JSON arrays, for example `['C']` and `['C1', 'C2']`. Empty scope denies queries. Superusers have unrestricted scope. Any `scope` sent by the browser is ignored for authorization.

## Query path

The endpoint is `POST /api/hr-copilot/query/` with `{ "message": "...", "conversation_id": "...", "scope": {} }`. Set `HR_COPILOT_LLM_PROVIDER=local_ollama_qwen`, `HR_COPILOT_LLM_URL=http://127.0.0.1:11434` for a host-run backend, or `HR_COPILOT_LLM_URL=http://host.docker.internal:11434` when the backend runs in Docker; set `HR_COPILOT_LLM_MODEL=qwen3-8b-q4km-local` to use the local Qwen3-8B provider. Only local loopback/Docker-host Ollama endpoints are accepted. `GET /api/hr-copilot/health/` is available to System Admins and reports whether the configured local model is installed and reachable. The model only extracts JSON intent/entities; if the configured provider is unavailable or returns invalid structured data, the request fails with a controlled error. SQL is always assembled by fixed templates with bound parameters, checked for SELECT-only access to allowlisted tables, and executed in a read-only transaction with a five-second timeout.

The response includes `answer`, `intent`, the backend-derived scope, `query_status`, structured `data`, and `visualization`. Audit records store the question, intent, plan, generated parameterized SQL template, status, and error code, but not result rows or bound values.

The parser handles common employee counts/lookups, attendance lookups/summaries/trends, leave lookups/summaries/trends, section/sub-section filters, employee type/status, and date phrases (today, yesterday, last 7 days, last calendar month, ISO date). Absence is inferred for one completed past date: an active employee hired on or before that date, with no attendance record and no approved leave covering it. The query stays within the caller's assigned section scope. Missing dates, date ranges, and current/future dates are rejected rather than guessed. Unsupported or ambiguous requests return a controlled response. Leave balances, policy documents, and BR data require schema/business definitions that do not currently exist.

## Conversational writes and saved sessions

Write requests are planned by deterministic backend code after the configured local LLM extracts intent and fields. Attendance marked `PRESENT` requires a resolved employee, date, check-in, and check-out. Attendance set to `LEAVE` uses the existing schema, clears old timing fields/events, and records an `AttendanceCorrection`; explicit absence does not introduce a new status. A missing required field creates an `AWAITING_INFORMATION` draft. Drafts cannot be approved until complete. Complete drafts require an explicit approve action or an unambiguous “approve change” message. Cancelled drafts never execute.

Successful writes and their audit rows are committed in the same database transaction. `CopilotActionAudit` captures the authenticated actor, session/action IDs, before/after states, explicit confirmation, and success. Attendance event snapshots are retained in the correction record when a Copilot correction replaces event timing.

Conversation messages and pending action state are stored under the authenticated user in `CopilotConversationContext`. `GET /api/hr-copilot/conversations/<conversation_id>/` restores a conversation; the frontend keeps only the current conversation ID in session storage and reloads message history from the backend. Message history is limited to the latest 200 messages per conversation.

`POST /api/hr-copilot/query/` and the approval/history endpoints require System Admin access. The browser-provided organization scope is never treated as authority; the backend derives scope from the authenticated user. If the configured local model is unavailable or returns invalid structured output, the request fails without creating a write action.
