import React from "react";
import type { RestSourceConfig } from "../types";

const EXAMPLE_CONNECTORS = [
  { name: "GitHub Repositories", path: "/static/examples/githubrepos.polymo.json", description: "Fetch repository data from GitHub API" },
  { name: "JSON Placeholder", path: "/static/examples/jsonplaceholder.polymo.json", description: "Sample posts and user data" },
  { name: "REST Countries", path: "/static/examples/countries.polymo.json", description: "Country information and statistics" },
  { name: "Weather API", path: "/static/examples/weather.polymo.json", description: "Current weather and forecast data" },
  { name: "JSON Placeholder Multiple Endpoints", path: "/static/examples/jsonplaceholder_endpoints.polymo.json", description: "Fetch posts, comments, and users" },
];

const exampleTestId = (name: string): string => name.toLowerCase().replace(/[^a-z0-9]+/g, "-");

// Minimal shape check for an uploaded/fetched config file: it must be a JSON
// object with `source` and `stream` keys to be worth handing to the reverse
// transform. Anything else is rejected with a friendly inline error instead
// of failing deep inside configToFormState.
const isPlausibleConfig = (value: unknown): value is RestSourceConfig => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.source === "object" && candidate.source !== null
    && typeof candidate.stream === "object" && candidate.stream !== null;
};

interface SavedConnectorSummary {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
}

interface WorkingStateSummary {
  label: string;
  savedAt: string;
}

interface LandingScreenProps {
  onStartNew: () => void;
  onImportConfig: (config: RestSourceConfig, options?: { suggestedName?: string }) => void;
  savedConnectors: SavedConnectorSummary[];
  onSelectSaved: (id: string) => void;
  onDeleteSaved: (id: string) => void;
  onExportSaved: (id: string) => void;
  workingState?: WorkingStateSummary | null;
  onResumeWorking?: () => void;
  onDiscardWorking?: () => void;
}

const formatDate = (value: string): string => {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Unknown";
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  } catch {
    return "Unknown";
  }
};

