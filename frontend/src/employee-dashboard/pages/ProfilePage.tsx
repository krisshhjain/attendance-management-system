import React, { useState } from "react";
import PageHeader from "../components/common/PageHeader";
import Card from "../components/common/Card";
import SectionTitle from "../components/common/SectionTitle";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import Avatar from "../components/common/Avatar";
import Field from "../components/common/Field";
import { useApp } from "../context/AppContext";

export default function ProfilePage() {
  const { user, updateProfile, todayRecord } = useApp();
  const [editing, setEditing] = useState(false);

  // Form states for editing
  const [name, setName] = useState(user.name);
  const [employeeId, setEmployeeId] = useState(user.employeeId);
  const [joiningDate, setJoiningDate] = useState(user.joiningDate);
  const [email, setEmail] = useState(user.email);
  const [phone, setPhone] = useState(user.phone);
  const [department, setDepartment] = useState(user.department);
  const [designation, setDesignation] = useState(user.designation);
  const [manager, setManager] = useState(user.manager);
  const [location, setLocation] = useState(user.location);

  const handleSave = async () => {
    await updateProfile({
      name,
      employeeId,
      joiningDate,
      email,
      phone,
      department,
      designation,
      manager,
      location,
    });
    setEditing(false);
  };

  const handleCancel = () => {
    // Reset to current user values
    setName(user.name);
    setEmployeeId(user.employeeId);
    setJoiningDate(user.joiningDate);
    setEmail(user.email);
    setPhone(user.phone);
    setDepartment(user.department);
    setDesignation(user.designation);
    setManager(user.manager);
    setLocation(user.location);
    setEditing(false);
  };

  return (
    <>
      <PageHeader
        title="My Profile"
        subtitle="View and manage your personal and work information."
        action={
          editing ? (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={handleCancel}>
                Cancel
              </Button>
              <Button onClick={handleSave}>Save Changes</Button>
            </div>
          ) : (
            <Button onClick={() => setEditing(true)}>Edit Profile</Button>
          )
        }
      />

      {/* Profile Header Card */}
      <Card className="mb-5 p-5">
        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
          <Avatar large />
          <div>
            <div className="text-xl font-bold text-slate-900">{user.name}</div>
            <div className="mt-1 text-sm text-slate-500">
              {user.employeeId} · {user.designation}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <Badge status={todayRecord.status === "Pending" ? "Present" : todayRecord.status} />
              <span className="text-xs text-slate-500">{user.department}</span>
              <span className="text-xs text-slate-400">·</span>
              <span className="text-xs text-slate-500">{user.location}</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Info Cards */}
      <div className="grid gap-5 xl:grid-cols-3">
        {/* Personal Information */}
        <Card>
          <SectionTitle title="Personal Information" />
          <div className="space-y-4 p-5">
            {editing ? (
              <>
                <Field label="Full Name" value={name} onChange={setName} required />
                <Field
                  label="Employee ID"
                  value={employeeId}
                  onChange={setEmployeeId}
                  required
                />
                <Field
                  label="Joining Date"
                  value={joiningDate}
                  onChange={setJoiningDate}
                />
              </>
            ) : (
              <>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Full Name</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">{user.name}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Employee ID</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">
                    {user.employeeId}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Joining Date</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">
                    {user.joiningDate}
                  </div>
                </div>
              </>
            )}
          </div>
        </Card>

        {/* Contact Information */}
        <Card>
          <SectionTitle title="Contact Information" />
          <div className="space-y-4 p-5">
            {editing ? (
              <>
                <Field label="Email" type="email" value={email} onChange={setEmail} required />
                <Field label="Phone" value={phone} onChange={setPhone} />
                <Field label="Work Location" value={location} onChange={setLocation} />
              </>
            ) : (
              <>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Email</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">{user.email}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Phone</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">{user.phone}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Work Location</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">{user.location}</div>
                </div>
              </>
            )}
          </div>
        </Card>

        {/* Work Information */}
        <Card>
          <SectionTitle title="Work Information" />
          <div className="space-y-4 p-5">
            {editing ? (
              <>
                <Field
                  label="Department"
                  value={department}
                  onChange={setDepartment}
                  options={[
                    "Product & Design",
                    "Engineering",
                    "Human Resources",
                    "Marketing",
                    "Operations",
                  ]}
                />
                <Field
                  label="Designation"
                  value={designation}
                  onChange={setDesignation}
                  required
                />
                <Field label="Reporting Manager" value={manager} onChange={setManager} />
              </>
            ) : (
              <>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Department</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">
                    {user.department}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Designation</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">
                    {user.designation}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-400">Reporting Manager</div>
                  <div className="mt-1 text-sm font-medium text-slate-800">{user.manager}</div>
                </div>
              </>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
