Create a complete responsive web application UI for an Attendance Management System with a clickable multi-page dashboard experience.

The application is for a company and has a Super Admin role.

IMPORTANT:
This should NOT be a single dashboard screen. Create separate pages for every major navigation item and make the navigation functional/prototyped so that clicking a sidebar item opens its corresponding page.

DESIGN STYLE:
- Modern professional SaaS dashboard
- Clean, minimal and premium
- White/light gray background
- Subtle borders and shadows
- Rounded cards and buttons
- Consistent 12–16px corner radius
- Modern sans-serif typography
- Spacious layout
- One primary accent color
- Simple professional icons
- Avoid excessive gradients and unnecessary decoration
- Consistent design system across every page

GLOBAL LAYOUT:
Every authenticated page should contain:

LEFT SIDEBAR:
- Logo + Attendance System
- Dashboard
- Employees
- Managers
- Attendance
- Leave Management
- Departments
- Reports
- Settings

BOTTOM OF SIDEBAR:
- User profile
- Logout

TOP HEADER:
- Page title
- Search
- Notification icon
- User profile/avatar

The sidebar must remain consistent across all pages.

Make every sidebar item clickable and navigate to the correct page.

==================================================
PAGE 1 — SUPER ADMIN DASHBOARD
==================================================

Route/page: Dashboard

Create:

- Welcome message: "Good Morning, Admin"
- Date
- Total Employees card
- Present Today card
- Absent Today card
- On Leave card

Attendance Overview:
- Line/bar chart showing attendance trends
- Date filter: Today / This Week / This Month

Today's Attendance:
Table columns:
- Employee
- Department
- Check-in
- Check-out
- Status

Status badges:
- Present
- Absent
- Late
- On Leave

Department Attendance:
- Department names
- Total employees
- Present
- Absent
- Attendance percentage

Recent Activity:
- Employee check-ins
- Leave requests
- Employee additions
- Attendance updates

Quick Actions:
- Add Employee
- View Attendance
- Manage Leave
- Generate Report

Clicking "View Attendance" should navigate to the Attendance page.
Clicking "Add Employee" should navigate to the Add Employee page.

==================================================
PAGE 2 — EMPLOYEES
==================================================

Route/page: Employees

Create an Employee Management page.

Header:
"Employees"

Actions:
- Search employees
- Filter
- Add Employee button

Employee table:

Columns:
- Employee ID
- Name
- Email
- Department
- Role
- Joining Date
- Status
- Actions

Actions:
- View
- Edit
- Delete

Add Employee button opens a separate Add Employee page/form.

Include:
- Pagination
- Employee count
- Filters by department and status

Clicking an employee should open an Employee Details page.

==================================================
PAGE 3 — ADD EMPLOYEE
==================================================

Create a dedicated Add Employee page.

Form fields:
- First Name
- Last Name
- Employee ID
- Email
- Phone
- Department
- Role
- Date of Joining
- Manager
- Status
- Profile Photo

Buttons:
- Save Employee
- Cancel

After Save Employee, return to Employees page.

==================================================
PAGE 4 — EMPLOYEE DETAILS
==================================================

Create an Employee Profile/Details page.

Show:

Profile section:
- Profile photo
- Name
- Employee ID
- Email
- Department
- Role
- Joining Date
- Current status

Statistics:
- Attendance percentage
- Present days
- Absent days
- Leave days

Tabs:
- Overview
- Attendance
- Leave History

Attendance history table:
- Date
- Check-in
- Check-out
- Status

Buttons:
- Edit Employee
- Back to Employees

==================================================
PAGE 5 — MANAGERS
==================================================

Create a Manager Management page.

Cards:
- Total Managers
- Active Managers
- Departments Managed

Manager table:

Columns:
- Name
- Email
- Department
- Employees Managed
- Status
- Actions

Actions:
- View
- Edit
- Delete

Add Manager button.

Clicking a manager opens Manager Details.

==================================================
PAGE 6 — MANAGER DETAILS
==================================================

Create Manager Profile page.

Show:
- Profile
- Name
- Email
- Department
- Employees managed
- Status

Team Overview:
- Total team members
- Present today
- Absent today
- On leave

Team attendance table:
- Employee
- Check-in
- Check-out
- Status

==================================================
PAGE 7 — ATTENDANCE
==================================================

Create a dedicated Attendance Management page.

Header:
"Attendance"

Top controls:
- Date picker
- Search
- Department filter
- Status filter

Summary cards:
- Present
- Absent
- Late
- On Leave

Attendance table:

Columns:
- Employee
- Department
- Date
- Check-in
- Check-out
- Working Hours
- Status

Add:
- Daily / Weekly / Monthly toggle
- Attendance percentage
- Export button

