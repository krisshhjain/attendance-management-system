import React from "react";

const statusStyles: Record<string, string> = {
  Present: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  Approved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  Absent: "bg-rose-50 text-rose-700 ring-rose-200",
  Rejected: "bg-rose-50 text-rose-700 ring-rose-200",
  Late: "bg-amber-50 text-amber-700 ring-amber-200",
  "On Leave": "bg-amber-50 text-amber-700 ring-amber-200",
  Pending: "bg-amber-50 text-amber-700 ring-amber-200",
  "Work From Home": "bg-violet-50 text-violet-700 ring-violet-200",
  "On Duty": "bg-blue-50 text-blue-700 ring-blue-200",
  "Missing Check-out": "bg-orange-50 text-orange-700 ring-orange-200",
  "Half Day": "bg-amber-50 text-amber-700 ring-amber-200",
  Holiday: "bg-sky-50 text-sky-700 ring-sky-200",
  Weekend: "bg-slate-100 text-slate-600 ring-slate-200",
};

export default function Badge({ status }: { status: string }) {
  return (
    <span
      className={`type-caption inline-flex whitespace-nowrap rounded-full px-2.5 py-1 font-semibold ring-1 ring-inset ${
        statusStyles[status] || "bg-slate-100 text-slate-600 ring-slate-200"
      }`}
    >
      {status}
    </span>
  );
}
