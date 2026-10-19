# HR Copilot Capability Audit

**Audit scope:** active frontend and backend HR Copilot implementation in `D:\attendance-management-system`

**Inspection mode:** code and test inspection only. No application code, prompts, database data, or packages were changed.

## 1. Current architecture

### User-facing flow

- The active frontend route is `frontend/src/routes/hr-copilot.jsx`.
- The route is protected by `RequireAuth` and additionally renders an access message unless `loginType === "systemadmin"`.
- `frontend/src/services/hrCopilotService.js` calls:
  - `POST /api/hr-copilot/query/`
  - `POST /api/hr-copilot/actions/approve/`
  - `GET /api/hr-copilot/actions/pending/`
  - `GET /api/hr-copilot/conversations/<conversation_id>/`
- Normal questions and answers remain in the chat UI. Pending write actions are rendered as approval cards by the Copilot chat components.
- The browser keeps only the current conversation ID in `sessionStorage`; message history is restored from the backend.
- The frontend sends an organization scope for UI continuity, but the backend does not trust it for authorization.

### API and authorization flow

`backend/hr_copilot/urls.py` exposes health, query, action approval, pending-action, and conversation endpoints. Every endpoint requires authentication and checks `is_system_admin` or `is_superuser`.

`HRCopilotQueryView.post()` in `backend/hr_copilot/views.py`:

1. Validates message length and conversation ID.
2. Creates `CopilotQueryAudit` and appends the user message to `CopilotConversationContext`.
3. Resolves an awaiting action or interprets a new question.
4. Derives authorization scope from the authenticated user.
5. Routes writes to `WriteActionPlanner` and stores a `CopilotPendingAction`.
6. Routes reads through `plan_query()`, fixed SQL generation, SQL validation, and a read-only database transaction.
7. Generates a deterministic answer first, then optionally asks local Qwen to phrase verified result data.
8. Persists answer/context/audit information and returns structured JSON.

### Interpretation and normalization

The active semantic path is:

`SemanticInterpreter.interpret_query()` → `llm.get_structured_intent()` → `IntentNormalizer.normalize_intent()` → `analyze_question()`.

The interpreter validates security-sensitive requests, resolves dates, applies limited context, resolves departments, checks employee-name ambiguity, and applies some safe defaults. The normalizer deterministically maps intents to sources and read/write classification, and has regex fallbacks for common attendance-write wording.

The allowed intent set is finite:

- Reads: employee lookup/count/summary, attendance lookup/summary/trend, absence lookup/count, leave lookup/summary/trend, comparison.
- Writes: attendance update/create/delete, leave create/update/cancel/approve/deny, employee update, bulk attendance update.

The configured provider is local Ollama/Qwen only. `backend/config/settings.py` defaults to local Qwen3-8B configuration; `backend/hr_copilot/services/providers.py` rejects cloud/non-local endpoints. `HR_COPILOT_LLM_URL`, `HR_COPILOT_LLM_MODEL`, timeout, and temperature are configurable. The provider disables model thinking output and parses structured JSON.

### Read query execution

`backend/hr_copilot/services/pipeline.py` is the read-query engine:

- Allowed source tables are employees, users, attendance, leave requests, and leave types.
- SQL is assembled only from fixed templates in `build_sql()`.
- Parameters are bound separately.
- `validate_sql()` requires the generated template, SELECT-only SQL, allowlisted tables, no wildcard selection, and bounded result size.
- `execute_query()` uses a read-only transaction and a five-second statement timeout.
- The maximum result size is 100 rows.

The supported data model is intentionally narrow. Attendance reads use the persisted `Attendance` table, not `AttendanceEvent` recomputation or a duration aggregation service.

### Write planning and execution

`backend/hr_copilot/services/write_actions.py` supports a small human-in-the-loop set:

- Attendance status/timing update or create.
- Leave create.
- Leave cancel.
- Leave approve or deny.

The planner resolves the employee, date, status, time fields, leave reason, and pending leave request. Missing fields produce an `AWAITING_INFORMATION` draft. Complete writes require confirmation.

`backend/hr_copilot/services/write_executor.py` executes approved actions transactionally and creates `CopilotActionAudit` rows. It revalidates the employee scope at execution time. Leave review delegates to existing leave services.

The write executor currently has an important data-integrity concern: `_execute_attendance_update()` deletes all `AttendanceEvent` rows for the employee/date before writing the ADMIN events. That behavior conflicts with the broader attendance requirement that event history remain auditable and means Copilot attendance correction is not merely an additive historical action.

### Context, memory, and audit

