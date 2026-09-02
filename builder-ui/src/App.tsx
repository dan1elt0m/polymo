import React from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
	configFormStateAtom,
	builderViewAtom,
	lastEditedAtom,
	statusAtom,
	isValidatingAtom,
	isSavingAtom,
	sampleAtom,
	streamOptionsAtom,
	configPayloadAtom,
	generatedCodeAtom,
	bearerTokenAtom,
	runtimeOptionsAtom,
	readerOptionsAtom,
	savedConnectorsAtom,
	activeConnectorIdAtom,
	workingStateAtom,
	DEFAULT_SAMPLE_STATE,
} from "./atoms";
import { configToFormState, formStateToConfig, validateFormState, findUnresolvedOptionPlaceholders } from "./lib/transform";
import { validateConfigRequest, sampleRequest, generateScript } from "./lib/api";
import { BuilderPanel } from "./components/BuilderPanel";
import { CodePane } from "./components/CodePane";
import { DeployPanel } from "./components/DeployPanel";
import { SamplePreview } from "./components/SamplePreview";
import { ThemeMenu } from "./components/ThemeMenu";
import { LandingScreen } from "./components/LandingScreen";
import { SplitLayout } from "./components/SplitLayout";
import { BTN_PRIMARY, BTN_SECONDARY, BTN_SMALL, Field, INPUT, cx } from "./components/ui/primitives";
import type { ConfigFormState, ValidationResponse, RestSourceConfig, SavedConnector, WorkingState } from "./types";
import { MAX_SAMPLE_ROWS, SAMPLE_VIEWS } from "./lib/constants";
import { INITIAL_FORM_STATE } from "./lib/initial-data";
import { createId } from "./lib/id";
import { configFileName, CONFIG_FILE_EXTENSION, slugifyName } from "./lib/filename";

const cloneFormState = (state: ConfigFormState): ConfigFormState => JSON.parse(JSON.stringify(state));

const createSampleState = () => JSON.parse(JSON.stringify(DEFAULT_SAMPLE_STATE));

const stripExtension = (name: string): string =>
	name.replace(/\.polymo\.json$/i, '').replace(/\.[^.]+$/, '').trim();

// Every raw stored formState (a saved connector loaded from localStorage, or
// a resumed working-state snapshot) must be defaults-merged before it enters
// live state: the schema has grown new fields over time (e.g. authSecretMode,
// authUcCredential), and an older persisted blob missing them would otherwise
// crash code that reads them without optional chaining (see
// validateFormState's formState.authToken.trim()). This also guarantees a
// scrubbed authToken always resolves to '' rather than undefined.
const mergeFormStateDefaults = (raw: Partial<ConfigFormState> | null | undefined): ConfigFormState => ({
	...INITIAL_FORM_STATE,
	...(raw ?? {}),
});

// Preview secrets (formState.authToken) must never be written to
// localStorage — they're session-only. Call this right before persisting
// any formState into savedConnectors or workingState.
const scrubAuthToken = (state: ConfigFormState): ConfigFormState => ({ ...state, authToken: '' });

