# System Logging and Audit Plan

## Phase 0 scope

This document is an inspection-based implementation plan only. No application code, migrations, frontend files, Docker files, packages, or Git state are changed by this phase.

The repository has two frontend-looking trees. The active application relevant to the requested SuperUser page is `frontend/`, which uses TanStack Router, React, and the `SuperAdminLayout`/`Sidebar` pair. The root `src/` tree is a separate Tailwind/Figma-style application surface and is not the route tree used by `frontend/index.html`.

## 1. Current logging and audit mechanisms

### Attendance audit records

The `attendance` app currently has two database-backed records:

- `attendance.models.AttendanceAuditLog`: timestamp, `event_type`, `status`, optional employee, face distance, and error message. Its event choices are `CHECK_IN`, `CHECK_OUT`, and `ENROLLMENT`; statuses distinguish successful recognition from no face, multiple faces, unknown identity, and errors. `attendance.views` creates rows in the face/kiosk recognition flows. It is attendance/face-specific, has no actor, request, source, IP, user-agent, before/after, category, or request ID, and is not a general system log.
- `attendance.models.AttendanceCorrection`: timestamp, correction type, reason, `previous_data` JSON, attendance target, and optional `admin_user`. It is written for admin reset/edit flows, regularization approval, and HR Copilot attendance writes. It is a useful historical source but does not consistently record the resulting after state, request metadata, event status, or a stable central taxonomy.

`AttendanceEvent` is the operational attendance event stream. It includes event type/source and is used to recompute daily attendance. The `post_save` signal in `attendance/signals.py` queues a notification task after an event is created; it is not an audit logger.

### HR Copilot audit records

The `hr_copilot` app has a more complete but domain-specific audit trail:

- `CopilotQueryAudit` records the authenticated user, question, intent, query plan, parameterized SQL template, validation/scope/execution results, error code, and creation time. The README explicitly says result rows and bound values are not stored.
- `CopilotActionAudit` records user, session, read/write action type, intent, operation, target description, previous/new state JSON, timing, success, confirmation, error, authorization scope, IP address, user agent, and timestamp. `hr_copilot/services/write_executor.py` writes successful action audits transactionally; `hr_copilot/views.py` writes failed approval/execution records where applicable.
- `CopilotPendingAction` is workflow state, not itself a general audit record. It tracks pending, approved, executed, cancelled, expired, and failed action state.

These records should remain as domain detail and be linked or mirrored into a central log for cross-system discovery. They should not be blindly duplicated as independent, differently-shaped audit systems.

### Ordinary application logging

`attendance/face_service.py`, `hr_copilot/views.py`, and `hr_copilot/services/providers.py` use Python `logging`; `notifications/tasks.py` logs email success, retry, and permanent failure. These are process logs, not durable records searchable through the application. They currently do not have a configured request ID, actor, source, or central retention path.

### Signals, middleware, and request logging

- `attendance/apps.py` imports `attendance.signals` in `ready()`.
- The only inspected application signal is the `post_save(AttendanceEvent)` notification enqueue signal.
- `config/settings.py` has no request-ID middleware, audit middleware, or logging configuration for a database sink.
- The middleware list contains standard Django, CORS, authentication, messages, CSRF, and clickjacking middleware only.
- There is no `log_event`, `AuditCreator`, `SystemLog`, generic audit service, or request logging middleware in first-party backend code.

### Current conclusion

The repository has valuable but fragmented domain audit data. A central append-only `SystemLog` is missing. The implementation must preserve the existing detailed records and make the new service the single common entry point for future cross-domain logs, with explicit adapters/links for existing attendance and Copilot records.

## 2. Missing logging coverage

The following are meaningful current actions found from the inspected URLs, views, models, services, and tasks. They are coverage gaps unless noted as an existing specialized record.

### Authentication and account security

