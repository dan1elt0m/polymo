import React from "react";
import { InputWithCursorPosition } from "../../InputWithCursorPosition";
import { KeyValueRow } from "../../ui/primitives";

export interface HeaderRowProps {
  originalKey: string;
  value: string;
  onUpdateKey: (oldKey: string, newKey: string, value: string) => void;
  onUpdateValue: (key: string, newKey: string, value: string) => void;
  onRemove: (key: string) => void;
}

export const HeaderRow: React.FC<HeaderRowProps> = ({
  originalKey,
  value,
  onUpdateKey,
  onUpdateValue,
  onRemove,
}) => {
  const [tempKey, setTempKey] = React.useState(originalKey);

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
      keyLabel="Header name"
      keyPlaceholder="X-Api-Key"
      keyTooltip="Header sent on every request."
      valuePlaceholder="{{ options.api_key }}"
      valueTooltip="Header value, supports secrets via {{ options.key }}."
      tempKey={tempKey}
      value={value}
      onTempKeyChange={setTempKey}
      onCommitKey={commitIfChanged}
      onValueChange={(next) => onUpdateValue(originalKey, originalKey, next)}
      onRemove={() => onRemove(originalKey)}
      removeLabel={`Remove header ${originalKey}`}
      renderKey={(className) => (
        <InputWithCursorPosition
          type="text"
          className={className}
          placeholder="X-Api-Key"
          aria-label="Header name"
          value={tempKey}
          onChange={(e) => setTempKey(e.target.value)}
          onBlur={commitIfChanged}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              (e.target as HTMLInputElement).blur();
            }
          }}
        />
      )}
      renderValue={(className) => (
        <InputWithCursorPosition
          type="text"
          className={className}
          placeholder="{{ options.api_key }}"
          aria-label="Header value"
          value={value}
          onValueChange={(newValue) => onUpdateValue(originalKey, originalKey, newValue)}
        />
      )}
    />
  );
};
