import React from "react";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";

export interface PartitioningSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "partitioning-section";

const partitionStrategies: Array<{ value: ConfigFormState["partitionStrategy"]; label: string }> = [
  { value: "none", label: "None" },
  { value: "pagination", label: "Mirror pagination" },
  { value: "param_range", label: "Parameter range" },
  { value: "endpoints", label: "Endpoint list" },
];

export const PartitioningSection: React.FC<PartitioningSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const summary = React.useMemo(() => {
    switch (state.partitionStrategy) {
      case "pagination":
        return "pagination";
      case "param_range": {
        if (state.partitionValues?.trim()) return "values list";
        if (state.partitionRangeStart?.trim() && state.partitionRangeEnd?.trim()) {
          return `${state.partitionRangeKind === "date" ? "date" : "numeric"} range`;
        }
        return "param range";
      }
      case "endpoints":
        return "multiple endpoints";
      default:
        return "none";
    }
  }, [
    state.partitionStrategy,
    state.partitionRangeEnd,
    state.partitionRangeKind,
    state.partitionRangeStart,
    state.partitionValues,
  ]);

  React.useEffect(() => {
    if (state.partitionStrategy !== "none") {
      setIsOpen(true);
    }
  }, [state.partitionStrategy]);

  const isParamRange = state.partitionStrategy === "param_range";
  const isPaginationMirror = state.partitionStrategy === "pagination";
  const isEndpoints = state.partitionStrategy === "endpoints";

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
          Partitioning
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
          <label className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Strategy</span>
              <InfoTooltip text="Split the workload to parallelize extraction. Some strategies rely on pagination or explicit lists." />
            </div>
            <select
              className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none"
              value={state.partitionStrategy}
              onChange={(event) => onUpdateState({ partitionStrategy: event.target.value as ConfigFormState["partitionStrategy"] })}
            >
              {partitionStrategies.map((strategy) => (
                <option key={strategy.value} value={strategy.value}>
                  {strategy.label}
                </option>
              ))}
            </select>
          </label>

          {isPaginationMirror && (
            <p className="text-xs text-muted dark:text-drac-muted">
              Mirrors the pagination cursor to create Spark partitions. Works best with page or offset pagination.
            </p>
          )}

          {isParamRange && (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Partition parameter</span>
                    <InfoTooltip text="Query parameter that receives each partition value." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="start_date"
                    value={state.partitionParam || ""}
                    onChange={(event) => onUpdateState({ partitionParam: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Kind</span>
                    <InfoTooltip text="Use numeric ranges for integers, or date ranges for ISO dates." />
                  </div>
                  <select
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none"
                    value={state.partitionRangeKind || "numeric"}
                    onChange={(event) => onUpdateState({ partitionRangeKind: event.target.value as ConfigFormState["partitionRangeKind"] })}
                  >
                    <option value="numeric">Numeric</option>
                    <option value="date">Date</option>
                  </select>
                </label>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Values list</span>
                    <InfoTooltip text="Comma-separated values or JSON array. Overrides range fields when present." />
                  </div>
                  <textarea
                    className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
                    rows={3}
                    placeholder="2024-01-01, 2024-01-02, 2024-01-03"
                    value={state.partitionValues || ""}
                    onChange={(event) => onUpdateState({ partitionValues: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Range start</span>
                    <InfoTooltip text="Inclusive start of the generated range." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder={state.partitionRangeKind === "date" ? "2024-01-01" : "0"}
                    value={state.partitionRangeStart || ""}
                    onChange={(event) => onUpdateState({ partitionRangeStart: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Range end</span>
                    <InfoTooltip text="Inclusive end of the generated range." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder={state.partitionRangeKind === "date" ? "2024-01-31" : "100"}
                    value={state.partitionRangeEnd || ""}
                    onChange={(event) => onUpdateState({ partitionRangeEnd: event.target.value })}
                  />
                </label>
              </div>

              <label className="flex flex-col gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Range step</span>
                  <InfoTooltip text="Step between generated values. For dates, use ISO 8601 duration (e.g. P1D)." />
                </div>
                <input
                  type="text"
                  className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                  placeholder={state.partitionRangeKind === "date" ? "P1D" : "10"}
                  value={state.partitionRangeStep || ""}
                  onChange={(event) => onUpdateState({ partitionRangeStep: event.target.value })}
                />
              </label>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Value template</span>
                    <InfoTooltip text="Template applied to each generated value (use {{ value }} placeholder)." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="{{ value }}"
                    value={state.partitionValueTemplate || ""}
                    onChange={(event) => onUpdateState({ partitionValueTemplate: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Extra parameters template</span>
                    <InfoTooltip text="JSON object merged into query params for each partition." />
                  </div>
                  <textarea
                    className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
                    rows={3}
                    placeholder='{"until": "{{ value }}"}'
                    value={state.partitionExtraTemplate || ""}
                    onChange={(event) => onUpdateState({ partitionExtraTemplate: event.target.value })}
                  />
                </label>
              </div>

              <p className="text-xs text-muted dark:text-drac-muted">
                Provide either explicit values or a start/end range. Templates are optional.
              </p>
            </div>
          )}

          {isEndpoints && (
            <div className="space-y-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Endpoint definitions</span>
                <InfoTooltip text="Accepted formats: comma-separated list (users:/users,posts:/posts,/status) or JSON array when using Spark reader options. Name is optional; if omitted the path is used as the name. When using this strategy the stream 'path' field may be omitted." />
              </div>
              <textarea
                className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
                rows={4}
                placeholder="users:/users,posts:/posts,/status"
                value={state.partitionEndpoints || ""}
                onChange={(event) => onUpdateState({ partitionEndpoints: event.target.value })}
              />
              <p className="text-xs text-muted dark:text-drac-muted">
                Each partition surfaces an <code>endpoint_name</code> column. Use a broad schema (e.g. endpoint_name STRING, data STRING) for heterogeneous payloads.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
