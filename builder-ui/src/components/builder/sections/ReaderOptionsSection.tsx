import React from "react";
import type { ConfigFormState } from "../../../types";
import { ReaderOptionRow } from "../rows/ReaderOptionRow";
import { BTN_LINK, Disclosure, HELP, PlusIcon } from "../../ui/primitives";

const TOGGLE_ID = "reader-options-section";

const MANAGED_PARTITION_OPTION_KEYS = new Set([
  "partition_strategy",
  "partition_param",
  "partition_values",
  "partition_range_start",
  "partition_range_end",
  "partition_range_step",
  "partition_range_kind",
  "partition_value_template",
  "partition_extra_template",
  "partition_endpoints",
]);

const SPECIAL_INCREMENTAL_KEYS = [
  "incremental_state_path",
  "incremental_start_value",
  "incremental_state_key",
  "incremental_memory_state",
] as const;

export interface ReaderOptionsSectionProps {
  readerOptions: Record<string, string>;
  setReaderOptions: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  runtimeOptions: Record<string, string>;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

export const ReaderOptionsSection: React.FC<ReaderOptionsSectionProps> = ({
  readerOptions,
  setReaderOptions,
  runtimeOptions,
  onUpdateState,
}) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const summary = React.useMemo(() => {
    const manual = Object.keys(readerOptions).length;
    const total = Object.keys(runtimeOptions).length;
    const incremental = Math.max(0, total - manual);
    if (!total) return "none";
    return `${manual} manual${incremental > 0 ? ` · ${incremental} incremental` : ""}`;
  }, [readerOptions, runtimeOptions]);

  React.useEffect(() => {
    if (Object.keys(readerOptions).length > 0) {
      setIsOpen(true);
    }
  }, [readerOptions]);

  React.useEffect(() => {
    const keys = Object.keys(readerOptions);
    if (!keys.length) return;
    const hasManaged = keys.some((key) => MANAGED_PARTITION_OPTION_KEYS.has(key));
    if (!hasManaged) return;
    setReaderOptions((current) => {
      const next = { ...current };
      let mutated = false;
      MANAGED_PARTITION_OPTION_KEYS.forEach((key) => {
        if (key in next) {
          delete next[key];
          mutated = true;
        }
      });
      return mutated ? next : current;
    });
  }, [readerOptions, setReaderOptions]);

  React.useEffect(() => {
    const patch: Partial<ConfigFormState> = {};
    let mutated = false;

    setReaderOptions((current) => {
      const next = { ...current };
      SPECIAL_INCREMENTAL_KEYS.forEach((key) => {
        if (next[key] !== undefined) {
          const raw = next[key];
          delete next[key];
          mutated = true;
          if (key === "incremental_state_path") {
            patch.incrementalStatePath = String(raw ?? "");
          } else if (key === "incremental_start_value") {
            patch.incrementalStartValue = String(raw ?? "");
          } else if (key === "incremental_state_key") {
            patch.incrementalStateKey = String(raw ?? "");
          } else if (key === "incremental_memory_state") {
            const normalized = String(raw ?? "").trim().toLowerCase();
            patch.incrementalMemoryEnabled = normalized !== "false";
          }
        }
      });
      return mutated ? next : current;
    });

    if (mutated && Object.keys(patch).length > 0) {
      onUpdateState(patch);
    }
  }, [readerOptions, setReaderOptions, onUpdateState]);

  const handleAddOption = React.useCallback(() => {
    setReaderOptions((prev) => {
      const next = { ...prev };
      let index = 1;
      let key = "option";
      while (key in next) {
        key = `option${index++}`;
      }
      next[key] = "";
      return next;
    });
    setIsOpen(true);
  }, [setReaderOptions]);

  const handleRemoveOption = React.useCallback(
    (key: string) => {
      setReaderOptions((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    },
    [setReaderOptions],
  );

  const handleUpdateOption = React.useCallback(
    (key: string, newKey: string, value: string) => {
      setReaderOptions((prev) => {
        const next = { ...prev };
        delete next[key];
        next[newKey] = value;
        return next;
      });
    },
    [setReaderOptions],
  );

  const manualOptions = Object.entries(readerOptions);

  return (
    <Disclosure
      id={TOGGLE_ID}
      title="Spark reader options"
      summary={summary}
      open={isOpen}
      onToggle={() => setIsOpen((v) => !v)}
      action={
        <button type="button" className={BTN_LINK} onClick={handleAddOption}>
          <PlusIcon /> Add
        </button>
      }
    >
      {manualOptions.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {manualOptions.map(([key, value]) => (
            <ReaderOptionRow
              key={key}
              originalKey={key}
              value={String(value)}
              onUpdateKey={handleUpdateOption}
              onUpdateValue={handleUpdateOption}
              onRemove={handleRemoveOption}
            />
          ))}
        </ul>
      ) : (
        <p className={HELP}>No reader options configured. Reference them as <code className="font-mono">{"{{ options.key }}"}</code> and pass them to <code className="font-mono">spark.read.option</code>.</p>
      )}
    </Disclosure>
  );
};
