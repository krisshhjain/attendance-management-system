import React, { useState, useMemo } from "react";
import PageHeader from "../components/common/PageHeader";
import Card from "../components/common/Card";
import SectionTitle from "../components/common/SectionTitle";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import Field from "../components/common/Field";
import DataTable from "../components/common/DataTable";
import LeaveForm from "../components/forms/LeaveForm";
import { useApp } from "../context/AppContext";
import { formatDateDisplay } from "../utils/dateUtils";

export default function LeavePage() {
  const { leaveBalances, leaveRequests } = useApp();
  const [showForm, setShowForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");

  const currentYear = new Date().getFullYear();

  // Dynamic balance metrics
  const availableLeaveTotal = useMemo(() => {
    return leaveBalances.reduce((sum, b) => sum + b.available, 0);
  }, [leaveBalances]);

  const usedLeaveTotal = useMemo(() => {
    return leaveBalances.reduce((sum, b) => sum + b.used, 0);
  }, [leaveBalances]);

  const pendingRequestsCount = useMemo(() => {
    return leaveRequests.filter((r) => r.status === "Pending").length;
  }, [leaveRequests]);

  // Filtered leave requests
  const filteredRequests = useMemo(() => {
    return leaveRequests.filter((req) => {
      if (statusFilter !== "All" && req.status !== statusFilter) return false;
      if (searchQuery.trim() !== "") {
        const q = searchQuery.toLowerCase();
        const typeMatch = req.leaveType.toLowerCase().includes(q);
        const reasonMatch = req.reason.toLowerCase().includes(q);
        const statusMatch = req.status.toLowerCase().includes(q);
        if (!typeMatch && !reasonMatch && !statusMatch) return false;
      }
      return true;
    });
  }, [leaveRequests, statusFilter, searchQuery]);

  const historyRows = useMemo(() => {
    return filteredRequests.map((req) => {
      const datesDisplay =
        req.startDate === req.endDate
          ? formatDateDisplay(req.startDate)
          : `${formatDateDisplay(req.startDate)} – ${formatDateDisplay(req.endDate)}`;

      return [
        <span key={`type-${req.id}`} className="font-semibold text-slate-700">
          {req.leaveType}
        </span>,
        datesDisplay,
        req.durationLabel,
        req.reason,
        <Badge key={`badge-${req.id}`} status={req.status} />,
      ];
    });
  }, [filteredRequests]);

  if (showForm) {
    return (
      <LeaveForm
        cancel={() => setShowForm(false)}
        onSubmitted={() => setShowForm(false)}
      />
    );
  }

  return (
    <>
      <PageHeader
        title="My Leave"
        subtitle="Manage your leave balance and view request history."
        action={
          <Button onClick={() => setShowForm(true)}>+ Apply for Leave</Button>
        }
      />

      {/* Metrics Cards */}
      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        {[
          ["Available Leave", `${availableLeaveTotal} days`, "text-emerald-600"],
          ["Used Leave", `${usedLeaveTotal} days`, "text-indigo-600"],
          [
            "Pending Requests",
            `${pendingRequestsCount} ${pendingRequestsCount === 1 ? "request" : "requests"}`,
            "text-amber-600",
          ],
        ].map(([label, value, color]) => (
          <Card key={label} className="p-5">
            <div className="text-xs font-semibold text-slate-500">{label}</div>
            <div className={`mt-2 text-xl font-bold ${color}`}>{value}</div>
            <div className="mt-1 text-xs text-slate-400">Leave year {currentYear}</div>
          </Card>
        ))}
      </div>

      {/* Leave Balances Breakdown */}
      <Card className="mb-5 overflow-hidden">
        <SectionTitle
          title="Leave Balances"
          subtitle={`Annual quota entitlements for calendar year ${currentYear}`}
        />
        <div className="grid divide-y divide-slate-100 sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
          {leaveBalances.map((item) => (
            <div key={item.type} className="p-4">
              <div className="text-xs font-semibold text-slate-700">{item.type}</div>
              <div className="mt-2 text-lg font-bold text-slate-900">
                {item.available}{" "}
                <span className="text-xs font-normal text-slate-500">/ {item.total} days</span>
              </div>
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>Used: {item.used}</span>
                {item.pending > 0 && (
                  <span className="font-medium text-amber-600">Pending: {item.pending}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Leave History */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <div className="text-sm font-semibold text-slate-900">Leave History</div>
            <div className="type-meta mt-0.5 font-normal text-slate-500">
              Past and upcoming leave applications
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="w-32">
              <Field
                label=""
                value={statusFilter}
                onChange={setStatusFilter}
                options={["All", "Pending", "Approved", "Rejected"]}
              />
            </div>
            <div className="w-48">
              <Field
                label=""
                placeholder="Search reason or type…"
                value={searchQuery}
                onChange={setSearchQuery}
              />
            </div>
          </div>
        </div>

        <DataTable
          headers={["Leave Type", "Date", "Duration", "Reason", "Status"]}
          rows={historyRows}
          emptyMessage="No leave requests match your search criteria."
        />
      </Card>
    </>
  );
}
