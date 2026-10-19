# System Admin Implementation Documentation

## Overview
The system has a **System Admin** role that sits alongside regular employees and super admins. System Admins have read-only access to organizational data with scoped permissions for HR Copilot queries.

---

## System Admin Features

### 1. **Separate Login Portal**
- **URL**: `/systemadmin-login`
- **Endpoint**: `/api/auth/systemadmin-login/`
- **Authentication**: Uses JWT tokens with `loginType: "systemadmin"` stored in localStorage

### 2. **User Model Integration**
**Backend Model** (`backend/accounts/models.py`):
```python
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_system_admin = models.BooleanField(default=False)
    hr_copilot_sections = models.JSONField(default=list, blank=True)
    hr_copilot_subsections = models.JSONField(default=list, blank=True)
```

**Key Fields**:
- `is_system_admin`: Boolean flag marking user as System Admin
- `hr_copilot_sections`: List of sections the admin can query (e.g., ["C", "D"])
- `hr_copilot_subsections`: List of subsections for scoped access (e.g., ["C1", "C2"])

### 3. **Permissions System**
**Custom Permission Class** (`backend/leave_management/permissions.py`):
```python
class IsSystemAdminOrSuperAdminReadOnly(BasePermission):
    """
    Allow System Admin reads while reserving configuration 
    changes for superusers.
    """
    - GET/HEAD/OPTIONS: System Admin OR Super Admin
    - POST/PUT/PATCH/DELETE: Super Admin only
```

**Usage**:
- Leave Types: System Admins can view but not modify
- Leave Policies: System Admins can view but not modify
- HR Copilot: System Admins can query within their scoped sections

### 4. **HR Copilot Integration**
System Admins have access to **HR Copilot** - an AI-powered query interface for organizational data.

**Access Control**:
- Must have `is_system_admin=True` or `is_superuser=True`
- Queries are scoped to assigned sections/subsections
- Cannot query data outside their scope

**Features**:
- Natural language queries about attendance, employees, leave
- Automatic scope validation
- Audit logging of all queries
- Data visualization support

**Frontend Component**: `SystemAdminChatWidget.jsx`
- Floating chat widget in bottom-right corner
- Real-time query processing
- Organization scope filtering

**Backend Endpoint**: `/api/hr-copilot/query/`
```python
# Example scoped query validation
if not (user.is_system_admin or user.is_superuser):
    return Response({"detail": "System Admin access is required."}, status=403)
```

### 5. **Dashboard & Layout**

**System Admin Layout** (`SuperAdminLayout.jsx`):
- Same layout as Super Admin but with "System Admin" label
- Access to: Dashboard, Attendance, Employees, Leave, Administration, HR Copilot
- Shows HR Copilot chat widget
- Organization scope filters on dashboard

**Navigation**:
```javascript
const NAVIGATION_ITEMS = [
  { text: "Dashboard", icon: ICONS.dashboard, path: "/dashboard" },
  { text: "My Attendance", icon: ICONS.attendance, path: "/attendance" },
  { text: "Employees", icon: ICONS.employees, path: "/employees" },
  { text: "My Leave", icon: ICONS.leave, path: "/leave" },
  { text: "Administration", icon: ICONS.administration, path: "/administration" },
  ...(loginType === "systemadmin" 
    ? [{ text: "HR Copilot", icon: ICONS.hrcopilot, path: "/hr-copilot" }] 
    : []),
];
```

### 6. **View-Only Access to Administration**

**Leave Management**:
- ✅ View leave requests
- ✅ View leave types
- ✅ View leave policies
- ✅ View employee balances
- ❌ Cannot approve/deny requests (reserved for Super Admin)
- ❌ Cannot create/edit leave types
- ❌ Cannot create/edit policies

**Implementation**: The Administration page checks `isSystemAdmin` and disables action buttons for System Admins while allowing read access.

### 7. **Scoped Data Access**