- `LOGIN_SUCCESS`: successful regular JWT login and successful Manager/System Admin login.
- `LOGIN_FAILED`: failed credential validation and rejected Manager/System Admin login. The current endpoints inherit or extend `TokenObtainPairView`, so failure instrumentation must be added deliberately rather than assumed.
- `LOGOUT`: the frontend currently clears tokens locally; the backend has no logout endpoint. Log this only when a backend logout/revocation endpoint exists, otherwise it cannot be reliably asserted.
- `PASSWORD_CHANGED`: `accounts.views.ChangePasswordView` changes the password and clears the employee forced-change flag.
- `UNAUTHORIZED_ACCESS`: authenticated or unauthenticated requests rejected with HTTP 401, if request-level security logging is enabled.
- `FORBIDDEN_ACCESS`: authenticated requests rejected with HTTP 403, including rejected role/permission checks.
- `PASSWORD_RESET`: currently there is an authenticated employee/manager password-change route, but no inspected token-based reset workflow. Use `PASSWORD_CHANGED` for the existing route; add `PASSWORD_RESET` only when a reset flow exists.

### Employee and account administration

From `employees/urls.py` and the employee/manager management views:

- `EMPLOYEE_CREATED`, `EMPLOYEE_UPDATED`, `EMPLOYEE_ACTIVATED`, `EMPLOYEE_DEACTIVATED`.
- `EMPLOYEE_PASSWORD_CHANGED` for admin-directed employee password changes.
- `FACE_ENROLLMENT` for employee face enrollment, with success and failure status; this complements the existing recognition audit.
- `MANAGER_CREATED`, `MANAGER_UPDATED`, `MANAGER_ACTIVATED`, `MANAGER_DEACTIVATED`, and `MANAGER_PASSWORD_CHANGED` for the SuperUser-only manager endpoints.
- `ACCESS_CHANGED` for changes to `Employee.app_access` or HR Copilot scope fields.
- `ROLE_CHANGED` for changes to `is_staff`, `is_superuser`, or `is_system_admin`.

The exact employee and manager view update semantics should be preserved when wiring the service; do not infer an event from a GET response.

### Attendance and configuration

From `attendance/urls.py`, `attendance/admin_urls.py`, `attendance/views.py`, and the attendance models:

- `CHECK_IN` and `CHECK_OUT` for employee, website facial, and kiosk flows. Existing `AttendanceAuditLog` covers face-specific recognition outcomes but not a central actor/source/request record.
- `FACE_VERIFY` for explicit face verification where it is a user-visible operation.
- `ADMIN_FORCE_CHECKOUT` for the admin force-checkout endpoint.
- `ATTENDANCE_RESET` and `ATTENDANCE_EDIT` for admin reset/edit endpoints; retain the existing `AttendanceCorrection` detail.
- `REGULARIZATION_CREATED`, `REGULARIZATION_SUBMITTED`, `REGULARIZATION_APPROVED`, `REGULARIZATION_REJECTED`, and `REGULARIZATION_QUOTA_CHANGED` for the regularization and quota endpoints. The current request model has `PENDING`, `APPROVED`, and `REJECTED`; `SUBMITTED` should be used only if the implementation has a distinct submission transition.
- `SHIFT_ASSIGNED`, `SHIFT_BULK_ASSIGNED`, and `SHIFT_CONFIGURATION_CHANGED` for self assignment, admin assignment, bulk assignment, and shift configuration.
- `OFFICE_LOCATION_CREATED`, `OFFICE_LOCATION_UPDATED`, and `OFFICE_LOCATION_DELETED` for the location endpoints.

`ABSENCE_DETECTED` is relevant for the scheduled `attendance.check_consecutive_absences` task, which evaluates two working days and queues manager notifications. It should identify the task as actor/source rather than inventing a human actor.

### Leave management

From `leave_management/urls.py`, the LeaveRequest and admin policy/type routes, and the leave services:

- `LEAVE_CREATED` for employee or Copilot-created requests.
- `LEAVE_UPDATED` for changes to an existing request, if supported by the detail view.
- `LEAVE_APPROVED`, `LEAVE_DENIED`, and `LEAVE_CANCELLED` for review/cancel transitions, including reviewer/canceller as actor.
- `LEAVE_TYPE_CREATED`, `LEAVE_TYPE_UPDATED`, `LEAVE_TYPE_DELETED`.
- `LEAVE_POLICY_CREATED`, `LEAVE_POLICY_UPDATED`, `LEAVE_POLICY_DELETED`.

