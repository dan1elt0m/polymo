import React from "react";
import { InputWithCursorPosition } from "../../InputWithCursorPosition";
import { KeyValueRow } from "../../ui/primitives";

export interface ParamRowProps {
  originalKey: string;
  value: string;
  onUpdateKey: (oldKey: string, newKey: string, value: string) => void;
  onUpdateValue: (key: string, newKey: string, value: string) => void;
  onRemove: (key: string) => void;
}

export const ParamRow: React.FC<ParamRowProps> = ({
  originalKey,
  value,
  onUpdateKey,
  onUpdateValue,
  onRemove,
}) => {
  const [tempKey, setTempKey] = React.useState(originalKey);
  const safeKey = React.useMemo(() => {
    const normalized = (originalKey || "param")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    return normalized || "param";
  }, [originalKey]);

  React.useEffect(() => {
    setTempKey(originalKey);
  }, [originalKey]);

  const commitIfChanged = React.useCallback(() => {
    if (tempKey && tempKey !== originalKey) {
      onUpdateKey(originalKey, tempKey, value);
    }
  }, [tempKey, originalKey, value, onUpdateKey]);

  return (
    <KeyValueRow
      keyLabel="Parameter name"
      keyPlaceholder="param_name"
      keyTooltip="Parameter key sent with request."
      valuePlaceholder="value"
      valueTooltip="Parameter value associated with the key."
      tempKey={tempKey}
      value={value}
      onTempKeyChange={setTempKey}
      onCommitKey={commitIfChanged}
      onValueChange={(next) => onUpdateValue(originalKey, originalKey, next)}
      onRemove={() => onRemove(originalKey)}
      removeLabel={`Remove parameter ${originalKey}`}
      rowTestId={`param-row-${safeKey}`}
      renderKey={(className) => (
        <InputWithCursorPosition
          type="text"
          className={className}
          placeholder="param_name"
          aria-label="Parameter name"
          value={tempKey}
          onChange={(e) => setTempKey(e.target.value)}
          onBlur={commitIfChanged}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              (e.target as HTMLInputElement).blur();
            }
          }}
          data-testid={`param-name-input-${safeKey}`}
        />
      )}
      renderValue={(className) => (
        <InputWithCursorPosition
          type="text"
          className={className}
          placeholder="value"
          aria-label="Parameter value"
          value={value}
          onValueChange={(newValue) => onUpdateValue(originalKey, originalKey, newValue)}
          data-testid={`param-value-input-${safeKey}`}
        />
      )}
    />
  );
};
