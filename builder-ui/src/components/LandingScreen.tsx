import React from "react";
import { useSetAtom } from "jotai";
import { configFormStateAtom, yamlTextAtom, lastEditedAtom, sampleAtom, statusAtom, readerOptionsAtom } from "../atoms";
import { configToFormState } from "../lib/transform";
import { INITIAL_FORM_STATE } from "../lib/initial-data";
import { DEFAULT_SAMPLE_LIMIT, DEFAULT_PAGE_SIZE, SAMPLE_VIEWS } from "../lib/constants";
import type { RestSourceConfig } from "../types";
import yaml from "js-yaml";

// Example connectors to show in the UI - path using static directory
const EXAMPLE_CONNECTORS = [
  { name: "GitHub Repositories", path: "/static/examples/githubrepos.yml" },
  { name: "JSON Placeholder", path: "/static/examples/jsonplaceholder.yml" },
];

interface LandingScreenProps {
  onComplete: () => void;
}

export const LandingScreen: React.FC<LandingScreenProps> = ({ onComplete }) => {
  const setConfigFormState = useSetAtom(configFormStateAtom);
  const setYamlText = useSetAtom(yamlTextAtom);
  const setLastEdited = useSetAtom(lastEditedAtom);
  const setSample = useSetAtom(sampleAtom);
  const setStatus = useSetAtom(statusAtom);
  const setReaderOptions = useSetAtom(readerOptionsAtom);
  const [isUploading, setIsUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Reset all application state to default values
  const resetAllState = () => {
    setConfigFormState(JSON.parse(JSON.stringify(INITIAL_FORM_STATE))); // Deep copy to avoid reference issues
    setYamlText('');
    setLastEdited('ui');
    setReaderOptions({});
    setSample({
      data: [],
      dtypes: [],
      stream: "",
      limit: DEFAULT_SAMPLE_LIMIT,
      view: SAMPLE_VIEWS.TABLE,
      wrap: false,
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE,
      loading: false,
      rawPages: [],
      restError: null
    });
    setStatus({ tone: "info", message: "Ready to configure" });
  };

  const handleStartFromScratch = () => {
    // Reset all state to defaults before proceeding
    resetAllState();
    // Proceed with clean state
    onComplete();
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const content = await file.text();
      // Try to parse as YAML
      try {
        const parsed = yaml.load(content) as RestSourceConfig;
        if (!parsed || typeof parsed !== "object") {
          throw new Error("Invalid YAML structure");
        }

        // Reset sample data and status before setting new config
        setSample({
          data: [],
          dtypes: [],
          stream: "",
          limit: DEFAULT_SAMPLE_LIMIT,
          view: SAMPLE_VIEWS.TABLE,
          wrap: false,
          page: 1,
          pageSize: DEFAULT_PAGE_SIZE,
          loading: false,
          rawPages: [],
          restError: null
        });
        setStatus({ tone: "info", message: "Configuration loaded from file" });
        setReaderOptions({});

        // Set form state from parsed config
        setConfigFormState(configToFormState(parsed as any));
        setYamlText(content);
        setLastEdited("yaml");
        onComplete();
      } catch (err) {
        setError(`Could not parse YAML file: ${err instanceof Error ? err.message : 'Unknown error'}`);
      }
    } catch (err) {
      setError(`Could not read file: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadExample = async (path: string) => {
    setError(null);
    setIsUploading(true);
    try {
      const response = await fetch(path);
      if (!response.ok) {
        throw new Error(`Failed to fetch example: ${response.statusText}`);
      }
      const content = await response.text();
      const parsed = yaml.load(content) as RestSourceConfig;

      // Reset sample data and status before setting new config
      setSample({
        data: [],
        dtypes: [],
        stream: "",
        limit: DEFAULT_SAMPLE_LIMIT,
        view: SAMPLE_VIEWS.TABLE,
        wrap: false,
        page: 1,
        pageSize: DEFAULT_PAGE_SIZE,
        loading: false,
        rawPages: [],
        restError: null
      });
      setStatus({ tone: "info", message: "Example configuration loaded" });
      setReaderOptions({});

      setConfigFormState(configToFormState(parsed as any));
      setYamlText(content);
      setLastEdited("yaml");
      onComplete();
    } catch (err) {
      setError(`Could not load example: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="h-full w-full flex flex-col items-center justify-center p-6 gap-12">
      <div className="text-center space-y-3">
        <div className="flex justify-center mb-6">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-blue-5 shadow-soft overflow-hidden dark:bg-blue-7/40">
            <img
              src={import.meta.env.DEV ? "/favicon.ico" : "/static/favicon.ico"}
              alt="polymo Logo"
              className="h-10 w-10 object-contain"
            />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-slate-12 dark:text-drac-foreground">Polymo Connector Builder</h1>
        <p className="text-muted dark:text-drac-muted max-w-md mx-auto">
          Create and configure REST API connectors with an easy-to-use visual editor
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl mx-auto">
        {/* Start from scratch */}
        <div
          onClick={handleStartFromScratch}
          className="flex flex-col gap-4 items-center rounded-xl border border-border hover:border-blue-7 dark:border-drac-border dark:hover:border-drac-accent bg-surface/90 dark:bg-[#282a36]/70 p-6 transition cursor-pointer group"
        >
          <div className="h-12 w-12 rounded-full bg-blue-4/50 dark:bg-blue-9/20 flex items-center justify-center group-hover:bg-blue-5/80 dark:group-hover:bg-blue-9/30 transition">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-blue-9 dark:text-blue-9" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-12 dark:text-drac-foreground">Start from scratch</h2>
          <p className="text-sm text-muted dark:text-drac-muted text-center">
            Create a new connector with the default configuration
          </p>
        </div>

        {/* Upload YAML */}
        <div
          onClick={handleUploadClick}
          className="flex flex-col gap-4 items-center rounded-xl border border-border hover:border-blue-7 dark:border-drac-border dark:hover:border-drac-accent bg-surface/90 dark:bg-[#282a36]/70 p-6 transition cursor-pointer group"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".yml,.yaml"
            className="hidden"
            onChange={handleFileChange}
            disabled={isUploading}
          />
          <div className="h-12 w-12 rounded-full bg-blue-4/50 dark:bg-blue-9/20 flex items-center justify-center group-hover:bg-blue-5/80 dark:group-hover:bg-blue-9/30 transition">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-blue-9 dark:text-blue-9" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-12 dark:text-drac-foreground">Upload YAML</h2>
          <p className="text-sm text-muted dark:text-drac-muted text-center">
            Import an existing connector configuration file
          </p>
        </div>

        {/* Example connectors */}
        <div className="flex flex-col gap-4 rounded-xl border border-border hover:border-blue-7 dark:border-drac-border dark:hover:border-drac-accent bg-surface/90 dark:bg-[#282a36]/70 p-6 transition group">
          <div className="h-12 w-12 rounded-full bg-blue-4/50 dark:bg-blue-9/20 flex items-center justify-center group-hover:bg-blue-5/80 dark:group-hover:bg-blue-9/30 transition">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-blue-9 dark:text-blue-9" viewBox="0 0 20 20" fill="currentColor">
              <path d="M7 3a1 1 0 000 2h6a1 1 0 100-2H7zM4 7a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1zM2 11a2 2 0 012-2h12a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2v-4z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-12 dark:text-drac-foreground">Example connectors</h2>
          <div className="flex flex-col gap-2">
            {EXAMPLE_CONNECTORS.map((example) => (
              <button
                key={example.path}
                onClick={() => handleLoadExample(example.path)}
                className="text-left text-sm px-3 py-2 rounded-md border border-border/60 dark:border-drac-border/40 bg-background/50 dark:bg-[#313341]/50 hover:bg-blue-3/40 dark:hover:bg-blue-9/20 transition text-slate-12 dark:text-drac-foreground"
                disabled={isUploading}
              >
                {example.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-3 dark:bg-red-9/20 border border-red-7 dark:border-red-9/30 rounded-lg text-red-11 dark:text-red-9">
          {error}
        </div>
      )}
    </div>
  );
};
