import React from "react";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";

export interface IncrementalSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "incremental-section";

export const IncrementalSection: React.FC<IncrementalSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const autoOpenRef = React.useRef(false);

  const summary = React.useMemo(() => {
    const parts: string[] = [];
    if (state.incrementalMode.trim()) parts.push(state.incrementalMode.trim());
    if (state.incrementalCursorParam.trim()) parts.push(`param ${state.incrementalCursorParam.trim()}`);
    if (state.incrementalCursorField.trim()) parts.push(`field ${state.incrementalCursorField.trim()}`);
    if (state.incrementalStatePath.trim()) parts.push("state path set");
    if (state.incrementalStartValue.trim()) parts.push("start value");
    if (state.incrementalStateKey.trim()) parts.push("state key");
    if (!state.incrementalMemoryEnabled) parts.push("memory off");
    return parts.length ? parts.join(" · ") : "optional";
  }, [
    state.incrementalCursorField,
    state.incrementalCursorParam,
    state.incrementalMode,
    state.incrementalStateKey,
    state.incrementalStatePath,
    state.incrementalStartValue,
    state.incrementalMemoryEnabled,
  ]);

  React.useEffect(() => {
    const hasValues = Boolean(
      state.incrementalMode.trim() ||
      state.incrementalCursorParam.trim() ||
      state.incrementalCursorField.trim() ||
      state.incrementalStatePath.trim() ||
      state.incrementalStartValue.trim() ||
      state.incrementalStateKey.trim() ||
      !state.incrementalMemoryEnabled,
    );

    if (hasValues && !isOpen && !autoOpenRef.current) {
      setIsOpen(true);
      autoOpenRef.current = true;
    }

    if (!hasValues) {
      autoOpenRef.current = false;
    }
  }, [
    isOpen,
    state.incrementalCursorField,
    state.incrementalCursorParam,
    state.incrementalMode,
    state.incrementalStateKey,
    state.incrementalStatePath,
    state.incrementalStartValue,
    state.incrementalMemoryEnabled,
  ]);

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
          Incremental Sync
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
          <div className="grid gap-4 md:grid-cols-3">
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Mode</span>
                <InfoTooltip text="Short label for the incremental strategy (e.g. updated_at, created_at)." />
              </div>
              <input
                type="text"
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
                placeholder="updated_at"
                value={state.incrementalMode}
                onChange={(event) => onUpdateState({ incrementalMode: event.target.value })}
              />
            </label>
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor parameter</span>
                <InfoTooltip text="Query parameter added to each request (e.g. since, updated_after)." />
              </div>
              <input
                type="text"
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
                placeholder="since"
                value={state.incrementalCursorParam}
                onChange={(event) => onUpdateState({ incrementalCursorParam: event.target.value })}
              />
            </label>
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor field</span>
                <InfoTooltip text="Field in the response used to compute the next cursor (supports dotted paths)." />
              </div>
              <input
                type="text"
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
                placeholder="updated_at"
                value={state.incrementalCursorField}
                onChange={(event) => onUpdateState({ incrementalCursorField: event.target.value })}
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">State file or URL</span>
                <InfoTooltip text="Location where Polymo stores the latest cursor. Supports local paths and fsspec URLs (s3://, gs://, etc.)." />
              </div>
              <input
                type="text"
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                placeholder="/tmp/polymo-state.json or s3://team/state.json"
                value={state.incrementalStatePath}
                onChange={(event) => onUpdateState({ incrementalStatePath: event.target.value })}
              />
            </label>
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Initial cursor value</span>
                <InfoTooltip text="Fallback value used when no state file is present." />
              </div>
              <input
                type="text"
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                placeholder="2024-01-01T00:00:00Z"
                value={state.incrementalStartValue}
                onChange={(event) => onUpdateState({ incrementalStartValue: event.target.value })}
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">State key override</span>
                <InfoTooltip text="Optional identifier when sharing a state file across multiple connectors." />
              </div>
              <input
                type="text"
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                placeholder="orders_incremental_sync"
                value={state.incrementalStateKey}
                onChange={(event) => onUpdateState({ incrementalStateKey: event.target.value })}
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-blue-7 focus:ring-blue-5"
                checked={state.incrementalMemoryEnabled}
                onChange={(event) => onUpdateState({ incrementalMemoryEnabled: event.target.checked })}
              />
              <span className="text-sm text-slate-11 dark:text-drac-foreground/90">Keep cursor in memory (faster but loses state on failure)</span>
            </label>
          </div>
        </div>
      )}
    </div>
  );
};
