import React from "react";
import type { ConfigFormState } from "../../../types";
import { CheckboxRow, Disclosure, Field, INPUT } from "../../ui/primitives";

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
    return parts.length ? parts.join(" · ") : "off";
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
    <Disclosure id={TOGGLE_ID} title="Incremental sync" summary={summary} open={isOpen} onToggle={() => setIsOpen((v) => !v)}>
      <div className="fields-3">
        <Field label="Mode" tooltip="Short label for the incremental strategy (e.g. updated_at, created_at).">
          <input
            type="text"
            className={INPUT}
            placeholder="updated_at"
            value={state.incrementalMode}
            onChange={(event) => onUpdateState({ incrementalMode: event.target.value })}
          />
        </Field>
        <Field label="Cursor parameter" tooltip="Query parameter added to each request (e.g. since, updated_after).">
          <input
            type="text"
            className={INPUT}
            placeholder="since"
            value={state.incrementalCursorParam}
            onChange={(event) => onUpdateState({ incrementalCursorParam: event.target.value })}
          />
        </Field>
        <Field label="Cursor field" tooltip="Field in the response used to compute the next cursor (supports dotted paths).">
          <input
            type="text"
            className={INPUT}
            placeholder="updated_at"
            value={state.incrementalCursorField}
            onChange={(event) => onUpdateState({ incrementalCursorField: event.target.value })}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="State file or URL" tooltip="Location where Polymo stores the latest cursor. Supports local paths and fsspec URLs (s3://, gs://, etc.).">
          <input
            type="text"
            className={INPUT}
            placeholder="/tmp/polymo-state.json or s3://team/state.json"
            value={state.incrementalStatePath}
            onChange={(event) => onUpdateState({ incrementalStatePath: event.target.value })}
          />
        </Field>
        <Field label="Initial cursor value" tooltip="Fallback value used when no state file is present.">
          <input
            type="text"
            className={INPUT}
            placeholder="2024-01-01T00:00:00Z"
            value={state.incrementalStartValue}
            onChange={(event) => onUpdateState({ incrementalStartValue: event.target.value })}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 items-end gap-4">
        <Field label="State key override" tooltip="Optional identifier when sharing a state file across multiple connectors.">
          <input
            type="text"
            className={INPUT}
            placeholder="orders_incremental_sync"
            value={state.incrementalStateKey}
            onChange={(event) => onUpdateState({ incrementalStateKey: event.target.value })}
          />
        </Field>
        <CheckboxRow
          className="pb-2"
          label="Keep cursor in memory"
          description="Faster, but loses state on failure."
          checked={state.incrementalMemoryEnabled}
          onChange={(event) => onUpdateState({ incrementalMemoryEnabled: event.target.checked })}
        />
      </div>
    </Disclosure>
  );
};
