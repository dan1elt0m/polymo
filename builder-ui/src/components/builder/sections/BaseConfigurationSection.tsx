import React from "react";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";

export interface BaseConfigurationSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

export const BaseConfigurationSection: React.FC<BaseConfigurationSectionProps> = ({ state, onUpdateState }) => {
  return (
    <div className="space-y-4">
      <label className="flex flex-col gap-2 w-full">
        <div className="flex items-center gap-1">
          <span className="text-sm font-medium text-slate-11">Base URL</span>
          <InfoTooltip text="Root HTTPS endpoint of the API. Exclude the trailing slash." />
        </div>
        <input
          type="url"
          className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2 transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
          placeholder="https://api.example.com"
          value={state.baseUrl}
          onChange={(e) => onUpdateState({ baseUrl: e.target.value })}
          data-testid="base-url-input"
        />
      </label>

      <label className="flex flex-col gap-2">
        <div className="flex items-center gap-1">
          <span className="text-sm font-medium text-slate-11">Stream Path</span>
          <InfoTooltip text="Endpoint path appended to the base URL. Must start with /" />
        </div>
        <input
          type="text"
          className="rounded-lg border border-border bg-background px-4 py-3 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2 transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
          placeholder="/v1/orders"
          value={state.streamPath}
          onChange={(e) => onUpdateState({ streamPath: e.target.value })}
          data-testid="stream-path-input"
        />
      </label>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-border text-blue-7 focus:ring-blue-5"
          checked={state.streaming}
          onChange={(e) => onUpdateState({ streaming: e.target.checked })}
          data-testid="streaming-toggle"
        />
        <span className="text-sm font-medium text-slate-11 flex items-center gap-1">
          Streaming table
          <InfoTooltip text="Reads records as a Spark Structured Streaming source instead of a batch read. Requires an explicit schema and offset or page pagination; not compatible with incremental state or partition strategies." />
        </span>
      </label>
    </div>
  );
};
