# Frontend Action Feedback Audit and Implementation Plan

**Scope:** inspection-only audit of the active frontend at `D:\attendance-management-system\frontend` on 2026-09-30. No application code, dependencies, routing, API behavior, or backend files were changed.

## 1. Active pages and routes inspected

The generated TanStack route tree and the source route files were inspected. The active routes are:

| Route | Main active surface |
|---|---|
| `/` | Authentication-aware redirect to `/dashboard` or `/login` |
| `/login` | Employee/manager sign-in |
| `/admin-login` | Admin sign-in |
| `/systemadmin-login` | System Manager sign-in |
| `/dashboard` | Role-aware dashboard; employee attendance, admin employee management and management widgets |
| `/attendance` | Employee attendance history/calendar and attendance actions |
| `/leave` | Employee/admin leave requests, attachments, cancellation and administration views |
| `/regularization` | Employee attendance-correction submission |
| `/admin-regularization` | Admin regularization list and quota configuration |
| `/administration/regularization/$id` | Admin regularization review detail |
| `/administration` | Leave administration, locations, shift configuration, leave balances and approval actions |
| `/employees` | Employee/manager management surface |
| `/my-team` | Team attendance/read-only view |
| `/settings` | Current-user password change |
| `/hr-copilot` | HR Copilot conversation and approval actions |
| `/system-logs` | Superuser log filtering, export and deletion |
| `/kiosk` | Public facial kiosk check-in/check-out |

Shared active surfaces inspected: `AuthProvider`, `RequireAuth`, employee and super-admin layouts/sidebars, dashboard dialogs/tables, attendance cards/widgets, face verification/enrollment, shift selection/configuration, notification bell, HR Copilot widget/components, API/auth/attendance services, and loading/error state components.

## 2. Important user actions found

The following table records the actual mutation or important async path, its current behavior, and the feedback requirement. `apiRequest` means `src/lib/api.js`; direct `fetch` paths are called out because they do not share the normal API error translation/retry handling.

