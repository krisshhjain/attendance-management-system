import React from "react";
import Button from "../common/Button";
import Icon from "../common/Icon";
import Badge from "../common/Badge";
import type { AttendanceRecord } from "../../types";
import { formatDateDisplay } from "../../utils/dateUtils";

function DetailRow({
  label,
  value,
  badge = false,
}: {
  label: string;
  value: string;
  badge?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-3">
      <span className="text-xs font-semibold text-slate-500">{label}</span>
      {badge ? (
        <Badge status={value} />
      ) : (
        <span className="text-sm font-semibold text-slate-800">{value}</span>
      )}
    </div>
  );
}

export default function AttendanceDetailModal({
  record,
  close,
  onRegularize,
  onViewDetails,
}: {
  record: AttendanceRecord;
  close: () => void;
  onRegularize: (dateIso: string, checkIn?: string) => void;
  onViewDetails: (page: "attendance" | "leave" | "onduty") => void;
}) {
  const { date, status, checkIn, checkOut, workingHours, attendanceType, notes } = record;
  const isMissingCheckout = status === "Missing Check-out";
  const isAbsent = status === "Absent";
  const isLeave = status === "On Leave";
  const isOnDuty = status === "On Duty";
  const isWeekend = status === "Weekend";

  const title = isMissingCheckout
    ? "Attendance Issue"
    : isLeave
    ? "Leave Details"
    : isOnDuty
    ? "On Duty Details"
    : "Attendance Details";

  const dateDisplay = formatDateDisplay(date);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-end bg-slate-950/30 backdrop-blur-xs transition-opacity"
      onClick={close}
    >
      <div
        className="w-full border-l border-slate-200 bg-white shadow-2xl sm:h-full sm:max-w-md animate-in slide-in-from-right duration-200 overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <div className="text-base font-bold text-slate-900">{title}</div>
            <div className="mt-1 text-xs text-slate-500">{dateDisplay}</div>
          </div>
          <Button
            variant="ghost"
            className="px-2 text-slate-400 hover:text-slate-600"
            onClick={close}
            ariaLabel="Close details panel"
          >
            <Icon name="close" />
          </Button>
        </div>

        <div className="p-5">
          {isMissingCheckout && (
            <div className="mb-4 rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
              <span className="font-semibold">Attention:</span> Your check-out time is missing for
              this day. Please submit a regularization request to correct your record.
            </div>
          )}

          {isAbsent && (
            <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
              No attendance record was detected for this workday.
            </div>
          )}

          <div className="space-y-4">
            <DetailRow label="Status" value={status} badge />

            {isLeave && (
              <>
                <DetailRow label="Leave Type" value={notes || "Casual Leave"} />
                <DetailRow label="Approval Status" value="Approved" badge />
              </>
            )}

            {isOnDuty && (
              <>
                <DetailRow label="Location" value={record.location || "Client Office, Cyber City"} />
                <DetailRow label="Purpose" value={notes || "Client Meeting"} />
                <DetailRow label="Start Time" value={checkIn} />
                <DetailRow label="End Time" value={checkOut} />
                <DetailRow label="Approval Status" value="Approved" badge />
              </>
            )}

            {!isLeave && !isOnDuty && !isWeekend && (
              <>
                <DetailRow label="Check-in" value={checkIn} />
                <DetailRow label="Check-out" value={checkOut === "--:--" ? "Not recorded" : checkOut} />
                <DetailRow label="Working Hours" value={workingHours} />
                {!isMissingCheckout && checkOut !== "--:--" && (
                  <DetailRow label="Break" value={record.breakHours || "01h 00m"} />
                )}
                <DetailRow label="Attendance Type" value={attendanceType || "Office"} />
                {notes && <DetailRow label="Notes" value={notes} />}
              </>
            )}
          </div>
        </div>

        {!isWeekend && (
          <div className="flex flex-col gap-2 border-t border-slate-200 p-5 sm:flex-row">
            {isMissingCheckout ? (
              <Button
                className="flex-1"
                onClick={() => {
                  close();
                  onRegularize(date, checkIn !== "--:--" ? checkIn : undefined);
                }}
              >
                Regularize Attendance
              </Button>
            ) : (
              <Button
                className="flex-1"
                onClick={() => {
                  close();
                  if (isLeave) onViewDetails("leave");
                  else if (isOnDuty) onViewDetails("onduty");
                  else onViewDetails("attendance");
                }}
              >
                {isLeave ? "View Leave" : isOnDuty ? "View Request" : "View Full Details"}
              </Button>
            )}

            {!isLeave && !isOnDuty && !isMissingCheckout && (
              <Button
                variant="secondary"
                className="flex-1"
                onClick={() => {
                  close();
                  onRegularize(date, checkIn !== "--:--" ? checkIn : undefined);
                }}
              >
                Regularize
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
