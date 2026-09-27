import React, { useState, useEffect } from "react";
import Card from "../common/Card";
import Button from "../common/Button";
import Icon from "../common/Icon";
import { formatTimeDisplay, calculateWorkingHours } from "../../utils/dateUtils";
import { useApp } from "../../context/AppContext";

export type ModalType = "checkin" | "checkout" | "facein" | "faceout";

export default function AttendanceModal({
  modal,
  close,
}: {
  modal: ModalType;
  close: () => void;
}) {
  const { checkIn, checkOut, todayRecord } = useApp();
  const face = modal.startsWith("face");
  const checkout = modal.endsWith("out");
  const [step, setStep] = useState<"ready" | "scanning" | "verified">("ready");
  const [currentTime, setCurrentTime] = useState(() => formatTimeDisplay(new Date()));

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(formatTimeDisplay(new Date()));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Compute duration if checking out
  const workingDuration = checkout && todayRecord?.checkIn && todayRecord.checkIn !== "--:--"
    ? calculateWorkingHours(todayRecord.checkIn, currentTime).formatted
    : "08h 30m";

  const handleConfirm = async () => {
    if (checkout) {
      await checkOut(face ? "face" : "standard");
    } else {
      await checkIn(face ? "face" : "standard");
    }
    close();
  };

  const handleStartScan = () => {
    setStep("scanning");
    setTimeout(() => {
      setStep("verified");
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-4 backdrop-blur-xs">
      <Card className="w-full max-w-md overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <div className="text-base font-bold text-slate-900">
              {face
                ? "Face Verification"
                : checkout
                ? "Check Out Confirmation"
                : "Check In Confirmation"}
            </div>
            <div className="mt-0.5 text-xs text-slate-500">
              {face
                ? "Secure biometric attendance verification"
                : "Confirm today's attendance action"}
            </div>
          </div>
          <Button
            variant="ghost"
            className="px-2 text-slate-400 hover:text-slate-600"
            onClick={close}
            ariaLabel="Close modal"
          >
            <Icon name="close" />
          </Button>
        </div>

        <div className="p-5">
          {face ? (
            <>
              <div className="relative mx-auto mb-4 grid aspect-[4/3] w-full max-w-xs place-items-center overflow-hidden rounded-xl border-2 border-dashed border-indigo-300 bg-slate-100">
                <div
                  className={`face-frame grid size-32 place-items-center rounded-[45%] border-2 transition-colors duration-300 ${
                    step === "verified"
                      ? "border-emerald-500 text-emerald-600 bg-emerald-50/50"
                      : "border-indigo-400 text-indigo-500 bg-indigo-50/30"
                  }`}
                >
                  {step === "verified" ? (
                    <Icon name="check" className="size-12" />
                  ) : (
                    <Icon name="user" className="size-14" />
                  )}
                </div>
                {step === "scanning" && (
                  <div className="scan-line absolute left-10 right-10 h-0.5 bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.8)]" />
                )}
              </div>

              <div className="text-center">
                <div className="text-sm font-bold text-slate-800">
                  {step === "verified"
                    ? "Face verified successfully"
                    : step === "scanning"
                    ? "Verifying biometric face signature…"
                    : "Position your face inside the frame"}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {step === "verified"
                    ? `${checkout ? "Check-out" : "Check-in"} will be recorded at ${currentTime}.`
                    : "Look straight at the camera and ensure lighting is adequate."}
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="rounded-xl bg-slate-50 p-4 border border-slate-200/60">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs font-medium text-slate-500">Current time</div>
                    <div className="mt-1 text-lg font-bold text-slate-900 tracking-tight">
                      {currentTime}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-500">
                      {checkout ? "Working duration" : "Location"}
                    </div>
                    <div className="mt-1 text-sm font-bold text-slate-800">
                      {checkout ? workingDuration : "Office (Gurugram)"}
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-4 text-sm text-slate-600">
                {checkout
                  ? "Are you ready to conclude your workday and submit your hours?"
                  : "Are you ready to mark attendance for today?"}
              </div>
            </>
          )}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-slate-200 p-4 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>

          {face && step !== "verified" ? (
            <Button onClick={handleStartScan} disabled={step === "scanning"}>
              {step === "scanning" ? "Scanning…" : `Scan & Check ${checkout ? "Out" : "In"}`}
            </Button>
          ) : (
            <Button onClick={handleConfirm}>
              {face
                ? `Record Check ${checkout ? "Out" : "In"}`
                : `Confirm Check ${checkout ? "Out" : "In"}`}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
