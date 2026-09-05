import React from "react";
import type { ConfigFormState } from "../../../types";
import { Disclosure, Field, INPUT } from "../../ui/primitives";

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
    return parts.length ? parts.join(" · ") : "off";
  }, [
    state.incrementalCursorField,
    state.incrementalCursorParam,
    state.incrementalMode,
    state.incrementalStateKey,
    state.incrementalStatePath,
    state.incrementalStartValue,
  ]);

  React.useEffect(() => {
    const hasValues = Boolean(
      state.incrementalMode.trim() ||
      state.incrementalCursorParam.trim() ||
      state.incrementalCursorField.trim() ||
      state.incrementalStatePath.trim() ||
      state.incrementalStartValue.trim() ||
      state.incrementalStateKey.trim(),
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
  ]);

  return (
    <Disclosure id={TOGGLE_ID} title="Incremental sync" summary={summary} open={isOpen} onToggle={() => setIsOpen((v) => !v)}>
      <div className="fields-3">
        <Field label="Mode" tooltip="Free-text label for the incremental strategy (e.g. updated_at, created_at); stored alongside the cursor in the state file.">
          <input
            type="text"
            className={INPUT}
            placeholder="updated_at"
            value={state.incrementalMode}
            onChange={(event) => onUpdateState({ incrementalMode: event.target.value })}
          />
        </Field>
        <Field label="Cursor parameter" tooltip="Query parameter the stored cursor is sent as on every request (e.g. since, updated_after). An explicit query parameter with the same name wins.">
          <input
            type="text"
            className={INPUT}
            placeholder="since"
            value={state.incrementalCursorParam}
            onChange={(event) => onUpdateState({ incrementalCursorParam: event.target.value })}
          />
        </Field>
        <Field label="Cursor field" tooltip="Response field whose highest value becomes the next cursor (supports dotted paths). Incremental sync is on once both the parameter and this field are set.">
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
        <Field
          label="State file or URL"
          tooltip="Where the generated script keeps the cursor between runs: a local path (a Databricks Volume works) or an fsspec URL such as s3://, gs:// or abfss://. Defaults to <stream>_state.json next to the script."
        >
          <input
            type="text"
            className={INPUT}
            placeholder="/Volumes/main/raw/state/orders.json or s3://team/state.json"
            value={state.incrementalStatePath}
            onChange={(event) => onUpdateState({ incrementalStatePath: event.target.value })}
          />
        </Field>
        <Field label="Initial cursor value" tooltip="Seed sent as the cursor while nothing is stored yet; ignored once the state file has a value.">
          <input
            type="text"
            className={INPUT}
            placeholder="2024-01-01T00:00:00Z"
            value={state.incrementalStartValue}
            onChange={(event) => onUpdateState({ incrementalStartValue: event.target.value })}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="State key override" tooltip="Entry name inside the state file, for sharing one file across connectors. Defaults to <stream>@<base URL>.">
          <input
            type="text"
            className={INPUT}
            placeholder="orders_incremental_sync"
            value={state.incrementalStateKey}
            onChange={(event) => onUpdateState({ incrementalStateKey: event.target.value })}
          />
        </Field>
      </div>
    </Disclosure>
  );
};
