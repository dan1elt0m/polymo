import React from "react";
import * as Tabs from "@radix-ui/react-tabs";
import type { ConfigFormState } from "../types";
import { ConfigurationTab } from "./builder/ConfigurationTab";
import { SchemaTab } from "./builder/SchemaTab";

interface BuilderPanelProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
  onAddParam: () => void;
  onRemoveParam: (key: string) => void;
  onUpdateParam: (key: string, newKey: string, value: string) => void;
}

export const BuilderPanel: React.FC<BuilderPanelProps> = ({
  state,
  onUpdateState,
  onAddParam,
  onRemoveParam,
  onUpdateParam,
}) => {
  return (
    <div className="h-full p-6">
      <div className="flex flex-col gap-6">
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-12">Stream Configuration</h2>
            <p className="text-sm text-muted">Configure your REST API stream and authentication.</p>
          </div>

          <Tabs.Root defaultValue="configuration" className="rounded-2xl border border-border bg-background overflow-hidden">
            <Tabs.List className="flex border-b border-border/70 bg-surface/80 dark:bg-[#1f232b]/60">
              <Tabs.Trigger
                value="configuration"
                className="flex-1 px-6 py-4 text-sm font-medium text-slate-11 dark:text-drac-foreground/80 hover:text-slate-12 dark:hover:text-drac-foreground data-[state=active]:text-blue-11 data-[state=active]:border-b-2 data-[state=active]:border-blue-9 dark:data-[state=active]:border-drac-accent dark:data-[state=active]:text-drac-accent outline-none transition-colors"
              >
                Configuration
              </Tabs.Trigger>
              <Tabs.Trigger
                value="schema"
                className="flex-1 px-6 py-4 text-sm font-medium text-slate-11 dark:text-drac-foreground/80 hover:text-slate-12 dark:hover:text-drac-foreground data-[state=active]:text-blue-11 data-[state=active]:border-b-2 data-[state=active]:border-blue-9 dark:data-[state=active]:border-drac-accent dark:data-[state=active]:text-drac-accent outline-none transition-colors"
              >
                Schema
              </Tabs.Trigger>
            </Tabs.List>

            <Tabs.Content value="configuration" className="p-8 outline-none">
              <ConfigurationTab
                state={state}
                onUpdateState={onUpdateState}
                onAddParam={onAddParam}
                onRemoveParam={onRemoveParam}
                onUpdateParam={onUpdateParam}
              />
            </Tabs.Content>

            <Tabs.Content value="schema" className="p-8 outline-none">
              <SchemaTab state={state} onUpdateState={onUpdateState} />
            </Tabs.Content>
          </Tabs.Root>
        </section>
      </div>
    </div>
  );
};