- `CopilotConversationContext` stores bounded message history and structured context per user/conversation.
- Conversation messages are capped at the most recent 200.
- `SessionMemoryManager` stores a compact, one-hour cache state and retains only a small set of slots such as employee, date, section, last intent, and pending action.
- `apply_context()` only copies selected safe facts for follow-up questions and pronoun references.
- `CopilotQueryAudit` records question, intent, plan, SQL template, validation/scope/execution status, and error code, but not result rows or bound SQL values.
- `CopilotActionAudit` records actor, action, before/after state, confirmation, authorization scope, and success/error.

## 2. Current capabilities

The implementation can currently do the following when the local provider is reachable and the request is inside the authenticated scope:

- Answer bounded employee profile, count, summary, and active/inactive queries.
- Read attendance records, statuses, check-in/check-out values, and persisted working duration for a date/range.
- Infer absence for one completed past date using active employees, hire date, absence of a non-ABSENT attendance record, and absence of approved leave.
- Read leave requests with status/date/employee filters and return summaries/trends based on the fixed templates.
- Compare authorized section/subsection groups where the intent supplies at least two comparison sub-sections.
- Resolve a unique employee by ID, email, or name; ask for an email when a name is ambiguous.
- Resolve common dates including today, yesterday, last week, this week, this month, last month, ISO dates, and common written dates.
- Maintain limited follow-up context within a conversation.
- Create approval drafts for supported attendance and leave writes.
- Require explicit approval before supported writes execute.
- Cancel pending actions without applying the write.
- Record query/action audit information and apply server-derived section/subsection scope.
- Return controlled errors for invalid provider output, unavailable local Qwen, unsafe SQL, unknown/unsupported questions, invalid dates, ambiguity, and scope violations.

The repository contains focused tests for API authorization, absence inference, SQL safety, date handling, employee resolution, context, provider behavior, natural-answer grounding, database reads, supported write flows, approval, cancellation, and transaction rollback. The README in `backend/hr_copilot/README.md` describes the feature as a bounded structured-record assistant, not document search or RAG.

## 3. Capability matrix for the requested HR questions

The classifications below reflect the actual fixed intents, filters, query templates, and write planner. “Supported” means the backend has a direct path; it does not mean the local model will classify every paraphrase reliably.

| Question | Current result | Why |
|---|---|---|
| Who was absent yesterday? | Supported | There is a deterministic `absence_lookup` path. It requires one completed past date and checks active employees against attendance and approved leave. Covered by tests. |
| Who has not checked in today? | Not supported as asked | Today is not a completed absence period, and there is no “not checked in” query template. A regular attendance query can return recorded rows, but it cannot reliably return the complement of employees without a check-in. |
| Show Krish's attendance for this month. | Partially supported | Employee resolution, date range, and attendance lookup exist. The result is a bounded list of persisted Attendance rows, not an employee-facing month summary or event-level explanation. Ambiguous names require email. |
| How many hours did I work last week? | Not supported as a metric | Attendance rows expose `working_duration`, but `build_sql()` does not sum durations, resolve the current employee identity, or return a total-hours aggregate. It may return records rather than answer the requested total. |
| Who is late today? | Not supported | No late intent, shift-start comparison, lateness field, or query template exists. |
| Show pending leave requests. | Supported in bounded form | `leave_lookup`/`leave_summary` can filter `leave_status=PENDING` and return leave rows within scope. It does not provide a workflow dashboard or richer policy interpretation. |
| Approve Krish's leave for tomorrow. | Partially supported with confirmation | `leave_approve` can resolve one employee and one pending request by date, then create a confirmation action and delegate approval to leave services. It fails/asks for clarification if the employee or request is ambiguous. The separate frontend approval endpoint currently uses a user-only session key while query-created actions use a user-plus-conversation session key; this can prevent approval cards submitted through that endpoint from finding the action. |
| Why is my attendance incomplete? | Not supported as an explanation | The read path can expose an `INCOMPLETE` record, but there is no rule/explanation service that evaluates open events, missing checkout, shift, geofence, or regularization state. |
| What is my remaining leave balance? | Explicitly rejected | `SemanticInterpreter._validate_security()` rejects leave-balance questions as an unsupported metric. There is no balance tool in the Copilot query engine. |
| Which employees have consecutive absences? | Not supported | There is only single-date absence inference. No consecutive-day aggregation or absence-streak query is available. |
| Who has regularized attendance this month? | Not supported | RegularizationRequest, AttendanceCorrection, and related audit data are not in the Copilot allowlist or fixed SQL templates. |
| Change X's shift to the morning shift. | Not supported as a write | Shift actions are not in `WriteActionPlanner.write_intents`, `CopilotPendingAction.action_type` support, or `WriteActionExecutor`. The current Copilot write path cannot safely mutate employee shifts. |
| Show employees who haven't enrolled their face. | Not supported | Face enrollment/profile fields and face-enrollment query logic are absent from the Copilot source allowlist and query templates. |
| Compare attendance this week vs last week. | Only superficially/partially supported | A generic `comparison` intent exists, but the current planner expects comparison sub-sections, and the SQL groups by subsection/status. There is no week-over-week period comparison or percentage/delta calculation. |

