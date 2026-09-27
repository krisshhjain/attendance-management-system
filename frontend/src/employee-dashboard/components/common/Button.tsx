import { createElement, type ReactNode } from "react";

export interface ButtonProps {
  children: ReactNode;
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit";
  ariaLabel?: string;
}

export default function Button({
  children,
  onClick,
  variant = "primary",
  disabled = false,
  className = "",
  type = "button",
  ariaLabel,
}: ButtonProps) {
  const styles = {
    primary: "bg-indigo-600 font-semibold text-white hover:bg-indigo-700 shadow-sm",
    secondary: "border border-slate-300 bg-white font-medium text-slate-700 hover:bg-slate-50",
    ghost: "font-medium text-slate-600 hover:bg-slate-100",
    danger: "bg-rose-600 font-semibold text-white hover:bg-rose-700",
  };

  return createElement(
    "button",
    {
      type,
      disabled,
      onClick,
      "aria-label": ariaLabel,
      className: `inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-xs transition focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:cursor-not-allowed disabled:opacity-50 md:min-h-10 ${styles[variant]} ${className}`,
    },
    children
  );
}
