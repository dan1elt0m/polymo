import React from "react";
import type { ConfigFormState } from "../../../types";
import { HeaderRow } from "../rows/HeaderRow";

export interface HeadersSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "headers-section";

export const HeadersSection: React.FC<HeadersSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const handleAddHeader = React.useCallback(() => {
    const headers = { ...state.headers };
    let key = "header";
    let index = 1;
    while (headers[key]) {
      key = `header${index++}`;
    }
    headers[key] = "";
    onUpdateState({ headers });
    setIsOpen(true);
  }, [state.headers, onUpdateState]);

  const handleRemoveHeader = React.useCallback(
    (key: string) => {
      const headers = { ...state.headers };
      delete headers[key];
      onUpdateState({ headers });
    },
    [state.headers, onUpdateState],
  );

  const handleUpdateHeader = React.useCallback(
    (key: string, newKey: string, value: string) => {
      const headers = { ...state.headers };
      delete headers[key];
      headers[newKey] = value;
      onUpdateState({ headers });
    },
    [state.headers, onUpdateState],
  );

  const headerCount = Object.keys(state.headers).length;

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
          Headers
          <span className="text-xs font-normal text-muted">({headerCount || "none"})</span>
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
            <h4 className="text-sm font-semibold text-slate-12 dark:text-drac-foreground">Headers</h4>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#242a33] px-4 py-1.5 text-xs font-medium text-slate-11 dark:text-drac-foreground shadow-sm transition-all duration-200 hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent hover:scale-105 hover:shadow-md dark:hover:shadow-[0_0_8px_rgba(80,250,123,0.15)] hover:bg-blue-3/50 dark:hover:bg-[#273242] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7 dark:focus-visible:ring-drac-accent"
              onClick={handleAddHeader}
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
              </svg>
              <span>Add Header</span>
            </button>
          </div>

          {headerCount > 0 ? (
            <ul className="flex flex-col gap-2">
              {Object.entries(state.headers).map(([key, value]) => (
                <HeaderRow
                  key={key}
                  originalKey={key}
                  value={value}
                  onUpdateKey={handleUpdateHeader}
                  onUpdateValue={handleUpdateHeader}
                  onRemove={handleRemoveHeader}
                />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted dark:text-drac-muted">No headers configured.</p>
          )}
        </div>
      )}
    </div>
  );
};

