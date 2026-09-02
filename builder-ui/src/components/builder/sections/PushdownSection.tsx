import React from "react";
import type { ConfigFormState } from "../../../types";
import { PushdownRow } from "../rows/PushdownRow";
import { BTN_LINK, Disclosure, HELP, PlusIcon } from "../../ui/primitives";

export interface PushdownSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "pushdown-section";

export const PushdownSection: React.FC<PushdownSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const mappings = state.pushdownParams || {};
  const count = Object.keys(mappings).length;

  React.useEffect(() => {
    if (count > 0) {
      setIsOpen(true);
    }
  }, [count]);

  const handleAdd = React.useCallback(() => {
    const next = { ...mappings };
    let key = "column";
    let index = 1;
    while (key in next) {
      key = `column${index++}`;
    }
    next[key] = "";
    onUpdateState({ pushdownParams: next });
    setIsOpen(true);
  }, [mappings, onUpdateState]);

  const handleRemove = React.useCallback(
    (key: string) => {
      const next = { ...mappings };
      delete next[key];
      onUpdateState({ pushdownParams: next });
    },
    [mappings, onUpdateState],
  );

  const handleUpdate = React.useCallback(
    (key: string, newKey: string, value: string) => {
      const next = { ...mappings };
      delete next[key];
      next[newKey] = value;
      onUpdateState({ pushdownParams: next });
    },
    [mappings, onUpdateState],
  );

  return (
    <Disclosure
      id={TOGGLE_ID}
      title="Filter pushdown"
      summary={count ? `${count} column${count === 1 ? "" : "s"}` : "off"}
      open={isOpen}
      onToggle={() => setIsOpen((v) => !v)}
      action={
        <button type="button" className={BTN_LINK} onClick={handleAdd}>
          <PlusIcon /> Add
        </button>
      }
    >
      <p className={HELP}>
        Equality filters on these columns are sent to the API as query parameters instead of being applied after the
        read (Spark 4.1+). A pushed value overrides a query parameter of the same name; not available for streaming
        tables.
      </p>
      {count > 0 && (
        <ul className="flex flex-col gap-2">
          {Object.entries(mappings).map(([column, param]) => (
            <PushdownRow key={column} originalKey={column} value={param} onUpdate={handleUpdate} onRemove={handleRemove} />
          ))}
        </ul>
      )}
    </Disclosure>
  );
};
