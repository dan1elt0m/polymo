import React from "react";
import type { ConfigFormState } from "../../types";
import { InfoTooltip } from "../InfoTooltip";

export interface SchemaTabProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

export const SchemaTab: React.FC<SchemaTabProps> = ({ state, onUpdateState }) => {
  // Add console log to help debug the state
  console.log("SchemaTab state:", state);

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            className="rounded border-border h-5 w-5 accent-blue-9 dark:accent-drac-accent focus:ring-blue-7 dark:focus:ring-drac-accent"
            checked={state.inferSchema}
            onChange={(event) => onUpdateState({ inferSchema: event.target.checked })}
          />
          <span className="text-sm font-medium text-slate-11 flex items-center gap-1">
            Infer schema automatically
            <InfoTooltip text="Automatically infer columns and types from sample data." />
          </span>
        </label>

        {!state.inferSchema && (
          <label className="flex flex-col gap-2 mt-4">
            <div className="flex items-center gap-1">
              <span className="text-sm font-medium text-slate-11">Schema DDL</span>
              <InfoTooltip text="Explicit schema when inference is disabled. Format: name TYPE, ..." />
            </div>
            <textarea
              className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2 transition-all focus-visible:ring-1 focus-visible:ring-blue-5 font-mono"
              placeholder="id INT, name STRING, created_at TIMESTAMP"
              rows={8}
              value={state.schema}
              onChange={(event) => onUpdateState({ schema: event.target.value })}
            />
            <p className="text-xs text-muted dark:text-drac-muted mt-1">
              Example: <code>id INTEGER, name STRING, created_at TIMESTAMP</code>
            </p>
          </label>
        )}
      </div>
    </div>
  );
};
