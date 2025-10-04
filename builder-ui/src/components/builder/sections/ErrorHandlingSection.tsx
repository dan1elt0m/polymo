import React from "react";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";
import { DEFAULT_ERROR_HANDLER } from "../../../lib/initial-data";

export interface ErrorHandlingSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "error-handler-section";

export const ErrorHandlingSection: React.FC<ErrorHandlingSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const summary = React.useMemo(() => {
    const retries = state.errorHandlerMaxRetries.trim() || String(DEFAULT_ERROR_HANDLER.max_retries);
    const statuses = (state.errorHandlerRetryStatuses || [])
      .map((status) => status.trim())
      .filter((status) => status.length > 0);
    const multiplier = state.errorHandlerBackoffMultiplier.trim() || String(DEFAULT_ERROR_HANDLER.backoff.multiplier);
    return [
      `${retries} retries`,
      `statuses: ${statuses.length ? statuses.join(", ") : "none"}`,
      `backoff ×${multiplier}`,
    ].join(" · ");
  }, [
    state.errorHandlerBackoffMultiplier,
    state.errorHandlerMaxRetries,
    state.errorHandlerRetryStatuses,
  ]);

  React.useEffect(() => {
    const defaultStatuses = DEFAULT_ERROR_HANDLER.retry_statuses.map((status) => status.toUpperCase());
    const currentStatuses = (state.errorHandlerRetryStatuses || [])
      .map((status) => status.trim().toUpperCase())
      .filter((status) => status.length > 0);
    const statusesMatch =
      currentStatuses.length === defaultStatuses.length &&
      currentStatuses.every((status, index) => status === defaultStatuses[index]);
    const matchesDefaults =
      state.errorHandlerMaxRetries.trim() === String(DEFAULT_ERROR_HANDLER.max_retries) &&
      statusesMatch &&
      state.errorHandlerInitialDelaySeconds.trim() === String(DEFAULT_ERROR_HANDLER.backoff.initial_delay_seconds) &&
      state.errorHandlerMaxDelaySeconds.trim() === String(DEFAULT_ERROR_HANDLER.backoff.max_delay_seconds) &&
      state.errorHandlerBackoffMultiplier.trim() === String(DEFAULT_ERROR_HANDLER.backoff.multiplier) &&
      state.errorHandlerRetryOnTimeout === DEFAULT_ERROR_HANDLER.retry_on_timeout &&
      state.errorHandlerRetryOnConnectionErrors === DEFAULT_ERROR_HANDLER.retry_on_connection_errors;
    if (!matchesDefaults) {
      setIsOpen(true);
    }
  }, [
    state.errorHandlerBackoffMultiplier,
    state.errorHandlerInitialDelaySeconds,
    state.errorHandlerMaxDelaySeconds,
    state.errorHandlerMaxRetries,
    state.errorHandlerRetryOnConnectionErrors,
    state.errorHandlerRetryOnTimeout,
    state.errorHandlerRetryStatuses,
  ]);

  const handleAddRetryStatus = React.useCallback(() => {
    const next = [...(state.errorHandlerRetryStatuses || []), ""];
    onUpdateState({ errorHandlerRetryStatuses: next });
  }, [state.errorHandlerRetryStatuses, onUpdateState]);

  const handleUpdateRetryStatus = React.useCallback(
    (index: number, value: string) => {
      const current = [...(state.errorHandlerRetryStatuses || [])];
      current[index] = value;
      onUpdateState({ errorHandlerRetryStatuses: current });
    },
    [state.errorHandlerRetryStatuses, onUpdateState],
  );

  const handleRemoveRetryStatus = React.useCallback(
    (index: number) => {
      const current = state.errorHandlerRetryStatuses || [];
      const next = current.filter((_, idx) => idx !== index);
      onUpdateState({ errorHandlerRetryStatuses: next });
    },
    [state.errorHandlerRetryStatuses, onUpdateState],
  );

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
          Error handling
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
          className="space-y-6 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
        >
          <div className="grid gap-5 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Max retries</span>
                <InfoTooltip text="Number of times a request is retried after the first attempt." />
              </div>
              <input
                type="number"
                min={0}
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                value={state.errorHandlerMaxRetries}
                onChange={(event) => onUpdateState({ errorHandlerMaxRetries: event.target.value })}
              />
            </label>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Retry status codes</span>
                <InfoTooltip text="HTTP codes or patterns (e.g. 429, 5XX) that should be retried." />
              </div>
              {(state.errorHandlerRetryStatuses || []).length > 0 ? (
                <ul className="flex flex-col gap-2">
                  {state.errorHandlerRetryStatuses.map((status, index) => (
                    <li key={`retry-status-${index}`} className="flex items-center gap-2">
                      <input
                        type="text"
                        className="flex-1 rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
                        placeholder="5XX"
                        value={status}
                        onChange={(event) => handleUpdateRetryStatus(index, event.target.value)}
                      />
                      <button
                        type="button"
                        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#2d3541] text-slate-11 dark:text-drac-muted hover:border-red-7 hover:text-red-9 hover:bg-red-3/40 dark:hover:border-drac-red/80 dark:hover:text-drac-red dark:hover:bg-[#3a3f4b] transition"
                        onClick={() => handleRemoveRetryStatus(index)}
                        aria-label={`Remove retry status ${status || index + 1}`}
                      >
                        <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                          <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted dark:text-drac-muted">No overrides configured. Defaults to retrying 5XX and 429 responses.</p>
              )}
              <button
                type="button"
                className="inline-flex w-fit items-center gap-2 rounded-md border border-border bg-background/70 dark:bg-[#272d38] px-3 py-1.5 text-xs font-medium text-blue-11 hover:bg-blue-3/40 dark:border-drac-border dark:text-drac-accent dark:hover:bg-[#283546] transition"
                onClick={handleAddRetryStatus}
              >
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
                  <path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
                </svg>
                <span>Add status</span>
              </button>
            </div>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Initial delay (s)</span>
                <InfoTooltip text="Delay before the first retry attempt." />
              </div>
              <input
                type="number"
                min={0}
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                value={state.errorHandlerInitialDelaySeconds}
                onChange={(event) => onUpdateState({ errorHandlerInitialDelaySeconds: event.target.value })}
              />
            </label>
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Max delay (s)</span>
                <InfoTooltip text="Upper bound for exponential backoff. Use 0 to disable the cap." />
              </div>
              <input
                type="number"
                min={0}
                step="0.1"
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                value={state.errorHandlerMaxDelaySeconds}
                onChange={(event) => onUpdateState({ errorHandlerMaxDelaySeconds: event.target.value })}
              />
            </label>
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Backoff multiplier</span>
                <InfoTooltip text="Factor by which delay increases between retries." />
              </div>
              <input
                type="number"
                min={1}
                step="0.1"
                className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                value={state.errorHandlerBackoffMultiplier}
                onChange={(event) => onUpdateState({ errorHandlerBackoffMultiplier: event.target.value })}
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-blue-7 focus:ring-blue-5"
                checked={state.errorHandlerRetryOnTimeout}
                onChange={(event) => onUpdateState({ errorHandlerRetryOnTimeout: event.target.checked })}
              />
              <span className="text-sm text-slate-11 dark:text-drac-foreground/90">Retry on request timeouts</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-blue-7 focus:ring-blue-5"
                checked={state.errorHandlerRetryOnConnectionErrors}
                onChange={(event) => onUpdateState({ errorHandlerRetryOnConnectionErrors: event.target.checked })}
              />
              <span className="text-sm text-slate-11 dark:text-drac-foreground/90">Retry on connection errors</span>
            </label>
          </div>
        </div>
      )}
    </div>
  );
};