export const LandingScreen: React.FC<LandingScreenProps> = ({
  onStartNew,
  onImportConfig,
  savedConnectors,
  onSelectSaved,
  onDeleteSaved,
  onExportSaved,
  workingState,
  onResumeWorking,
  onDiscardWorking,
}) => {
  const [isUploading, setIsUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleStartFromScratch = () => {
    setError(null);
    onStartNew();
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    if (!file) return;

    setError(null);
    setIsUploading(true);
    try {
      const text = await file.text();
      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch {
        throw new Error("That file isn't valid JSON. Export a config with \"Save config\" and try again.");
      }
      if (!isPlausibleConfig(parsed)) {
        throw new Error("That file doesn't look like a polymo config (expected \"source\" and \"stream\" sections).");
      }
      onImportConfig(parsed, { suggestedName: file.name });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read that file.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadExample = async (path: string, name: string) => {
    setError(null);
    setIsUploading(true);
    try {
      const response = await fetch(path);
      if (!response.ok) {
        throw new Error(`Could not load ${name} (${response.status}).`);
      }
      const parsed = (await response.json()) as unknown;
      if (!isPlausibleConfig(parsed)) {
        throw new Error(`${name} is not a valid polymo config.`);
      }
      onImportConfig(parsed, { suggestedName: name });
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not load ${name}.`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-full w-full flex flex-col items-center justify-center p-6 gap-12">
      <div className="text-center space-y-3">
        <div className="flex justify-center mb-6">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-accent-soft shadow-soft overflow-hidden">
            <img
              src={import.meta.env.DEV ? "/favicon.ico" : "/static/favicon.ico"}
              alt="polymo Logo"
              className="h-10 w-10 object-contain"
            />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-fg">Polymo</h1>
        <p className="text-fg-muted max-w-md mx-auto">
          Create and configure REST API connectors with an easy-to-use visual editor
        </p>
      </div>

      {workingState && onResumeWorking && (
        <div
          className="w-full max-w-4xl mx-auto rounded-xl border-2 border-accent bg-accent-soft/60 px-6 py-5 shadow-soft flex flex-wrap items-center justify-between gap-4"
          data-testid="resume-working-state-card"
        >
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent/15">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-accent-text" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <p className="text-base font-semibold text-fg">Resume where you left off</p>
              <p className="text-sm text-fg-muted">
                {workingState.label} · saved {formatDate(workingState.savedAt)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onDiscardWorking && (
              <button
                type="button"
                onClick={onDiscardWorking}
                className="rounded-full px-3 py-1.5 text-xs font-medium text-fg-muted hover:text-fg transition"
              >
                Discard
              </button>
            )}
            <button
              type="button"
              onClick={onResumeWorking}
              className="inline-flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-accent-fg shadow-soft transition hover:bg-accent-hover"
              data-testid="resume-working-state"
            >
              Resume
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl mx-auto">
        <button
          type="button"
          onClick={handleStartFromScratch}
          className="flex flex-col gap-4 items-center rounded-xl border border-border hover:border-accent bg-surface p-6 transition cursor-pointer group"
        >
          <div className="h-12 w-12 rounded-full bg-accent-soft flex items-center justify-center group-hover:bg-accent/20 transition">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-accent" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-fg">Start from scratch</h2>
          <p className="text-sm text-fg-muted text-center">
            Create a new connector with the default configuration
          </p>
        </button>

        <div className="flex flex-col gap-4 items-center rounded-xl border border-border hover:border-accent bg-surface p-6 transition group">
          <div className="h-12 w-12 rounded-full bg-accent-soft flex items-center justify-center group-hover:bg-accent/20 transition">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-accent" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-fg">Import Connector</h2>
          <div className="w-full space-y-3">
            <button
              type="button"
              onClick={handleUploadClick}
              disabled={isUploading}
              className="w-full flex items-center justify-center gap-2 rounded-lg border border-border bg-field px-4 py-2.5 text-sm font-medium text-fg hover:border-accent hover:text-accent-text transition disabled:opacity-50"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M5.5 17a4.5 4.5 0 01-1.44-8.765 4.5 4.5 0 018.302-3.046 3.5 3.5 0 014.504 4.272A4 4 0 0115 17H5.5zm3.75-2.75a.75.75 0 001.5 0V9.66l1.95 2.1a.75.75 0 101.1-1.02l-3.25-3.5a.75.75 0 00-1.1 0l-3.25 3.5a.75.75 0 101.1 1.02l1.95-2.1v4.59z" clipRule="evenodd" />
              </svg>
              {isUploading ? "Importing..." : "Upload Config File"}
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={handleFileChange}
            disabled={isUploading}
          />
        </div>

        <div className="flex flex-col gap-4 items-center rounded-xl border border-border hover:border-accent bg-surface p-6 transition">
          <div className="h-12 w-12 rounded-full bg-accent-soft flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-accent" viewBox="0 0 20 20" fill="currentColor">
              <path d="M4.5 3a.5.5 0 0 0-.5.5V5h-.5A1.5 1.5 0 0 0 2 6.5v9A1.5 1.5 0 0 0 3.5 17h9a1.5 1.5 0 0 0 1.5-1.5V15h1.5a1.5 1.5 0 0 0 1.5-1.5v-9A1.5 1.5 0 0 0 15.5 3h-11ZM3 6.5A.5.5 0 0 1 3.5 6H5v9H3.5a.5.5 0 0 1-.5-.5v-8Zm5 9V6h-2v9h2Zm1 0h2V6h-2v9Zm5 0V6h1.5a.5.5 0 0 1 .5.5v8a.5.5 0 0 1-.5.5H14Z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-fg">Start from an example</h2>
          <div className="relative w-full">
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-lg border border-border/70 bg-field px-4 py-2 text-sm text-fg hover:border-accent hover:text-accent-text transition"
              onClick={() => {
                const dropdown = document.getElementById("example-dropdown");
                dropdown?.classList.toggle("hidden");
              }}
              data-testid="landing-example-toggle"
            >
              <span>Select an example connector</span>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M7.793 14.707a1 1 0 010-1.414L10.086 11H3a1 1 0 110-2h7.086L7.793 6.707a1 1 0 011.414-1.414l4.5 4.5a1 1 0 010 1.414l-4.5 4.5a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
            </button>
            <div
              id="example-dropdown"
              className="absolute left-0 z-10 mt-2 w-full rounded-lg border border-border bg-field shadow-lg hidden"
            >
              <div className="max-h-60 rounded-lg border-t border-border/70 overflow-auto">
                {EXAMPLE_CONNECTORS.map((example) => (
                  <button
                    key={example.path}
                    type="button"
                    onClick={() => handleLoadExample(example.path, example.name)}
                    className="flex w-full items-center justify-between rounded-lg border-b border-border/70 bg-field px-4 py-2 text-sm text-fg hover:bg-raised transition"
                    data-testid={`landing-example-${exampleTestId(example.name)}`}
                  >
                    <div className="flex flex-col">
                      <span className="font-medium">{example.name}</span>
                      <span className="text-xs text-fg-muted">
                        {example.description}
                      </span>
                    </div>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M7.793 14.707a1 1 0 010-1.414L10.086 11H3a1 1 0 110-2h7.086L7.793 6.707a1 1 0 011.414-1.414l4.5 4.5a1 1 0 010 1.414l-4.5 4.5a1 1 0 01-1.414 0z" clipRule="evenodd" />
                    </svg>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-error/40 bg-error/10 px-4 py-3 text-sm text-error max-w-3xl w-full">
          {error}
        </div>
      )}

      <section className="w-full max-w-4xl space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-fg">Saved connectors</h2>
          {savedConnectors.length > 0 && (
            <button
              type="button"
              onClick={handleStartFromScratch}
              className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-field px-3 py-1.5 text-xs font-medium text-fg hover:border-accent hover:text-accent-text transition"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
              New connector
            </button>
          )}
        </div>

        {savedConnectors.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/70 bg-surface px-6 py-10 text-center text-sm text-fg-muted">
            Saved connectors will appear here automatically. Start a new connector or import a config file to begin.
          </div>
        ) : (
          <ul className="space-y-3">
            {savedConnectors.map((connector) => {
              // Rename disabled: always display static name
              return (
                <li
                  key={connector.id}
                  className="rounded-xl border border-border/70 bg-field px-5 py-4 shadow-sm flex flex-col gap-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        <p className="text-base font-medium text-fg">{connector.name}</p>
                        {/* Rename button removed per requirement */}
                      </div>
                      <span className="text-xs text-fg-muted">
                        Last updated {formatDate(connector.updatedAt)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-full border border-border bg-field px-3 py-1.5 text-xs font-medium text-fg hover:border-accent hover:text-accent-text"
                        onClick={() => onSelectSaved(connector.id)}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M4 3a1 1 0 011-1h3.586a1 1 0 01.707.293l1.414 1.414a1 1 0 00.707.293H15a1 1 0 011 1v1H4V3zm12 4H4v9a1 1 0 001 1h10a1 1 0 001-1V7z" clipRule="evenodd" />
                        </svg>
                        Open
                      </button>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-full border border-border bg-field px-3 py-1.5 text-xs font-medium text-fg hover:border-accent hover:text-accent-text"
                        onClick={() => onExportSaved(connector.id)}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm7-14a1 1 0 011 1v5h2.586a1 1 0 01.707 1.707l-3.586 3.586a1 1 0 01-1.414 0L6.707 10.707A1 1 0 017.414 9H10V4a1 1 0 011-1z" clipRule="evenodd" />
                        </svg>
                        Export
                      </button>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-full border border-border bg-field px-3 py-1.5 text-xs font-medium text-error hover:border-error/60"
                        onClick={() => onDeleteSaved(connector.id)}
                        aria-label={`Delete ${connector.name}`}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 100 2h.293l.853 9.373A2 2 0 007.138 17h5.724a2 2 0 001.992-1.627L15.707 6H16a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zm-1 5a1 1 0 112 0v6a1 1 0 11-2 0V7zm4 0a1 1 0 112 0v6a1 1 0 11-2 0V7z" clipRule="evenodd" />
                        </svg>
                        Delete
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
};