### Notifications and email

`notifications` has persistent user notifications with read/delete endpoints and an email task:

- `NOTIFICATION_CREATED`, `NOTIFICATION_READ`, and `NOTIFICATION_DELETED`.
- `EMAIL_QUEUED`, `EMAIL_SENT`, `EMAIL_FAILED`, and `EMAIL_RETRY` for `notifications.tasks.send_notification_email` and the queueing helpers. The recipient address must be redacted or represented by a safe count/domain policy in log metadata.

The attendance signal and notification tasks should not create duplicate records for the same event without a deduplication/correlation key.

### HR Copilot

The existing Copilot audits provide detail, but central searchable events should be emitted for:

- `COPILOT_CONVERSATION` for a query/conversation request, subject to secret and prompt-content redaction.
- `COPILOT_ACTION_REQUESTED`, `COPILOT_ACTION_CONFIRMED`, `COPILOT_ACTION_EXECUTED`, `COPILOT_ACTION_FAILED`, `COPILOT_ACTION_CANCELLED`, and `COPILOT_ACTION_EXPIRED`.
- `COPILOT_QUERY_FAILED` for validation, scope, provider, or execution failures.

The central record should link to Copilot audit IDs and should not store raw prompts, SQL values, model secrets, or result rows unless a later retention/security decision explicitly permits a redacted representation.

### Celery

Celery is configured with `CELERY_TASK_TRACK_STARTED = True`, a 30-minute time limit, and a daily `attendance.check_consecutive_absences` beat schedule. No central task event sink was found. Add task lifecycle events only for selected business/security-relevant tasks, not every trivial internal task by default:

- `TASK_STARTED`, `TASK_SUCCESS`, `TASK_FAILED`, and `TASK_RETRY`.
- Include task name, task ID, retry count, and correlation/request ID when available; do not include arbitrary task arguments by default.

## 3. Proposed SystemLog model

Create a new `system_logs` Django app in a later phase. The model should be append-oriented and immutable from the API/UI. Suggested fields:

| Field | Type and nullability | Purpose |
|---|---|---|
| `id` | BigAutoField primary key | Stable log identifier. |
| `timestamp` | DateTimeField, default timezone now, indexed | Event time; store UTC in the database and render configured local time. |
| `severity` | Short CharField, required | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. Normal business audits are usually `INFO`; denials/failures are `WARNING` or `ERROR`. |
| `category` | Short CharField, required | `AUTHENTICATION`, `EMPLOYEE`, `ATTENDANCE`, `REGULARIZATION`, `LEAVE`, `ADMINISTRATION`, `NOTIFICATION`, `HR_COPILOT`, `CELERY`, or `SECURITY`. |
| `event_type` | Short CharField, required, indexed | Stable machine identifier from the taxonomy below. |
| `status` | Short CharField, required, indexed | `SUCCESS`, `FAILED`, `DENIED`, `PENDING`, `RETRY`, `CANCELLED`, or `SKIPPED`. |
| `actor` | ForeignKey to `settings.AUTH_USER_MODEL`, nullable, `SET_NULL` | Human/system user responsible for the action. Null for anonymous requests and background tasks. |
| `actor_role` | Short CharField, required at write time | Snapshot such as `EMPLOYEE`, `MANAGER`, `STAFF`, `SUPERUSER`, `SYSTEM`, or `ANONYMOUS`; do not derive historical role from current user flags. |
| `target_type` | Short CharField, nullable | Application label/model type, for example `employees.Employee`. |
| `target_id` | CharField, nullable | String-safe primary key or external identifier; supports integer and UUID targets. |
| `target_label` | Short CharField/TextField, nullable | Safe display snapshot such as employee name; never use it as the authority for lookup. |
| `message` | TextField, required | Human-readable redacted summary. |
| `source` | Short CharField, required, indexed | `API`, `WEB`, `KIOSK`, `FACE_SERVICE`, `CELERY`, `HR_COPILOT`, `ADMIN`, or another controlled source. |
| `ip_address` | GenericIPAddressField, nullable | Client IP after proxy trust policy is defined. |
| `user_agent` | TextField, nullable | Request user-agent, bounded and redacted as needed. |
| `request_id` | UUID/short CharField, nullable, indexed | Correlates all logs in one request/task chain. |
| `before_state` | JSONField nullable | Redacted state immediately before a mutation. |
| `after_state` | JSONField nullable | Redacted state immediately after a mutation. |
| `metadata` | JSONField default dict | Safe structured context: endpoint, HTTP method/status, task ID, source record IDs, failure code, duration, and counts. |
| `created_at` | DateTimeField, indexed | Database insertion time if distinct from event timestamp. |

