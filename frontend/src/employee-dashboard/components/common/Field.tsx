import React, { type ChangeEvent } from "react";

export interface FieldProps {
  label: string;
  type?: string;
  value?: string | number;
  onChange?: (value: string) => void;
  placeholder?: string;
  options?: string[];
  error?: string;
  disabled?: boolean;
  required?: boolean;
  min?: string;
  max?: string;
  className?: string;
}

export default function Field({
  label,
  type = "text",
  value = "",
  onChange,
  placeholder,
  options,
  error,
  disabled = false,
  required = false,
  min,
  max,
  className = "",
}: FieldProps) {
  const shared = `min-h-11 w-full min-w-0 rounded-lg border bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50 disabled:text-slate-400 md:min-h-10 ${
    error ? "border-rose-400" : "border-slate-300"
  } ${className}`;

  return (
    <label className="block min-w-0">
      {label && (
        <span className="mb-1.5 block text-xs font-semibold text-slate-700">
          {label} {required && <span className="text-rose-500">*</span>}
        </span>
      )}
      {options ? (
        <select
          value={value}
          disabled={disabled}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange?.(event.target.value)}
          className={shared}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ) : type === "textarea" ? (
        <textarea
          value={value}
          disabled={disabled}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange?.(event.target.value)}
          placeholder={placeholder}
          rows={3}
          className={`${shared} py-2`}
        />
      ) : (
        <input
          type={type}
          value={value}
          disabled={disabled}
          min={min}
          max={max}
          onChange={(event: ChangeEvent<HTMLInputElement>) => onChange?.(event.target.value)}
          placeholder={placeholder}
          className={shared}
        />
      )}
      {error && <span className="mt-1 block text-xs font-medium text-rose-600">{error}</span>}
    </label>
  );
}