**Organization Scope Filters**:
System Admins see organization-wide data filtered by their assigned scope:
- Dashboard shows stats for their sections/subsections only
- Employee list filtered by scope
- Attendance reports scoped to their sections
- Leave requests from their scope only

**Scope Configuration** (Set in Django Admin):
```python
# Example: System Admin for Section C
user.hr_copilot_sections = ["C"]
user.hr_copilot_subsections = ["C1", "C2", "C3"]
```

---

## How to Create a System Admin

### Via Django Admin:
1. Create a new user account
2. Set `is_system_admin = True`
3. Configure `hr_copilot_sections` (e.g., `["C", "D"]`)
4. Optionally set `hr_copilot_subsections` for finer control
5. User can now log in at `/systemadmin-login`

### Via Django Shell:
```python
from django.contrib.auth import get_user_model
User = get_user_model()

# Create System Admin
admin = User.objects.create_user(
    email="systemadmin@example.com",
    password="secure_password",
    first_name="System",
    last_name="Admin",
    is_system_admin=True
)

# Assign scope
admin.hr_copilot_sections = ["C", "D"]
admin.hr_copilot_subsections = ["C1", "C2"]
admin.save()
```

---

## Key Differences: System Admin vs Super Admin

| Feature | System Admin | Super Admin |
|---------|-------------|-------------|
| Login Portal | `/systemadmin-login` | `/admin-login` |
| Leave Request Management | ❌ View only | ✅ Approve/Deny |
| Leave Type/Policy Config | ❌ View only | ✅ Full CRUD |
| HR Copilot Access | ✅ Scoped queries | ✅ Full access |
| Data Scope | Restricted to assigned sections | Organization-wide |
| Shift Configuration | ✅ Full access | ✅ Full access |
| Employee Management | ✅ View, scoped by section | ✅ Full access |

---

## Security Considerations

1. **Scope Enforcement**: All HR Copilot queries are validated against assigned scope
2. **Read-Only Permissions**: System Admins cannot modify leave policies or types
3. **Audit Logging**: All HR Copilot queries are logged with user ID and timestamp
4. **Separate Login**: System Admins use dedicated login endpoint with validation
5. **JWT Token Scoping**: `loginType` in token payload differentiates System Admin sessions

---

## Testing System Admin

**Backend Tests**: `backend/hr_copilot/test_api.py`
```python
def test_query_requires_system_admin(api):
    employee = system_admin(is_system_admin=False)
    response = call_endpoint(factory, employee, {"message": "How many employees?"})
    assert response.status_code == 403

def test_unassigned_scope_is_rejected_and_audited(api):
    unscoped = system_admin(hr_copilot_sections=[], hr_copilot_subsections=[])
    response = call_endpoint(factory, unscoped, {"message": "How many employees?"})
    assert response.status_code == 403
```

---

## Migration History

1. **0003_user_is_system_admin.py**: Added `is_system_admin` field
2. **0004_user_hr_copilot_scope.py**: Added scope fields for HR Copilot

---

## Current Status

✅ **Fully Implemented**:
- Separate login portal
- User model with system admin flag
- Scoped permissions for HR Copilot
- Read-only access to leave management
- Organization scope filtering
- Audit logging

🔧 **Configuration Required**:
- Set `is_system_admin=True` for designated users
- Assign sections/subsections for scope
- Test HR Copilot queries within scope

---

## Related Files

**Backend**:
- `backend/accounts/models.py` - User model
- `backend/accounts/views.py` - SystemAdminLoginView
- `backend/leave_management/permissions.py` - Permissions
- `backend/hr_copilot/views.py` - HR Copilot query handler

**Frontend**:
- `frontend/src/routes/systemadmin-login.jsx` - Login page
- `frontend/src/components/SuperAdminLayout.jsx` - Layout
- `frontend/src/components/SystemAdminChatWidget.jsx` - HR Copilot widget
- `frontend/src/routes/hr-copilot.jsx` - HR Copilot page