Use `actor` nullable because anonymous failures and system tasks are real events. Keep `actor_role` as a snapshot because role flags can change. Use `target_id` as text rather than a polymorphic foreign key; optionally add a nullable link to a concrete audit record only where a stable relation exists.

Recommended composite indexes:

- `(timestamp, id)` for newest-first keyset pagination.
- `(category, timestamp, id)`, `(event_type, timestamp, id)`, `(severity, timestamp, id)`, `(status, timestamp, id)`, and `(source, timestamp, id)` for common filters.
- `(actor, timestamp, id)` and `(actor_role, timestamp, id)`.
- `(request_id)` and `(target_type, target_id, timestamp)`.

Avoid indexing the full `message` or unrestricted JSON. For global search, add PostgreSQL full-text search using a generated/search-vector column or a maintained denormalized search document containing only approved text fields. A trigram index may be added for partial name/email/ID matching after query volume is measured.

Never store passwords, password hashes, JWTs, refresh tokens, API keys, cookies, authorization headers, face templates/embeddings, raw biometric images, email SMTP credentials, LLM credentials, raw SQL bound values, or unrestricted uploaded document contents. Before/after and metadata must use allowlisted serializers with field redaction. Consider hashing or partially masking IP/user-agent data if retention/privacy requirements require it.

Retention should be configurable by category/severity and implemented as a scheduled purge/archive process in a later phase. Preserve security events longer than routine informational events; document legal/privacy requirements before deletion. Do not make log deletion available through the SuperUser page.

## 4. Event taxonomy

Use uppercase stable identifiers, with category and status carried separately. The initial taxonomy proposed from the current code is:

- `AUTHENTICATION`: `LOGIN_SUCCESS`, `LOGIN_FAILED`, `PASSWORD_CHANGED`, `UNAUTHORIZED_ACCESS`, `FORBIDDEN_ACCESS`.
- `EMPLOYEE`: `EMPLOYEE_CREATED`, `EMPLOYEE_UPDATED`, `EMPLOYEE_ACTIVATED`, `EMPLOYEE_DEACTIVATED`, `EMPLOYEE_PASSWORD_CHANGED`, `FACE_ENROLLMENT`, `MANAGER_CREATED`, `MANAGER_UPDATED`, `MANAGER_ACTIVATED`, `MANAGER_DEACTIVATED`, `MANAGER_PASSWORD_CHANGED`, `ACCESS_CHANGED`, `ROLE_CHANGED`.
- `ATTENDANCE`: `CHECK_IN`, `CHECK_OUT`, `FACE_VERIFY`, `ADMIN_FORCE_CHECKOUT`, `ATTENDANCE_RESET`, `ATTENDANCE_EDIT`, `ABSENCE_DETECTED`.
- `REGULARIZATION`: `REGULARIZATION_CREATED`, `REGULARIZATION_SUBMITTED`, `REGULARIZATION_APPROVED`, `REGULARIZATION_REJECTED`, `REGULARIZATION_QUOTA_CHANGED`.
- `ADMINISTRATION`: `SHIFT_ASSIGNED`, `SHIFT_BULK_ASSIGNED`, `SHIFT_CONFIGURATION_CHANGED`, `OFFICE_LOCATION_CREATED`, `OFFICE_LOCATION_UPDATED`, `OFFICE_LOCATION_DELETED`, `LEAVE_TYPE_CREATED`, `LEAVE_TYPE_UPDATED`, `LEAVE_TYPE_DELETED`, `LEAVE_POLICY_CREATED`, `LEAVE_POLICY_UPDATED`, `LEAVE_POLICY_DELETED`.
- `LEAVE`: `LEAVE_CREATED`, `LEAVE_UPDATED`, `LEAVE_APPROVED`, `LEAVE_DENIED`, `LEAVE_CANCELLED`.
- `NOTIFICATION`: `NOTIFICATION_CREATED`, `NOTIFICATION_READ`, `NOTIFICATION_DELETED`, `EMAIL_QUEUED`, `EMAIL_SENT`, `EMAIL_FAILED`, `EMAIL_RETRY`.
- `HR_COPILOT`: `COPILOT_CONVERSATION`, `COPILOT_QUERY_FAILED`, `COPILOT_ACTION_REQUESTED`, `COPILOT_ACTION_CONFIRMED`, `COPILOT_ACTION_EXECUTED`, `COPILOT_ACTION_FAILED`, `COPILOT_ACTION_CANCELLED`, `COPILOT_ACTION_EXPIRED`.
- `CELERY`: `TASK_STARTED`, `TASK_SUCCESS`, `TASK_FAILED`, `TASK_RETRY`.

