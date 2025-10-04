import React from "react";
import type { ConfigFormState } from "../../types";
import { bearerTokenAtom, readerOptionsAtom, runtimeOptionsAtom } from "../../atoms";
import { useAtom, useSetAtom, useAtomValue } from "jotai";
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

export interface ConfigurationTabProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
  onAddParam: () => void;
  onRemoveParam: (key: string) => void;
  onUpdateParam: (key: string, newKey: string, value: string) => void;
}

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
    <div className="space-y-8">
      <BaseConfigurationSection state={state} onUpdateState={onUpdateState} />

      <AuthenticationSection state={state} onUpdateState={onUpdateState} setBearerToken={setBearerToken} />

      <HeadersSection state={state} onUpdateState={onUpdateState} />

      <ParamsSection params={state.params} onAddParam={onAddParam} onRemoveParam={onRemoveParam} onUpdateParam={onUpdateParam} />

      <ErrorHandlingSection state={state} onUpdateState={onUpdateState} />

      <PaginationSection state={state} onUpdateState={onUpdateState} />

      <IncrementalSection state={state} onUpdateState={onUpdateState} />

      <RecordSelectorSection state={state} onUpdateState={onUpdateState} />

      <PartitioningSection state={state} onUpdateState={onUpdateState} />

      <ReaderOptionsSection
        readerOptions={readerOptions}
        setReaderOptions={setReaderOptions}
        runtimeOptions={runtimeOptions}
        onUpdateState={onUpdateState}
      />
    </div>
  );
};

