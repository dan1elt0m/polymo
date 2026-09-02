import React from "react";
import type { ConfigFormState } from "../../../types";
import { InputWithCursorPosition } from "../../InputWithCursorPosition";
import { BTN_LINK, CheckboxRow, Disclosure, Field, ICON_BTN, INPUT, PlusIcon, TEXTAREA, XIcon, cx } from "../../ui/primitives";

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
  const summary = React.useMemo(() => {
    const parts: string[] = [];
    if (segments.length) parts.push(segments.filter(Boolean).join(".") || `${segments.length} segments`);
    if (state.recordFilter.trim()) parts.push("filter");
    if (state.castToSchemaTypes) parts.push("cast");
    return parts.length ? parts.join(" · ") : "whole response";
  }, [segments, state.recordFilter, state.castToSchemaTypes]);

  return (
    <Disclosure id={TOGGLE_ID} title="Record selector" summary={summary} open={isOpen} onToggle={() => setIsOpen((v) => !v)}>
      <Field as="div" label="Record path" tooltip="Dotted path segments pointing at the array of records inside the response payload.">
        {segments.length > 0 ? (
          <ul className="flex flex-wrap items-center gap-2">
            {segments.map((segment, index) => (
              <li key={`record-path-${index}`} className="flex items-center gap-1">
                {index > 0 && <span className="font-mono text-xs text-fg-subtle">.</span>}
                <InputWithCursorPosition
                  className={cx(INPUT, "max-w-[9rem] font-mono text-xs")}
                  placeholder={index === 0 ? "data" : "items"}
                  value={segment}
                  onValueChange={(value) => handleUpdateSegment(index, value)}
                  aria-label={`Path segment ${index + 1}`}
                />
                <button type="button" className={ICON_BTN} onClick={() => handleRemoveSegment(index)} aria-label={`Remove segment ${index + 1}`}>
                  <XIcon />
                </button>
              </li>
            ))}
            <li>
              <button type="button" className={BTN_LINK} onClick={handleAddSegment}>
                <PlusIcon /> Add segment
              </button>
            </li>
          </ul>
        ) : (
          <div className="flex items-center gap-3 text-xs text-fg-muted">
            <span>No selector path — records are read from the response root.</span>
            <button type="button" className={BTN_LINK} onClick={handleAddSegment}>
              <PlusIcon /> Add segment
            </button>
          </div>
        )}
      </Field>

      <Field label="Record filter" tooltip="Provide a Python expression evaluated against each record (access the payload via record).">
        <textarea
          className={cx(TEXTAREA, "min-h-[60px] font-mono text-xs")}
          rows={2}
          placeholder="record.get('status') == 'active'"
          value={state.recordFilter}
          onChange={(event) => onUpdateState({ recordFilter: event.target.value })}
        />
      </Field>

      <CheckboxRow
        label="Cast values to schema types"
        checked={state.castToSchemaTypes}
        onChange={(event) => onUpdateState({ castToSchemaTypes: event.target.checked })}
      />
    </Disclosure>
  );
};
