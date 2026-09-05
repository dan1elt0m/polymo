import React from "react";
import { KeyValueRow } from "../../ui/primitives";

export interface PushdownRowProps {
  originalKey: string;
  value: string;
  onUpdate: (oldKey: string, newKey: string, value: string) => void;
  onRemove: (key: string) => void;
}

/** One `column -> query parameter` mapping of the filter-pushdown table. */
export const PushdownRow: React.FC<PushdownRowProps> = ({ originalKey, value, onUpdate, onRemove }) => {
  const [tempKey, setTempKey] = React.useState(originalKey);

  React.useEffect(() => {
    setTempKey(originalKey);
  }, [originalKey]);

  const commitIfChanged = React.useCallback(() => {
    if (tempKey && tempKey !== originalKey) {
      onUpdate(originalKey, tempKey, value);
    }
  }, [tempKey, originalKey, value, onUpdate]);

  return (
    <KeyValueRow
      keyLabel="Column name"
      keyPlaceholder="status"
      keyTooltip="DataFrame column an equality filter can be pushed down on."
      valuePlaceholder="status"
      valueTooltip="Query parameter the filter value is sent as."
      tempKey={tempKey}
      value={value}
      onTempKeyChange={setTempKey}
      onCommitKey={commitIfChanged}
      onValueChange={(next) => onUpdate(originalKey, originalKey, next)}
      onRemove={() => onRemove(originalKey)}
      removeLabel={`Remove pushdown mapping ${originalKey}`}
      testIdPrefix={`pushdown-${originalKey}`}
    />
  );
};
