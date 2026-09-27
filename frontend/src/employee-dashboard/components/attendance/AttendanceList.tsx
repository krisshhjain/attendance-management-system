import React, { useMemo } from "react";
import DataTable from "../common/DataTable";
import Badge from "../common/Badge";
import type { AttendanceRecord } from "../../types";
import { formatDateDisplay } from "../../utils/dateUtils";

export default function AttendanceList({
  year,
  month,
  statusFilter,
  searchQuery,
  attendanceRecords,
  onSelectRecord,
}: {
  year: number;
  month: number;
  statusFilter: string;
  searchQuery?: string;
  attendanceRecords: Record<string, AttendanceRecord>;
  onSelectRecord: (record: AttendanceRecord) => void;
}) {
  const filteredRecords = useMemo(() => {
    const list = Object.values(attendanceRecords || {}).filter((record) => {
      const [y, m] = record.date.split("-").map(Number);
      if (y !== year || m - 1 !== month) return false;

      if (statusFilter && statusFilter !== "All Status" && statusFilter !== "All") {
        if (statusFilter === "On Leave" && record.status !== "On Leave") return false;
        if (statusFilter !== "On Leave" && record.status !== statusFilter) return false;
      }

      if (searchQuery && searchQuery.trim() !== "") {
        const q = searchQuery.toLowerCase();
        const dateStr = formatDateDisplay(record.date).toLowerCase();
        const statusStr = record.status.toLowerCase();
        if (!dateStr.includes(q) && !statusStr.includes(q)) return false;
      }

      return true;
    });

    // Sort descending by date
    list.sort((a, b) => b.date.localeCompare(a.date));
    return list;
  }, [year, month, statusFilter, searchQuery, attendanceRecords]);

  const rows = filteredRecords.map((record) => [
    <span key={record.id} className="font-semibold text-slate-700">
      {formatDateDisplay(record.date)}
    </span>,
    <Badge key={`badge-${record.id}`} status={record.status} />,
    record.checkIn,
    record.checkOut === "--:--" ? "Not recorded" : record.checkOut,
    record.workingHours,
  ]);

  return (
    <DataTable
      headers={["Date", "Status", "Check In", "Check Out", "Working Hours"]}
      rows={rows}
      actions
      actionLabel="Details"
      onActionClick={(idx) => {
        onSelectRecord(filteredRecords[idx]);
      }}
      emptyMessage="No attendance records match the selected filter."
    />
  );
}