| Route/surface | User action and API/function | Current success behavior | Current error behavior / reload | Existing feedback and gap |
|---|---|---|---|---|
| `/login`, `/admin-login`, `/systemadmin-login` | Sign in via `useAuth().login()` → `/auth/login/` or `/auth/systemadmin-login/` | Navigate to `/dashboard` | Inline error from caught `ApiError`; no reload | Loading button and inline error exist. No global success, and failures are implemented three times. |
| Employee sidebar / super-admin layout | Logout via `logout()` then navigate `/login` | Immediate navigation | No API mutation; no error path | No confirmation or completion feedback needed; optional session-expired global handling is separate. |
| Dashboard / attendance card and employee `TodayAttendanceWidget` | Check in/out via `checkIn`/`checkOut` → `/attendance/check-in/`, `/attendance/check-out/` with coordinates | Local success message; refreshes today data | Local error; geolocation failures are surfaced locally | Inline success/error exists in two separate implementations. Needs one global success/error wording and consistent location/geofence warnings. |
| Employee face attendance | `FaceVerificationModal` → `/attendance/website-facial-check-in/` or facial check-out endpoint | Modal success for 2 seconds, then `onSuccess()` and parent refresh | Modal error with special mappings for multi-face, no face, and confidence failures | Good domain-specific errors and loading. Needs global result notification after modal completion and consistent failure translation. |
| `/kiosk` facial attendance | `WebcamCapture` then direct `fetch` multipart → `/attendance/kiosk/check-in/` or `/attendance/kiosk/check-out/` | Local `Snackbar` using backend message | Local `Snackbar`; direct fetch does not use `ApiError`/token handling | One of the few complete timed snackbars, but position/duration/wording differ from other surfaces and it has no shared error normalization. |
| Employee face enrollment in `EmployeeTable` | Burst capture then direct multipart `fetch` → `/admin/employees/:id/enroll-face/` | Inline “Successfully enrolled! Closing...” then closes after 2 seconds and refetches | Inline error; dialog remains open | Feedback exists, but direct fetch and custom styling duplicate the system. |
| Dashboard `/employees` | Create employee → `POST /admin/employees/` (`AddEmployeeDialog`) | Dialog callback closes/refetches | Inline dialog error; no parent success | Success is silent. Needs global “Employee created successfully.” |
| Dashboard `/employees` | Edit employee → `PATCH /admin/employees/:id/` (`EditEmployeeDialog`) | Dialog callback closes/refetches | Inline dialog error | Success is silent. Needs global update result. |
| Dashboard `/employees` | Delete/deactivate employee → `DELETE /admin/employees/:id/` | Dialog closes/refetches | Error is intentionally swallowed; dialog closes and refetch is relied on | Critical missing error and success feedback. Do not silently close on failure. |
| Dashboard `/employees` | Reset employee password → `POST /admin/employees/:id/change-password/` | Callback closes dialog | Inline dialog error | Success is silent. Needs global confirmation. |
| Dashboard `/employees` | Assign employee shift → direct `POST /attendance/admin/shift/assign/` | Callback closes/refetches | Inline dialog error | Success is silent. Needs global result. |
| Dashboard `/employees` | Create/update manager → `POST /admin/employees/managers/` or `PATCH /admin/employees/managers/:id/` | Mutation closes dialog and refetches | Inline `Alert`; local success `Alert` | Feedback exists but persistent/local and generic. Needs global timed feedback. |
| Dashboard `/employees` | Delete manager → `DELETE /admin/employees/managers/:id/` | Closes/refetches | Local error `Alert` | Needs global success/error. |
| Dashboard `/employees` | Change manager password → `POST /admin/employees/managers/:id/change-password/` | Closes/refetches | Dialog validation or local mutation error | Needs global success/error; validation should remain inline. |
| `/leave` | Upload attachment → `uploadFile()` → `POST /leave/upload/` | URL stored in form; no success notice | Form error on upload failure, then submission is stopped | Upload progress/result is silent; show an error when it fails, but do not show a success toast for an intermediate upload. |
| `/leave` | Submit leave request → `submitLeaveRequest()` → `POST /leave/requests/` | Local success message and data reload | Local error message; no full page reload | Feedback exists, but local and duplicated with admin leave. Needs global success/error. |
| `/leave` | Cancel own leave → `cancelLeaveRequest()` → `POST /leave/requests/:id/cancel/` | Local success and data reload | Local error | Needs global success/error and a warning/confirmation before destructive cancellation. |
| `/leave` | Estimate leave duration → `estimateLeaveDuration()` → `POST /leave/estimate-duration/` | Updates form calculation | Inline form error/validation path | Informational calculation does not need a toast; error should remain adjacent to the form. |
| `/administration` | Create/update/delete office location → `POST /attendance/locations/`, `PUT /attendance/locations/:id/`, `DELETE /attendance/locations/:id/` | Local success message and locations reload | Local error; browser `confirm` for delete | Feedback exists as local message. Needs global timed success/error; deletion confirmation remains a dialog/confirmation, not a toast. |
| `/administration` | Approve/deny/cancel approved leave → `approveLeaveRequest`, `denyLeaveRequest`, `cancelApprovedLeaveRequest` → `/leave/admin/requests/:id/.../` | Local success message and list reload | Local action error | Needs global success/error with action-specific wording. |
| `/administration` | Create/update/deactivate leave policy → `createLeavePolicy`, `updateLeavePolicy`, `deleteLeavePolicy` | Local success and reload; delete is presented as deactivation | Local error | Needs global success/error; keep confirmation for deactivation. |
| `/administration` | Create/update/deactivate leave type → `createLeaveType`, `updateLeaveType`, `deleteLeaveType` | Local success and reload | Local error | Needs global success/error; keep confirmation for deactivation. |
| `/administration` | Configure employment-type shifts → `configureEmploymentTypeShifts()` → `POST /attendance/admin/shift/configure/` | Local success `Alert` and configuration reload | Local error `Alert`; unsaved-change browser confirms | Needs global success/error; unsaved-change prompt is not a notification. |
| Employee shift selection | `useMutation` `selfAssignShift()` → `POST /attendance/my-shift/assign/` | Mutation success updates screen | Mutation error inline `Alert` | Needs global success/error after assignment; unavailable/no-shift warning should remain contextual. |
| `/regularization` | Upload attachment then submit → `uploadFile`, `createRegularizationRequest()` → `POST /attendance/regularization/` | Form closes/updates quota and list (no clear success toast) | Inline form error; loading button | Needs global success: “Regularization request submitted.” Upload failure needs useful error. |
| `/admin-regularization` | Save quota limits → `PATCH /attendance/admin/regularization/quota-settings/` | Inline saved `Alert` | Inline error `Alert` | Needs timed global success/error; validation remains inline. |
| `/administration/regularization/$id` | Approve regularization → `approveRegularizationRequest()` → `POST .../:id/approve/` | Detail state/navigation update | Inline error | Needs global success/error. |
| `/administration/regularization/$id` | Reject regularization → `rejectRegularizationRequest()` → `POST .../:id/reject/` | Detail state/navigation update | Inline error | Needs global success/error; rejection reason stays in dialog/form. |
| `/settings` | Change current password → `POST /auth/change-password/` | Inline success; closes after 1.5 seconds | Inline error; no reload | Needs global success/error; retain inline field validation. |
| Forced password modal | Change forced password → `POST /auth/change-password/` | Calls `window.location.reload()` after success | Inline error | Success is not visible before reload; unnecessary full page reload. Replace later with auth/profile state refresh and global success where safe. Logout remains immediate local action. |
| Notification bell | Mark notification read → `PATCH /notifications/:id/read/` | Optimistic removal from unread query and refetch | Rollback on error, but no visible error | Missing feedback on failed mark-read. A brief error is warranted; successful read needs no toast. |
| Notification bell | Click notification currently marks read then deletes → `DELETE /notifications/:id/` | Optimistic removal/refetch | Rollback on error, no visible error | Semantics are destructive and success is silent. Needs error feedback; success toast is optional and likely unnecessary for routine dismissal. |
| `/hr-copilot` | Send question → `sendMessage()` → `POST /hr-copilot/query/` | Appends assistant response to conversation | Inline chat error; loading/typing indicator | Chat errors belong in the conversation, not a global toast; no success toast for each message. |
| `/hr-copilot` | Approve/cancel pending action → `respondToAction()` → `POST /hr-copilot/actions/approve/` | Updates pending action to executed/cancelled | Inline chat error | Needs a global success/error because this is a consequential mutation, plus inline result in the message. |
| `/system-logs` | Export CSV/XLSX → `downloadSystemLogs()` direct fetch → `/system-logs/export/` | Browser download starts silently | Inline error `Alert` | Needs timed success/info (“CSV download started”) and global/API-normalized error. |
| `/system-logs` | Delete logs → `deleteSystemLogs()` → `DELETE /system-logs/?until_date=...` | Local timed `Snackbar`, reloads list | Inline error `Alert` | Existing success snackbar; needs shared global system and consistent warning/confirmation. |
| Admin attendance | Checkout one/all → `forceAdminCheckout()` → `/admin/force-checkout/` | Refetch and local success snackbar | Local error snackbar | Existing local snackbars; migrate to global. |
| Admin attendance | Edit attendance → `editAdminAttendance()` → `/admin/attendance/edit/` | Refetch and local success snackbar | Local error snackbar | Migrate to global success/error. |
| Admin attendance | Reset attendance → `resetAdminAttendance()` → `/admin/attendance/reset/` | Refetch and local success snackbar | Local error snackbar | Migrate to global success/error; retain reason confirmation. |
| Admin attendance | Download Excel | Client-side `exportToExcel` from filtered records | No clear failure path | Add an info/success result only if generation can fail; no toast for routine synchronous download. |