Clicking an employee opens their attendance details.

==================================================
PAGE 8 — ATTENDANCE DETAILS
==================================================

Create an attendance details page.

Show:
- Employee information
- Selected date
- Check-in time
- Check-out time
- Working hours
- Attendance status

Monthly attendance calendar:
- Present
- Absent
- Late
- Leave

Attendance statistics:
- Present days
- Absent days
- Late days
- Leave days
- Attendance percentage

==================================================
PAGE 9 — LEAVE MANAGEMENT
==================================================

Create a Leave Management page.

Summary cards:
- Pending Requests
- Approved
- Rejected
- Total Leave

Leave request table:

Columns:
- Employee
- Department
- Leave Type
- Start Date
- End Date
- Number of Days
- Reason
- Status
- Actions

Actions:
- Approve
- Reject
- View Details

Filters:
- Status
- Department
- Leave Type
- Date

Clicking View Details opens Leave Request Details.

==================================================
PAGE 10 — LEAVE REQUEST DETAILS
==================================================

Create a Leave Request Details page.

Show:
- Employee information
- Leave type
- Start date
- End date
- Number of days
- Reason
- Request date
- Current status

Actions:
- Approve
- Reject
- Back

Include an approval history/timeline.

==================================================
PAGE 11 — DEPARTMENTS
==================================================

Create a Department Management page.

Show department cards or table.

Each department should show:
- Department name
- Department head
- Number of employees
- Attendance percentage
- Status

Actions:
- View
- Edit
- Delete

Button:
"Add Department"

Clicking a department opens Department Details.

==================================================
PAGE 12 — DEPARTMENT DETAILS
==================================================

Create a Department Details page.

Show:
- Department name
- Department head
- Total employees
- Attendance percentage

Employee list:
- Name
- Role
- Status
- Attendance percentage

Department attendance chart.

==================================================
PAGE 13 — REPORTS
==================================================

Create a Reports page.

Report categories:

- Attendance Report
- Employee Report
- Leave Report
- Department Report

Controls:
- Date range
- Department
- Employee
- Report type

Show report preview with charts and tables.

Buttons:
- Generate Report
- Export PDF
- Export CSV

==================================================
PAGE 14 — SETTINGS
==================================================

Create a Settings page.

Sections:

Profile Settings:
- Name
- Email
- Phone
- Profile photo

Security:
- Change Password
- Two-factor authentication

Attendance Settings:
- Working hours
- Late threshold
- Check-in rules
- Check-out rules

Notification Settings:
- Email notifications
- Leave notifications
- Attendance notifications

Buttons:
- Save Changes
- Cancel

==================================================
PAGE 15 — NOTIFICATIONS
==================================================

Create a Notifications page accessible by clicking the notification icon.

Categories:
- Attendance
- Leave
- Employee
- System

Each notification should show:
- Icon
- Message
- Date/time
- Read/unread state

Include:
- Mark all as read
- Clear notifications

==================================================
PAGE 16 — SEARCH
==================================================

Create a global search interaction.

When the user clicks the search bar, allow searching for:
- Employees
- Managers
- Departments
- Attendance records
- Leave requests

Show grouped search results.

Clicking a result should navigate to the corresponding page.

==================================================
NAVIGATION / PROTOTYPE BEHAVIOR
==================================================

Make the application fully clickable.

Sidebar:

Dashboard → Dashboard
Employees → Employees
Managers → Managers
Attendance → Attendance
Leave Management → Leave Management
Departments → Departments
Reports → Reports
Settings → Settings

Additional navigation:

Employee row → Employee Details
Add Employee → Add Employee
Save Employee → Employees
Manager row → Manager Details
Attendance record → Attendance Details
Leave request → Leave Request Details
Department → Department Details
Notification icon → Notifications
Search → Search results

Buttons such as Back should return to the previous relevant page.

Use realistic sample data throughout the interface so the pages look complete.

==================================================
RESPONSIVE DESIGN
==================================================

Create responsive versions for:

- Desktop
- Tablet
- Mobile

On mobile:
- Convert sidebar into a hamburger menu
- Make tables horizontally scrollable or convert them into cards
- Stack dashboard cards vertically
- Keep forms easy to use
- Maintain readable typography and spacing

==================================================
COMPONENT SYSTEM
==================================================

Create reusable components for:

- Sidebar
- Header
- Search
- Notification dropdown
- User profile
- Stat cards
- Buttons
- Tables
- Status badges
- Filters
- Dropdowns
- Modals
- Forms
- Charts
- Pagination
- Empty states
- Confirmation dialogs

Keep the design system consistent across every page.

The final result should feel like one complete production-ready Attendance Management System rather than separate unrelated screens.