import React from "react";
import type { ConfigFormState } from "../../../types";
import { Field, INPUT, SelectInput } from "../../ui/primitives";

export interface BaseConfigurationSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

export const BaseConfigurationSection: React.FC<BaseConfigurationSectionProps> = ({ state, onUpdateState }) => {
  const isXml = state.responseFormat === 'xml';
  return (
    <div className="space-y-4">
      <Field label="Base URL" tooltip="Root HTTPS endpoint of the API. Exclude the trailing slash.">
        <input
          type="url"
          className={INPUT}
          placeholder="https://api.example.com"
          value={state.baseUrl}
          onChange={(e) => onUpdateState({ baseUrl: e.target.value })}
          data-testid="base-url-input"
        />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Stream path" tooltip="Endpoint path appended to the base URL. Must start with /">
          <input
            type="text"
            className={INPUT}
            placeholder="/v1/orders"
            value={state.streamPath}
            onChange={(e) => onUpdateState({ streamPath: e.target.value })}
            data-testid="stream-path-input"
          />
        </Field>
        <Field
          label="Table name"
          tooltip="Becomes the dp table name in the generated script (sanitized to a SQL identifier on export). Defaults to a name derived from the stream path when left blank."
        >
          <input
            type="text"
            className={INPUT}
            placeholder="orders (from path if blank)"
            value={state.streamName}
            onChange={(e) => onUpdateState({ streamName: e.target.value })}
            data-testid="stream-name-input"
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field
          label="Response format"
          tooltip="Format of the API response body. XML responses are flattened by matching an element path and cannot be combined with JSON-path features (cursor/next-url/total-pages paths, or a record selector field path)."
        >
          <SelectInput
            value={state.responseFormat || 'json'}
            onChange={(e) => onUpdateState({ responseFormat: e.target.value as ConfigFormState['responseFormat'] })}
            data-testid="response-format-select"
          >
            <option value="json">JSON</option>
            <option value="xml">XML</option>
          </SelectInput>
        </Field>
        {isXml && (
          <Field label="XML record path" tooltip="ElementTree find-style path selecting each record element, e.g. .//contact">
            <input
              type="text"
              className={INPUT}
              placeholder=".//contact"
              value={state.xmlRecordPath || ''}
              onChange={(e) => onUpdateState({ xmlRecordPath: e.target.value })}
              data-testid="xml-record-path-input"
            />
          </Field>
        )}
      </div>
    </div>
  );
};
