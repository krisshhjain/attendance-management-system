import React, { useEffect } from "react";
import Icon from "./Icon";
import Button from "./Button";

export default function Toast({
  text,
  close,
  duration = 4000,
}: {
  text: string;
  close: () => void;
  duration?: number;
}) {
  useEffect(() => {
    if (!text) return;
    const timer = setTimeout(() => {
      close();
    }, duration);
    return () => clearTimeout(timer);
  }, [text, duration, close]);

  if (!text) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-5 left-4 right-4 z-50 flex min-w-0 items-center gap-3 rounded-xl bg-slate-900 px-4 py-3 text-sm font-medium text-white shadow-xl sm:left-auto sm:right-5 sm:max-w-sm"
    >
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-emerald-500 text-white">
        <Icon name="check" className="size-4" />
      </span>
      <span className="min-w-0 flex-1 break-words">{text}</span>
      <Button
        variant="ghost"
        className="min-h-8 shrink-0 px-1 text-slate-300 hover:bg-slate-800"
        onClick={close}
      >
        <Icon name="close" className="size-4" />
      </Button>
    </div>
  );
}
