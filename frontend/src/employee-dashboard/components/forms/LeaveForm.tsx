import React, { useState, useEffect } from "react";
import PageHeader from "../common/PageHeader";
import Card from "../common/Card";
import SectionTitle from "../common/SectionTitle";
import Button from "../common/Button";
import Field from "../common/Field";
import Icon from "../common/Icon";
import { useApp } from "../../context/AppContext";
import { countWorkingDays, formatToISODate } from "../../utils/dateUtils";

export default function LeaveForm({
  cancel,
  onSubmitted,
}: {
  cancel: () => void;
  onSubmitted: () => void;
}) {
  const { leaveBalances, applyLeave } = useApp();

  const today = formatToISODate(new Date());
  const tomorrow = formatToISODate(new Date(Date.now() + 86400000));

  const [leaveType, setLeaveType] = useState(
    leaveBalances[0]?.type || "Casual Leave"
  );
  const [startDate, setStartDate] = useState(tomorrow);
  const [endDate, setEndDate] = useState(tomorrow);
  const [durationDays, setDurationDays] = useState(1);
  const [reason, setReason] = useState("");
  const [attachment, setAttachment] = useState<string>();
  const [error, setError] = useState<string>();

  // Calculate duration whenever dates change
  useEffect(() => {
    if (startDate && endDate) {
      if (startDate > endDate) {
        setError("End date must be after start date.");
        setDurationDays(0);
      } else {
        setError(undefined);
        const days = countWorkingDays(startDate, endDate);
        setDurationDays(days);
      }
    }
  }, [startDate, endDate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (error || durationDays <= 0) return;

    if (!reason || reason.trim() === "") {
      setError("Please provide a reason for your leave.");
      return;
    }

    const durationLabel = `${durationDays} ${durationDays === 1 ? "day" : "days"}`;

    await applyLeave({
      leaveType,
      startDate,
      endDate,
      duration: durationDays,
      durationLabel,
      reason,
      attachmentName: attachment,
    });

    onSubmitted();
  };

  const leaveOptions = leaveBalances.map((b) => b.type);

  return (
    <>
      <PageHeader
        title="Apply for Leave"
        subtitle="Submit your leave dates and supporting details."
        action={
          <Button variant="secondary" onClick={cancel}>
            Back to leave history
          </Button>
        }
      />

      <form onSubmit={handleSubmit}>
        <Card className="overflow-hidden">
          <SectionTitle
            title="Request details"
            subtitle="Fields marked with an asterisk must be completed"
          />

          <div className="grid gap-4 p-5 md:grid-cols-2">
            <Field
              label="Leave Type"
              value={leaveType}
              onChange={setLeaveType}
              options={leaveOptions}
              required
            />

            <label className="block min-w-0">
              <span className="mb-1.5 block text-xs font-semibold text-slate-700">
                Calculated Duration
              </span>
              <div className="min-h-11 md:min-h-10 flex items-center rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-bold text-indigo-700">
                {durationDays} {durationDays === 1 ? "Working Day" : "Working Days"}
              </div>
            </label>

            <Field
              label="Start Date"
              type="date"
              value={startDate}
              min={today}
              onChange={setStartDate}
              required
            />

            <Field
              label="End Date"
              type="date"
              value={endDate}
              min={startDate}
              onChange={setEndDate}
              error={error}
              required
            />

            <div className="md:col-span-2">
              <Field
                label="Reason"
                type="textarea"
                placeholder="Please describe why you are requesting leave…"
                value={reason}
                onChange={(val) => {
                  setReason(val);
                  if (error) setError(undefined);
                }}
                required
              />
            </div>

            <div className="md:col-span-2">
              <div className="mb-1.5 text-xs font-semibold text-slate-700">
                Supporting Document (Optional)
              </div>
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-center">
                <Icon name="upload" className="mx-auto mb-2 size-5 text-indigo-600" />
                <div className="text-sm font-semibold text-slate-700">
                  {attachment ? `Attached: ${attachment}` : "Upload supporting document"}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  Doctor note, certificate or travel tickets (PDF, JPG, PNG)
                </div>
                <input
                  type="file"
                  id="leave-file-input"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setAttachment(f.name);
                  }}
                />
                <label
                  htmlFor="leave-file-input"
                  className="mt-3 inline-flex min-h-8 cursor-pointer items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  {attachment ? "Change file" : "Choose file"}
                </label>
              </div>
            </div>
          </div>

          <div className="flex flex-col-reverse gap-2 border-t border-slate-200 p-5 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={cancel}>
              Cancel
            </Button>
            <Button type="submit">Submit Leave Request</Button>
          </div>
        </Card>
      </form>
    </>
  );
}