## 3. Current feedback gaps

- No global feedback context/provider, queue, or imperative notification API exists.
- Success feedback is frequently silent: employee create/update/delete, employee password reset, shift assignment, regularization submission, many manager actions, and HR Copilot confirmations.
- Error handling is inconsistent: some errors are inline, some are local snackbars, some are React Query query errors, and employee deletion deliberately swallows the exception.
- `apiRequest` already translates common backend statuses and handles token refresh, but direct `fetch` is used for face enrollment, kiosk attendance, leave upload, and system-log export. These paths duplicate or bypass error normalization.
- The same feedback state is implemented independently in `AttendanceCard`, `TodayAttendanceWidget`, `AdminAttendancePage`, `system-logs`, `kiosk`, `administration`, `leave`, dialogs, and manager components.
- Snackbar positioning and durations are inconsistent; most inline alerts are persistent until dismissed or until a component rerenders.
- There is no consistent warning/info policy for geofence failures, pending/duplicate submissions, destructive actions, downloads, or successful background refetches.
- Full reload is used after forced password change; facial flows use delayed callbacks and parent refreshes. The notification plan should avoid introducing reloads and should favor query invalidation/state refresh.
- Loading states are generally present (`CircularProgress`, disabled buttons, React Query `isPending`), but feedback does not have a shared pending lifecycle or protection against duplicate submissions across all patterns.
- Root theme setup is duplicated in `main.jsx` and `__root.jsx`; the active root theme is effectively light-only. A future feedback surface must consume the active MUI theme and remain safe if dark mode is enabled later.
- Notification read/delete mutations optimistically update queries but provide no visible failure feedback.

