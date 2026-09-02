import React from "react";
import { ParamRow } from "../rows/ParamRow";
import { BTN_LINK, Disclosure, HELP, PlusIcon } from "../../ui/primitives";

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
    <Disclosure
      id={TOGGLE_ID}
      title="Query parameters"
      summary={paramCount ? `${paramCount} param${paramCount === 1 ? "" : "s"}` : "none"}
      open={isOpen}
      onToggle={() => setIsOpen((v) => !v)}
      testId="query-params-toggle"
      action={
        <button type="button" className={BTN_LINK} onClick={handleAdd}>
          <PlusIcon /> Add
        </button>
      }
    >
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
        <p className={HELP}>No query parameters configured.</p>
      )}
    </Disclosure>
  );
};
