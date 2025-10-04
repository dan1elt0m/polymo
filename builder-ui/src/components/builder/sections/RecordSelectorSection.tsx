import React from "react";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";
import { InputWithCursorPosition } from "../../InputWithCursorPosition";

export interface RecordSelectorSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "record-selector-section";

export const RecordSelectorSection: React.FC<RecordSelectorSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  React.useEffect(() => {
    if ((state.recordFieldPath?.length ?? 0) > 0 || state.recordFilter.trim() || state.castToSchemaTypes) {
      setIsOpen(true);
    }
  }, [state.recordFieldPath, state.recordFilter, state.castToSchemaTypes]);

  const handleAddSegment = React.useCallback(() => {
    const next = [...(state.recordFieldPath || []), ""];
    onUpdateState({ recordFieldPath: next });
    setIsOpen(true);
  }, [state.recordFieldPath, onUpdateState]);

  const handleUpdateSegment = React.useCallback(
    (index: number, value: string) => {
      const current = state.recordFieldPath || [];
      const next = current.map((segment, idx) => (idx === index ? value : segment));
      onUpdateState({ recordFieldPath: next });
    },
    [state.recordFieldPath, onUpdateState],
  );

  const handleRemoveSegment = React.useCallback(
    (index: number) => {
      const current = state.recordFieldPath || [];
      const next = current.filter((_, idx) => idx !== index);
      onUpdateState({ recordFieldPath: next });
    },
    [state.recordFieldPath, onUpdateState],
  );

  const segments = state.recordFieldPath || [];

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
          Record Selector
          <span className="text-xs font-normal text-muted">({segments.length ? `${segments.length} path segments` : "optional"})</span>
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
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-slate-12 dark:text-drac-foreground">Record path</h4>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#242a33] px-4 py-1.5 text-xs font-medium text-slate-11 dark:text-drac-foreground shadow-sm transition-all duration-200 hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent hover:scale-105 hover:shadow-md dark:hover:shadow-[0_0_8px_rgba(80,250,123,0.15)] hover:bg-blue-3/50 dark:hover:bg-[#273242] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7 dark:focus-visible:ring-drac-accent"
                onClick={handleAddSegment}
              >
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                  <path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
                </svg>
                <span>Add segment</span>
              </button>
            </div>

            {segments.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {segments.map((segment, index) => (
                  <li key={`record-path-${index}`} className="group relative">
                    <div className="flex items-center gap-2">
                      <InputWithCursorPosition
                        className="flex-1 rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5"
                        placeholder={index === 0 ? "data" : "items"}
                        value={segment}
                        onValueChange={(value) => handleUpdateSegment(index, value)}
                      />
                      <button
                        type="button"
                        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#2d3541] text-slate-11 dark:text-drac-muted opacity-0 shadow-sm transition-all duration-200 group-hover:opacity-100 hover:border-red-7 hover:text-red-9 hover:bg-red-3/40 dark:hover:border-drac-red/80 dark:hover:text-drac-red dark:hover:bg-[#3a3f4b]"
                        onClick={() => handleRemoveSegment(index)}
                        aria-label={`Remove segment ${index + 1}`}
                      >
                        <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                          <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                        </svg>
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted dark:text-drac-muted">No selector path configured.</p>
            )}
          </div>

          <label className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Record filter (optional)</span>
              <InfoTooltip text="Provide a Python expression evaluated against each record (access the payload via record)." />
            </div>
            <textarea
              className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
              rows={3}
              placeholder="record.get('status') == 'active'"
              value={state.recordFilter}
              onChange={(event) => onUpdateState({ recordFilter: event.target.value })}
            />
          </label>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border text-blue-7 focus:ring-blue-5"
              checked={state.castToSchemaTypes}
              onChange={(event) => onUpdateState({ castToSchemaTypes: event.target.checked })}
            />
            <span className="text-sm text-slate-11 dark:text-drac-foreground/90">Cast values to schema types</span>
          </label>
        </div>
      )}
    </div>
  );
};
