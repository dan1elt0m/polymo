import React from "react";
import { InfoTooltip } from "../../InfoTooltip";
import { InputWithCursorPosition } from "../../InputWithCursorPosition";

export interface ParamRowProps {
  originalKey: string;
  value: string;
  onUpdateKey: (oldKey: string, newKey: string, value: string) => void;
  onUpdateValue: (key: string, newKey: string, value: string) => void;
  onRemove: (key: string) => void;
}

export const ParamRow: React.FC<ParamRowProps> = ({
  originalKey,
  value,
  onUpdateKey,
  onUpdateValue,
  onRemove,
}) => {
  const [tempKey, setTempKey] = React.useState(originalKey);

  React.useEffect(() => {
    setTempKey(originalKey);
  }, [originalKey]);

  const commitIfChanged = React.useCallback(() => {
    if (tempKey && tempKey !== originalKey) {
      onUpdateKey(originalKey, tempKey, value);
    }
  }, [tempKey, originalKey, value, onUpdateKey]);

  return (
    <li className="group relative rounded-xl border border-border/60 dark:border-drac-border/60 bg-background/60 dark:bg-[#262c35] backdrop-blur-sm px-4 py-4 shadow-inner transition-all duration-200 hover:border-blue-7/60 dark:hover:border-drac-accent/60 hover:shadow-sm">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] tracking-wide text-muted dark:text-drac-muted font-medium flex items-center gap-1">
            Name <InfoTooltip text="Parameter key sent with request." />
          </label>
          <InputWithCursorPosition
            type="text"
            className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#303745] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm transition-all focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5 dark:focus-visible:ring-drac-accent/40 group-hover:border-blue-7/50"
            placeholder="param_name"
            value={tempKey}
            onChange={(e) => setTempKey(e.target.value)}
            onBlur={commitIfChanged}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                (e.target as HTMLInputElement).blur();
              }
            }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] tracking-wide text-muted dark:text-drac-muted font-medium flex items-center gap-1">
            Value <InfoTooltip text="Parameter value associated with the key." />
          </label>
          <InputWithCursorPosition
            type="text"
            className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#303745] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm transition-all focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5 dark:focus-visible:ring-drac-accent/40 group-hover:border-blue-7/50"
            placeholder="value"
            value={value}
            onValueChange={(newValue) => onUpdateValue(originalKey, originalKey, newValue)}
          />
        </div>
      </div>
      <button
        type="button"
        className="absolute -right-2 -top-2 inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 dark:border-drac-border bg-background/80 dark:bg-[#2d3541] text-slate-11 dark:text-drac-muted opacity-0 shadow-sm backdrop-blur transition-all duration-200 hover:text-red-10 hover:border-red-7 hover:bg-red-3/60 dark:hover:text-drac-red dark:hover:border-drac-red/80 dark:hover:bg-[#383f4c] group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7"
        onClick={() => onRemove(originalKey)}
        aria-label={`Remove parameter ${originalKey}`}
      >
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
          <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
        </svg>
      </button>
    </li>
  );
};

