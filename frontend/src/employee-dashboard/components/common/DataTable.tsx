import React, { type ReactNode } from "react";
import Button from "./Button";

export default function DataTable({
  headers,
  rows,
  actions,
  onActionClick,
  actionLabel = "View",
  emptyMessage = "No records found.",
}: {
  headers: string[];
  rows: ReactNode[][];
  actions?: boolean;
  onActionClick?: (rowIndex: number) => void;
  actionLabel?: string;
  emptyMessage?: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-slate-500">
        {emptyMessage}
      </div>
    );
  }

  return (
    <>
      {/* Desktop Table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-max text-left text-xs">
          <thead className="type-caption bg-slate-50 font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              {headers.map((header) => (
                <th key={header} className="px-5 py-3">
                  {header}
                </th>
              ))}
              {actions && <th className="px-5 py-3 text-right">Action</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row, index) => (
              <tr key={index} className="text-slate-600 hover:bg-slate-50/70 transition">
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="px-5 py-3.5">
                    {cell}
                  </td>
                ))}
                {actions && (
                  <td className="px-5 py-3.5 text-right">
                    <Button
                      variant="ghost"
                      className="min-h-8 px-2 text-indigo-600 hover:text-indigo-700"
                      onClick={() => onActionClick?.(index)}
                    >
                      {actionLabel}
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card Layout */}
      <div className="divide-y divide-slate-100 md:hidden">
        {rows.map((row, rowIndex) => (
          <div key={rowIndex} className="w-full min-w-0 p-4">
            <div className="grid min-w-0 grid-cols-2 gap-x-4 gap-y-3">
              {row.map((cell, cellIndex) => (
                <div
                  key={cellIndex}
                  className={`min-w-0 ${
                    cellIndex === 0 ? "col-span-2 border-b border-slate-100 pb-2" : ""
                  }`}
                >
                  <div className="type-caption mb-1 font-semibold uppercase tracking-wide text-slate-400">
                    {headers[cellIndex]}
                  </div>
                  <div className="min-w-0 break-words text-xs text-slate-700">{cell}</div>
                </div>
              ))}
            </div>
            {actions && (
              <Button
                variant="secondary"
                className="mt-3 w-full"
                onClick={() => onActionClick?.(rowIndex)}
              >
                {actionLabel} Details
              </Button>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
