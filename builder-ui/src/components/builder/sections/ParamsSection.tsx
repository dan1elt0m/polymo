import React from "react";
import { ParamRow } from "../rows/ParamRow";

export interface ParamsSectionProps {
  params: Record<string, string>;
  onAddParam: () => void;
  onRemoveParam: (key: string) => void;
  onUpdateParam: (key: string, newKey: string, value: string) => void;
}

const TOGGLE_ID = "params-section";

export const ParamsSection: React.FC<ParamsSectionProps> = ({ params, onAddParam, onRemoveParam, onUpdateParam }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const paramCount = Object.keys(params).length;

  const handleAdd = React.useCallback(() => {
    onAddParam();
    setIsOpen(true);
  }, [onAddParam]);

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
          Query Parameters
          <span className="text-xs font-normal text-muted">({paramCount || "none"})</span>
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
            <h4 className="text-sm font-semibold text-slate-12 dark:text-drac-foreground">Parameters</h4>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#242a33] px-4 py-1.5 text-xs font-medium text-slate-11 dark:text-drac-foreground shadow-sm transition-all duration-200 hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent hover:scale-105 hover:shadow-md dark:hover:shadow-[0_0_8px_rgba(80,250,123,0.15)] hover:bg-blue-3/50 dark:hover:bg-[#273242] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7 dark:focus-visible:ring-drac-accent"
              onClick={handleAdd}
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
              </svg>
              <span>Add</span>
            </button>
          </div>

          {paramCount > 0 ? (
            <ul className="flex flex-col gap-2">
              {Object.entries(params).map(([key, value]) => (
                <ParamRow
                  key={key}
                  originalKey={key}
                  value={value}
                  onUpdateKey={onUpdateParam}
                  onUpdateValue={onUpdateParam}
                  onRemove={onRemoveParam}
                />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted dark:text-drac-muted">No parameters configured.</p>
          )}
        </div>
      )}
    </div>
  );
};