## 4. Current limitations and weak interaction types

### Natural-language understanding

- The model is constrained by a compact prompt whose explicit intent examples cover only a small subset of business language. The runtime schema contains more intents than the prompt describes, increasing classification ambiguity for newer capabilities.
- The system depends on one local model call for structured intent. If Ollama/Qwen is unavailable or returns malformed JSON, the question fails with a controlled 503 rather than using a broad deterministic fallback.
- There is no confidence threshold or user-visible “I am not sure” policy beyond schema/ambiguity errors.
- Context is slot-based and deliberately shallow. It does not preserve a robust conversation plan, result references, selected leave request, or multi-turn analytical state.
- The frontend has a disabled conversation search UI and only restores the currently selected conversation ID.

### Data and query planning

- Query planning is fixed to three sources and a small set of columns. There is no general business-domain registry or composable query planner.
- Attendance queries read `Attendance`, not `AttendanceEvent`, effective correction events, shift assignments, regularization records, or recomputed duration logic.
- There is no aggregation for hours, averages, lateness, missing check-ins, consecutive absences, leave balances, regularization counts, or week-over-week comparisons.
- The absence query is deliberately single-date and treats absence as an inferred complement. It is not a general attendance-status engine.
- Result data is capped and natural-language compacting limits many result types to the first few rows before optional Qwen response generation.
- The answer generator can truthfully summarize fixed result shapes, but it cannot explain domain rules that were never queried.

### Action coverage

- The implemented write executor supports attendance corrections and selected leave operations only.
- Declared/normalized write intents such as employee update, attendance delete, leave update, and bulk attendance update do not have corresponding executor branches; they eventually produce `unsupported_action` if they reach execution.
- Employee administration, manager administration, office/location, shift, face enrollment, password, notification, regularization, reporting, and system-log actions are not Copilot tools.
- Leave creation defaults to the first configured LeaveType rather than requiring the user to select an explicit type. This is unsafe for a general HR assistant.
- Leave cancellation selects the most recent pending/approved future leave rather than always requiring a unique request identifier/date.
- Leave approval/denial requires a uniquely matched pending request, but matching and confirmation presentation are still limited to one action at a time.

### Confirmation/session defect

The normal query path creates a session ID of the form:

`hr-copilot-user-<user-id>-conversation-<conversation-id>`

However, `HRCopilotActionApprovalView` and `HRCopilotPendingActionsView` use:

`hr-copilot-user-<user-id>`

`PendingActionManager` requires an exact session ID when retrieving, approving, cancelling, or listing actions. The frontend’s `respondToAction()` calls the separate approval endpoint, so actions created by the conversation query path can fail with “Pending action not found or expired.” Inline approval through the query path uses the conversation session and is not affected. This is a concrete end-to-end defect, not merely a model limitation.

### Attendance correction/data-history concern

`WriteActionExecutor._execute_attendance_update()` snapshots events into `AttendanceCorrection`, then deletes all same-day `AttendanceEvent` rows and inserts ADMIN events for the replacement interval. This preserves a snapshot in the correction record but does not preserve the original `AttendanceEvent` rows themselves. It also means repeated Copilot corrections operate on a destructive replacement model rather than a clearly versioned effective-event model.

## 5. Root causes

1. **Bounded MVP data contract:** The read engine was designed around employee, attendance, leave-request, and leave-type tables only. Domain entities such as shifts, locations, face enrollment, regularizations, notifications, logs, and event history were intentionally excluded.
2. **Fixed SQL templates instead of business-query tools:** Intent normalization selects one source/template, but there is no service layer for domain calculations or composable query plans.
3. **Prompt/schema drift:** The provider prompt describes only basic attendance/employee/leave intents while the enum, normalizer, and planner contain additional partially implemented intents.
4. **No metric layer:** Stored fields are exposed as rows, but no calculation layer exists for duration totals, lateness, streaks, balances, comparisons, or “missing” complements.
5. **Shallow context:** Conversation state stores a few slots and bounded messages, but not durable references to query results or business objects.
6. **Narrow write allowlist:** Human approval is present, but only attendance and selected leave mutations have complete planning/execution implementations.
7. **Session identity split:** Conversation-aware query sessions and user-only action endpoints were implemented with different keys.
8. **Correction implementation predates a versioned event model:** Copilot attendance correction deletes same-day events after snapshotting them rather than retaining immutable source events with an effective-correction selector.
9. **Frontend is a chat shell, not an assistant workspace:** The UI supports messages and one pending action card, but has no result follow-up controls, query explanation, report view, action history, or conversation search.