Do not add `LOGOUT`, `PASSWORD_RESET`, `LOCATION_CHANGE`, or arbitrary generic `CREATE`/`UPDATE` events until the corresponding backend flow is confirmed or implemented. The existing attendance `ENROLLMENT` can be mapped to central `FACE_ENROLLMENT` while retaining the original audit row and source event type for compatibility.

## 5. Logging service design

Add a small service in the future `system_logs` app, for example `system_logs.services.record_event`, with a typed/validated payload rather than ad hoc model creation. It should:

1. Accept event type, category, severity, status, actor, target, message, source, request context, before/after state, and safe metadata.
2. Resolve `actor_role` at write time using the actual User flags and explicit `SYSTEM`/`ANONYMOUS` handling.
3. Normalize request ID from middleware context and task correlation context.
4. Redact and allowlist JSON fields before persistence.
5. Write inside the same transaction as the business mutation for important state changes. Use `transaction.on_commit` only for non-critical asynchronous side effects.
6. Be failure-aware: a logging failure must not silently convert a successful business operation into a false audit entry. For security-critical operations, define whether the transaction must fail closed and test that policy.
7. Return the created ID/correlation data to callers without exposing secrets.
8. Support a source-record link in metadata or a nullable generic relation strategy without introducing a second polymorphic authority.

Request middleware should later generate/accept a validated request ID, attach it to request-local context, capture bounded request metadata, and emit only selected request/security outcomes. It must not log every request as a business action by default. Celery task wrappers/signals should cover selected lifecycle events and preserve task IDs.

For existing audit systems, add explicit adapters at the owning code paths rather than signal-logging every model save. A single user action may create an `AttendanceCorrection` plus one central log; use `metadata`/source IDs to correlate them.

## 6. API design

Mount a future endpoint under the existing API root, preferably:

- `GET /api/system-logs/` for the paginated collection.
- `GET /api/system-logs/<id>/` for the detailed immutable record.
- `GET /api/system-logs/export/` for an asynchronously safe or bounded export, depending on volume.

Use DRF serializers with read-only fields. The collection response should be an object containing `count` or a cursor/pagination structure, `next`, `previous`, and `results`; choose one pagination contract and use it consistently with the frontend. Newest-first ordering must be enforced server-side.

Query parameters should be:

- `search`
- `category`
- `event_type`
- `severity`
- `status`
- `source`
- `actor` (User primary key)
- `actor_role`
- `date_from`
- `date_to`
- `page`/`page_size` for offset pagination, or `cursor`/`page_size` for cursor pagination
- `ordering`, constrained to an allowlist and defaulting to `-timestamp,-id`

Reject invalid choices, malformed dates, excessive page sizes, and unbounded export requests. Export must apply the same permission and filter rules as listing and must redact fields according to an explicit export policy.

The detail response should include display-safe actor and target summaries, all filter fields, message, request/task correlation IDs, before/after state, metadata, and links/IDs for specialized audit records where available. It must not expose secrets or unrestricted prompt/request bodies.

