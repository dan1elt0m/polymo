import React from "react";
import type { ConfigFormState } from "../types";
import { ConfigurationTab } from "./builder/ConfigurationTab";

interface BuilderPanelProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
  onAddParam: () => void;
  onRemoveParam: (key: string) => void;
  onUpdateParam: (key: string, newKey: string, value: string) => void;
}

/**
 * The UI Builder tab body. Deliberately flat: the pane that hosts this
 * already provides the single card + padding, so the form starts here
 * with no further wrapping.
 */
export const BuilderPanel: React.FC<BuilderPanelProps> = ({
  state,
  onUpdateState,
  onAddParam,
  onRemoveParam,
  onUpdateParam,
}) => (
  <ConfigurationTab
    state={state}
    onUpdateState={onUpdateState}
    onAddParam={onAddParam}
    onRemoveParam={onRemoveParam}
    onUpdateParam={onUpdateParam}
  />
);
