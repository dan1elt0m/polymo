import React from "react";
import type { ConfigFormState } from "../../../types";
import { DEFAULT_ERROR_HANDLER } from "../../../lib/initial-data";
import { BTN_LINK, CheckboxRow, Disclosure, Field, ICON_BTN, INPUT, PlusIcon, XIcon, cx } from "../../ui/primitives";

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
      statuses.length ? statuses.join(", ") : "no statuses",
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

  const statuses = state.errorHandlerRetryStatuses || [];

  return (
    <Disclosure id={TOGGLE_ID} title="Error handling" summary={summary} open={isOpen} onToggle={() => setIsOpen((v) => !v)}>
      <div className="fields-4">
        <Field label="Max retries" tooltip="Number of times a request is retried after the first attempt.">
          <input
            type="number"
            min={0}
            className={INPUT}
            value={state.errorHandlerMaxRetries}
            onChange={(event) => onUpdateState({ errorHandlerMaxRetries: event.target.value })}
          />
        </Field>
        <Field label="Initial delay (s)" tooltip="Delay before the first retry attempt.">
          <input
            type="number"
            min={0}
            className={INPUT}
            value={state.errorHandlerInitialDelaySeconds}
            onChange={(event) => onUpdateState({ errorHandlerInitialDelaySeconds: event.target.value })}
          />
        </Field>
        <Field label="Max delay (s)" tooltip="Upper bound for exponential backoff. Use 0 to disable the cap.">
          <input
            type="number"
            min={0}
            step="0.1"
            className={INPUT}
            value={state.errorHandlerMaxDelaySeconds}
            onChange={(event) => onUpdateState({ errorHandlerMaxDelaySeconds: event.target.value })}
          />
        </Field>
        <Field label="Backoff ×" tooltip="Factor by which delay increases between retries.">
          <input
            type="number"
            min={1}
            step="0.1"
            className={INPUT}
            value={state.errorHandlerBackoffMultiplier}
            onChange={(event) => onUpdateState({ errorHandlerBackoffMultiplier: event.target.value })}
          />
        </Field>
      </div>

      <Field as="div" label="Retry status codes" tooltip="HTTP codes or patterns (e.g. 429, 5XX) that should be retried.">
        {statuses.length > 0 ? (
          <ul className="flex flex-wrap gap-2">
            {statuses.map((status, index) => (
              <li key={`retry-status-${index}`} className="flex items-center gap-1">
                <input
                  type="text"
                  className={cx(INPUT, "max-w-[5.5rem] font-mono text-xs uppercase")}
                  placeholder="5XX"
                  value={status}
                  onChange={(event) => handleUpdateRetryStatus(index, event.target.value)}
                  aria-label={`Retry status ${index + 1}`}
                />
                <button
                  type="button"
                  className={ICON_BTN}
                  onClick={() => handleRemoveRetryStatus(index)}
                  aria-label={`Remove retry status ${status || index + 1}`}
                >
                  <XIcon />
                </button>
              </li>
            ))}
            <li className="flex items-center">
              <button type="button" className={BTN_LINK} onClick={handleAddRetryStatus}>
                <PlusIcon /> Add status
              </button>
            </li>
          </ul>
        ) : (
          <div className="flex items-center gap-3 text-xs text-fg-muted">
            <span>None — defaults to retrying 5XX and 429.</span>
            <button type="button" className={BTN_LINK} onClick={handleAddRetryStatus}>
              <PlusIcon /> Add status
            </button>
          </div>
        )}
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <CheckboxRow
          label="Retry on request timeouts"
          checked={state.errorHandlerRetryOnTimeout}
          onChange={(event) => onUpdateState({ errorHandlerRetryOnTimeout: event.target.checked })}
        />
        <CheckboxRow
          label="Retry on connection errors"
          checked={state.errorHandlerRetryOnConnectionErrors}
          onChange={(event) => onUpdateState({ errorHandlerRetryOnConnectionErrors: event.target.checked })}
        />
      </div>
    </Disclosure>
  );
};
