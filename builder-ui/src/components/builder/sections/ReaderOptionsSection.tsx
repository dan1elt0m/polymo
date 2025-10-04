import React from "react";
import type { ConfigFormState } from "../../../types";
import { ReaderOptionRow } from "../rows/ReaderOptionRow";

const TOGGLE_ID = "reader-options-section";

const MANAGED_PARTITION_OPTION_KEYS = new Set([
  "partition_strategy",
  "partition_param",
  "partition_values",
  "partition_range_start",
  "partition_range_end",
  "partition_range_step",
  "partition_range_kind",
  "partition_value_template",
  "partition_extra_template",
  "partition_endpoints",
]);

const SPECIAL_INCREMENTAL_KEYS = [
  "incremental_state_path",
  "incremental_start_value",
  "incremental_state_key",
  "incremental_memory_state",
] as const;

export interface ReaderOptionsSectionProps {
  readerOptions: Record<string, string>;
  setReaderOptions: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  runtimeOptions: Record<string, string>;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

export const ReaderOptionsSection: React.FC<ReaderOptionsSectionProps> = ({
  readerOptions,
  setReaderOptions,
  runtimeOptions,
  onUpdateState,
}) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const summary = React.useMemo(() => {
    const manual = Object.keys(readerOptions).length;
    const total = Object.keys(runtimeOptions).length;
    const incremental = Math.max(0, total - manual);
    if (!total) return "none";
    return `${manual} manual${incremental > 0 ? ` · ${incremental} incremental` : ""}`;
  }, [readerOptions, runtimeOptions]);

  React.useEffect(() => {
    if (Object.keys(readerOptions).length > 0) {
      setIsOpen(true);
    }
  }, [readerOptions]);

  React.useEffect(() => {
    const keys = Object.keys(readerOptions);
    if (!keys.length) return;
    const hasManaged = keys.some((key) => MANAGED_PARTITION_OPTION_KEYS.has(key));
    if (!hasManaged) return;
    setReaderOptions((current) => {
      const next = { ...current };
      let mutated = false;
      MANAGED_PARTITION_OPTION_KEYS.forEach((key) => {
        if (key in next) {
          delete next[key];
          mutated = true;
        }
      });
      return mutated ? next : current;
    });
  }, [readerOptions, setReaderOptions]);

  React.useEffect(() => {
    const patch: Partial<ConfigFormState> = {};
    let mutated = false;

    setReaderOptions((current) => {
      const next = { ...current };
      SPECIAL_INCREMENTAL_KEYS.forEach((key) => {
        if (next[key] !== undefined) {
          const raw = next[key];
          delete next[key];
          mutated = true;
          if (key === "incremental_state_path") {
            patch.incrementalStatePath = String(raw ?? "");
          } else if (key === "incremental_start_value") {
            patch.incrementalStartValue = String(raw ?? "");
          } else if (key === "incremental_state_key") {
            patch.incrementalStateKey = String(raw ?? "");
          } else if (key === "incremental_memory_state") {
            const normalized = String(raw ?? "").trim().toLowerCase();
            patch.incrementalMemoryEnabled = normalized !== "false";
          }
        }
      });
      return mutated ? next : current;
    });

    if (mutated && Object.keys(patch).length > 0) {
      onUpdateState(patch);
    }
  }, [readerOptions, setReaderOptions, onUpdateState]);

  const handleAddOption = React.useCallback(() => {
    setReaderOptions((prev) => {
      const next = { ...prev };
      let index = 1;
      let key = "option";
      while (key in next) {
        key = `option${index++}`;
      }
      next[key] = "";
      return next;
    });
    setIsOpen(true);
  }, [setReaderOptions]);

  const handleRemoveOption = React.useCallback(
    (key: string) => {
      setReaderOptions((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    },
    [setReaderOptions],
  );

  const handleUpdateOption = React.useCallback(
    (key: string, newKey: string, value: string) => {
      setReaderOptions((prev) => {
        const next = { ...prev };
        delete next[key];
        next[newKey] = value;
        return next;
      });
    },
    [setReaderOptions],
  );

  const manualOptions = Object.entries(readerOptions);

  return (
    <div className="space-y-3">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
        onClick={() => setIsOpen((value) => !value)}
        aria-expanded={isOpen}
        aria-controls={TOGGLE_ID}
      >
        <span className="flex items-center gap-2">
          Spark Reader Options
          <span className="text-xs font-normal text-muted">({summary})</span>
        </span>
        <span className={`transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}>
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
          </svg>
        </span>
      </button>

      {isOpen && (
        <div
          id={TOGGLE_ID}
          className="space-y-4 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
        >
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-12 dark:text-drac-foreground">Reader Options</h4>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#242a33] px-4 py-1.5 text-xs font-medium text-slate-11 dark:text-drac-foreground shadow-sm transition-all duration-200 hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent hover:scale-105 hover:shadow-md dark:hover:shadow-[0_0_8px_rgba(80,250,123,0.15)] hover:bg-blue-3/50 dark:hover:bg-[#273242] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7 dark:focus-visible:ring-drac-accent"
              onClick={handleAddOption}
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
              </svg>
              <span>Add Option</span>
            </button>
          </div>

          {manualOptions.length > 0 ? (
            <ul className="flex flex-col gap-2">
              {manualOptions.map(([key, value]) => (
                <ReaderOptionRow
                  key={key}
                  originalKey={key}
                  value={String(value)}
                  onUpdateKey={handleUpdateOption}
                  onUpdateValue={handleUpdateOption}
                  onRemove={handleRemoveOption}
                />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted dark:text-drac-muted">No reader options configured.</p>
          )}
        </div>
      )}
    </div>
  );
};