## 7. Search design

Global search should cover the following approved denormalized/search-vector fields:

- actor email, first name, and last name;
- employee/target name, email, and employee ID when present;
- event type, category, severity, status, and source;
- message and target label;
- request ID, target type, target ID, task ID, and safe external/source IDs in metadata;
- selected redacted before/after labels or reason fields, only where approved.

Do not search raw unrestricted JSON by default. Prefer PostgreSQL full-text search for tokenized names/messages and exact/trigram lookup for emails, employee IDs, request IDs, target IDs, and event types. Search by normalized lowercase values, bound query parameters, and a fixed maximum length. Explain the chosen index strategy in the implementation phase and confirm the query plan against a representative growing table.

## 8. Filter design

All filters are ANDed together:

- `category`, `event_type`, `severity`, `status`, and `source`: exact allowlisted values; allow repeated values only if the API contract explicitly supports OR within one field.
- `actor`: exact User ID, with optional server-side actor search/autocomplete rather than accepting arbitrary display names as authority.
- `actor_role`: exact role snapshot.
- `date_from`: inclusive start at `00:00:00` in the API's documented timezone.
- `date_to`: inclusive end implemented as an exclusive next-day boundary to avoid precision bugs.
- `search`: global search as defined above.
- ordering: default `-timestamp,-id`; only allow indexed fields and always add `id` as a deterministic tie-breaker.

Use cursor pagination for a growing append-only table, ordered by `(timestamp, id)`. If the existing frontend conventions require page numbers, use bounded offset pagination initially and plan migration to cursors before the table becomes large. The API should return filter options from controlled constants or a small endpoint, not by scanning the entire log table on every request.

## 9. SuperUser UI design

Add a new TanStack route under `frontend/src/routes/`, likely `/system-logs`, rendered through `RequireAuth` and therefore `SuperAdminLayout`. Add a `System Logs` item to `frontend/src/components/Sidebar.jsx` only when `user.is_superuser` (and not merely for `is_staff` or `is_system_admin`). The route itself must still rely on the backend permission check.

Use the existing frontend conventions:

- API calls belong in `frontend/src/lib/api.js` or a dedicated system-log service module and use `apiRequest`, which already supplies JWT authentication and refresh handling.
- Use the established table styling, status chips, search controls, and responsive layout used by administration and regularization pages.
- Provide a toolbar with global search, category/event/severity/status/source/role filters, actor selection, and date range controls.
- Keep filter state in the URL when practical so refresh/back navigation preserves the query.
- Show newest-first rows with timestamp, severity/status, category/event, actor, target, source, and message summary.
- Use a right-side drawer or existing detail pattern for the full log, including before/after JSON rendered safely and a copyable request ID. Do not make the table itself the only detail surface.
- Use server pagination and loading/empty/error states. Debounce global search and cancel or ignore stale requests.
- Provide export as an explicit icon/text action with a loading state, filter confirmation, and server-generated response. Do not build a client-side export from only the current page unless that is explicitly the product requirement.

No current dedicated pagination/export component was identified as a stable shared abstraction in the active frontend. Reuse local administration/regularization patterns first; extract a shared component only after the system-log page establishes the needed behavior.

## 10. Permission design

The project identifies roles as follows:

- Employee: an authenticated user with a related `employees.Employee`, normally `employee.is_active`, and app access controlled by `Employee.app_access` through `IsEmployee`.
- Manager/System Admin: `User.is_system_admin=True` and, by the documented login flow, not a superuser. The frontend stores `loginType === "systemadmin"` for this session.
- SuperUser: `User.is_superuser=True`, authenticated through the regular admin login. `is_staff` is broader and is not sufficient for the requested page.

The future System Logs API must use `leave_management.permissions.IsSuperAdmin`, or an equivalent shared permission moved to a neutral common location, which checks authenticated `request.user.is_superuser`. Apply it to list, detail, and export endpoints. Do not allow Manager/System Admin read access, even though other administration and HR Copilot endpoints intentionally allow `is_system_admin`.

