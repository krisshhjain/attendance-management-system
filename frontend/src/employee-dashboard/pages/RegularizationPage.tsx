import React, { useState, useMemo } from "react";
import PageHeader from "../components/common/PageHeader";
import Card from "../components/common/Card";
import SectionTitle from "../components/common/SectionTitle";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import Field from "../components/common/Field";
import DataTable from "../components/common/DataTable";
import RegularizationForm from "../components/forms/RegularizationForm";
import { useApp } from "../context/AppContext";

export default function RegularizationPage({
  back,
  initialDate,
  initialCheckIn,
}: {
  back?: () => void;
  initialDate?: string;
  initialCheckIn?: string;
}) {
  const { regularizations } = useApp();
  const [showForm, setShowForm] = useState(Boolean(initialDate));
  const [statusFilter, setStatusFilter] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");

  // Dynamically calculate status counts
  const stats = useMemo(() => {
    let pending = 0;
    let approved = 0;
    let rejected = 0;

    regularizations.forEach((item) => {
      if (item.status === "Pending") pending++;
      else if (item.status === "Approved") approved++;
      else if (item.status === "Rejected") rejected++;
    });

    return [
      {
        label: "Pending",
        value: `${pending} ${pending === 1 ? "request" : "requests"}`,
        color: "text-amber-600",
      },
      {
        label: "Approved",
        value: `${approved} ${approved === 1 ? "request" : "requests"}`,
        color: "text-emerald-600",
      },
      {
        label: "Rejected",
        value: `${rejected} ${rejected === 1 ? "request" : "requests"}`,
        color: "text-rose-600",
      },
    ];
  }, [regularizations]);

  // Filter requests
  const filteredRequests = useMemo(() => {
    return regularizations.filter((item) => {
      if (statusFilter !== "All" && item.status !== statusFilter) return false;
      if (searchQuery.trim() !== "") {
        const q = searchQuery.toLowerCase();
        const idMatch = item.id.toLowerCase().includes(q);
        const reasonMatch = item.reason.toLowerCase().includes(q);
        const dateMatch = item.date.toLowerCase().includes(q);
        if (!idMatch && !reasonMatch && !dateMatch) return false;
      }
      return true;
    });
  }, [regularizations, statusFilter, searchQuery]);

  const rows = useMemo(() => {
    return filteredRequests.map((req) => [
      <span key={`id-${req.id}`} className="font-semibold text-indigo-600">
        {req.id}
      </span>,
      req.date,
      req.reason,
      req.submittedOn,
      <Badge key={`badge-${req.id}`} status={req.status} />,
    ]);
  }, [filteredRequests]);

  if (showForm) {
    return (
      <RegularizationForm
        initialDate={initialDate}
        initialCheckIn={initialCheckIn}
        cancel={() => setShowForm(false)}
        onSubmitted={() => setShowForm(false)}
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Regularization"
        subtitle="Request corrections for missing or incorrect attendance records."
        action={
          <div className="flex flex-wrap gap-2">
            {back && (
              <Button variant="secondary" onClick={back}>
                Back
              </Button>
            )}
            <Button onClick={() => setShowForm(true)}>+ Request Regularization</Button>
          </div>
        }
      />

      {/* Metrics */}
      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        {stats.map(({ label, value, color }) => (
          <Card className="p-4" key={label}>
            <div className="text-xs font-semibold text-slate-500">{label}</div>
            <div className={`mt-2 text-lg font-bold ${color}`}>{value}</div>
          </Card>
        ))}
      </div>

      {/* Table Card */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <div className="text-sm font-semibold text-slate-900">My Requests</div>
            <div className="type-meta mt-0.5 font-normal text-slate-500">
              Track regularization requests and approval status
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
                placeholder="Search ID, reason or date…"
                value={searchQuery}
                onChange={setSearchQuery}
              />
            </div>
          </div>
        </div>

        <DataTable
          actions
          headers={["Request ID", "Date / Period", "Reason", "Submitted On", "Status"]}
          rows={rows}
          emptyMessage="No regularization requests found."
        />
      </Card>
    </>
  );
}
