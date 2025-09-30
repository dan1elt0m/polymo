import React from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { useAtom, useAtomValue } from "jotai";
import {
	configFormStateAtom,
	builderViewAtom,
	yamlTextAtom,
	yamlErrorAtom,
	lastEditedAtom,
	statusAtom,
	isValidatingAtom,
	isSavingAtom,
	sampleAtom,
	streamOptionsAtom,
	configPayloadAtom,
	formStateToYamlAtom,
	bearerTokenAtom,
	runtimeOptionsAtom,
	readerOptionsAtom,
	savedConnectorsAtom,
	activeConnectorIdAtom,
	DEFAULT_SAMPLE_STATE,
} from "./atoms";
import { configToFormState, formStateToConfig } from "./lib/transform";
import { validateConfigRequest, sampleRequest } from "./lib/api";
import { BuilderPanel } from "./components/BuilderPanel";
import { YamlEditor } from "./components/YamlEditor";
import { SamplePreview } from "./components/SamplePreview";
import { ThemeMenu } from "./components/ThemeMenu";
import { LandingScreen } from "./components/LandingScreen";
import type { ConfigFormState, ValidationResponse, RestSourceConfig, SavedConnector } from "./types";
import { MAX_SAMPLE_ROWS, SAMPLE_VIEWS } from "./lib/constants";
import yaml from 'js-yaml';
import { INITIAL_FORM_STATE } from "./lib/initial-data";
import { createId } from "./lib/id";

const cloneFormState = (state: ConfigFormState): ConfigFormState => JSON.parse(JSON.stringify(state));

const createSampleState = () => JSON.parse(JSON.stringify(DEFAULT_SAMPLE_STATE));

const slugify = (value: string): string => {
	return value
		.toLowerCase()
		.trim()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '') || 'connector';
};

const stripExtension = (name: string): string => name.replace(/\.[^.]+$/, '').trim();

