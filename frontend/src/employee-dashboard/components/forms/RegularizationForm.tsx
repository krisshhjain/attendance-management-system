import React, { useState, useEffect } from "react";
import PageHeader from "../common/PageHeader";
import Card from "../common/Card";
import SectionTitle from "../common/SectionTitle";
import Button from "../common/Button";
import Field from "../common/Field";
import Icon from "../common/Icon";
import { useApp } from "../../context/AppContext";
import {
  calculateWorkingHours,
  formatDateDisplay,
  formatToISODate,
} from "../../utils/dateUtils";

function UploadBox({
  fileName,
  onFileSelect,
}: {
  fileName?: string;
  onFileSelect: (name: string) => void;
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-center">
      <Icon name="upload" className="mx-auto mb-2 size-5 text-indigo-600" />
      <div className="text-sm font-semibold text-slate-700">
        {fileName ? `Attached: ${fileName}` : "Upload supporting document"}
      </div>
      <div className="mt-1 text-xs text-slate-500">
        PDF, XLS, DOC or image · Maximum 5MB
      </div>
      <input
        type="file"
        id="reg-upload"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            onFileSelect(file.name);
          }
        }}
      />
      <label
        htmlFor="reg-upload"
        className="mt-3 inline-flex min-h-8 cursor-pointer items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        {fileName ? "Change file" : "Choose file"}
      </label>
    </div>
  );
}

function to24HourTime(timeStr?: string): string {
  if (!timeStr || timeStr === "--:--") return "";
  const match12 = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
  if (match12) {
    let hour = parseInt(match12[1], 10) % 12;
    if (match12[3].toUpperCase() === "PM") hour += 12;
    return `${String(hour).padStart(2, "0")}:${match12[2]}`;
  }
  const match24 = timeStr.match(/(\d{1,2}):(\d{2})/);
  if (match24) {
    return `${String(parseInt(match24[1], 10)).padStart(2, "0")}:${match24[2]}`;
  }
  return "";
}

function to12HourTime(timeStr?: string): string {
  if (!timeStr || timeStr === "--:--") return "--:--";
  const match24 = timeStr.match(/(\d{1,2}):(\d{2})/);
  if (match24) {
    const h = parseInt(match24[1], 10);
    const m = match24[2];
    const ampm = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 || 12;
    return `${String(h12).padStart(2, "0")}:${m} ${ampm}`;
  }
  return timeStr;
}

