import React from "react";
import type { ConfigFormState } from "../../types";
import { bearerTokenAtom, readerOptionsAtom, runtimeOptionsAtom } from "../../atoms";
import { useAtom, useSetAtom, useAtomValue } from "jotai";
import { CheckboxRow, Eyebrow } from "../ui/primitives";
import { BaseConfigurationSection } from "./sections/BaseConfigurationSection";
import { AuthenticationSection } from "./sections/AuthenticationSection";
import { HeadersSection } from "./sections/HeadersSection";
import { ParamsSection } from "./sections/ParamsSection";
import { ErrorHandlingSection } from "./sections/ErrorHandlingSection";
import { PaginationSection } from "./sections/PaginationSection";
import { IncrementalSection } from "./sections/IncrementalSection";
import { RecordSelectorSection } from "./sections/RecordSelectorSection";
import { PartitioningSection } from "./sections/PartitioningSection";
import { ReaderOptionsSection } from "./sections/ReaderOptionsSection";
import { SchemaTab } from "./SchemaTab";

export interface ConfigurationTabProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
  onAddParam: () => void;
  onRemoveParam: (key: string) => void;
  onUpdateParam: (key: string, newKey: string, value: string) => void;
}

/**
 * Two tiers: Essentials (always visible — the five things every connector
 * needs) and Advanced (compact disclosures, closed by default unless they
 * already carry a value).
 */
export const ConfigurationTab: React.FC<ConfigurationTabProps> = ({
  state,
  onUpdateState,
  onAddParam,
  onRemoveParam,
  onUpdateParam,
}) => {
  const setBearerToken = useSetAtom(bearerTokenAtom);
  const [readerOptions, setReaderOptions] = useAtom(readerOptionsAtom);
  const runtimeOptions = useAtomValue(runtimeOptionsAtom);

  React.useEffect(() => {
    if (!state.headers) {
      onUpdateState({ headers: {} });
    }
  }, [state.headers, onUpdateState]);

  return (
    <div className="flex flex-col gap-8">
      <section className="space-y-5" aria-labelledby="essentials-heading">
        <Eyebrow>
          <span id="essentials-heading">Essentials</span>
        </Eyebrow>
        <BaseConfigurationSection state={state} onUpdateState={onUpdateState} />
        <AuthenticationSection state={state} onUpdateState={onUpdateState} setBearerToken={setBearerToken} />
      </section>

      <section className="space-y-2" aria-labelledby="advanced-heading">
        <Eyebrow>
          <span id="advanced-heading">Advanced</span>
        </Eyebrow>
        <div className="flex flex-col">
          <div className="flex min-h-[40px] items-center border-b border-border py-2">
            <CheckboxRow
              label="Streaming table"
              tooltip="Reads records as a Spark Structured Streaming source instead of a batch read. Requires an explicit schema and offset or page pagination; not compatible with incremental state or partition strategies."
              checked={state.streaming}
              onChange={(e) => onUpdateState({ streaming: e.target.checked })}
              data-testid="streaming-toggle"
              className="items-center [&>input]:mt-0"
            />
          </div>
          <SchemaTab state={state} onUpdateState={onUpdateState} />
          <PaginationSection state={state} onUpdateState={onUpdateState} />
          <IncrementalSection state={state} onUpdateState={onUpdateState} />
          <PartitioningSection state={state} onUpdateState={onUpdateState} />
          <ErrorHandlingSection state={state} onUpdateState={onUpdateState} />
          <HeadersSection state={state} onUpdateState={onUpdateState} />
          <ParamsSection params={state.params} onAddParam={onAddParam} onRemoveParam={onRemoveParam} onUpdateParam={onUpdateParam} />
          <ReaderOptionsSection
            readerOptions={readerOptions}
            setReaderOptions={setReaderOptions}
            runtimeOptions={runtimeOptions}
            onUpdateState={onUpdateState}
          />
          <RecordSelectorSection state={state} onUpdateState={onUpdateState} />
        </div>
      </section>
    </div>
  );
};