## 6. Missing capabilities

### Read/query capabilities

- Today’s missing check-ins and present/not-present complements.
- Late/early/shift-adherence calculations using effective shifts and timezone rules.
- Working-hours totals and daily/weekly/monthly attendance summaries.
- Effective AttendanceEvent/recomputation-aware explanations for incomplete attendance.
- Multi-day absence streaks and consecutive-absence detection.
- RegularizationRequest and AttendanceCorrection reporting.
- Leave balance calculations using leave policy, accrual, holidays, half-days, and approved usage.
- Week-over-week/month-over-month comparisons with totals, deltas, and percentages.
- Face-enrollment coverage queries.
- Shift, office/location, geofence, and employee status context.
- Report/export-oriented result sets and pagination.

### Action capabilities

- Shift assignment/configuration.
- Employee and manager administration.
- Office/location maintenance.
- Face enrollment and face-verification administration.
- Regularization submission/review/correction.
- Password/reset, notification, system-log, report, and export actions.
- Explicit action identifiers for leave operations rather than “most recent matching request.”
- Bulk actions with preview, per-record validation, partial-failure reporting, and idempotency.
- A consistent action-session model shared by query, pending, approval, and cancellation endpoints.

### Safety and experience capabilities

- Domain-specific explanation cards with source records and calculation assumptions.
- Confidence/ambiguity handling that asks targeted questions before planning.
- Freshness timestamps and “data as of” labels for operational questions.
- Query/result pagination and downloadable reports.
- Stronger confirmation summaries including affected records, current state, proposed state, and authorization scope.
- Immutable event history and effective-correction/version semantics for attendance writes.
- Explicit audit links from Copilot actions to underlying business records.

## 7. Recommended target capabilities

The target should be a governed HR assistant, not an unrestricted text-to-SQL agent.

### Target service architecture

1. **Intent and entity contract:** Version a canonical intent schema with explicit read metrics, entities, time periods, action types, confidence, ambiguity, and clarification requirements. Keep the LLM responsible for language interpretation only.
2. **Domain tool registry:** Replace source-only planning with typed read tools such as `attendance_summary`, `working_hours`, `late_employees`, `absence_streaks`, `leave_balances`, `regularization_history`, `face_enrollment_status`, and `shift_assignments`.
3. **Business calculation services:** Reuse the application’s attendance recomputation, effective correction, shift, leave-balance, and regularization services. Do not duplicate formulas in SQL or prompts.
4. **Authorization-aware tool execution:** Every tool should receive the server-derived scope and apply employee/section/subsection restrictions before returning records or aggregates. Revalidate scope for writes.
5. **Immutable write workflow:** Use immutable source events and a correction/request relation or generation marker to identify the effective correction. Preserve historical events and make current calculations/API responses use the same effective-event rules.
6. **Action lifecycle:** Use one stable action-session/conversation identity across create, restore, approve, cancel, pending-list, expiry, and retry. Add idempotency and stale-state revalidation.
7. **Grounded response layer:** Generate answers only from tool output, with deterministic templates for sensitive metrics and optional local Qwen phrasing for non-sensitive presentation. Include assumptions, date range, scope, and data freshness where relevant.
8. **Clarification and preview UX:** For ambiguous employee/leave/action targets, show candidate records and ask a precise follow-up. For writes, show a complete before/after preview and require explicit confirmation.
9. **Observability and evaluation:** Expand `CopilotQueryAudit` with tool name, normalized slots, confidence, clarification count, data freshness, and result metadata without storing sensitive result rows unnecessarily.

### Example target answers

- “Who has not checked in today?” should use an authorized active-employee roster, today’s effective attendance/check-in state, shift/timezone rules, and return the missing set with a timestamp.
- “How many hours did I work last week?” should resolve the authenticated employee, use effective attendance intervals, sum only valid completed intervals, disclose incomplete days, and identify the date range.
- “Why is my attendance incomplete?” should inspect the day’s effective events, missing counterpart, shift boundary, and regularization state, then explain the exact reason and next available action.
- “Approve Krish’s leave for tomorrow” should resolve one pending request by employee/date, display leave type/dates/reason/current status, enforce scope, and execute one idempotent reviewed action.
- “Compare attendance this week vs last week” should return comparable periods, total employees/days, present/incomplete/leave/absence counts, deltas, and percentages using the same attendance rules as the main API.