The frontend `RequireAuth`/`SuperAdminLayout` is useful for navigation and presentation, but it is not the security boundary. Direct route access by a Manager and direct HTTP calls by any non-SuperUser must receive 403. Add tests for anonymous, employee, manager, staff-only, and SuperUser users.

## 11. Files that will need modification in later phases

Backend, subject to final implementation structure:

- `backend/config/settings.py`: install the new app and request/logging context configuration.
- `backend/config/urls.py`: mount the System Logs API.
- `backend/system_logs/`: new app containing models, migrations, serializers, services, permissions reuse, views, URLs, admin/read-only support, filters, and tests.
- `backend/accounts/views.py` and possibly authentication serializer/endpoint classes: success/failure/password event instrumentation.
- `backend/accounts/urls.py`: only if a logout/reset endpoint is introduced or authentication classes are replaced.
- `backend/employees/views.py`, `backend/employees/serializers.py`, and related services: employee, manager, password, access, role, and face events.
- `backend/attendance/views.py`, `backend/attendance/services.py` if present, `backend/attendance/tasks.py`, and possibly `backend/attendance/signals.py`: attendance, correction, regularization, shift, location, absence, and notification correlations.
- `backend/leave_management/views.py` and `backend/leave_management/services.py`: request/review/policy/type transitions.
- `backend/notifications/views.py` and `backend/notifications/tasks.py`: notification and email lifecycle events.
- `backend/hr_copilot/views.py` and `backend/hr_copilot/services/write_executor.py`: central correlation with existing Copilot audits.
- Celery application/configuration files discovered during implementation: selected task lifecycle hooks and request/task correlation.

Frontend, subject to the active app confirmation:

- `frontend/src/routes/system-logs.jsx` or equivalent route file.
- `frontend/src/components/Sidebar.jsx`.
- `frontend/src/lib/api.js` or a new `frontend/src/services/systemLogsService.js`.
- A new focused table/filter/detail component under `frontend/src/components/` if existing components cannot be reused.
- `frontend/src/routeTree.gen.js` only through the route generation/build process; do not hand-edit generated output unless the project requires it.

Do not modify the root `src/App.tsx` unless a later product decision confirms that tree is also a supported deployment target.

## 12. Risks and conflicts with existing audit systems

1. **Duplicate audit meaning:** Attendance and Copilot already store detailed audits. Central logs must link to them, not create competing before/after semantics.
2. **Transaction consistency:** Logging before a mutation can record a false success; logging after commit can lose the event if the process fails. Define per-event transaction policy and test rollback behavior.
3. **Authentication failures:** JWT failures happen inside Simple JWT before ordinary view code. Instrument the authentication boundary carefully and avoid logging passwords or raw request bodies.
4. **Role drift:** Historical actor role must be snapshotted; current User flags are not reliable for reconstructing past access.
5. **Sensitive data:** Face data, passwords, tokens, SQL values, prompts, attachments, and email contents can leak through generic JSON snapshots or exception messages.
6. **High-volume events:** Check-ins, notification events, Celery lifecycle events, and denied requests may grow quickly. Use controlled event selection, indexes, retention, and cursor pagination.
7. **Background actor identity:** Tasks often have no human request user. Use `SYSTEM` actor role and task/request correlation IDs.
8. **Proxy IP correctness:** `REMOTE_ADDR` is not automatically the real client IP. Establish trusted proxy configuration before recording IP addresses.
9. **Export risk:** Large exports can exhaust memory or expose more detail than the table view. Use streaming or bounded asynchronous exports with the same authorization and redaction policy.
10. **Frontend duplication:** `frontend/` and root `src/` have different structures. The deployment entrypoint must remain the source of truth for the page integration.
11. **Existing unrelated worktree edits:** At audit time, unrelated changes exist in `backend/hr_copilot/services/semantic_interpreter.py`, `backend/hr_copilot/test_api.py`, `backend/hr_copilot/test_compact_context.py`, and `backend/hr_copilot/test_semantic_generalization.py`; this phase does not alter them.

## 13. Recommended implementation order

