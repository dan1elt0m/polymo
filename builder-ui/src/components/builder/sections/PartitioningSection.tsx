import React from "react";
import type { ConfigFormState } from "../../../types";
import { Disclosure, Field, HELP, INPUT, SelectInput, TEXTAREA, cx } from "../../ui/primitives";

export interface PartitioningSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "partitioning-section";

const partitionStrategies: Array<{ value: ConfigFormState["partitionStrategy"]; label: string }> = [
  { value: "none", label: "None" },
  { value: "pagination", label: "Mirror pagination" },
  { value: "param_range", label: "Parameter range" },
  { value: "endpoints", label: "Endpoint list" },
];

export const PartitioningSection: React.FC<PartitioningSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const summary = React.useMemo(() => {
    switch (state.partitionStrategy) {
      case "pagination":
        return "mirror pagination";
      case "param_range": {
        if (state.partitionValues?.trim()) return "values list";
        if (state.partitionRangeStart?.trim() && state.partitionRangeEnd?.trim()) {
          return `${state.partitionRangeKind === "date" ? "date" : "numeric"} range`;
        }
        return "param range";
      }
      case "endpoints":
        return "multiple endpoints";
      default:
        return "none";
    }
  }, [
    state.partitionStrategy,
    state.partitionRangeEnd,
    state.partitionRangeKind,
    state.partitionRangeStart,
    state.partitionValues,
  ]);

  React.useEffect(() => {
    if (state.partitionStrategy !== "none") {
      setIsOpen(true);
    }
  }, [state.partitionStrategy]);

  const isParamRange = state.partitionStrategy === "param_range";
  const isPaginationMirror = state.partitionStrategy === "pagination";
  const isEndpoints = state.partitionStrategy === "endpoints";
  const isDate = state.partitionRangeKind === "date";

  return (
    <Disclosure id={TOGGLE_ID} title="Partitioning" summary={summary} open={isOpen} onToggle={() => setIsOpen((v) => !v)}>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Strategy" tooltip="Split the workload to parallelize extraction. Some strategies rely on pagination or explicit lists.">
          <SelectInput
            value={state.partitionStrategy}
            onChange={(event) => onUpdateState({ partitionStrategy: event.target.value as ConfigFormState["partitionStrategy"] })}
          >
            {partitionStrategies.map((strategy) => (
              <option key={strategy.value} value={strategy.value}>
                {strategy.label}
              </option>
            ))}
          </SelectInput>
        </Field>
        {isParamRange && (
          <Field label="Range kind" tooltip="Use numeric ranges for integers, or date ranges for ISO dates.">
            <SelectInput
              value={state.partitionRangeKind || "numeric"}
              onChange={(event) => onUpdateState({ partitionRangeKind: event.target.value as ConfigFormState["partitionRangeKind"] })}
            >
              <option value="numeric">Numeric</option>
              <option value="date">Date</option>
            </SelectInput>
          </Field>
        )}
      </div>

      {isPaginationMirror && (
        <p className={HELP}>
          Fans out one Spark partition per page: the driver fetches the first page once, reads the page count from the
          total-pages / total-records hints in the Pagination section, and each partition fetches exactly one page.
          Needs page or offset pagination with a page size and at least one of those hints; otherwise the table reads
          sequentially, exactly as with no partitioning.
        </p>
      )}

      {isParamRange && (
        <>
          <div className="fields-4">
            <Field label="Partition parameter" tooltip="Query parameter that receives each partition value.">
              <input
                type="text"
                className={INPUT}
                placeholder="start_date"
                value={state.partitionParam || ""}
                onChange={(event) => onUpdateState({ partitionParam: event.target.value })}
              />
            </Field>
            <Field label="Range start" tooltip="Inclusive start of the generated range.">
              <input
                type="text"
                className={INPUT}
                placeholder={isDate ? "2024-01-01" : "0"}
                value={state.partitionRangeStart || ""}
                onChange={(event) => onUpdateState({ partitionRangeStart: event.target.value })}
              />
            </Field>
            <Field label="Range end" tooltip="Inclusive end of the generated range.">
              <input
                type="text"
                className={INPUT}
                placeholder={isDate ? "2024-01-31" : "100"}
                value={state.partitionRangeEnd || ""}
                onChange={(event) => onUpdateState({ partitionRangeEnd: event.target.value })}
              />
            </Field>
            <Field label="Step" tooltip="Step between generated values. For dates, use ISO 8601 duration (e.g. P1D).">
              <input
                type="text"
                className={INPUT}
                placeholder={isDate ? "P1D" : "10"}
                value={state.partitionRangeStep || ""}
                onChange={(event) => onUpdateState({ partitionRangeStep: event.target.value })}
              />
            </Field>
          </div>

          <Field
            label="Values list"
            tooltip="Comma-separated values or JSON array. Overrides range fields when present."
            help="Provide either explicit values or a start/end range."
          >
            <textarea
              className={cx(TEXTAREA, "min-h-[60px] font-mono text-xs")}
              rows={2}
              placeholder="2024-01-01, 2024-01-02, 2024-01-03"
              value={state.partitionValues || ""}
              onChange={(event) => onUpdateState({ partitionValues: event.target.value })}
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Value template" tooltip="Template applied to each generated value (use {{ value }} placeholder).">
              <input
                type="text"
                className={cx(INPUT, "font-mono text-xs")}
                placeholder="{{ value }}"
                value={state.partitionValueTemplate || ""}
                onChange={(event) => onUpdateState({ partitionValueTemplate: event.target.value })}
              />
            </Field>
            <Field label="Extra parameters template" tooltip="JSON object merged into query params for each partition.">
              <input
                type="text"
                className={cx(INPUT, "font-mono text-xs")}
                placeholder='{"until": "{{ value }}"}'
                value={state.partitionExtraTemplate || ""}
                onChange={(event) => onUpdateState({ partitionExtraTemplate: event.target.value })}
              />
            </Field>
          </div>
        </>
      )}

      {isEndpoints && (
        <Field
          label="Endpoint definitions"
          tooltip="Accepted formats: comma-separated list (users:/users,posts:/posts,/status) or JSON array when using Spark reader options. Name is optional; if omitted the path is used as the name. When using this strategy the stream 'path' field may be omitted."
          help={
            <>
              One Spark partition per endpoint. Records are flat, with no <code className="font-mono">endpoint_name</code>{" "}
              column or <code className="font-mono">data</code> wrapper, so every endpoint must fit the same schema.
            </>
          }
        >
          <textarea
            className={cx(TEXTAREA, "font-mono text-xs")}
            rows={3}
            placeholder="users:/users,posts:/posts,/status"
            value={state.partitionEndpoints || ""}
            onChange={(event) => onUpdateState({ partitionEndpoints: event.target.value })}
          />
        </Field>
      )}
    </Disclosure>
  );
};
