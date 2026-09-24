# HR Copilot ADI (Phase 1)

This feature answers a bounded set of questions about structured employee, attendance, and leave records. It does not implement document search or RAG.

## Tests

Install development dependencies with `python -m pip install -r backend/requirements-dev.txt`, then run `pytest` from the repository root. The Copilot suite mocks database access and does not need PostgreSQL.

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

The endpoint is `POST /api/hr-copilot/query/` with `{ "message": "...", "conversation_id": "...", "scope": {} }`. A structured intent provider may be enabled with `HR_COPILOT_LLM_URL` (Ollama `/api/chat`) and `HR_COPILOT_LLM_MODEL` (defaults to `qwen3:8b`). The model only extracts JSON intent/entities; without a configured URL a deterministic parser is used. SQL is always assembled by fixed templates with bound parameters, checked for SELECT-only access to allowlisted tables, and executed in a read-only transaction with a five-second timeout.

The response includes `answer`, `intent`, the backend-derived scope, `query_status`, structured `data`, and `visualization`. Audit records store the question, intent, plan, generated parameterized SQL template, status, and error code, but not result rows or bound values.

The parser handles common employee counts/lookups, attendance lookups/summaries/trends, leave lookups/summaries/trends, section/sub-section filters, employee type/status, and date phrases (today, yesterday, last 7 days, last calendar month, ISO date). Absence is inferred for one completed past date: an active employee hired on or before that date, with no attendance record and no approved leave covering it. The query stays within the caller's assigned section scope. Missing dates, date ranges, and current/future dates are rejected rather than guessed. Unsupported or ambiguous requests return a controlled response. Leave balances, policy documents, and BR data require schema/business definitions that do not currently exist.
