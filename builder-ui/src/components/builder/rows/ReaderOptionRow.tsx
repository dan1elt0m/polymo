import React from "react";
import { InputWithCursorPosition } from "../../InputWithCursorPosition";
import { KeyValueRow } from "../../ui/primitives";

export interface ReaderOptionRowProps {
  originalKey: string;
  value: string;
  onUpdateKey: (oldKey: string, newKey: string, value: string) => void;
  onUpdateValue: (key: string, newKey: string, value: string) => void;
  onRemove: (key: string) => void;
}

export const ReaderOptionRow: React.FC<ReaderOptionRowProps> = ({
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
      keyLabel="Option key"
      keyPlaceholder="api_key"
      keyTooltip="Name to reference via {{ options.key }} and pass to spark.read.option."
      valuePlaceholder="value"
      valueTooltip="Runtime value supplied to the Spark reader."
      tempKey={tempKey}
      value={value}
      onTempKeyChange={setTempKey}
      onCommitKey={commitIfChanged}
      onValueChange={(next) => onUpdateValue(originalKey, originalKey, next)}
      onRemove={() => onRemove(originalKey)}
      removeLabel={`Remove spark option ${originalKey}`}
      renderKey={(className) => (
        <InputWithCursorPosition
          type="text"
          className={className}
          placeholder="api_key"
          aria-label="Option key"
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
          placeholder="value"
          aria-label="Option value"
          value={value}
          onValueChange={(newValue) => onUpdateValue(originalKey, originalKey, newValue)}
        />
      )}
    />
  );
};
