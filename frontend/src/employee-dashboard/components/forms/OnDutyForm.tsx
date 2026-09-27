import React, { useState } from "react";
import PageHeader from "../common/PageHeader";
import Card from "../common/Card";
import SectionTitle from "../common/SectionTitle";
import Button from "../common/Button";
import Field from "../common/Field";
import Icon from "../common/Icon";
import { useApp } from "../../context/AppContext";
import { formatDateDisplay, formatToISODate } from "../../utils/dateUtils";

export default function OnDutyForm({
  cancel,
  onSubmitted,
}: {
  cancel: () => void;
  onSubmitted: () => void;
}) {
  const { submitOnDuty } = useApp();
  const today = formatToISODate(new Date());

  const [date, setDate] = useState(today);
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("17:00");
  const [location, setLocation] = useState("");
  const [purpose, setPurpose] = useState("");
  const [description, setDescription] = useState("");
  const [attachment, setAttachment] = useState<string>();
  const [error, setError] = useState<string>();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!location.trim() || !purpose.trim()) {
      setError("Location and Purpose are required fields.");
      return;
    }

    // Format start time & end time nicely for display
    const formatTime12 = (t: string) => {
      const [h, m] = t.split(":").map(Number);
      const ampm = h >= 12 ? "PM" : "AM";
      const hour12 = h % 12 || 12;
      return `${String(hour12).padStart(2, "0")}:${String(m).padStart(2, "0")} ${ampm}`;
    };

    const timeRangeStr = `${formatTime12(startTime)} – ${formatTime12(endTime)}`;
    const dateDisplay = formatDateDisplay(date);

    await submitOnDuty({
      date: dateDisplay,
      startDate: date,
      startTime: formatTime12(startTime),
      endTime: formatTime12(endTime),
      location,
      purpose,
      description: description || `${purpose} at ${location}`,
      attachmentName: attachment,
    });

    onSubmitted();
  };

  return (
    <>
      <PageHeader
        title="Request On Duty"
        subtitle="Provide details for official work outside your normal office location."
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
            subtitle="Fields marked as required must be completed"
          />

          <div className="grid gap-4 p-5 md:grid-cols-2">
            <Field
              label="Date"
              type="date"
              value={date}
              onChange={setDate}
              required
            />

            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Start Time"
                type="time"
                value={startTime}
                onChange={setStartTime}
                required
              />
              <Field
                label="End Time"
                type="time"
                value={endTime}
                onChange={setEndTime}
                required
              />
            </div>

            <Field
              label="Location"
              placeholder="e.g. Client office, Cyber City, Gurugram"
              value={location}
              onChange={(val) => {
                setLocation(val);
                if (error) setError(undefined);
              }}
              required
            />

            <Field
              label="Purpose"
              placeholder="e.g. Client Meeting, UX Research, Site Audit"
              value={purpose}
              onChange={(val) => {
                setPurpose(val);
                if (error) setError(undefined);
              }}
              required
            />

            <div className="md:col-span-2">
              <Field
                label="Description"
                type="textarea"
                placeholder="Additional details regarding the official duty visit…"
                value={description}
                onChange={setDescription}
              />
            </div>

            <div className="md:col-span-2">
              <div className="mb-1.5 text-xs font-semibold text-slate-700">
                Supporting Document (Optional)
              </div>
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-center">
                <Icon name="upload" className="mx-auto mb-2 size-5 text-indigo-600" />
                <div className="text-sm font-semibold text-slate-700">
                  {attachment ? `Attached: ${attachment}` : "Upload supporting invitation / approval"}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  Meeting invite, email screenshot or official permit (PDF, JPG, PNG)
                </div>
                <input
                  type="file"
                  id="od-file-input"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setAttachment(f.name);
                  }}
                />
                <label
                  htmlFor="od-file-input"
                  className="mt-3 inline-flex min-h-8 cursor-pointer items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  {attachment ? "Change file" : "Choose file"}
                </label>
              </div>
            </div>

            {error && (
              <div className="md:col-span-2 text-xs font-medium text-rose-600">
                {error}
              </div>
            )}
          </div>

          <div className="flex flex-col-reverse gap-2 border-t border-slate-200 p-5 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={cancel}>
              Cancel
            </Button>
            <Button type="submit">Submit On Duty Request</Button>
          </div>
        </Card>
      </form>
    </>
  );
}
