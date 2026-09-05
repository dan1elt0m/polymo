import React from "react";
import type { ConfigFormState } from "../../../types";
import { HeaderRow } from "../rows/HeaderRow";
import { BTN_LINK, Disclosure, HELP, PlusIcon } from "../../ui/primitives";

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
    <Disclosure
      id={TOGGLE_ID}
      title="Headers"
      summary={headerCount ? `${headerCount} header${headerCount === 1 ? "" : "s"}` : "none"}
      open={isOpen}
      onToggle={() => setIsOpen((v) => !v)}
      action={
        <button type="button" className={BTN_LINK} onClick={handleAddHeader}>
          <PlusIcon /> Add
        </button>
      }
    >
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
        <p className={HELP}>No headers configured. Values support secrets via <code className="font-mono">{"{{ options.key }}"}</code>.</p>
      )}
    </Disclosure>
  );
};
