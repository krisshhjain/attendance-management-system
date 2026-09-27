import React from "react";
import { useApp } from "../../context/AppContext";

export default function Avatar({
  large = false,
  customName,
}: {
  large?: boolean;
  customName?: string;
}) {
  const { user } = useApp();
  const nameToUse = customName || user.name || "User";

  const initials = nameToUse
    .trim()
    .split(/\s+/)
    .map((part) => part[0]?.toUpperCase() || "")
    .slice(0, 2)
    .join("") || "U";

  return (
    <div
      className={`grid shrink-0 place-items-center rounded-full bg-indigo-100 font-bold text-indigo-700 select-none ${
        large ? "size-20 text-xl" : "size-9 text-sm"
      }`}
      aria-label={nameToUse}
    >
      {initials}
    </div>
  );
}