1. Freeze and document the event taxonomy, redaction rules, role snapshot rules, source values, retention policy, and transaction policy.
2. Add the `system_logs` app/model and indexes, then create and validate migrations in a dedicated implementation phase.
3. Add the redacting `record_event` service with unit tests for actor roles, secrets, before/after data, anonymous/system actors, and rollback behavior.
4. Add request ID context and selected authentication/security outcome instrumentation.
5. Instrument mutation owners in this order: employee/account administration, attendance/corrections, regularization, leave, administration configuration, notifications/email, HR Copilot, and selected Celery tasks.
6. Add adapters/correlation IDs for `AttendanceAuditLog`, `AttendanceCorrection`, `CopilotQueryAudit`, and `CopilotActionAudit`; verify no duplicate event is emitted by signals and owning services.
7. Add the SuperUser-only list/detail/export API with exact filters, search, validation, ordering, pagination, and permission tests.
8. Add the frontend route, SuperUser sidebar entry, table, filter state, detail drawer, pagination, error/loading states, and export flow.
9. Load-test search and pagination with representative log volume, verify query plans, and test retention/archive behavior.
10. Perform an end-to-end authorization and redaction review, including direct API access by every role and failed authentication/permission paths.

## Inspection record

### Files and areas inspected

- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/accounts/models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`
- `backend/employees/models.py`, `views.py`, `urls.py`, `admin.py`
- `backend/attendance/models.py`, `views.py`, `urls.py`, `admin_urls.py`, `signals.py`, `tasks.py`, `apps.py`, `face_service.py`
- `backend/leave_management/models.py`, `views.py`, `services.py`, `urls.py`, `permissions.py`, `admin.py`
- `backend/notifications/models.py`, `views.py`, `urls.py`, `tasks.py`, `serializers.py`
- `backend/hr_copilot/models.py`, `views.py`, `services/write_executor.py`, `admin.py`, `README.md`
- Relevant backend migrations, especially `attendance/migrations/0003_attendanceauditlog.py` and `0004_alter_attendanceauditlog_options_and_more.py`
- `frontend/src/components/RequireAuth.jsx`
- `frontend/src/components/SuperAdminLayout.jsx`
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/lib/auth.jsx`, `frontend/src/lib/api.js`, `frontend/src/router.jsx`
- `frontend/src/routes/administration.jsx`, `hr-copilot.jsx`, `admin-regularization.jsx`, and related route files
- `frontend/src/services/hrCopilotService.js`
- `frontend/src/main.jsx` for theme conventions
- Root `src/App.tsx` only to distinguish the separate frontend tree

### Existing logging mechanisms found

- `AttendanceAuditLog` for face/attendance recognition outcomes.
- `AttendanceCorrection` for attendance reset/edit/regularization/Copilot corrections.
- `CopilotQueryAudit` for HR Copilot query planning/execution.
- `CopilotActionAudit` for HR Copilot read/write action execution.
- Python process logging in face service, HR Copilot, and notification email task code.
- An `AttendanceEvent` post-save signal that queues a notification; it is not an audit mechanism.
- No central SystemLog model, event service, request logging middleware, or database-backed general activity logger.

### Proposed event categories

`AUTHENTICATION`, `EMPLOYEE`, `ATTENDANCE`, `REGULARIZATION`, `LEAVE`, `ADMINISTRATION`, `NOTIFICATION`, `HR_COPILOT`, `CELERY`, and `SECURITY`.

### Proposed event types

`LOGIN_SUCCESS`, `LOGIN_FAILED`, `PASSWORD_CHANGED`, `UNAUTHORIZED_ACCESS`, `FORBIDDEN_ACCESS`; employee/manager lifecycle, password, face, access, and role events; `CHECK_IN`, `CHECK_OUT`, `FACE_VERIFY`, `ADMIN_FORCE_CHECKOUT`, `ATTENDANCE_RESET`, `ATTENDANCE_EDIT`, `ABSENCE_DETECTED`; regularization lifecycle and quota events; shift/location/leave configuration events; leave lifecycle events; notification/email lifecycle events; Copilot conversation/query/action lifecycle events; and selected Celery task lifecycle events, as enumerated in Section 4.

### Files created

- `SYSTEM_LOGGING_PLAN.md`

No other file was created or modified by this phase.