export default function RegularizationForm({
  initialDate,
  initialCheckIn,
  cancel,
  onSubmitted,
}: {
  initialDate?: string;
  initialCheckIn?: string;
  cancel: () => void;
  onSubmitted: () => void;
}) {
  const { submitRegularization, attendanceRecords } = useApp();
  const defaultDate = initialDate || formatToISODate(new Date());

  const [period, setPeriod] = useState<"Day" | "Week" | "Month">("Day");
  const [selectedDate, setSelectedDate] = useState(defaultDate);
  const [endDate, setEndDate] = useState(defaultDate);
  const [workLocation, setWorkLocation] = useState("Office");

  // Lookup record if exists
  const existingRecord = attendanceRecords[defaultDate];

  const [checkInTime, setCheckInTime] = useState(
    to24HourTime(initialCheckIn || existingRecord?.checkIn) || "09:00"
  );
  const [checkOutTime, setCheckOutTime] = useState(
    to24HourTime(existingRecord?.checkOut) || "17:30"
  );
  const [reason, setReason] = useState("Forgot to Check Out");
  const [description, setDescription] = useState("");
  const [attachment, setAttachment] = useState<string>();
  const [error, setError] = useState<string>();

  // Dynamic calculated total hours
  const [totalHours, setTotalHours] = useState("08h 30m");

  useEffect(() => {
    if (checkInTime && checkOutTime) {
      const calc = calculateWorkingHours(checkInTime, checkOutTime);
      setTotalHours(calc.formatted !== "--:--" ? calc.formatted : "00h 00m");
    } else {
      setTotalHours("00h 00m");
    }
  }, [checkInTime, checkOutTime]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkOutTime || checkOutTime.trim() === "") {
      setError("Check-out time is required.");
      return;
    }

    const dateDisplay = formatDateDisplay(selectedDate);

    await submitRegularization({
      periodType: period,
      date: period === "Day" ? dateDisplay : `${dateDisplay} – ${formatDateDisplay(endDate)}`,
      startDate: selectedDate,
      endDate: period !== "Day" ? endDate : undefined,
      checkIn: to12HourTime(checkInTime),
      checkOut: to12HourTime(checkOutTime),
      totalHours,
      reason,
      description: description || `Regularization request for ${reason}`,
      attachmentName: attachment,
    });

    onSubmitted();
  };

  return (
    <>
      <PageHeader
        title="Request Regularization"
        subtitle="Correct attendance details for the selected work period."
        action={
          <Button variant="secondary" onClick={cancel}>
            Back to requests
          </Button>
        }
      />

      <form onSubmit={handleSubmit}>
        <Card className="overflow-hidden">
          <SectionTitle
            title="Request details"
            subtitle="Select a period and provide the corrected work records"
          />

          <div className="grid gap-4 p-5 md:grid-cols-3">
            <Field
              label="Period"
              value={period}
              onChange={(val) => setPeriod(val as "Day" | "Week" | "Month")}
              options={["Day", "Week", "Month"]}
            />

            <Field
              label={period === "Day" ? "Date" : "Start date"}
              type="date"
              value={selectedDate}
              onChange={setSelectedDate}
              required
            />

            {period === "Day" ? (
              <Field
                label="Work location"
                value={workLocation}
                onChange={setWorkLocation}
                options={["Office", "Work From Home", "Client Site"]}
              />
            ) : (
              <Field
                label="End date"
                type="date"
                value={endDate}
                onChange={setEndDate}
                required
              />
            )}
          </div>

          <div className="px-5 pb-5">
            <div className="mb-1.5 text-xs font-semibold text-slate-700">Attachment</div>
            <UploadBox fileName={attachment} onFileSelect={setAttachment} />
          </div>

          <div className="border-y border-slate-200 bg-slate-50 px-5 py-3">
            <div className="text-sm font-bold text-slate-800">Worked Day Record</div>
            <div className="text-xs text-slate-500">
              Provide the corrected punch times and reason for this date
            </div>
          </div>

          <div className="p-5">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Field
                label="Check-in time"
                type="time"
                value={checkInTime}
                onChange={setCheckInTime}
                required
              />

              <Field
                label="Check-out time"
                type="time"
                value={checkOutTime}
                onChange={(val) => {
                  setCheckOutTime(val);
                  setError(undefined);
                }}
                error={error}
                required
              />

              <label className="block min-w-0">
                <span className="mb-1.5 block text-xs font-semibold text-slate-700">
                  Calculated Hours
                </span>
                <div className="min-h-11 md:min-h-10 flex items-center rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-bold text-indigo-700">
                  {totalHours}
                </div>
              </label>

              <Field
                label="Reason"
                value={reason}
                onChange={setReason}
                options={[
                  "Forgot to Check Out",
                  "Forgot to Check In",
                  "Incorrect Attendance",
                  "Device Issue",
                  "Work Location Issue",
                  "Other",
                ]}
              />
            </div>

            <div className="mt-4">
              <Field
                label="Description"
                type="textarea"
                placeholder="Explain the reason for regularization in detail…"
                value={description}
                onChange={setDescription}
              />
            </div>
          </div>

          <div className="flex flex-col-reverse gap-2 border-t border-slate-200 p-5 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={cancel}>
              Cancel
            </Button>
            <Button type="submit">Submit Request</Button>
          </div>
        </Card>
      </form>
    </>
  );
}