const App: React.FC = () => {
	const [showLandingScreen, setShowLandingScreen] = React.useState(true);
	// Focus mode hands the whole width to the preview; session-only by design.
	const [focusPreview, setFocusPreview] = React.useState(false);
	const toggleFocusPreview = React.useCallback(() => setFocusPreview((value) => !value), []);
	const [configFormState, setConfigFormState] = useAtom(configFormStateAtom);
	const [builderView, setBuilderView] = useAtom(builderViewAtom);
	const [lastEdited, setLastEdited] = useAtom(lastEditedAtom);
	const [status, setStatus] = useAtom(statusAtom);
	const [isValidating, setIsValidating] = useAtom(isValidatingAtom);
	const [isSaving, setIsSaving] = useAtom(isSavingAtom);
	const [sample, setSample] = useAtom(sampleAtom);
	const [readerOptions, setReaderOptions] = useAtom(readerOptionsAtom);
	const streamOptions = useAtomValue(streamOptionsAtom);
	const configPayload = useAtomValue(configPayloadAtom);
	const [generatedCode, setGeneratedCode] = useAtom(generatedCodeAtom);
	const bearerToken = useAtomValue(bearerTokenAtom); // moved from inside handlePreview
	const setBearerToken = useSetAtom(bearerTokenAtom);
	const runtimeOptions = useAtomValue(runtimeOptionsAtom);
	const [savedConnectors, setSavedConnectors] = useAtom(savedConnectorsAtom);
	const [activeConnectorId, setActiveConnectorId] = useAtom(activeConnectorIdAtom);
	const [workingState, setWorkingState] = useAtom(workingStateAtom);
	const [showSaveModal, setShowSaveModal] = React.useState(false);
	const [saveFileName, setSaveFileName] = React.useState(`config${CONFIG_FILE_EXTENSION}`);
	const [saveDirHandle, setSaveDirHandle] = React.useState<any | null>(null); // directory handle
	const [saveDirName, setSaveDirName] = React.useState<string | null>(null);
	const [isRenamingConnector, setIsRenamingConnector] = React.useState(false);
	const [connectorNameDraft, setConnectorNameDraft] = React.useState('');
	const [appVersion, setAppVersion] = React.useState<string | null>(null);

	// Removed autoCreatedRef and auto-create behavior so refresh returns to landing screen
	// const autoCreatedRef = React.useRef(false);

	// feature detection for directory picker
const winRef = typeof window !== 'undefined' ? (window as any) : undefined;
const dirPickerSupported = !!(winRef && typeof winRef.showDirectoryPicker === 'function');
const filePickerSupported = !!(winRef && typeof winRef.showSaveFilePicker === 'function');
	const initialLoadRef = React.useRef(true);

	React.useEffect(() => {
		let cancelled = false;
		(async () => {
			try {
				const response = await fetch('/api/meta');
				if (!response.ok) return;
				const payload = (await response.json()) as { version?: string };
				if (!cancelled && payload?.version) {
					setAppVersion(payload.version);
				}
			} catch {
				/* ignore */
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	const currentConnector = React.useMemo(() => (
		savedConnectors.find((entry) => entry.id === activeConnectorId) ?? null
	), [savedConnectors, activeConnectorId]);

	const updateSaveFileName = React.useCallback((name: string) => {
		setSaveFileName(`${slugifyName(name)}${CONFIG_FILE_EXTENSION}`);
	}, [setSaveFileName]);

	const resetWorkingState = React.useCallback(() => {
		setSample(createSampleState());
		setIsValidating(false);
		setIsSaving(false);
	}, [setIsSaving, setIsValidating, setSample]);

	const generateConnectorName = React.useCallback((baseName?: string, existing: SavedConnector[] = savedConnectors) => {
		const trimmed = baseName && baseName.trim() ? baseName.trim() : 'Untitled connector';
		if (!existing.some((entry) => entry.name === trimmed)) {
			return trimmed;
		}
		let counter = 2;
		while (existing.some((entry) => entry.name === `${trimmed} (${counter})`)) {
			counter += 1;
		}
		return `${trimmed} (${counter})`;
	}, [savedConnectors]);

	const loadConnector = React.useCallback(
		(connector: SavedConnector, options?: { message?: string }) => {
			resetWorkingState();
			// Defaults-merge in case this connector was persisted by an older
			// schema version, then scrub any secret that older code may have
			// written into storage before saved connectors stopped persisting it.
			const effectiveFormState = scrubAuthToken(mergeFormStateDefaults(cloneFormState(connector.formState)));
			setActiveConnectorId(connector.id);
			setConfigFormState(effectiveFormState);
			setBearerToken('');
			setLastEdited(connector.lastEdited);
			setBuilderView(
				connector.builderView === 'code' || connector.builderView === 'deploy' ? connector.builderView : 'ui',
			);
			setReaderOptions({ ...connector.readerOptions });
			// Loading a connector is an explicit "work on something else" action —
			// drop any stale resumable draft so the landing screen doesn't offer
			// to resume into a session the user just navigated away from.
			setWorkingState(null);
			setStatus({ tone: 'info', message: options?.message ?? `Loaded ${connector.name}` });
			updateSaveFileName(connector.name);
			setShowLandingScreen(false);
			setIsRenamingConnector(false);
			setConnectorNameDraft('');
		},
		[
			resetWorkingState,
			setActiveConnectorId,
			setBearerToken,
			setBuilderView,
			setConfigFormState,
			setLastEdited,
			setReaderOptions,
			setShowLandingScreen,
			setStatus,
			setWorkingState,
			updateSaveFileName,
		],
	);

	const createConnector = React.useCallback(
		(options?: {
			name?: string;
			formState?: ConfigFormState;
			builderView?: 'ui' | 'code';
			readerOptions?: Record<string, string>;
			statusMessage?: string;
		}) => {
			const now = new Date().toISOString();
			const uniqueName = generateConnectorName(options?.name);
			const connector: SavedConnector = {
				id: createId('connector'),
				name: uniqueName,
				createdAt: now,
				updatedAt: now,
				formState: scrubAuthToken(mergeFormStateDefaults(cloneFormState(options?.formState ?? INITIAL_FORM_STATE))),
				lastEdited: 'ui',
				builderView: options?.builderView ?? 'ui',
				readerOptions: { ...(options?.readerOptions ?? {}) },
			};
			setSavedConnectors((prev) => [...prev, connector]);
			loadConnector(connector, { message: options?.statusMessage ?? `Created ${uniqueName}` });
		},
		[generateConnectorName, loadConnector, setSavedConnectors],
	);

	// Removed effect that auto-created a connector when none existed
	/* React.useEffect(() => {
		if (!autoCreatedRef.current && savedConnectors.length === 0) {
			autoCreatedRef.current = true;
			createConnector({ statusMessage: 'Started new connector' });
		}
	}, [savedConnectors, createConnector]); */

	const handleStartNewConnector = React.useCallback(() => {
		createConnector({ statusMessage: 'Ready to configure a new connector' });
	}, [createConnector]);

	const handleImportConnector = React.useCallback(
		(config: RestSourceConfig, meta?: { suggestedName?: string }) => {
			const formState = configToFormState(config);
			const derivedFromPath = (config.stream?.path || '').split('/').filter(Boolean).pop() || 'imported';
			const baseName = meta?.suggestedName ? stripExtension(meta.suggestedName) : derivedFromPath || 'Imported connector';
			createConnector({
				name: baseName,
				formState,
				statusMessage: `Loaded ${baseName}`,
			});
		},
		[createConnector],
	);

	const handleSelectSavedConnector = React.useCallback(
		(id: string) => {
			const connector = savedConnectors.find((entry) => entry.id === id);
			if (connector) {
				loadConnector(connector, { message: `Loaded ${connector.name}` });
			}
		},
		[savedConnectors, loadConnector],
	);

	const handleDeleteSavedConnector = React.useCallback(
		(id: string) => {
			const removed = savedConnectors.find((entry) => entry.id === id);
			const next = savedConnectors.filter((entry) => entry.id !== id);
			setSavedConnectors(next);
			if (removed) {
				setStatus({ tone: 'info', message: `Deleted ${removed.name}` });
			}
			if (workingState?.activeConnectorId === id) {
				// Don't leave a "Resume where you left off" card pointing at a
				// connector that no longer exists.
				setWorkingState(null);
			}
			if (id === activeConnectorId) {
				// If we're currently on the landing screen, don't auto-load another connector.
				if (showLandingScreen) {
					setActiveConnectorId(null);
					return;
				}
				if (next.length) {
					loadConnector(next[0], { message: `Loaded ${next[0].name}` });
				} else {
					setActiveConnectorId(null);
					setShowLandingScreen(true);
				}
			}
		},
		[activeConnectorId, loadConnector, savedConnectors, setActiveConnectorId, setSavedConnectors, setShowLandingScreen, setStatus, setWorkingState, showLandingScreen, workingState],
	);

	const handleExportSavedConnector = React.useCallback(
		(id: string) => {
			const connector = savedConnectors.find((entry) => entry.id === id);
			if (!connector) return;
			try {
				// Saved configs may be incomplete work-in-progress; export the raw
				// config dict as-is rather than requiring it to validate first.
				const configDict = formStateToConfig(mergeFormStateDefaults(connector.formState));
				const contents = JSON.stringify(configDict, null, 2);
				const blob = new Blob([contents], { type: 'application/json' });
				const link = document.createElement('a');
				link.href = URL.createObjectURL(blob);
				link.download = `${slugifyName(connector.name)}${CONFIG_FILE_EXTENSION}`;
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);
				URL.revokeObjectURL(link.href);
				setStatus({ tone: 'success', message: `Saved ${connector.name}` });
			} catch (error) {
				setStatus({ tone: 'error', message: formatError(error) });
			}
		},
		[savedConnectors, setStatus],
	);

	const handleRenameSavedConnector = React.useCallback(
		(id: string, name: string) => {
			const trimmed = name.trim() || 'Untitled connector';
			const nextName = generateConnectorName(trimmed, savedConnectors.filter((entry) => entry.id !== id));
			const updatedAt = new Date().toISOString();
			setSavedConnectors((prev) => prev.map((entry) => (entry.id === id ? { ...entry, name: nextName, updatedAt } : entry)));
			if (id === activeConnectorId) {
				setStatus({ tone: 'info', message: `Renamed connector to ${nextName}` });
				updateSaveFileName(nextName);
			}
		},
		[activeConnectorId, generateConnectorName, savedConnectors, setSavedConnectors, setStatus, updateSaveFileName],
	);

	const beginHeaderRename = React.useCallback(() => {
		if (!currentConnector) return;
		setIsRenamingConnector(true);
		setConnectorNameDraft(currentConnector.name);
	}, [currentConnector]);

	const commitHeaderRename = React.useCallback(() => {
		if (!currentConnector) return;
		handleRenameSavedConnector(currentConnector.id, connectorNameDraft);
		setIsRenamingConnector(false);
		setConnectorNameDraft('');
	}, [connectorNameDraft, currentConnector, handleRenameSavedConnector]);

	const cancelHeaderRename = React.useCallback(() => {
		setIsRenamingConnector(false);
		setConnectorNameDraft('');
	}, []);

	const openConnectorLibrary = React.useCallback(() => {
		setShowLandingScreen(true);
		setIsRenamingConnector(false);
		setConnectorNameDraft('');
	}, [setShowLandingScreen]);

	const savedConnectorSummaries = React.useMemo(
		() =>
			[...savedConnectors]
				.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
				.map(({ id, name, createdAt, updatedAt }) => ({ id, name, createdAt, updatedAt })),
		[savedConnectors],
	);

	// Drives the landing screen's "Resume where you left off" card. Only
	// surfaced once something was actually configured — a working-state
	// snapshot of an untouched blank form isn't worth resuming into.
	const workingStateSummary = React.useMemo(() => {
		if (!workingState) return null;
		const fs = workingState.formState;
		const hasContent = !!(fs.baseUrl?.trim() || fs.streamPath?.trim() || fs.streamName?.trim());
		if (!hasContent) return null;
		const linkedConnector = workingState.activeConnectorId
			? savedConnectors.find((entry) => entry.id === workingState.activeConnectorId)
			: undefined;
		const label = linkedConnector?.name
			|| fs.streamName?.trim()
			|| fs.streamPath?.trim()
			|| fs.baseUrl?.trim()
			|| 'Untitled connector';
		return { label, savedAt: workingState.savedAt };
	}, [savedConnectors, workingState]);

	const handleResumeWorkingState = React.useCallback(() => {
		if (!workingState) return;
		resetWorkingState();
		const restoredFormState = mergeFormStateDefaults(cloneFormState(workingState.formState));
		setConfigFormState(restoredFormState);
		// The working state never carries authToken (session-only secret) —
		// make sure no stale preview value lingers from a prior session either.
		setBearerToken('');
		setActiveConnectorId(workingState.activeConnectorId);
		setBuilderView(workingState.builderView);
		setReaderOptions({ ...workingState.readerOptions });
		setLastEdited('ui');
		updateSaveFileName(restoredFormState.streamName || restoredFormState.streamPath || 'config');
		setStatus({ tone: 'info', message: 'Resumed your last working session — re-enter any preview secret.' });
		setShowLandingScreen(false);
		setIsRenamingConnector(false);
		setConnectorNameDraft('');
	}, [
		resetWorkingState,
		setActiveConnectorId,
		setBearerToken,
		setBuilderView,
		setConfigFormState,
		setLastEdited,
		setReaderOptions,
		setShowLandingScreen,
		setStatus,
		updateSaveFileName,
		workingState,
	]);

	const handleDiscardWorkingState = React.useCallback(() => {
		setWorkingState(null);
	}, [setWorkingState]);

	React.useEffect(() => {
		setIsRenamingConnector(false);
		setConnectorNameDraft('');
	}, [currentConnector?.id]);

	React.useEffect(() => {
		if (!activeConnectorId) return;
		// Do not sync while on landing screen (avoids wiping saved connector with empty draft after refresh)
		if (showLandingScreen) return;
		const handle = window.setTimeout(() => {
			setSavedConnectors((prev) => prev.map((entry) => {
				if (entry.id !== activeConnectorId) return entry;
				return {
					...entry,
					// Saved connectors never carry the preview secret — it's
					// session-only, scrubbed before this hits localStorage.
					formState: scrubAuthToken(cloneFormState(configFormState)),
					lastEdited,
					builderView,
					readerOptions: { ...readerOptions },
					updatedAt: new Date().toISOString(),
				};
			}));
		}, 400);
		return () => window.clearTimeout(handle);
	}, [activeConnectorId, builderView, configFormState, lastEdited, readerOptions, setSavedConnectors, showLandingScreen]);

	// Snapshot the in-progress editor session into workingStateAtom
	// (localStorage) any time it changes, debounced ~500ms, whenever the
	// editor is actually open. This is the fix for imported-but-unsaved
	// work vanishing on reload: unlike the savedConnectors sync above (which
	// only ever touches the entry matching activeConnectorId once one
	// exists), this always captures the live editor state, independent of
	// whether/when a save has happened. authToken is stripped — preview
	// secrets are never written to storage.
	React.useEffect(() => {
		if (showLandingScreen) return;
		const handle = window.setTimeout(() => {
			setWorkingState({
				formState: scrubAuthToken(cloneFormState(configFormState)),
				readerOptions: { ...readerOptions },
				builderView,
				activeConnectorId,
				savedAt: new Date().toISOString(),
			});
		}, 500);
		return () => window.clearTimeout(handle);
	}, [activeConnectorId, builderView, configFormState, readerOptions, setWorkingState, showLandingScreen]);

	// Instead, just mark initialLoadRef consumed once after first render
	React.useEffect(() => { if (initialLoadRef.current) initialLoadRef.current = false; }, []);

	// Regenerate the PySpark script pane whenever the form-state config dict
	// changes, debounced by 400ms. Replaces the old client-side form-state ->
	// YAML derivation now that codegen happens on the backend.
	React.useEffect(() => {
		if (showLandingScreen) return;
		if (!configFormState.baseUrl.trim()) {
			setGeneratedCode({ script: "", stream: "", error: null, loading: false });
			return;
		}
		setGeneratedCode((prev) => ({ ...prev, loading: true }));
		let cancelled = false;
		const handle = window.setTimeout(() => {
			const configDict = formStateToConfig(configFormState);
			generateScript(configDict)
				.then((result) => {
					if (cancelled) return;
					setGeneratedCode({ script: result.script, stream: result.stream, error: null, loading: false });
				})
				.catch((error) => {
					if (cancelled) return;
					setGeneratedCode((prev) => ({ ...prev, script: "", error: formatError(error), loading: false }));
				});
		}, 400);
		return () => {
			cancelled = true;
			window.clearTimeout(handle);
		};
	}, [configFormState, setGeneratedCode, showLandingScreen]);

	const busy = sample.loading || isValidating;
	const [validateFlashClass, setValidateFlashClass] = React.useState('');
	React.useEffect(() => {
		let timeoutId: number | undefined;
		if (!isValidating && (status.tone === 'success' || status.tone === 'error')) {
			setValidateFlashClass(status.tone === 'success' ? 'validate-flash-success' : 'validate-flash-error');
			timeoutId = window.setTimeout(() => setValidateFlashClass(''), 700);
		}
		return () => { if (timeoutId) window.clearTimeout(timeoutId); };
	}, [isValidating, status.tone]);

	const handleUpdateFormState = React.useCallback(
		(patch: Partial<ConfigFormState>) => {
			setConfigFormState((prev) => ({ ...prev, ...patch }));
			setLastEdited("ui");
		},
		[setConfigFormState, setLastEdited],
	);

	const handleAddParam = React.useCallback(() => {
		const newKey = ``;
		setConfigFormState((prev) => ({
			...prev,
			params: { ...prev.params, [newKey]: "" }
		}));
		setLastEdited("ui");
	}, [setConfigFormState, setLastEdited]);

	const handleRemoveParam = React.useCallback((key: string) => {
		setConfigFormState((prev) => {
			const { [key]: removed, ...rest } = prev.params;
			return { ...prev, params: rest };
		});
		setLastEdited("ui");
	}, [setConfigFormState, setLastEdited]);

	const handleUpdateParam = React.useCallback((oldKey: string, newKey: string, value: string) => {
		setConfigFormState((prev) => {
			const newParams = { ...prev.params };
			if (oldKey !== newKey) {
				delete newParams[oldKey];
			}
			newParams[newKey] = value;
			return { ...prev, params: newParams };
		});
		setLastEdited("ui");
	}, [setConfigFormState, setLastEdited]);

	const applyValidationPayload = React.useCallback(
		(payload: ValidationResponse) => {
			if (!payload.valid || !payload.config) return;

			const nextState = configToFormState(payload.config);
			// Preserve existing auth details since backend strips secrets.
			if (configFormState.authType !== 'none') {
				nextState.authType = configFormState.authType;
				nextState.authToken = configFormState.authToken;
				nextState.authApiKeyIn = configFormState.authApiKeyIn;
				nextState.authApiKeyName = configFormState.authApiKeyName;
				nextState.authTokenUrl = configFormState.authTokenUrl;
				nextState.authClientId = configFormState.authClientId;
				nextState.authScopes = configFormState.authScopes;
				nextState.authAudience = configFormState.authAudience;
				nextState.authExtraParams = configFormState.authExtraParams;
			}
			setConfigFormState(nextState);
		},
		[setConfigFormState, configFormState]
	);

	const runValidation = React.useCallback(
		async ({ applyResponse = true }: { applyResponse?: boolean } = {}) => {
			// Gate on the same client-side validation the Deploy tab's Bootstrap
			// button uses before hitting the backend. Without this, an invalid
			// config (e.g. API Key auth with an empty header/query name) would
			// silently drop its auth block and fire an unauthenticated request.
			const formErrors = validateFormState(configFormState);
			if (formErrors.length > 0) {
				throw new Error(formErrors.join('; '));
			}
			setIsValidating(true);
			try {
				const shouldSendToken = configFormState.authType === 'bearer' || configFormState.authType === 'oauth2' || configFormState.authType === 'api_key';
				const authSecret = shouldSendToken ? bearerToken : '';
				const payload = await validateConfigRequest({
					...configPayload,
					...(authSecret ? { token: authSecret } : {}),
					options: runtimeOptions,
				});

				if (applyResponse) {
					applyValidationPayload(payload);
				}

				return payload;
			} finally {
				setIsValidating(false);
			}
		},
		[applyValidationPayload, configFormState, configPayload, setIsValidating, bearerToken, runtimeOptions]
	);

	const handleValidate = React.useCallback(async () => {
		try {
			setStatus({ tone: "info", message: "Validating configuration…" });
			const result = await runValidation({ applyResponse: true });

			if (result.valid) {
				setStatus({ tone: "success", message: "Configuration is valid" });
			} else {
				setStatus({ tone: "error", message: result.message || "Configuration is invalid" });
			}
		} catch (error) {
			setStatus({ tone: "error", message: formatError(error) });
		}
	}, [runValidation, setStatus]);

	const handlePreview = React.useCallback(async () => {
		if (!streamOptions.length) {
			setStatus({ tone: "warn", message: "Add a stream with a name before sampling." });
			return;
		}

		const nextLimit = Math.min(MAX_SAMPLE_ROWS, Math.max(1, Math.round(sample.limit)));
		// use top-level captured bearerToken instead of hook call here
		setSample((prev) => ({
			...prev,
			limit: nextLimit,
			loading: true,
			view: SAMPLE_VIEWS.TABLE,
			page: 1,
			rawPages: [],
			restError: null,
		}));
		setStatus({ tone: "info", message: "Validating configuration…" });

		try {
			// Don't apply the validation response to form state during preview
			await runValidation({ applyResponse: false });
			setStatus({ tone: "info", message: "Fetching sample..." });
				const shouldSendToken = configFormState.authType === 'bearer' || configFormState.authType === 'oauth2' || configFormState.authType === 'api_key';
				const authSecret = shouldSendToken ? bearerToken : '';
				const payload = await sampleRequest({
					...configPayload,
					...(authSecret ? { token: authSecret } : {}),
					limit: nextLimit,
					options: runtimeOptions,
				});
			const records = Array.isArray(payload.records) ? payload.records : [];
			const truncated = records.slice(0, MAX_SAMPLE_ROWS);
			const rowCount = truncated.length;
			const rawPages = Array.isArray(payload.raw_pages) ? payload.raw_pages : [];
			const restError = payload.rest_error ?? null;
			setSample((prev) => ({
				...prev,
				data: truncated,
				dtypes: payload.dtypes || [],
				rawPages,
				restError,
				loading: false,
				view: restError ? SAMPLE_VIEWS.RAW : SAMPLE_VIEWS.TABLE,
			}));

			if (restError) {
				setStatus({ tone: "error", message: restError });
			} else {
				setStatus({
					tone: "success",
					message: `Fetched ${rowCount} sample record${rowCount === 1 ? "" : "s"}`,
				});
			}
		} catch (error) {
			setSample((prev) => ({ ...prev, loading: false }));
			setStatus({ tone: "error", message: formatError(error) });
		}
	}, [configFormState.authType, configPayload, runValidation, sample.limit, sample.stream, setSample, setStatus, streamOptions, bearerToken, runtimeOptions]);

	const handleViewChange = React.useCallback(
		(value: string) => {
			setBuilderView(value === "code" ? "code" : value === "deploy" ? "deploy" : "ui");
		},
		[setBuilderView],
	);

	const handleSampleViewChange = React.useCallback(
		(value: "table" | "json" | "raw") => {
			setSample((prev) => ({ ...prev, view: value }));
		},
		[setSample],
	);

	const handleWrapToggle = React.useCallback(() => {
		setSample((prev) => ({ ...prev, wrap: !prev.wrap }));
	}, [setSample]);

	const handleLimitChange = React.useCallback(
		(value: number) => {
			setSample((prev) => ({ ...prev, limit: value }));
		},
		[setSample],
	);

	const handlePageSizeChange = React.useCallback(
		(value: number) => {
			setSample((prev) => ({ ...prev, pageSize: value, page: 1 }));
		},
		[setSample],
	);

	const handlePageChange = React.useCallback(
		(value: number) => {
			setSample((prev) => ({ ...prev, page: value }));
		},
		[setSample],
	);

	// Directory chooser (added)
	const handleChooseDirectory = React.useCallback(async () => {
		if (!dirPickerSupported) return; // silent no-op if unsupported
		try {
			const w: any = window as any;
			const dir = await w.showDirectoryPicker({ mode: 'readwrite' });
			setSaveDirHandle(dir);
			setSaveDirName(dir.name || 'selected');
		} catch {
			/* user cancelled */
		}
	}, [dirPickerSupported]);

	const handleSave = React.useCallback(async (explicitName?: string) => {
		if (isSaving) return;
		const defaultName = `config${CONFIG_FILE_EXTENSION}`;
		const targetName = (explicitName || saveFileName || defaultName).trim() || defaultName;
		setIsSaving(true);
		setStatus({ tone: "info", message: "Saving…" });
		try {
			// Work-in-progress configs may not be complete/valid yet; save the
			// current form state as-is so it can be reloaded and finished later.
			const contents = JSON.stringify(configPayload.config_dict, null, 2);
			await downloadTextFile(contents, targetName, saveDirHandle, 'application/json');
			setStatus({ tone: "success", message: `Saved ${saveDirName ? saveDirName + '/' : ''}${targetName}` });
			window.setTimeout(() => {
				setStatus({ tone: "info", message: "Ready to configure" });
			}, 3000);
		} catch (error) {
			setStatus({ tone: "error", message: formatError(error) });
		} finally {
			setIsSaving(false);
		}
	}, [isSaving, configPayload, saveFileName, saveDirHandle, saveDirName, setIsSaving, setStatus]);

	const openSaveModal = React.useCallback(() => {
		setSaveFileName(configFileName(generatedCode.stream || configFormState.streamPath));
		setShowSaveModal(true);
	}, [configFormState.streamPath, generatedCode.stream]);

	React.useEffect(() => {
		const handler = (event: KeyboardEvent) => {
			if ((event.metaKey || event.ctrlKey) && event.key === "s") {
				event.preventDefault();
				openSaveModal();
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [openSaveModal]);

	// Theme management (light/dark/system)
	const getSystemDark = () => (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches);
	const [themeMode, setThemeMode] = React.useState<'light' | 'dark' | 'system'>(() => {
		if (typeof window === 'undefined') return 'light';
		const stored = localStorage.getItem('polymo-theme-mode');
		if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
		return 'system';
	});
	// Tracked as state so a live OS theme change re-renders the app (theme
	// menu label, `key={effectiveTheme}` fade) instead of only toggling the
	// root class behind React's back.
	const [systemDark, setSystemDark] = React.useState<boolean>(() => getSystemDark());
	const effectiveTheme = themeMode === 'system' ? (systemDark ? 'dark' : 'light') : themeMode;

	React.useEffect(() => {
		const root = document.documentElement;
		if (effectiveTheme === 'dark') root.classList.add('dark'); else root.classList.remove('dark');
	}, [effectiveTheme]);

	React.useEffect(() => {
		localStorage.setItem('polymo-theme-mode', themeMode);
	}, [themeMode]);

	React.useEffect(() => {
		const mq = window.matchMedia('(prefers-color-scheme: dark)');
		const handler = () => setSystemDark(mq.matches);
		handler();
		mq.addEventListener('change', handler);
		return () => mq.removeEventListener('change', handler);
	}, []);

	const handleCopySchema = React.useCallback(() => {
		let ddl: string;
		if (sample.dtypes && sample.dtypes.length) {
			// Single-line comma separated DDL
			ddl = sample.dtypes.map((d: { column: string; type: string }) => `${d.column} ${d.type}`).join(', ');
		} else if (configFormState.schema.trim()) {
			ddl = configFormState.schema.trim();
		} else {
			ddl = '# No schema available yet – run a Preview to infer or provide a schema.';
		}
		try {
			void navigator.clipboard.writeText(ddl);
			setStatus({ tone: 'success', message: 'Schema copied to clipboard' });
		} catch {
			const temp = document.createElement('textarea');
			temp.value = ddl;
			temp.style.position = 'fixed';
			temp.style.left = '-9999px';
			document.body.appendChild(temp);
			temp.select();
			try { document.execCommand('copy'); } catch { /* ignore */ }
			document.body.removeChild(temp);
			setStatus({ tone: 'success', message: 'Schema copied (fallback)' });
		}
	}, [configFormState.schema, sample.dtypes, setStatus]);

	// After a successful sample run, flag any OPT_<NAME> placeholders left
	// unresolved in the generated script (unresolved {{ options.* }}
	// references). Preview requests send the literal "REPLACE_ME" for these,
	// which otherwise looks like real data with no explanation.
	const placeholderNotice = React.useMemo(() => {
		if (sample.loading) return null;
		if (!sample.data.length && !sample.rawPages.length) return null;
		const names = findUnresolvedOptionPlaceholders(generatedCode.script);
		if (!names.length) return null;
		return `This config references runtime options (${names.join(', ')}) that preview sends as "REPLACE_ME" — remove leftover {{ options.* }} params or fill them at deploy time.`;
	}, [sample.loading, sample.data.length, sample.rawPages.length, generatedCode.script]);

	const tabTriggerClass =
		"h-7 whitespace-nowrap rounded-[5px] px-3 text-xs font-medium text-fg-muted transition-colors hover:text-fg data-[state=active]:bg-accent data-[state=active]:text-accent-fg data-[state=active]:shadow-sm focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:bg-raised";
	const activeTabLabel = builderView === "code" ? "Generated code" : builderView === "deploy" ? "Deploy" : "Configuration";

	const primaryPane = (
		<section
			className="pane flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-card"
			aria-label="Connector configuration"
		>
			<Tabs.Root value={builderView} onValueChange={handleViewChange} className="flex h-full min-h-0 flex-col">
				<div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-border px-3">
					<Tabs.List className="inline-flex rounded-md border border-border bg-field p-0.5" aria-label="Builder view">
						<Tabs.Trigger value="ui" className={tabTriggerClass} aria-label="UI Builder">
							<span className="label-long">UI Builder</span>
							<span className="label-short">Builder</span>
						</Tabs.Trigger>
						<Tabs.Trigger value="code" className={tabTriggerClass} aria-label="Generated Code">
							<span className="label-long">Generated Code</span>
							<span className="label-short">Code</span>
						</Tabs.Trigger>
						<Tabs.Trigger value="deploy" className={tabTriggerClass}>
							Deploy
						</Tabs.Trigger>
					</Tabs.List>
					<div className="flex items-center gap-2">
						<button
							type="button"
							className={cx(BTN_SECONDARY, "h-8 px-3 text-xs", validateFlashClass)}
							onClick={handleValidate}
							disabled={busy}
						>
							{isValidating ? 'Validating…' : 'Validate'}
						</button>
						<button
							type="button"
							className={cx(BTN_PRIMARY, "h-8 px-3.5 text-xs")}
							onClick={openSaveModal}
							disabled={busy}
							data-testid="open-export-modal"
							aria-label="Save config"
						>
							<span className="label-long">Save config</span>
							<span className="label-short">Save</span>
						</button>
					</div>
				</div>
				<Tabs.Content value="ui" className="scroll-thin min-h-0 flex-1 overflow-y-auto px-5 py-5 outline-none">
					<BuilderPanel
						state={configFormState}
						onUpdateState={handleUpdateFormState}
						onAddParam={handleAddParam}
						onRemoveParam={handleRemoveParam}
						onUpdateParam={handleUpdateParam}
					/>
				</Tabs.Content>
				<Tabs.Content value="code" className="min-h-0 flex-1 px-5 py-4 outline-none">
					<CodePane
						script={generatedCode.script}
						stream={generatedCode.stream}
						error={generatedCode.error}
						loading={generatedCode.loading}
						emptyMessage={
							configFormState.baseUrl.trim()
								? undefined
								: "Fill in a base URL to see the generated script."
						}
					/>
				</Tabs.Content>
				<Tabs.Content value="deploy" className="scroll-thin min-h-0 flex-1 overflow-y-auto px-5 py-5 outline-none">
					<DeployPanel />
				</Tabs.Content>
			</Tabs.Root>
		</section>
	);

	const secondaryPane = (
		<section
			className="pane flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-card"
			aria-label="Data preview"
		>
			<SamplePreview
				status={status}
				limit={sample.limit}
				onLimitChange={handleLimitChange}
				onPreview={handlePreview}
				isBusy={busy}
				view={sample.view}
				onViewChange={handleSampleViewChange}
				wrap={sample.wrap}
				onWrapToggle={handleWrapToggle}
				page={sample.page}
				pageSize={sample.pageSize}
				onPageSizeChange={handlePageSizeChange}
				onPageChange={handlePageChange}
				data={sample.data}
				dtypes={sample.dtypes}
				rawPages={sample.rawPages}
				restError={sample.restError}
				onCopySchema={handleCopySchema}
				placeholderNotice={placeholderNotice}
				focus={focusPreview}
				onToggleFocus={toggleFocusPreview}
			/>
		</section>
	);

	return (
		<div key={effectiveTheme} className="theme-fade flex h-screen flex-col overflow-hidden bg-background text-fg">
			<header className="z-20 shrink-0 border-b border-border bg-surface">
				<div className="flex h-12 w-full items-center justify-between gap-4 px-4">
					<div className="flex min-w-0 items-center gap-2.5">
						<div className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full bg-accent-soft">
							<img
								src={import.meta.env.DEV ? "/favicon.ico" : "/static/favicon.ico"}
								alt="polymo Logo"
								className="h-6 w-6 object-contain"
							/>
						</div>
						<div className="flex min-w-0 items-baseline gap-2 leading-tight select-none">
							<h1 className="text-sm font-semibold text-fg">Connector Builder</h1>
							{appVersion && (
								<span className="font-mono text-[11px] text-fg-subtle">v{appVersion}</span>
							)}
						</div>
						{currentConnector && (
							<>
								<span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
								{isRenamingConnector ? (
									<div className="flex items-center gap-1.5">
										<input
											autoFocus
											className={cx(INPUT, "h-8 w-56 text-sm")}
											value={connectorNameDraft}
											onChange={(e) => setConnectorNameDraft(e.target.value)}
											onKeyDown={(e) => {
												if (e.key === 'Enter') {
													e.preventDefault();
													commitHeaderRename();
												} else if (e.key === 'Escape') {
													cancelHeaderRename();
												}
											}}
											onBlur={commitHeaderRename}
											aria-label="Connector name"
										/>
										<button
											type="button"
											className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-accent text-accent-fg hover:bg-accent-hover"
											onClick={commitHeaderRename}
											aria-label="Save name"
										>
											<svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
												<path fillRule="evenodd" d="M16.704 5.29a1 1 0 010 1.42l-7.5 7.5a1 1 0 01-1.42 0l-3.5-3.5a1 1 0 111.42-1.42L8.5 11.58l6.79-6.79a1 1 0 011.414 0z" clipRule="evenodd" />
											</svg>
										</button>
										<button
											type="button"
											className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border text-fg-muted hover:text-error"
											onClick={cancelHeaderRename}
											aria-label="Cancel rename"
										>
											<svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
												<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
											</svg>
										</button>
									</div>
								) : (
									<button
										type="button"
										className="group inline-flex h-8 min-w-0 items-center gap-1.5 rounded-md px-2 text-sm font-medium text-fg hover:bg-raised"
										onClick={beginHeaderRename}
										title="Rename connector"
									>
										<span className="truncate">{currentConnector.name}</span>
										<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5 shrink-0 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true">
											<path d="M10.5 2.5 13.5 5.5 6 13H3v-3z" />
										</svg>
									</button>
								)}
							</>
						)}
					</div>
					<div className="flex shrink-0 items-center gap-2">
						<button
							type="button"
							className={cx(BTN_SECONDARY, "h-8 px-3 text-xs")}
							onClick={openConnectorLibrary}
							data-testid="open-connector-library"
						>
							Connectors
						</button>
						<button
							type="button"
							className={cx(BTN_SECONDARY, "h-8 px-3 text-xs")}
							onClick={() => currentConnector && handleExportSavedConnector(currentConnector.id)}
							disabled={!currentConnector}
						>
							Save config
						</button>
						<ThemeMenu mode={themeMode} effective={effectiveTheme} onChange={setThemeMode} />
					</div>
				</div>
			</header>
			{showLandingScreen ? (
				<main className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 py-8 lg:px-6">
					<LandingScreen
						onStartNew={handleStartNewConnector}
						onImportConfig={handleImportConnector}
						savedConnectors={savedConnectorSummaries}
						onSelectSaved={handleSelectSavedConnector}
						onDeleteSaved={handleDeleteSavedConnector}
						onExportSaved={handleExportSavedConnector}
						workingState={workingStateSummary}
						onResumeWorking={handleResumeWorkingState}
						onDiscardWorking={handleDiscardWorkingState}
					/>
				</main>
			) : (
				<main className="min-h-0 flex-1 p-3">
					<SplitLayout primary={primaryPane} secondary={secondaryPane} focus={focusPreview} railLabel={activeTabLabel} />
				</main>
			)}
			{showSaveModal && (
				<div className="fixed inset-0 z-50 flex items-center justify-center p-4">
					<div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => !isSaving && setShowSaveModal(false)} />
					<div role="dialog" aria-modal="true" className="relative z-10 flex w-full max-w-md flex-col gap-5 rounded-xl border border-border bg-surface p-6 shadow-card">
						<header className="flex items-start justify-between gap-4">
							<h2 className="text-base font-semibold text-fg">Save config</h2>
						</header>
						<div className="space-y-4">
							<Field label="File name">
								<input
									type="text"
									className={cx(INPUT, "font-mono text-xs")}
									value={saveFileName}
									onChange={(e) => setSaveFileName(e.target.value)}
									placeholder={`config${CONFIG_FILE_EXTENSION}`}
									data-testid="export-file-name-input"
								/>
							</Field>
							<div className="flex items-center gap-3">
								{dirPickerSupported ? (
									<button
										type="button"
										className={cx(BTN_SECONDARY, BTN_SMALL)}
										onClick={handleChooseDirectory}
										disabled={isSaving}
									>
										{saveDirName ? 'Change folder' : 'Choose folder'}
									</button>
								) : (
									<span className="rounded-md border border-border bg-raised px-2.5 py-1 text-xs text-fg-muted">
										Folder selection not available in this browser
									</span>
								)}
								{saveDirName && dirPickerSupported && <span className="max-w-[160px] truncate font-mono text-xs text-fg-muted" title={saveDirName}>{saveDirName}/</span>}
							</div>
							<p className="text-xs leading-relaxed text-fg-muted">
								{dirPickerSupported
									? (saveDirName ? 'Will write directly into the selected folder (if permissions granted).' : 'Select a folder for direct write or leave blank to download.')
									: (filePickerSupported
										? 'Safari will prompt you to choose a location when you click Save.'
										: 'The file will download automatically when you click Save.')}
							</p>
						</div>
						<div className="flex justify-end gap-2 pt-1">
							<button
								type="button"
								className={BTN_SECONDARY}
								onClick={() => !isSaving && setShowSaveModal(false)}
								disabled={isSaving}
							>
								Cancel
							</button>
							<button
								type="button"
								className={BTN_PRIMARY}
								onClick={() => { setShowSaveModal(false); handleSave(saveFileName); }}
								disabled={isSaving || !saveFileName.trim()}
								data-testid="confirm-export"
							>
								{isSaving ? 'Saving…' : 'Save'}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};



function formatError(error: unknown): string {
	if (error instanceof Error) {
		return error.message;
	}
	return String(error ?? "Unknown error");
}

function downloadTextFile(contents: string, fileName = 'config.txt', directoryHandle?: any, mimeType = 'text/plain') {
	const writeToDirectory = async () => {
		if (!directoryHandle) return false;
		try {
			// Ensure permission
			if (directoryHandle.queryPermission) {
				let perm = await directoryHandle.queryPermission({ mode: 'readwrite' });
				if (perm === 'prompt' && directoryHandle.requestPermission) {
					perm = await directoryHandle.requestPermission({ mode: 'readwrite' });
				}
				if (perm !== 'granted') return false;
			}
			const fileHandle = await directoryHandle.getFileHandle(fileName, { create: true });
			const writable = await fileHandle.createWritable();
			await writable.write(contents);
			await writable.close();
			return true;
		} catch (e) {
			return false;
		}
	};
	const saveWithPicker = async () => {
		try {
			const w: any = window as any;
			if (w.showSaveFilePicker) {
				const handle = await w.showSaveFilePicker({
					suggestedName: fileName,
					types: [
						{
							description: mimeType === 'application/json' ? 'JSON Files' : 'Text Files',
							accept: { [mimeType]: mimeType === 'application/json' ? ['.json'] : ['.txt', '.py', '.text'] },
						},
					],
				});
				const writable = await handle.createWritable();
				await writable.write(contents);
				await writable.close();
				return true;
			}
		} catch (e) {
			// user may have cancelled
		}
		return false;
	};
	void (async () => {
		if (await writeToDirectory()) return;
		if (await saveWithPicker()) return;
		// Fallback anchor download
		const blob = new Blob([contents], { type: mimeType });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = fileName;
		document.body.appendChild(anchor);
		anchor.click();
		document.body.removeChild(anchor);
		URL.revokeObjectURL(url);
	})();
}

export default App;