## 4. Existing feedback mechanisms

- MUI `Alert` is used for inline validation, access warnings, load errors, modal errors, success confirmations, and the HR Copilot preview notice.
- MUI `Snackbar` + `Alert` exists locally in `kiosk`, `AdminAttendancePage`, and `system-logs`; these have different durations/anchors and no shared API.
- Component-local success/error state exists in attendance widgets, leave, administration, shift configuration, face flows, dialogs, manager management, and settings.
- React Query provides loading/error/mutation state and optimistic rollback for notifications; it is not connected to a global feedback layer.
- `api.js` exposes `ApiError` and `friendlyMessage()` with network, authentication, authorization, validation, conflict, and server-error wording. This should be the canonical source for fallback error text.
- Auth token refresh is centralized in `apiRequest`, but direct `fetch` mutations do not benefit from it.
- Loading feedback is mostly local button text/spinners. Read-only fetches use `LoadingState`, `CircularProgress`, skeletons, or page-level alerts.
- Browser `window.confirm` is used for location deletion and unsaved shift changes. These are confirmations, not replacements for post-action notifications.

## 5. Recommended global feedback architecture

Implement one MUI-based `FeedbackProvider` mounted once inside the root providers and theme, with a `useFeedback()` hook and a small imperative enqueue API:

```text
enqueue({ severity: "success" | "error" | "warning" | "info", message, duration?, id? })
close(id)
closeAll()
```

Recommended behavior:

1. Render one `Snackbar`/`Alert` host at a consistent responsive position, preferably bottom-right on desktop and bottom-center on mobile, above dialogs and app chrome.
2. Use a small queue/stack with stable IDs, automatic timeout by severity, manual close, accessible live-region semantics, keyboard focus safety, and deduplication for repeated API errors.
3. Use the active MUI theme rather than hard-coded colors. Define success/error/warning/info variants that work in light and dark modes and meet contrast requirements.
4. Centralize `toUserMessage(error, context)` around `ApiError`, HTTP status, field validation payloads, network errors, geofence errors, facial-recognition errors, and safe fallback text. Do not expose raw HTML, stack traces, or sensitive backend details.
5. Keep field-level validation and durable page-load failures inline. Global feedback is for completed user actions and actionable transient failures, not every query or every chat message.
6. Standardize mutation lifecycle: disable the initiating control, show existing local pending state, await the mutation, invalidate/refetch the affected query, enqueue success on completion, enqueue normalized error on failure, and preserve the dialog/form when retry is possible.
7. Replace local success/error snackbars incrementally with the provider. Avoid two notifications for one action; do not render both a global success toast and an identical inline success alert.
8. Prefer query invalidation/state updates over `window.location.reload()`. Preserve the forced-password security flow while refreshing auth/profile state deliberately.
9. Add an optional action metadata/context field for logging and testability, but do not make notification text depend on raw endpoint strings.

