import React from "react";
import type { ConfigFormState } from "../../types";
import { CheckboxRow, Disclosure, Field, TEXTAREA, cx } from "../ui/primitives";

export interface SchemaTabProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "schema-section";

/** Schema disclosure in the Advanced tier (infer vs. explicit DDL). */
export const SchemaTab: React.FC<SchemaTabProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  React.useEffect(() => {
    if (!state.inferSchema) setIsOpen(true);
  }, [state.inferSchema]);

  const summary = state.inferSchema ? "inferred from sample" : state.schema.trim() ? "explicit DDL" : "explicit DDL · empty";

  return (
    <Disclosure id={TOGGLE_ID} title="Schema" summary={summary} open={isOpen} onToggle={() => setIsOpen((v) => !v)}>
      <CheckboxRow
        label="Infer schema automatically"
        tooltip="Automatically infer columns and types from sample data."
        checked={state.inferSchema}
        onChange={(event) => onUpdateState({ inferSchema: event.target.checked })}
      />
      {!state.inferSchema && (
        <Field
          label="Schema DDL"
          tooltip="Explicit schema when inference is disabled. Format: name TYPE, ..."
          help={
            <>
              Example: <code className="font-mono">id INTEGER, name STRING, created_at TIMESTAMP</code>
            </>
          }
        >
          <textarea
            className={cx(TEXTAREA, "font-mono text-xs")}
            placeholder="id INT, name STRING, created_at TIMESTAMP"
            rows={6}
            value={state.schema}
            onChange={(event) => onUpdateState({ schema: event.target.value })}
          />
        </Field>
      )}
    </Disclosure>
  );
};
