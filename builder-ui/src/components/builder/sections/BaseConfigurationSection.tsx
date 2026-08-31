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

      <label className="flex flex-col gap-2">
        <div className="flex items-center gap-1">
          <span className="text-sm font-medium text-slate-11">Response format</span>
          <InfoTooltip text="Format of the API response body. XML responses are flattened by matching an element path and cannot be combined with JSON-path features (cursor/next-url/total-pages paths, or a record selector field path)." />
        </div>
        <div className="relative">
          <select
            className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-slate-12 shadow-sm appearance-none pr-9 dark:border-slate-6 dark:bg-slate-2 transition-all focus-visible:border-blue-7 focus-visible:ring-1 focus-visible:ring-blue-5"
            value={state.responseFormat || 'json'}
            onChange={(e) =>
              onUpdateState({ responseFormat: e.target.value as ConfigFormState['responseFormat'] })
            }
            data-testid="response-format-select"
          >
            <option value="json">JSON</option>
            <option value="xml">XML</option>
          </select>
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" />
            </svg>
          </span>
        </div>
      </label>

      {state.responseFormat === 'xml' && (
        <label className="flex flex-col gap-2">
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium text-slate-11">XML record path</span>
            <InfoTooltip text="ElementTree find-style path selecting each record element, e.g. .//contact" />
          </div>
          <input
            type="text"
            className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2 transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
            placeholder=".//contact"
            value={state.xmlRecordPath || ''}
            onChange={(e) => onUpdateState({ xmlRecordPath: e.target.value })}
            data-testid="xml-record-path-input"
          />
        </label>
      )}
    </div>
  );
};