Suggested message examples:

- “Attendance marked successfully.”
- “You have been checked out successfully.”
- “Leave request submitted.”
- “Leave request cancelled.”
- “Employee updated successfully.”
- “Regularization request approved.”
- “Face enrollment completed for {employee}.”
- “Unable to save changes. Please check the highlighted fields.”
- “We couldn’t reach the server. Check your connection and try again.”

## 6. Actions that need success/error feedback

Global success and error feedback should be added for all completed mutations:

- All three login attempts: error on failure; success is normally represented by navigation, so do not add a redundant success toast unless the destination is delayed.
- Check-in, check-out, facial check-in/out, and kiosk facial actions.
- Leave submission, cancellation, attachment-upload failure, admin approve/deny/cancel.
- Regularization submission, approval, rejection, and quota-policy save.
- Employee create/update/delete/deactivate, face enrollment, password reset, and shift assignment.
- Manager create/update/delete/deactivate and manager password change.
- Office location create/update/delete.
- Leave type and leave policy create/update/deactivation.
- Shift self-assignment and admin shift configuration.
- Current-user and forced password change.
- HR Copilot approve/cancel action; keep ordinary chat request failures in-chat.
- System-log export start/failure and log deletion.
- Admin attendance checkout, bulk checkout, edit, and reset.
- Notification mark-read/delete failures; success is not necessary for routine read/dismiss actions.

Error messages should be actionable and retain domain-specific mappings already present for face detection, geofence/location, validation, conflict, session expiration, and network failure.

## 7. Actions that should not show a notification

- Navigation, opening/closing dialogs, toggling password visibility, changing filters, pagination, changing attendance view/month, and selecting a dashboard card.
- Logout success; redirect is sufficient. Show a notification only if logout fails in a future server-backed logout flow.
- Routine successful data loads, refetches, polling, and cache invalidations.
- Opening/closing/minimizing the HR assistant and starting a new Copilot chat.
- Each normal HR Copilot question/answer; use the chat transcript and typing indicator. Show an inline chat error if the request fails.
- Leave-duration estimation success; show the result in the form.
- Marking a notification read or dismissing one successfully; only show an error if the mutation cannot be persisted.
- Download success for a routine synchronous client-side Excel export; use feedback only when generation/download startup is asynchronous or fails.
- Confirmation dialogs, unsaved-change prompts, field validation, empty states, permission warnings, and page-load errors should remain contextual UI rather than transient toasts.

## 8. Recommended implementation order

1. Define notification vocabulary, severity rules, duration defaults, position, accessibility requirements, deduplication, and the API-error translation contract.
2. Add the single provider/host and `useFeedback` API at the root provider level. Add focused tests for queueing, timeout, manual close, duplicate messages, theme contrast, and normalized errors.
3. Migrate the existing local `Snackbar` implementations (`AdminAttendancePage`, `system-logs`, `kiosk`) so there is one rendering system and one positioning policy.
4. Migrate core attendance and facial flows: check-in/out, geofence/location errors, facial verification, kiosk, and face enrollment.
5. Migrate leave and regularization mutations, including employee/admin approval flows and attachment failures.
6. Migrate employee, manager, password, shift, office-location, leave-type, leave-policy, and shift-configuration actions. Fix silent employee-delete failures while doing this.
7. Migrate HR Copilot consequential confirmations and system-log export/delete. Keep chat/query and filter feedback contextual.
8. Normalize direct `fetch` mutation error handling behind shared API helpers where compatible, without changing backend contracts; eliminate avoidable full-page reloads in favor of auth/query state refresh.
9. Remove duplicate local success/error notification rendering only after each flow has been verified, then run the full frontend lint/build and manual role-based action matrix.

### Verification matrix for implementation phase

Test employee, manager, admin, system manager, and kiosk contexts; success, validation failure, permission denial, conflict, expired session, offline/network failure, server error, duplicate click, dialog retry, mobile placement, and light/dark theme. Confirm that every mutation has exactly one appropriate completion/error path and that read-only navigation/query activity does not generate notification noise.