## 8. Recommended implementation phases

### Phase 1 — Correctness and lifecycle foundation

- Fix the conversation/action session mismatch across query, pending, approve, cancel, and restore endpoints.
- Define the canonical intent/action schema and remove or explicitly mark unsupported normalized intents.
- Add end-to-end tests for frontend approval, cancellation, expiry, retries, and stale pending actions.
- Make attendance corrections immutable and traceable to the originating request/correction while keeping historical `AttendanceEvent` rows.
- Establish one effective-event/recomputation service used by Copilot, attendance APIs, and reports.

### Phase 2 — Attendance intelligence

- Add typed tools for today’s missing check-ins, late employees, working-hours totals, incomplete-attendance explanations, absence streaks, and period summaries.
- Reuse shift boundaries, timezone, multi-cycle event, forgotten-checkout, and correction rules.
- Add regression fixtures for open events, cross-midnight behavior, regularization, and repeated corrections.

### Phase 3 — Leave and regularization intelligence

- Add leave-balance and policy services as authoritative tools.
- Add pending/approved leave workflow queries with unique request targeting.
- Add regularization history, pending-review summaries, correction explanations, and approved/rejected outcomes.

### Phase 4 — Workforce administration and operational context

- Add read tools for employee enrollment, shifts, locations, departments, managers, and account status.
- Add carefully scoped, preview-first write tools for shift assignment, employee administration, and face-enrollment administration.
- Add bulk-action planning, per-record validation, idempotency, and partial-failure reporting.

### Phase 5 — Reporting, comparison, and assistant UX

- Add period comparisons, trends, exports, pagination, and chart-ready structured output.
- Add source/freshness indicators, saved conversations/search, result follow-ups, and action history.
- Add evaluation suites covering the supplied questions, paraphrases, ambiguity, permissions, stale data, provider failures, and prompt-injection attempts.

### Phase 6 — Production hardening

- Add performance budgets, query-plan monitoring, rate limits, provider health UX, structured redaction, and retention policies.
- Require approval for all writes and enforce immutable audit links.
- Review every tool against least privilege, sensitive-data minimization, and deterministic business-rule reuse.

## Files inspected

### Backend

- `backend/hr_copilot/urls.py`
- `backend/hr_copilot/views.py`
- `backend/hr_copilot/models.py`
- `backend/hr_copilot/services/pipeline.py`
- `backend/hr_copilot/services/semantic_interpreter.py`
- `backend/hr_copilot/services/intent_normalizer.py`
- `backend/hr_copilot/services/llm.py`
- `backend/hr_copilot/services/providers.py`
- `backend/hr_copilot/services/conversation.py`
- `backend/hr_copilot/services/session_memory.py`
- `backend/hr_copilot/services/employee_resolver.py`
- `backend/hr_copilot/services/tools.py`
- `backend/hr_copilot/services/write_actions.py`
- `backend/hr_copilot/services/write_executor.py`
- `backend/hr_copilot/README.md`
- Copilot tests including `test_api.py`, `tests.py`, `test_database_operations.py`, `test_complete_flow.py`, `test_conversation.py`, `test_employee_resolver.py`, `test_fallback_responses.py`, `test_intent_normalization.py`, `test_llm.py`, `test_natural_responses.py`, `test_providers.py`, `test_semantic_generalization.py`, `test_write_intent_failure.py`, and `test_write_planning.py`.

### Frontend

- `frontend/src/services/hrCopilotService.js`
- `frontend/src/routes/hr-copilot.jsx`
- `frontend/src/components/hr-copilot/ChatInput.jsx`
- `frontend/src/components/hr-copilot/ChatMessage.jsx`
- `frontend/src/components/hr-copilot/ChatMessages.jsx`
- `frontend/src/components/hr-copilot/TypingIndicator.jsx`
- `frontend/src/components/SystemAdminChatWidget.jsx`
- `frontend/src/components/Sidebar.jsx`

## Audit conclusion

The current Copilot is a secure, bounded structured-record assistant with useful employee, attendance, leave, absence, comparison-by-subsection, and approval-gated attendance/leave capabilities. It is not yet a general HR assistant because the semantic layer, query planner, and write executor do not cover the application’s broader HR domains or the requested calculations. The first implementation priority should be correctness of action lifecycle and attendance correction history, followed by reusable domain calculation tools rather than expanding the prompt alone.
