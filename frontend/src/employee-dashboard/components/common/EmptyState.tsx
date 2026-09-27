import React from "react";
import Card from "./Card";
import Icon from "./Icon";
import type { IconName } from "../../types";

export default function EmptyState({
  title,
  text,
  icon = "bell",
}: {
  title: string;
  text: string;
  icon?: IconName;
}) {
  return (
    <Card className="p-10 text-center">
      <div className="mx-auto mb-3 grid size-12 place-items-center rounded-full bg-slate-100 text-slate-400">
        <Icon name={icon} className="size-6" />
      </div>
      <div className="text-sm font-bold text-slate-800">{title}</div>
      <div className="mt-1 text-xs text-slate-500">{text}</div>
    </Card>
  );
}
