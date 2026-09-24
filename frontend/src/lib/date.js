export function formatTime(value) {
  if (!value) return "—";
  const date = parse(value);
  if (!date) return "—";
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export function formatDate(value) {
  if (!value) return "—";
  const date = parse(value);
  if (!date) return String(value);
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatDuration(value) {
  if (!value) return "—";

  if (typeof value === "string") {
    const hms = /^(\d+):(\d{2}):(\d{2})(?:\.\d+)?$/.exec(value);

    if (hms) {
      const hours = Number(hms[1]);
      const minutes = Number(hms[2]);
      return `${hours}h ${minutes}m`;
    }

    const djangoDuration = /^(?:(\d+)\s+days?,\s*)?(\d{1,2}):(\d{2}):(\d{2})(?:\.\d+)?$/.exec(value);

    if (djangoDuration) {
      const days = Number(djangoDuration[1] || 0);
      const hours = days * 24 + Number(djangoDuration[2]);
      const minutes = Number(djangoDuration[3]);
      return `${hours}h ${minutes}m`;
    }

    const seconds = Number(value);

    if (Number.isFinite(seconds)) {
      const totalMinutes = Math.floor(seconds / 60);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;

      return `${hours}h ${minutes}m`;
    }
  }

  return "—";
}

export function greeting(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function parse(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}