const App: React.FC = () => {
	const [showLandingScreen, setShowLandingScreen] = React.useState(true);
	const [configFormState, setConfigFormState] = useAtom(configFormStateAtom);
	const [builderView, setBuilderView] = useAtom(builderViewAtom);
	const [yamlText, setYamlText] = useAtom(yamlTextAtom);
	const [yamlError, setYamlError] = useAtom(yamlErrorAtom);
	const [lastEdited, setLastEdited] = useAtom(lastEditedAtom);
	const [status, setStatus] = useAtom(statusAtom);
	const [isValidating, setIsValidating] = useAtom(isValidatingAtom);
	const [isSaving, setIsSaving] = useAtom(isSavingAtom);
	const [sample, setSample] = useAtom(sampleAtom);
	const [readerOptions, setReaderOptions] = useAtom(readerOptionsAtom);
	const streamOptions = useAtomValue(streamOptionsAtom);
	const configPayload = useAtomValue(configPayloadAtom);
	const formStateYaml = useAtomValue(formStateToYamlAtom);
	const bearerToken = useAtomValue(bearerTokenAtom); // moved from inside handlePreview
	const runtimeOptions = useAtomValue(runtimeOptionsAtom);
	const [savedConnectors, setSavedConnectors] = useAtom(savedConnectorsAtom);
	const [activeConnectorId, setActiveConnectorId] = useAtom(activeConnectorIdAtom);
	const [yamlErrorLine, setYamlErrorLine] = React.useState<number | null>(null);
	const [yamlErrorCol, setYamlErrorCol] = React.useState<number | null>(null);
	const [yamlSnapshot, setYamlSnapshot] = React.useState<string | null>(null);
	const [formSnapshot, setFormSnapshot] = React.useState<ConfigFormState | null>(null);
	const [showYamlInvalidModal, setShowYamlInvalidModal] = React.useState(false);
	const [showSaveModal, setShowSaveModal] = React.useState(false);
	const [saveFileName, setSaveFileName] = React.useState('config.yml');
	const [saveDirHandle, setSaveDirHandle] = React.useState<any | null>(null); // directory handle
	const [saveDirName, setSaveDirName] = React.useState<string | null>(null);
	const [isRenamingConnector, setIsRenamingConnector] = React.useState(false);
	const [connectorNameDraft, setConnectorNameDraft] = React.useState('');

	// Removed autoCreatedRef and auto-create behavior so refresh returns to landing screen
	// const autoCreatedRef = React.useRef(false);

	// feature detection for directory picker
	const dirPickerSupported = typeof window !== 'undefined' && 'showDirectoryPicker' in window;
	const initialLoadRef = React.useRef(true);

	const currentConnector = React.useMemo(() => (
		savedConnectors.find((entry) => entry.id === activeConnectorId) ?? null
	), [savedConnectors, activeConnectorId]);

	const updateSaveFileName = React.useCallback((name: string) => {
		setSaveFileName(`${slugify(name)}.yml`);
	}, [setSaveFileName]);

	const resetWorkingState = React.useCallback(() => {
		setSample(createSampleState());
		setYamlError(null);
		setYamlErrorLine(null);
		setYamlErrorCol(null);
		setYamlSnapshot(null);
		setFormSnapshot(null);
		setIsValidating(false);
		setIsSaving(false);
	}, [setFormSnapshot, setIsSaving, setIsValidating, setSample, setYamlError, setYamlErrorCol, setYamlErrorLine, setYamlSnapshot]);

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
			let effectiveFormState = cloneFormState(connector.formState);
			// Fallback: if the stored formState looks empty but we have YAML, attempt to rebuild from YAML
			const looksEmpty = !effectiveFormState.baseUrl && !effectiveFormState.streamPath && Object.keys(effectiveFormState.params || {}).length === 0;
			if (looksEmpty && connector.yaml && connector.yaml.trim().length) {
				try {
					const loaded: any = yaml.load(connector.yaml) || {};
					if (loaded && typeof loaded === 'object') {
						const parsed = configToFormState(loaded as RestSourceConfig);
						// Preserve auth fields from existing state if any
						parsed.authType = effectiveFormState.authType || parsed.authType;
						parsed.authToken = effectiveFormState.authToken || parsed.authToken;
						effectiveFormState = cloneFormState(parsed);
					}
				} catch {/* ignore parse errors; keep existing */}
			}
			setActiveConnectorId(connector.id);
			setConfigFormState(effectiveFormState);
			setYamlText(connector.yaml);
			setLastEdited(connector.lastEdited);
			setBuilderView(connector.builderView ?? 'ui');
			setReaderOptions({ ...connector.readerOptions });
			setStatus({ tone: 'info', message: options?.message ?? `Loaded ${connector.name}` });
			updateSaveFileName(connector.name);
			setShowLandingScreen(false);
			setIsRenamingConnector(false);
			setConnectorNameDraft('');
		},
		[
			resetWorkingState,
			setActiveConnectorId,
			setBuilderView,
			setConfigFormState,
			setLastEdited,
			setReaderOptions,
			setShowLandingScreen,
			setStatus,
			setYamlText,
			updateSaveFileName,
		],
	);

	const createConnector = React.useCallback(
		(options?: {
			name?: string;
			formState?: ConfigFormState;
			yamlText?: string;
			lastEdited?: 'ui' | 'yaml';
			builderView?: 'ui' | 'yaml';
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
				formState: cloneFormState(options?.formState ?? INITIAL_FORM_STATE),
				yaml: options?.yamlText ?? '',
				lastEdited: options?.lastEdited ?? 'ui',
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
		(config: RestSourceConfig, yamlContent: string, meta?: { suggestedName?: string }) => {
			const formState = configToFormState(config);
			const derivedFromPath = (config.stream?.path || '').split('/').filter(Boolean).pop() || 'imported';
			const baseName = meta?.suggestedName ? stripExtension(meta.suggestedName) : derivedFromPath || 'Imported connector';
			createConnector({
				name: baseName,
				formState,
				yamlText: yamlContent.trimEnd(),
				lastEdited: 'yaml',
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
		[activeConnectorId, loadConnector, savedConnectors, setActiveConnectorId, setSavedConnectors, setShowLandingScreen, setStatus, showLandingScreen],
	);

	const handleExportSavedConnector = React.useCallback(
		(id: string) => {
			const connector = savedConnectors.find((entry) => entry.id === id);
			if (!connector) return;
			const yamlTextToSave = connector.yaml && connector.yaml.trim().length
				? connector.yaml
				: yaml.dump(formStateToConfig(connector.formState), { noRefs: true, lineWidth: 120, sortKeys: false, quotingType: "'" }).trimEnd();
			const blob = new Blob([yamlTextToSave], { type: 'text/yaml' });
			const link = document.createElement('a');
			link.href = URL.createObjectURL(blob);
			link.download = `${slugify(connector.name)}.yml`;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			URL.revokeObjectURL(link.href);
		},
		[savedConnectors],
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
					formState: cloneFormState(configFormState),
					yaml: yamlText,
					lastEdited,
					builderView,
					readerOptions: { ...readerOptions },
					updatedAt: new Date().toISOString(),
				};
			}));
		}, 400);
		return () => window.clearTimeout(handle);
	}, [activeConnectorId, builderView, configFormState, lastEdited, readerOptions, setSavedConnectors, yamlText, showLandingScreen]);

	// Instead, just mark initialLoadRef consumed once after first render
	React.useEffect(() => { if (initialLoadRef.current) initialLoadRef.current = false; }, []);

	// sync form state -> yaml when UI edits
	React.useEffect(() => {
		if (lastEdited !== "ui") return;
		const next = formStateYaml.trimEnd();
		if (yamlText.trimEnd() !== next) {
			setYamlText(next);
		}
		setYamlError(null);
	}, [formStateYaml, lastEdited, setYamlText, setYamlError, yamlText]);

	// sync yaml -> form state when YAML edits (debounced with lint)
	React.useEffect(() => {
		if (lastEdited !== 'yaml') return;
		const handle = window.setTimeout(() => {
			try {
				const loaded: any = yaml.load(yamlText) || {};
				if (loaded && typeof loaded === 'object') {
					const nextState = configToFormState(loaded as RestSourceConfig);
					setConfigFormState(nextState);
					setStatus({ tone: 'info', message: 'YAML parsed' });
					setYamlError(null);
					setYamlErrorLine(null);
					setYamlErrorCol(null);
				}
			} catch (e: any) {
				const reason = e?.reason || e?.message || 'Invalid YAML';
				setYamlError(reason);
				if (e?.mark && typeof e.mark.line === 'number') {
					setYamlErrorLine(e.mark.line); // 0-based
					setYamlErrorCol(typeof e.mark.column === 'number' ? e.mark.column : null);
				} else {
					setYamlErrorLine(null);
					setYamlErrorCol(null);
				}
			}
		}, 300); // debounce 300ms
		return () => window.clearTimeout(handle);
	}, [yamlText, lastEdited, setConfigFormState, setStatus, setYamlError]);

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

			if (builderView === "yaml" && payload.yaml) {
				setYamlText(payload.yaml);
			} else {
				const nextState = configToFormState(payload.config);
				// Preserve existing auth token & type since backend strips secrets.
				if (configFormState.authType !== 'none') {
					nextState.authType = configFormState.authType;
					nextState.authToken = configFormState.authToken; // keep token in form state
				}
				setConfigFormState(nextState);
			}
		},
		[builderView, setConfigFormState, setYamlText, configFormState]
	);

	const runValidation = React.useCallback(
		async ({ updateYaml = false, applyResponse = true }: { updateYaml?: boolean; applyResponse?: boolean } = {}) => {
			setIsValidating(true);
			try {
				const payload = await validateConfigRequest({
					...configPayload,
					token: bearerToken,
					options: runtimeOptions,
				});

				if (applyResponse) {
					applyValidationPayload(payload);
				}

				if (updateYaml && payload.yaml) {
					setYamlText(payload.yaml);
				}

				return payload;
			} finally {
				setIsValidating(false);
			}
		},
		[applyValidationPayload, configPayload, setIsValidating, setYamlText, bearerToken, runtimeOptions]
	);

	const handleValidate = React.useCallback(async () => {
		try {
			setStatus({ tone: "info", message: "Validating configuration…" });
			const result = await runValidation({ updateYaml: builderView === "yaml", applyResponse: true });

			if (result.valid) {
				setStatus({ tone: "success", message: "Configuration is valid" });
			} else {
				setStatus({ tone: "error", message: result.message || "Configuration is invalid" });
			}
		} catch (error) {
			setStatus({ tone: "error", message: formatError(error) });
		}
	}, [builderView, runValidation, setStatus]);

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
			await runValidation({ updateYaml: builderView === "yaml", applyResponse: false });
			setStatus({ tone: "info", message: "Fetching sample..." });
				const payload = await sampleRequest({
					...configPayload,
					token: bearerToken,
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
	}, [builderView, configPayload, runValidation, sample.limit, sample.stream, setSample, setStatus, streamOptions, bearerToken, runtimeOptions]);

	const handleYamlChange = React.useCallback(
		(value: string) => {
			setYamlText(value);
			setLastEdited("yaml");
		},
		[setLastEdited, setYamlText],
	);

	const handleViewChange = React.useCallback(
		(value: string) => {
			// If switching INTO YAML: capture snapshot
			if (value === "yaml" && builderView !== "yaml") {
				setYamlSnapshot(formStateYaml);
				setFormSnapshot(configFormState);
				setBuilderView("yaml");
				setStatus({ tone: "info", message: "Switched to YAML editor" });
				return;
			}
			// If switching to UI from YAML -> validate first
			if (value === "ui" && builderView === "yaml") {
				(async () => {
					setStatus({ tone: "info", message: "Validating YAML before switching…" });
					try {
					const payload = await validateConfigRequest({
						config: yamlText,
						token: bearerToken,
						options: runtimeOptions,
					});
						if (payload.valid && payload.config) {
							const nextState = configToFormState(payload.config as any);
							// Preserve current auth settings
							if (configFormState.authType !== 'none') {
								nextState.authType = configFormState.authType;
								nextState.authToken = configFormState.authToken;
							}
							setConfigFormState(nextState);
							setBuilderView("ui");
							setLastEdited("ui");
							setYamlError(null);
							setStatus({ tone: "success", message: "YAML valid. Switched to UI." });
						} else {
							const msg = payload.message || "Invalid YAML";
							setYamlError(msg);
							setShowYamlInvalidModal(true);
							setStatus({ tone: "error", message: msg });
						}
					} catch (e) {
						const msg = formatError(e);
						setYamlError(msg);
						setShowYamlInvalidModal(true);
						setStatus({ tone: "error", message: msg });
					}
				})();
				return;
			}
		},
		[builderView, configFormState, formStateYaml, setBuilderView, setConfigFormState, setLastEdited, setStatus, yamlText, setYamlError, bearerToken, runtimeOptions]
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
		const targetName = (explicitName || saveFileName || 'config.yml').trim() || 'config.yml';
		setIsSaving(true);
		setStatus({ tone: "info", message: "Validating & saving…" });
		try {
			await runValidation({ updateYaml: builderView === "yaml", applyResponse: false });
			const yamlToDownload = builderView === "yaml" ? yamlText : formStateYaml;
			await downloadYaml(yamlToDownload, targetName, saveDirHandle);
			setStatus({ tone: "success", message: `Saved ${saveDirName ? saveDirName + '/' : ''}${targetName}` });
			window.setTimeout(() => {
				setStatus({ tone: "info", message: "Ready to configure" });
			}, 3000);
		} catch (error) {
			setStatus({ tone: "error", message: formatError(error) });
		} finally {
			setIsSaving(false);
		}
	}, [builderView, formStateYaml, isSaving, runValidation, saveFileName, saveDirHandle, saveDirName, setIsSaving, setStatus, yamlText]);

	React.useEffect(() => {
		const handler = (event: KeyboardEvent) => {
			if ((event.metaKey || event.ctrlKey) && event.key === "s") {
				event.preventDefault();
				setShowSaveModal(true);
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, []);

	// Theme management (light/dark/system)
	const getSystemDark = () => (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches);
	const [themeMode, setThemeMode] = React.useState<'light' | 'dark' | 'system'>(() => {
		if (typeof window === 'undefined') return 'light';
		const stored = localStorage.getItem('polymo-theme-mode');
		if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
		return 'system';
	});
	const effectiveTheme = themeMode === 'system' ? (getSystemDark() ? 'dark' : 'light') : themeMode;

	React.useEffect(() => {
		const root = document.documentElement;
		if (effectiveTheme === 'dark') root.classList.add('dark'); else root.classList.remove('dark');
	}, [effectiveTheme]);

	React.useEffect(() => {
		localStorage.setItem('polymo-theme-mode', themeMode);
	}, [themeMode]);

	React.useEffect(() => {
		if (themeMode !== 'system') return;
		const mq = window.matchMedia('(prefers-color-scheme: dark)');
		const handler = () => {
			const dark = mq.matches;
			const root = document.documentElement;
			if (dark) root.classList.add('dark'); else root.classList.remove('dark');
		};
		mq.addEventListener('change', handler);
		return () => mq.removeEventListener('change', handler);
	}, [themeMode]);

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

	return (
		<div key={effectiveTheme} className="min-h-screen flex flex-col bg-background text-background-foreground dark:bg-slate-1 dark:text-slate-12 transition-colors theme-fade">
			<header className="sticky top-0 z-20 border-b border-border bg-surface/95 backdrop-blur dark:bg-[#1d2026] dark:border-[#2c313a] transition-colors">
				<div className="flex w-full items-center justify-between px-4 py-2">
					<div className="flex items-center gap-2">
						<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-5 shadow-soft overflow-hidden dark:bg-blue-7/40">
							<img
								src={import.meta.env.DEV ? "/favicon.ico" : "/static/favicon.ico"}
								alt="polymo Logo"
								className="h-7 w-7 object-contain"
							/>
						</div>
						<div className="leading-tight select-none">
							<p className="text-[11px] font-medium tracking-wide text-muted uppercase">polymo</p>
							<h1 className="text-base font-semibold text-slate-12 dark:text-drac-foreground">Connector Builder</h1>
						</div>
					</div>
				<div className="flex items-center gap-3">
					{currentConnector && (
						<div className="flex items-center gap-2 rounded-full border border-border/70 bg-background/80 px-3 py-1.5 text-sm text-slate-12 dark:border-drac-border/60 dark:bg-[#1f232b] dark:text-drac-foreground">
							{isRenamingConnector ? (
								<div className="flex items-center gap-2">
									<input
										autoFocus
										className="w-48 rounded-md border border-border bg-surface/70 px-3 py-1 text-sm text-slate-12 dark:border-drac-border/70 dark:bg-[#202530] dark:text-drac-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7"
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
									/>
									<button
										type="button"
										className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-border bg-blue-9 text-white hover:bg-blue-10"
										onClick={commitHeaderRename}
										aria-label="Save name"
									>
										<svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
											<path fillRule="evenodd" d="M16.704 5.29a1 1 0 010 1.42l-7.5 7.5a1 1 0 01-1.42 0l-3.5-3.5a1 1 0 111.42-1.42L8.5 11.58l6.79-6.79a1 1 0 011.414 0z" clipRule="evenodd" />
										</svg>
									</button>
									<button
										type="button"
										className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-border bg-background text-slate-11 hover:text-red-9 hover:border-red-7 dark:border-drac-border/60 dark:bg-[#1f232b] dark:text-drac-muted"
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
									className="inline-flex items-center gap-2 rounded-full bg-transparent text-sm font-medium text-slate-12 dark:text-drac-foreground"
									onClick={beginHeaderRename}
								>
									<svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5 text-blue-9" viewBox="0 0 20 20" fill="currentColor">
										<path fillRule="evenodd" d="M5 10a5 5 0 015-5h1a5 5 0 015 5v4a1 1 0 01-1 1H6a1 1 0 01-1-1v-4zm5-3.5A3.5 3.5 0 006.5 10V13h7V10A3.5 3.5 0 0011 6.5h-1z" clipRule="evenodd" />
									</svg>
										{currentConnector.name}
								</button>
							)}
						</div>
					)}
					<button
						type="button"
						className="rounded-full px-3 py-1.5 text-xs font-medium border border-border bg-background text-slate-12 hover:bg-blue-3/40 dark:border-drac-border/50 dark:bg-[#1f232b] dark:text-drac-foreground dark:hover:bg-blue-9/20 transition"
						onClick={openConnectorLibrary}
					>
						Connectors
					</button>
					<button
						type="button"
						className="rounded-full px-3 py-1.5 text-xs font-medium border border-border bg-background text-slate-12 hover:bg-blue-3/40 dark:border-drac-border/50 dark:bg-[#1f232b] dark:text-drac-foreground dark:hover:bg-blue-9/20 transition disabled:opacity-50 disabled:cursor-not-allowed"
						onClick={() => currentConnector && handleExportSavedConnector(currentConnector.id)}
						disabled={!currentConnector}
					>
						Export
					</button>
					<ThemeMenu mode={themeMode} effective={effectiveTheme} onChange={setThemeMode} />
				</div>
				</div>
			</header>
			<main className="flex-1 flex w-full gap-6 px-4 py-8 lg:px-6 items-stretch">
				{showLandingScreen ? (
					<LandingScreen
						onStartNew={handleStartNewConnector}
						onImportConfig={handleImportConnector}
						savedConnectors={savedConnectorSummaries}
						onSelectSaved={handleSelectSavedConnector}
						onDeleteSaved={handleDeleteSavedConnector}
						onExportSaved={handleExportSavedConnector}
					/>
				) : (
					<>
						<section className="w-full max-w-2xl flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6 shadow-soft h-full">
							<Tabs.Root value={builderView} onValueChange={handleViewChange}>
								<div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
									<Tabs.List className="inline-flex rounded-full border border-border bg-background p-1 text-sm font-medium">
										<Tabs.Trigger
											value="ui"
											className="rounded-full px-4 py-1.5 transition text-slate-11 dark:text-drac-foreground/80 hover:text-slate-12 dark:hover:text-drac-foreground data-[state=active]:bg-blue-9 data-[state=active]:text-white data-[state=active]:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7"
										>
											UI Builder
										</Tabs.Trigger>
										<Tabs.Trigger
											value="yaml"
											className="rounded-full px-4 py-1.5 transition text-slate-11 dark:text-drac-foreground/80 hover:text-slate-12 dark:hover:text-drac-foreground data-[state=active]:bg-blue-9 data-[state=active]:text-white data-[state=active]:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7"
										>
											YAML Editor
										</Tabs.Trigger>
									</Tabs.List>
									<div className="flex items-center gap-3">
										<button
											type="button"
											className={"inline-flex items-center gap-1 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-slate-12 hover:border-blue-7 hover:text-blue-11 disabled:opacity-50 disabled:cursor-not-allowed transition " + validateFlashClass}
											onClick={handleValidate}
											disabled={busy}
										>
											{isValidating ? 'Validating…' : 'Validate'}
										</button>
										<button
											type="button"
											className="inline-flex items-center gap-1 rounded-full bg-blue-9 px-5 py-2 text-sm font-semibold text-white shadow-soft transition hover:bg-blue-10 disabled:opacity-50 disabled:cursor-not-allowed"
											onClick={() => setShowSaveModal(true)}
											disabled={busy}
										>
											Export
										</button>
									</div>
								</div>
								<Tabs.Content value="ui" className="outline-none">
									<BuilderPanel
										state={configFormState}
										onUpdateState={handleUpdateFormState}
										onAddParam={handleAddParam}
										onRemoveParam={handleRemoveParam}
										onUpdateParam={handleUpdateParam}
									/>
								</Tabs.Content>
								<Tabs.Content value="yaml" className="outline-none">
									<YamlEditor value={yamlText} onChange={handleYamlChange} error={yamlError} errorLine={yamlErrorLine} errorCol={yamlErrorCol} />
								</Tabs.Content>
							</Tabs.Root>
						</section>
						<section className="flex-1 min-w-0 flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6 shadow-soft h-full">
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
											/>
						</section>
					</>
				)}
			</main>
			{showYamlInvalidModal && (
				<div className="fixed inset-0 z-50 flex items-center justify-center p-4">
					<div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
					<div role="dialog" aria-modal="true" className="relative z-10 w-full max-w-md rounded-xl border border-border dark:border-drac-border bg-surface dark:bg-drac-surface shadow-soft p-6 flex flex-col gap-5">
						<header className="flex items-start justify-between gap-4">
							<h2 className="text-lg font-semibold text-slate-12 dark:text-drac-foreground">Invalid YAML</h2>
						</header>
						<p className="text-sm text-slate-11 dark:text-drac-foreground/80 leading-relaxed">Your YAML did not validate. Continue editing to fix the issues, or revert to the last valid configuration captured before entering the YAML editor.</p>
						<div className="flex flex-col gap-2 rounded-md bg-red-3/50 dark:bg-red-9/15 border border-red-7/50 px-3 py-2 text-xs">
							<p className="font-medium text-red-11 dark:text-red-9">Error</p>
							<p className="text-red-11 dark:text-red-9 whitespace-pre-wrap break-words">{yamlError || 'Validation error.'}</p>
						</div>
						<div className="flex justify-end gap-3 pt-1">
							<button
								type="button"
								className="rounded-full px-4 py-2 text-sm font-medium border border-border dark:border-drac-border text-slate-12 dark:text-drac-foreground hover:bg-blue-3/60 dark:hover:bg-blue-9/30 transition"
								onClick={() => { setShowYamlInvalidModal(false); setStatus({ tone: 'info', message: 'Continue editing YAML' }); }}
							>
								Continue Editing
							</button>
							<button
								type="button"
								className="rounded-full px-4 py-2 text-sm font-semibold bg-red-9 text-white hover:bg-red-10 shadow-soft transition"
								onClick={() => {
									if (formSnapshot && yamlSnapshot !== null) {
										setConfigFormState(formSnapshot);
										setYamlText(yamlSnapshot);
										setLastEdited('ui');
										setBuilderView('ui');
										setStatus({ tone: 'success', message: 'Reverted to previous configuration' });
										setYamlError(null);
									}
									setShowYamlInvalidModal(false);
								}}
							>
								Revert Changes
							</button>
						</div>
					</div>
				</div>
			)}
			{showSaveModal && (
				<div className="fixed inset-0 z-50 flex items-center justify-center p-4">
					<div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => !isSaving && setShowSaveModal(false)} />
					<div role="dialog" aria-modal="true" className="relative z-10 w-full max-w-md rounded-2xl border border-border bg-surface dark:bg-drac-surface shadow-soft p-6 flex flex-col gap-5">
						<header className="flex items-start justify-between gap-4">
							<h2 className="text-lg font-semibold text-slate-12 dark:text-drac-foreground">Save Configuration</h2>
						</header>
						<div className="space-y-4">
							<label className="flex flex-col gap-2">
								<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/80">File Name</span>
								<input
									type="text"
									className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-drac-border dark:bg-drac-surface dark:text-drac-foreground"
									value={saveFileName}
									onChange={(e) => setSaveFileName(e.target.value)}
									placeholder="config.yml"
								/>
							</label>
							<div className="flex items-center gap-3">
								<button
									type="button"
									className="rounded-full px-3 py-1.5 text-xs font-medium border border-border bg-background hover:border-blue-7 hover:text-blue-11 transition disabled:opacity-50"
									onClick={handleChooseDirectory}
									disabled={isSaving || !dirPickerSupported}
								>
									{dirPickerSupported ? (saveDirName ? 'Change Folder' : 'Choose Folder') : 'Folder Unsupported'}
								</button>
								{saveDirName && dirPickerSupported && <span className="text-xs text-muted truncate max-w-[140px]" title={saveDirName}>{saveDirName}/</span>}
							</div>
							<p className="text-xs text-muted dark:text-drac-muted">
								{dirPickerSupported
									? (saveDirName ? 'Will write directly into the selected folder (if permissions granted).' : 'Select a folder for direct write or leave blank to download.')
									: 'This browser does not support selecting a target folder; the file will download normally.'}
							</p>
						</div>
						<div className="flex justify-end gap-3 pt-2">
							<button
								type="button"
								className="rounded-full px-4 py-2 text-sm font-medium border border-border dark:border-drac-border text-slate-12 dark:text-drac-foreground hover:bg-blue-3/40 dark:hover:bg-blue-9/25 transition disabled:opacity-50"
								onClick={() => !isSaving && setShowSaveModal(false)}
								disabled={isSaving}
							>
								Cancel
							</button>
							<button
								type="button"
								className="rounded-full px-5 py-2 text-sm font-semibold bg-blue-9 text-white hover:bg-blue-10 shadow-soft transition disabled:opacity-50"
								onClick={() => { setShowSaveModal(false); handleSave(saveFileName); }}
								disabled={isSaving || !saveFileName.trim()}
							>
								{isSaving ? 'Saving…' : 'Save File'}
							</button>
						</div>
					</div>
				</div>
			)}
			<footer className="mt-auto border-t border-border bg-surface/80 py-4 dark:bg-[#1d2026] dark:border-[#2c313a] transition-colors">
				<div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 text-sm text-muted">
					<span>
					</span>
				</div>
			</footer>
		</div>
	);
};


function formatError(error: unknown): string {
	if (error instanceof Error) {
		return error.message;
	}
	return String(error ?? "Unknown error");
}

function downloadYaml(contents: string, fileName = 'config.yml', directoryHandle?: any) {
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
					types: [{ description: 'YAML Files', accept: { 'text/yaml': ['.yml', '.yaml'] } }],
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
		const blob = new Blob([contents], { type: 'text/yaml' });
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
