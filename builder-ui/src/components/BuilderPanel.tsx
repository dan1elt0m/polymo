import React from "react";
import * as Tabs from "@radix-ui/react-tabs";
import type { ConfigFormState } from "../types";
import { InfoTooltip } from "./InfoTooltip";
import { useAtom, useSetAtom, useAtomValue } from "jotai";
import { bearerTokenAtom, readerOptionsAtom, runtimeOptionsAtom } from "../atoms";
import { InputWithCursorPosition } from "./InputWithCursorPosition";
import { DEFAULT_ERROR_HANDLER } from "../lib/initial-data";

// Add row components that defer key renames until blur to avoid remounting each keystroke
const ParamRow: React.FC<{
	originalKey: string;
	value: string;
	onUpdateKey: (oldKey: string, newKey: string, value: string) => void;
	onUpdateValue: (key: string, newKey: string, value: string) => void;
	onRemove: (key: string) => void;
}> = ({ originalKey, value, onUpdateKey, onUpdateValue, onRemove }) => {
	const [tempKey, setTempKey] = React.useState(originalKey);
	// Sync local state if the key changes externally (e.g. after commit)
	React.useEffect(() => { setTempKey(originalKey); }, [originalKey]);

	const commitIfChanged = React.useCallback(() => {
		if (tempKey && tempKey !== originalKey) {
			onUpdateKey(originalKey, tempKey, value);
		}
	}, [tempKey, originalKey, value, onUpdateKey]);

	return (
		<li className="group relative rounded-xl border border-border/60 dark:border-drac-border/60 bg-background/60 dark:bg-[#262c35] backdrop-blur-sm px-4 py-4 shadow-inner transition-all duration-200 hover:border-blue-7/60 dark:hover:border-drac-accent/60 hover:shadow-sm">
			<div className="grid gap-4 md:grid-cols-2">
				<div className="flex flex-col gap-1.5">
					<label className="text-[11px] tracking-wide text-muted dark:text-drac-muted font-medium flex items-center gap-1">
						Name <InfoTooltip text="Parameter key sent with request." />
					</label>
					<InputWithCursorPosition
						type="text"
						className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#303745] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm transition-all focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5 dark:focus-visible:ring-drac-accent/40 group-hover:border-blue-7/50"
						placeholder="param_name"
						value={tempKey}
						onChange={(e) => setTempKey(e.target.value)}
						onBlur={commitIfChanged}
						onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); (e.target as HTMLInputElement).blur(); } }}
					/>
				</div>
				<div className="flex flex-col gap-1.5">
					<label className="text-[11px] tracking-wide text-muted dark:text-drac-muted font-medium flex items-center gap-1">
						Value <InfoTooltip text="Parameter value associated with the key." />
					</label>
					<InputWithCursorPosition
						type="text"
						className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#303745] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm transition-all focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5 dark:focus-visible:ring-drac-accent/40 group-hover:border-blue-7/50"
						placeholder="value"
						value={value}
						onValueChange={(newValue) => onUpdateValue(originalKey, originalKey, newValue)}
					/>
				</div>
			</div>
			<button
				type="button"
				className="absolute -right-2 -top-2 inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 dark:border-drac-border bg-background/80 dark:bg-[#2d3541] text-slate-11 dark:text-drac-muted opacity-0 shadow-sm backdrop-blur transition-all duration-200
																		 hover:text-red-10 hover:border-red-7 hover:bg-red-3/60 dark:hover:text-drac-red dark:hover:border-drac-red/80 dark:hover:bg-[#383f4c]
																		 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7"
				onClick={() => onRemove(originalKey)}
				aria-label={`Remove parameter ${originalKey}`}
			>
				<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
					<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
				</svg>
			</button>
		</li>
	);
};

const HeaderRow: React.FC<{
	originalKey: string;
	value: string;
	onUpdateKey: (oldKey: string, newKey: string, value: string) => void;
	onUpdateValue: (key: string, newKey: string, value: string) => void;
	onRemove: (key: string) => void;
}> = ({ originalKey, value, onUpdateKey, onUpdateValue, onRemove }) => {
	const [tempKey, setTempKey] = React.useState(originalKey);
	React.useEffect(() => { setTempKey(originalKey); }, [originalKey]);
	const commitIfChanged = React.useCallback(() => {
		if (tempKey && tempKey !== originalKey) {
			onUpdateKey(originalKey, tempKey, value);
		}
	}, [tempKey, originalKey, value, onUpdateKey]);
	return (
		<li className="group relative rounded-xl border border-border/60 dark:border-drac-border/60 bg-background/60 dark:bg-[#262c35] backdrop-blur-sm px-4 py-4 shadow-inner transition-all duration-200 hover:border-blue-7/60 dark:hover:border-drac-accent/60 hover:shadow-sm">
			<div className="grid gap-4 md:grid-cols-2">
				<div className="flex flex-col gap-1.5">
					<label className="text-[11px] tracking-wide text-muted dark:text-drac-muted font-medium flex items-center gap-1">
						Name <InfoTooltip text="Header key sent with request." />
					</label>
					<InputWithCursorPosition
						type="text"
						className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#303745] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm transition-all focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5 dark:focus-visible:ring-drac-accent/40 group-hover:border-blue-7/50"
						placeholder="header_name"
						value={tempKey}
						onChange={(e) => setTempKey(e.target.value)}
						onBlur={commitIfChanged}
						onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); (e.target as HTMLInputElement).blur(); } }}
					/>
				</div>
				<div className="flex flex-col gap-1.5">
					<label className="text-[11px] tracking-wide text-muted dark:text-drac-muted font-medium flex items-center gap-1">
						Value <InfoTooltip text="Header value associated with the key." />
					</label>
					<InputWithCursorPosition
						type="text"
						className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#303745] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm transition-all focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5 dark:focus-visible:ring-drac-accent/40 group-hover:border-blue-7/50"
						placeholder="value"
						value={value}
						onValueChange={(newValue) => onUpdateValue(originalKey, originalKey, newValue)}
					/>
				</div>
			</div>
			<button
				type="button"
				className="absolute -right-2 -top-2 inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 dark:border-drac-border bg-background/80 dark:bg-[#2d3541] text-slate-11 dark:text-drac-muted opacity-0 shadow-sm backdrop-blur transition-all duration-200 hover:text-red-10 hover:border-red-7 hover:bg-red-3/60 dark:hover:text-drac-red dark:hover:border-drac-red/80 dark:hover:bg-[#383f4c] group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7"
				onClick={() => onRemove(originalKey)}
				aria-label={`Remove header ${originalKey}`}
			>
				<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
					<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
				</svg>
			</button>
		</li>
	);
};

const ReaderOptionRow: React.FC<{
	originalKey: string;
	value: string;
	onUpdateKey: (oldKey: string, newKey: string, value: string) => void;
	onUpdateValue: (key: string, newKey: string, value: string) => void;
	onRemove: (key: string) => void;
}> = ({ originalKey, value, onUpdateKey, onUpdateValue, onRemove }) => {
	const [tempKey, setTempKey] = React.useState(originalKey);
	React.useEffect(() => { setTempKey(originalKey); }, [originalKey]);
	const commitIfChanged = React.useCallback(() => {
		if (tempKey && tempKey !== originalKey) {
			onUpdateKey(originalKey, tempKey, value);
		}
	}, [tempKey, originalKey, value, onUpdateKey]);
	return (
		<li className="group relative rounded-xl border border-border/60 dark:border-drac-border/60 bg-background/60 dark:bg-[#262c35] backdrop-blur-sm px-4 py-4 shadow-inner transition-all duration-200 hover:border-blue-7/60 dark:hover:border-drac-accent/60 hover:shadow-sm">
			<div className="grid gap-4 md:grid-cols-2">
				<div className="flex flex-col gap-1.5">
					<label className="text-[11px] tracking-wide text-muted dark:text-drac-muted font-medium flex items-center gap-1">
						Option Key <InfoTooltip text="Name to reference via {{ options.key }} and pass to spark.read.option." />
					</label>
					<InputWithCursorPosition
						type="text"
						className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#303745] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm transition-all focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5 dark:focus-visible:ring-drac-accent/40 group-hover:border-blue-7/50"
						placeholder="api_key"
						value={tempKey}
						onChange={(e) => setTempKey(e.target.value)}
						onBlur={commitIfChanged}
						onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); (e.target as HTMLInputElement).blur(); } }}
					/>
				</div>
				<div className="flex flex-col gap-1.5">
					<label className="text-[11px] tracking-wide text-muted dark:text-drac-muted font-medium flex items-center gap-1">
						Value <InfoTooltip text="Runtime value supplied to the Spark reader." />
					</label>
					<InputWithCursorPosition
						type="text"
						className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#303745] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm transition-all focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5 dark:focus-visible:ring-drac-accent/40 group-hover:border-blue-7/50"
						placeholder="value"
						value={value}
						onValueChange={(newValue) => onUpdateValue(originalKey, originalKey, newValue)}
					/>
				</div>
			</div>
			<button
				type="button"
				className="absolute -right-2 -top-2 inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 dark:border-drac-border bg-background/80 dark:bg-[#2d3541] text-slate-11 dark:text-drac-muted opacity-0 shadow-sm backdrop-blur transition-all duration-200 hover:text-red-10 hover:border-red-7 hover:bg-red-3/60 dark:hover:text-drac-red dark:hover:border-drac-red/80 dark:hover:bg-[#383f4c] group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7"
				onClick={() => onRemove(originalKey)}
				aria-label={`Remove spark option ${originalKey}`}
			>
				<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
					<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
				</svg>
			</button>
		</li>
	);
};

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
	const setBearerToken = useSetAtom(bearerTokenAtom);
	const [readerOptions, setReaderOptions] = useAtom(readerOptionsAtom);
	const runtimeOptions = useAtomValue(runtimeOptionsAtom);
	const manualOptionCount = Object.keys(readerOptions).length;
	const totalRuntimeOptions = Object.keys(runtimeOptions).length;
	const incrementalOptionCount = Math.max(0, totalRuntimeOptions - manualOptionCount);
	const runtimeOptionSummary = totalRuntimeOptions
		? `${manualOptionCount} manual${incrementalOptionCount > 0 ? ` · ${incrementalOptionCount} incremental` : ''}`
		: 'none';
	// All panels collapsed initially
	const [showAuth, setShowAuth] = React.useState(false);
	const [showPagination, setShowPagination] = React.useState(false);
	const [showParams, setShowParams] = React.useState(false);
	const [showHeaders, setShowHeaders] = React.useState(false);
	const [showRecordSelector, setShowRecordSelector] = React.useState(false);
	const [showReaderOptions, setShowReaderOptions] = React.useState(false);
	const [showIncremental, setShowIncremental] = React.useState(false);
	const [showErrorHandling, setShowErrorHandling] = React.useState(false);
	const incrementalAutoOpenRef = React.useRef(false);

	const incrementalSummary = React.useMemo(() => {
		const parts: string[] = [];
		if (state.incrementalMode.trim()) {
			parts.push(state.incrementalMode.trim());
		}
		if (state.incrementalCursorParam.trim()) {
			parts.push(`param ${state.incrementalCursorParam.trim()}`);
		}
		if (state.incrementalCursorField.trim()) {
			parts.push(`field ${state.incrementalCursorField.trim()}`);
		}
		if (state.incrementalStatePath.trim()) {
			parts.push('state path set');
		}
		if (state.incrementalStartValue.trim()) {
			parts.push('start value');
		}
		if (state.incrementalStateKey.trim()) {
			parts.push('state key');
		}
		if (!state.incrementalMemoryEnabled) {
			parts.push('memory off');
		}
		return parts.length ? parts.join(' · ') : 'optional';
	}, [state.incrementalMode, state.incrementalCursorParam, state.incrementalCursorField, state.incrementalStatePath, state.incrementalStartValue, state.incrementalStateKey, state.incrementalMemoryEnabled]);

	const errorHandlerSummary = React.useMemo(() => {
		const retries = state.errorHandlerMaxRetries.trim() || String(DEFAULT_ERROR_HANDLER.max_retries);
		const statuses = (state.errorHandlerRetryStatuses || [])
			.map((status) => status.trim())
			.filter((status) => status.length > 0);
		const multiplier = state.errorHandlerBackoffMultiplier.trim() || String(DEFAULT_ERROR_HANDLER.backoff.multiplier);
		const parts = [
			`${retries} retries`,
			`statuses: ${statuses.length ? statuses.join(', ') : 'none'}`,
			`backoff ×${multiplier}`,
		];
		return parts.join(' · ');
	}, [state.errorHandlerMaxRetries, state.errorHandlerRetryStatuses, state.errorHandlerBackoffMultiplier]);

	// Initialize headers if not present
	React.useEffect(() => {
		if (!state.headers) {
			onUpdateState({ headers: {} });
		}
	}, [state.headers, onUpdateState]);

	React.useEffect(() => {
		if ((state.recordFieldPath?.length ?? 0) > 0 || state.recordFilter.trim() || state.castToSchemaTypes) {
			setShowRecordSelector(true);
		}
	}, [state.recordFieldPath, state.recordFilter, state.castToSchemaTypes]);

	React.useEffect(() => {
		if (Object.keys(readerOptions).length > 0) {
			setShowReaderOptions(true);
		}
	}, [readerOptions]);

	React.useEffect(() => {
		const defaultStatuses = DEFAULT_ERROR_HANDLER.retry_statuses.map((status) => status.toUpperCase());
		const currentStatuses = (state.errorHandlerRetryStatuses || [])
			.map((status) => status.trim().toUpperCase())
			.filter((status) => status.length > 0);
		const statusesMatch =
			currentStatuses.length === defaultStatuses.length &&
			currentStatuses.every((status, index) => status === defaultStatuses[index]);
		const matchesDefaults =
			state.errorHandlerMaxRetries.trim() === String(DEFAULT_ERROR_HANDLER.max_retries) &&
			statusesMatch &&
			state.errorHandlerInitialDelaySeconds.trim() === String(DEFAULT_ERROR_HANDLER.backoff.initial_delay_seconds) &&
			state.errorHandlerMaxDelaySeconds.trim() === String(DEFAULT_ERROR_HANDLER.backoff.max_delay_seconds) &&
			state.errorHandlerBackoffMultiplier.trim() === String(DEFAULT_ERROR_HANDLER.backoff.multiplier) &&
			state.errorHandlerRetryOnTimeout === DEFAULT_ERROR_HANDLER.retry_on_timeout &&
			state.errorHandlerRetryOnConnectionErrors === DEFAULT_ERROR_HANDLER.retry_on_connection_errors;
		if (!matchesDefaults) {
			setShowErrorHandling(true);
		}
	}, [
		state.errorHandlerMaxRetries,
		state.errorHandlerRetryStatuses,
		state.errorHandlerInitialDelaySeconds,
		state.errorHandlerMaxDelaySeconds,
		state.errorHandlerBackoffMultiplier,
		state.errorHandlerRetryOnTimeout,
		state.errorHandlerRetryOnConnectionErrors,
	]);

	React.useEffect(() => {
		const hasIncrementalValues = Boolean(
			state.incrementalMode.trim() ||
			state.incrementalCursorParam.trim() ||
			state.incrementalCursorField.trim() ||
			state.incrementalStatePath.trim() ||
			state.incrementalStartValue.trim() ||
			state.incrementalStateKey.trim() ||
			!state.incrementalMemoryEnabled,
		);
		if (hasIncrementalValues && !showIncremental && !incrementalAutoOpenRef.current) {
			setShowIncremental(true);
			incrementalAutoOpenRef.current = true;
		}
		if (!hasIncrementalValues) {
			incrementalAutoOpenRef.current = false;
		}
	}, [showIncremental, state.incrementalMode, state.incrementalCursorParam, state.incrementalCursorField, state.incrementalStatePath, state.incrementalStartValue, state.incrementalStateKey, state.incrementalMemoryEnabled]);

	React.useEffect(() => {
		const specialKeys = [
			'incremental_state_path',
			'incremental_start_value',
			'incremental_state_key',
			'incremental_memory_state',
		] as const;

		let mutated = false;
		const nextOptions = { ...readerOptions };
		const patch: Partial<ConfigFormState> = {};

		specialKeys.forEach((key) => {
			if (nextOptions[key] !== undefined) {
				const raw = nextOptions[key];
				delete nextOptions[key];
				mutated = true;
				if (key === 'incremental_state_path') {
					patch.incrementalStatePath = String(raw ?? '');
				} else if (key === 'incremental_start_value') {
					patch.incrementalStartValue = String(raw ?? '');
				} else if (key === 'incremental_state_key') {
					patch.incrementalStateKey = String(raw ?? '');
				} else if (key === 'incremental_memory_state') {
					const normalized = String(raw ?? '').trim().toLowerCase();
					patch.incrementalMemoryEnabled = normalized !== 'false';
				}
			}
		});

		if (mutated) {
			setReaderOptions(nextOptions);
		}
		if (Object.keys(patch).length > 0) {
			onUpdateState(patch);
		}
	}, [readerOptions, onUpdateState, setReaderOptions]);

	// Handle header add/remove/update
	const onAddHeader = React.useCallback(() => {
		const headers = { ...state.headers };
		let key = "header";
		let i = 1;
		while (headers[key]) {
			key = `header${i++}`;
		}
		headers[key] = "";
		onUpdateState({ headers });
	}, [state.headers, onUpdateState]);

	const onRemoveHeader = React.useCallback((key: string) => {
		const headers = { ...state.headers };
		delete headers[key];
		onUpdateState({ headers });
	}, [state.headers, onUpdateState]);

	const onUpdateHeader = React.useCallback((key: string, newKey: string, value: string) => {
		const headers = { ...state.headers };
		delete headers[key];
		headers[newKey] = value;
		onUpdateState({ headers });
	}, [state.headers, onUpdateState]);

	const handleAddRetryStatus = React.useCallback(() => {
		const next = [...(state.errorHandlerRetryStatuses || []), ""];
		onUpdateState({ errorHandlerRetryStatuses: next });
	}, [state.errorHandlerRetryStatuses, onUpdateState]);

	const handleUpdateRetryStatus = React.useCallback((index: number, value: string) => {
		const current = [...(state.errorHandlerRetryStatuses || [])];
		current[index] = value;
		onUpdateState({ errorHandlerRetryStatuses: current });
	}, [state.errorHandlerRetryStatuses, onUpdateState]);

	const handleRemoveRetryStatus = React.useCallback((index: number) => {
		const current = state.errorHandlerRetryStatuses || [];
		const next = current.filter((_, idx) => idx !== index);
		onUpdateState({ errorHandlerRetryStatuses: next });
	}, [state.errorHandlerRetryStatuses, onUpdateState]);

	const handleAddReaderOption = React.useCallback(() => {
		setReaderOptions((prev) => {
			const next = { ...prev };
			let index = 1;
			let key = "option";
			while (key in next) {
				key = `option${index++}`;
			}
			next[key] = "";
			return next;
		});
		setShowReaderOptions(true);
	}, [setReaderOptions]);

	const handleRemoveReaderOption = React.useCallback((key: string) => {
		setReaderOptions((prev) => {
			const next = { ...prev };
			delete next[key];
			return next;
		});
	}, [setReaderOptions]);

	const handleUpdateReaderOption = React.useCallback((key: string, newKey: string, value: string) => {
		setReaderOptions((prev) => {
			const next = { ...prev };
			delete next[key];
			next[newKey] = value;
			return { ...next };
		});
	}, [setReaderOptions]);

	React.useEffect(() => { if (state.authType === 'bearer' || state.authType === 'api_key') setShowAuth(true); }, [state.authType]);

	const handleAddFieldPathSegment = React.useCallback(() => {
		const next = [...(state.recordFieldPath || []), ""];
		onUpdateState({ recordFieldPath: next });
	}, [state.recordFieldPath, onUpdateState]);

	const handleUpdateFieldPathSegment = React.useCallback((index: number, value: string) => {
		const current = state.recordFieldPath || [];
		const next = current.map((segment, idx) => (idx === index ? value : segment));
		onUpdateState({ recordFieldPath: next });
	}, [state.recordFieldPath, onUpdateState]);

	const handleRemoveFieldPathSegment = React.useCallback((index: number) => {
		const current = state.recordFieldPath || [];
		const next = current.filter((_, idx) => idx !== index);
		onUpdateState({ recordFieldPath: next });
	}, [state.recordFieldPath, onUpdateState]);

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
							<div className="space-y-8">
								{/* Base URL & Path */}
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
										/>
									</label>
								</div>

								{/* Authentication */}
								<div className="space-y-3">
									<button
										type="button"
										className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
										onClick={() => setShowAuth(v => !v)}
										aria-expanded={showAuth}
										aria-controls="auth-section"
									>
										<span className="flex items-center gap-2">
											Authentication
											<span className="text-xs font-normal text-muted">(optional{state.authType !== 'none' ? `: ${state.authType}` : ''})</span>
										</span>
										<span className={"transition-transform duration-200 " + (showAuth ? 'rotate-90' : '')}>
											<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
												<path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
											</svg>
										</span>
									</button>
									{showAuth && (
										<div
											id="auth-section"
											className="space-y-5 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
										>
											<div className="grid gap-5 md:grid-cols-2">
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Auth Type</span>
														<InfoTooltip text="Authentication method applied to each request. Not stored in YAML." />
													</div>
													<div className="relative">
														<select
															className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm appearance-none pr-9 transition-all focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none"
															value={state.authType}
															onChange={(e) => {
																const authType = e.target.value as 'none' | 'bearer' | 'api_key';
																const patch: Partial<ConfigFormState> = { authType };
																if (authType === 'none') { patch.authToken = ''; patch.authApiKeyParamName = state.authApiKeyParamName; setBearerToken(''); }
																if (authType === 'bearer') { patch.authApiKeyParamName = state.authApiKeyParamName; }
																if (authType === 'api_key') { patch.authToken = ''; if (!state.authApiKeyParamName) patch.authApiKeyParamName = 'api_key'; setBearerToken(''); }
																onUpdateState(patch);
															}}
														>
															<option value="none">None</option>
															<option value="bearer">Bearer Token</option>
															<option value="api_key">API Key</option>
														</select>
														<span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10 dark:text-drac-muted">
															<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
																<path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" />
															</svg>
														</span>
													</div>
												</label>
												{state.authType === 'bearer' && (
													<label className="flex flex-col gap-2">
														<div className="flex items-center gap-1">
															<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Bearer Token</span>
															<InfoTooltip text="Secret token sent as Authorization header." />
														</div>
														<input
															type="password"
															className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
															placeholder="your-token-here"
															value={state.authToken}
															onChange={(e) => {
																const value = e.target.value;
																onUpdateState({ authToken: value });
																setBearerToken(value);
															}}
														/>
													</label>
												)}
												{state.authType === 'api_key' && (
													<div className="grid gap-5 md:grid-cols-2">
														<label className="flex flex-col gap-2">
															<div className="flex items-center gap-1">
																<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">API Key Param</span>
																<InfoTooltip text="Query parameter name that will hold the API key at runtime." />
															</div>
															<input
																type="text"
																className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																placeholder="api_key"
																value={state.authApiKeyParamName || ''}
																onChange={(e) => onUpdateState({ authApiKeyParamName: e.target.value.trim() })}
															/>
														</label>
														<label className="flex flex-col gap-2">
															<div className="flex items-center gap-1">
																<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">API Key (secret)</span>
																<InfoTooltip text="Secret API key stored only in the browser session and supplied at runtime via Spark options." />
															</div>
															<input
																type="password"
																className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																placeholder="your-api-key"
																value={state.authToken}
																onChange={(e) => { const value = e.target.value; onUpdateState({ authToken: value }); setBearerToken(value); }}
															/>
														</label>
													</div>
												)}
											</div>
										</div>
									)}
								</div>

								{/* Headers */}
								<div className="space-y-3">
									<button
										type="button"
										className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
										onClick={() => setShowHeaders(v => !v)}
										aria-expanded={showHeaders}
										aria-controls="headers-section"
									>
										<span className="flex items-center gap-2">
											Headers
											<span className="text-xs font-normal text-muted">({Object.keys(state.headers).length || 'none'})</span>
										</span>
										<span className={"transition-transform duration-200 " + (showHeaders ? 'rotate-90' : '')}>
											<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
												<path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
											</svg>
										</span>
									</button>
									{showHeaders && (
										<div
											id="headers-section"
											className="space-y-4 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
										>
											<div className="flex items-center justify-between">
												<h4 className="text-sm font-semibold text-slate-12 dark:text-drac-foreground">Headers</h4>
												<button
													type="button"
													className="inline-flex items-center gap-1.5 rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#242a33] px-4 py-1.5 text-xs font-medium text-slate-11 dark:text-drac-foreground shadow-sm transition-all duration-200
													hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent
													hover:scale-105 hover:shadow-md dark:hover:shadow-[0_0_8px_rgba(80,250,123,0.15)] hover:bg-blue-3/50 dark:hover:bg-[#273242]
													focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7 dark:focus-visible:ring-drac-accent"
													onClick={onAddHeader}
												>
													<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
														<path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
													</svg>
													<span>Add Header</span>
												</button>
											</div>
											{Object.entries(state.headers).length > 0 ? (
												<ul className="flex flex-col gap-2">
													{Object.entries(state.headers).map(([key, value]) => (
														<HeaderRow key={key} originalKey={key} value={value} onUpdateKey={onUpdateHeader} onUpdateValue={onUpdateHeader} onRemove={onRemoveHeader} />
													))}
												</ul>
											) : (
												<p className="text-sm text-muted dark:text-drac-muted">No headers configured.</p>
											)}
										</div>
									)}
								</div>

								{/* Query Parameters */}
								<div className="space-y-3">
									<button
										type="button"
										className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
										onClick={() => setShowParams(v => !v)}
										aria-expanded={showParams}
										aria-controls="params-section"
									>
										<span className="flex items-center gap-2">
											Query Parameters
											<span className="text-xs font-normal text-muted">({Object.keys(state.params).length || 'none'})</span>
										</span>
										<span className={"transition-transform duration-200 " + (showParams ? 'rotate-90' : '')}>
                                            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                                                <path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
                                            </svg>
                                        </span>
									</button>
									{showParams && (
										<div
											id="params-section"
											className="space-y-4 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
										>
											<div className="flex items-center justify-between">
												<h4 className="text-sm font-semibold text-slate-12 dark:text-drac-foreground">Parameters</h4>
												<button
													type="button"
													className="inline-flex items-center gap-1.5 rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#242a33] px-4 py-1.5 text-xs font-medium text-slate-11 dark:text-drac-foreground shadow-sm transition-all duration-200 hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent hover:scale-105 hover:shadow-md dark:hover:shadow-[0_0_8px_rgba(80,250,123,0.15)] hover:bg-blue-3/50 dark:hover:bg-[#273242] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7 dark:focus-visible:ring-drac-accent"
													onClick={() => { onAddParam(); setShowParams(true); }}
												>
													<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
														<path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
													</svg>
													<span>Add</span>
												</button>
											</div>
											{Object.entries(state.params).length > 0 ? (
												<ul className="flex flex-col gap-2">
													{Object.entries(state.params).map(([key, value]) => (
														<ParamRow key={key} originalKey={key} value={value} onUpdateKey={onUpdateParam} onUpdateValue={onUpdateParam} onRemove={onRemoveParam} />
													))}
												</ul>
											) : (
												<p className="text-sm text-muted dark:text-drac-muted">No parameters configured.</p>
											)}
										</div>
									)}
								</div>

								{/* Error handling */}
								<div className="space-y-3">
									<button
										type="button"
										className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
										onClick={() => setShowErrorHandling((v) => !v)}
										aria-expanded={showErrorHandling}
										aria-controls="error-handler-section"
									>
										<span className="flex items-center gap-2">
											Error handling
											<span className="text-xs font-normal text-muted">({errorHandlerSummary})</span>
										</span>
										<span className={"transition-transform duration-200 " + (showErrorHandling ? 'rotate-90' : '')}>
											<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
												<path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
											</svg>
										</span>
									</button>
									{showErrorHandling && (
										<div
											id="error-handler-section"
											className="space-y-6 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
										>
											<div className="grid gap-5 md:grid-cols-2">
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Max retries</span>
														<InfoTooltip text="Number of times a request is retried after the first attempt." />
													</div>
													<input
														type="number"
														min={0}
														className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
														value={state.errorHandlerMaxRetries}
														onChange={(e) => onUpdateState({ errorHandlerMaxRetries: e.target.value })}
													/>
												</label>
												<div className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Retry status codes</span>
														<InfoTooltip text="HTTP codes or patterns (e.g. 429, 5XX) that should be retried." />
													</div>
													{(state.errorHandlerRetryStatuses || []).length > 0 ? (
														<ul className="flex flex-col gap-2">
															{state.errorHandlerRetryStatuses.map((status, index) => (
																<li key={`retry-status-${index}`} className="flex items-center gap-2">
																	<input
																		type="text"
																		className="flex-1 rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="5XX"
																		value={status}
																		onChange={(e) => handleUpdateRetryStatus(index, e.target.value)}
																	/>
																	<button
																		type="button"
																		className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#2d3541] text-slate-11 dark:text-drac-muted hover:border-red-7 hover:text-red-9 hover:bg-red-3/40 dark:hover:border-drac-red/80 dark:hover:text-drac-red dark:hover:bg-[#3a3f4b] transition"
																		onClick={() => handleRemoveRetryStatus(index)}
																		aria-label={`Remove retry status ${status || index + 1}`}
																	>
																		<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
																			<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
																		</svg>
																	</button>
																</li>
															))}
														</ul>
													) : (
														<p className="text-sm text-muted dark:text-drac-muted">No overrides configured. Defaults to retrying 5XX and 429 responses.</p>
													)}
													<button
														type="button"
														className="inline-flex w-fit items-center gap-2 rounded-md border border-border bg-background/70 dark:bg-[#272d38] px-3 py-1.5 text-xs font-medium text-blue-11 hover:bg-blue-3/40 dark:border-drac-border dark:text-drac-accent dark:hover:bg-[#283546] transition"
														onClick={handleAddRetryStatus}
													>
														<svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
															<path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
														</svg>
														<span>Add status</span>
													</button>
												</div>
											</div>

											<div className="grid gap-5 md:grid-cols-3">
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Initial delay (s)</span>
														<InfoTooltip text="Delay before the first retry attempt." />
													</div>
													<input
														type="number"
														min={0}
														className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
														value={state.errorHandlerInitialDelaySeconds}
														onChange={(e) => onUpdateState({ errorHandlerInitialDelaySeconds: e.target.value })}
													/>
												</label>
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Max delay (s)</span>
														<InfoTooltip text="Upper bound for exponential backoff. Use 0 to disable the cap." />
													</div>
													<input
														type="number"
														min={0}
														step="0.1"
														className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
														value={state.errorHandlerMaxDelaySeconds}
														onChange={(e) => onUpdateState({ errorHandlerMaxDelaySeconds: e.target.value })}
													/>
												</label>
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Backoff multiplier</span>
														<InfoTooltip text="Factor by which delay increases between retries." />
													</div>
													<input
														type="number"
														min={1}
														step="0.1"
														className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
														value={state.errorHandlerBackoffMultiplier}
														onChange={(e) => onUpdateState({ errorHandlerBackoffMultiplier: e.target.value })}
													/>
												</label>
											</div>

											<div className="grid gap-5 md:grid-cols-2">
												<label className="flex items-center gap-2">
													<input
														type="checkbox"
														className="h-4 w-4 rounded border-border text-blue-9 focus:ring-blue-5 dark:border-drac-border dark:text-drac-accent dark:focus:ring-drac-accent/40"
														checked={state.errorHandlerRetryOnTimeout}
														onChange={(e) => onUpdateState({ errorHandlerRetryOnTimeout: e.target.checked })}
													/>
													<span className="text-sm text-slate-11 dark:text-drac-foreground/90">Retry on timeout</span>
													<InfoTooltip text="Whether to retry requests that time out." />
												</label>
												<label className="flex items-center gap-2">
													<input
														type="checkbox"
														className="h-4 w-4 rounded border-border text-blue-9 focus:ring-blue-5 dark:border-drac-border dark:text-drac-accent dark:focus:ring-drac-accent/40"
														checked={state.errorHandlerRetryOnConnectionErrors}
														onChange={(e) => onUpdateState({ errorHandlerRetryOnConnectionErrors: e.target.checked })}
													/>
													<span className="text-sm text-slate-11 dark:text-drac-foreground/90">Retry on connection errors</span>
													<InfoTooltip text="Whether to retry requests that fail due to connection issues." />
												</label>
											</div>
										</div>
									)}
								</div>

								{/* Pagination */}
								<div className="space-y-3">
									<button
										type="button"
										className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
										onClick={() => setShowPagination(v => !v)}
										aria-expanded={showPagination}
										aria-controls="pagination-section"
									>
										<span className="flex items-center gap-2">
											Pagination
											<span className="text-xs font-normal text-muted">(optional)</span>
										</span>
										<span className={"transition-transform duration-200 " + (showPagination ? 'rotate-90' : '')}>
											<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
												<path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
											</svg>
										</span>
									</button>
									{showPagination && (
										<div
											id="pagination-section"
											className="space-y-4 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
										>
											<div className="space-y-4">
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Pagination Type</span>
														<InfoTooltip text="Method used to paginate through multiple pages of results" />
													</div>
													<div className="relative">
														<select
															className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm appearance-none pr-9 transition-all focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none"
															value={state.paginationType || 'none'}
															onChange={(e) => onUpdateState({ paginationType: e.target.value as any })}
														>
															<option value="none">None</option>
															<option value="offset">Offset-based</option>
															<option value="cursor">Cursor-based</option>
															<option value="page">Page-based</option>
														</select>
														<span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10 dark:text-drac-muted">
															<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
																<path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" />
															</svg>
														</span>
													</div>
												</label>

												{state.paginationType && state.paginationType !== 'none' && (
													<div className="space-y-4">
														{['offset', 'page', 'cursor'].includes(state.paginationType) && (
															<div className="grid gap-4 md:grid-cols-2">
															<label className="flex flex-col gap-2">
																<div className="flex items-center gap-1">
																	<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Page Size</span>
																	<InfoTooltip text="Number of records requested per page." />
																</div>
																<input
																	type="number"
																	min={1}
																	className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																	placeholder="100"
																	value={state.paginationPageSize || ''}
																	onChange={(e) => onUpdateState({ paginationPageSize: e.target.value })}
																/>
															</label>

															{['offset', 'page', 'cursor'].includes(state.paginationType) && (
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Limit Parameter</span>
																		<InfoTooltip text="Query parameter name used for page size (leave empty to keep existing params)." />
																	</div>
																	<input
																		type="text"
																		className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder={state.paginationType === 'page' ? 'per_page' : 'limit'}
																		value={state.paginationLimitParam || ''}
																		onChange={(e) => onUpdateState({ paginationLimitParam: e.target.value })}
																	/>
																</label>
															)}
														</div>)})

														{state.paginationType === 'offset' && (
															<div className="grid gap-4 md:grid-cols-2">
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Offset Parameter</span>
																		<InfoTooltip text="Query parameter that carries the current offset value." />
																	</div>
																	<input
																		type="text"
																		className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="offset"
																		value={state.paginationOffsetParam || ''}
																		onChange={(e) => onUpdateState({ paginationOffsetParam: e.target.value })}
																	/>
																</label>
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Start Offset</span>
																		<InfoTooltip text="First offset value to request (defaults to 0)." />
																	</div>
																	<input
																		type="number"
																		min={0}
																		className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="0"
																		value={state.paginationStartOffset || ''}
																		onChange={(e) => onUpdateState({ paginationStartOffset: e.target.value })}
																	/>
																</label>
															</div>)})
															</div>
														)}

														{state.paginationType === 'page' && (
															<div className="grid gap-4 md:grid-cols-2">
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Page Parameter</span>
																		<InfoTooltip text="Query parameter that carries the current page number." />
																	</div>
																	<input
																		type="text"
																		className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="page"
																		value={state.paginationPageParam || ''}
																		onChange={(e) => onUpdateState({ paginationPageParam: e.target.value })}
																	/>
																</label>
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Start Page</span>
																		<InfoTooltip text="First page number to request (defaults to 1)." />
																	</div>
																	<input
																		type="number"
																		min={1}
																		className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="1"
																		value={state.paginationStartPage || ''}
																		onChange={(e) => onUpdateState({ paginationStartPage: e.target.value })}
																	/>
																</label>
															</div>
														)}

														{state.paginationType === 'cursor' && (
															<div className="grid gap-4 md:grid-cols-2">
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor Parameter</span>
																		<InfoTooltip text="Query parameter that receives the next cursor value." />
																	</div>
																	<input
																		type="text"
																		className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="cursor"
																		value={state.paginationCursorParam || ''}
																		onChange={(e) => onUpdateState({ paginationCursorParam: e.target.value })}
																	/>
																</label>
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor Path</span>
																		<InfoTooltip text="Dotted path to the cursor value in the response payload (e.g. meta.next_cursor)." />
																	</div>
																	<InputWithCursorPosition
																		className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="meta.next_cursor"
																		value={state.paginationCursorPath || ''}
																		onValueChange={(value) => onUpdateState({ paginationCursorPath: value })}
																	/>
																</label>
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Next URL Path</span>
																		<InfoTooltip text="Dotted path to a fully qualified 'next' link in the payload (optional)." />
																	</div>
																	<InputWithCursorPosition
																		className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="links.next"
																		value={state.paginationNextUrlPath || ''}
																		onValueChange={(value) => onUpdateState({ paginationNextUrlPath: value })}
																	/>
																</label>
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor Header</span>
																		<InfoTooltip text="Response header that carries the next cursor (optional)." />
																	</div>
																	<input
																		type="text"
																		className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="X-Next-Cursor"
																		value={state.paginationCursorHeader || ''}
																		onChange={(e) => onUpdateState({ paginationCursorHeader: e.target.value })}
																	/>
																</label>
																<label className="flex flex-col gap-2">
																	<div className="flex items-center gap-1">
																		<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Initial Cursor</span>
																		<InfoTooltip text="Fallback cursor value sent on the first request." />
																	</div>
																	<input
																		type="text"
																		className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder="Provided by API"
																		value={state.paginationInitialCursor || ''}
																		onChange={(e) => onUpdateState({ paginationInitialCursor: e.target.value })}
																	/>
																</label>
															</div>
														)}

														<div className="flex items-center gap-2">
															<input
																type="checkbox"
																className="h-4 w-4 rounded border-border text-blue-7 focus:ring-blue-5"
																checked={state.paginationStopOnEmptyResponse}
																onChange={(e) => onUpdateState({ paginationStopOnEmptyResponse: e.target.checked })}
															/>
															<span className="text-sm text-slate-11 dark:text-drac-foreground/90">Stop when the API returns no records</span>
														</div>
													</div>
												)
											</div>)}
										</div>
									)
								</div>

								{/* Incremental Sync */}
								<div className="space-y-3">
									<button
										type="button"
										className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
										onClick={() => setShowIncremental(v => !v)}
										aria-expanded={showIncremental}
										aria-controls="incremental-section"
									>
										<span className="flex items-center gap-2">
											Incremental Sync
											<span className="text-xs font-normal text-muted">({incrementalSummary})</span>
										</span>
										<span className={"transition-transform duration-200 " + (showIncremental ? 'rotate-90' : '')}>
											<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
												<path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
											</svg>
										</span>
									</button>
									{showIncremental && (
										<div
											id="incremental-section"
											className="space-y-4 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
										>
											<div className="grid gap-4 md:grid-cols-3">
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Mode</span>
														<InfoTooltip text="Short label for the incremental strategy (e.g. updated_at, created_at)." />
													</div>
													<input
														type="text"
														className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
														placeholder="updated_at"
														value={state.incrementalMode}
														onChange={(e) => onUpdateState({ incrementalMode: e.target.value })}
													/>
												</label>
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor parameter</span>
														<InfoTooltip text="Query parameter added to each request (e.g. since, updated_after)." />
													</div>
													<input
														type="text"
														className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
														placeholder="since"
														value={state.incrementalCursorParam}
														onChange={(e) => onUpdateState({ incrementalCursorParam: e.target.value })}
													/>
												</label>
												<label className="flex flex-col gap-2">
													<div className="flex items-center gap-1">
														<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor field</span>
														<InfoTooltip text="Field in the response used to compute the next cursor (supports dotted paths)." />
													</div>
													<input
														type="text"
														className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
														placeholder="updated_at"
														value={state.incrementalCursorField}
														onChange={(e) => onUpdateState({ incrementalCursorField: e.target.value })}
													/>
												</label>
											</div>

											<div className="space-y-4">
												<p className="text-xs text-muted dark:text-drac-muted">
													Runtime options are passed to <code>spark.read.option(...)</code> and are not stored in the YAML file.
												</p>
												<div className="grid gap-4 md:grid-cols-2">
													<label className="flex flex-col gap-2">
														<div className="flex items-center gap-1">
															<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">State file or URL</span>
															<InfoTooltip text="Location where Polymo stores the latest cursor. Supports local paths and fsspec URLs (s3://, gs://, etc.)." />
														</div>
														<input
															type="text"
															className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
															placeholder="/tmp/polymo-state.json or s3://team/state.json"
															value={state.incrementalStatePath}
															onChange={(e) => onUpdateState({ incrementalStatePath: e.target.value })}
														/>
													</label>
													<label className="flex flex-col gap-2">
														<div className="flex items-center gap-1">
															<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Initial cursor value</span>
															<InfoTooltip text="Fallback value used when no state file is present." />
														</div>
														<input
															type="text"
															className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
															placeholder="2024-01-01T00:00:00Z"
															value={state.incrementalStartValue}
															onChange={(e) => onUpdateState({ incrementalStartValue: e.target.value })}
														/>
													</label>
												</div>
												<div className="grid gap-4 md:grid-cols-2">
													<label className="flex flex-col gap-2">
														<div className="flex items-center gap-1">
															<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">State key override</span>
															<InfoTooltip text="Optional identifier when sharing a state file across multiple connectors." />
														</div>
														<input
															type="text"
															className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
															placeholder="orders-prod"
															value={state.incrementalStateKey}
															onChange={(e) => onUpdateState({ incrementalStateKey: e.target.value })}
														/>
													</label>
													<label className="flex items-start gap-3 rounded-xl border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-3 text-left">
														<input
															type="checkbox"
															className="mt-1 h-4 w-4 rounded border border-border accent-blue-9"
															checked={state.incrementalMemoryEnabled}
															onChange={(e) => onUpdateState({ incrementalMemoryEnabled: e.target.checked })}
														/>
														<div className="space-y-1">
															<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Keep cursor in memory when no file is set</span>
															<p className="text-xs text-muted dark:text-drac-muted">Uncheck to force a fresh start unless a state path is provided.</p>
														</div>
													</label>
												</div>
											</div>
										</div>
									)}
								</div>

								{/* Record Selector */}
								<div className="space-y-3">
									<button
									 type="button"
										className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
										onClick={() => setShowRecordSelector(v => !v)}
										aria-expanded={showRecordSelector}
										aria-controls="record-selector-section"
									>
										<span className="flex items-center gap-2">
											Record Selector
											<span className="text-xs font-normal text-muted">
												{(state.recordFieldPath?.length ?? 0) > 0 ? state.recordFieldPath.join(' › ') : 'root'}
												{state.recordFilter.trim() ? ' · filter' : ''}
												{state.castToSchemaTypes ? ' · cast' : ''}
											</span>
										</span>
										<span className={"transition-transform duration-200 " + (showRecordSelector ? 'rotate-90' : '')}>
											<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
												<path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
											</svg>
										</span>
									</button>
									{showRecordSelector && (
										<div
											id="record-selector-section"
											className="space-y-4 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
										>
											<div className="space-y-3">
												<div className="flex items-center gap-1">
													<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Field Path</span>
													<InfoTooltip text="List the keys leading to the array of records. Use * to follow all children." />
												</div>
												<div className="space-y-2">
													{(state.recordFieldPath?.length ?? 0) > 0 ? (
														<div className="space-y-2">
															{(state.recordFieldPath || []).map((segment, index) => (
																<div key={index} className="flex items-center gap-2">
																	<input
																		type="text"
																		className="flex-1 rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5"
																		placeholder={index === 0 ? 'data' : index === (state.recordFieldPath?.length ?? 0) - 1 ? 'items' : 'segment'}
																		value={segment}
																		onChange={(e) => handleUpdateFieldPathSegment(index, e.target.value)}
																	/>
																	<button
																		type="button"
																		className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#2d3541] text-slate-11 dark:text-drac-muted hover:text-red-10 hover:border-red-7 hover:bg-red-3/60 dark:hover:text-drac-red dark:hover:border-drac-red/80 dark:hover:bg-[#383f4c] transition-colors"
																		onClick={() => handleRemoveFieldPathSegment(index)}
																		aria-label={`Remove path segment ${segment || index + 1}`}
																	>
																		<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
																			<path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
																		</svg>
																	</button>
																</div>
															))}
														</div>
													) : (
														<p className="text-sm text-muted dark:text-drac-muted">Selecting records from the response root.</p>
													)}
													<div>
														<button
															type="button"
															className="inline-flex items-center gap-1.5 rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#242a33] px-3 py-1.5 text-xs font-medium text-slate-11 dark:text-drac-foreground shadow-sm transition-all duration-200 hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent"
															onClick={handleAddFieldPathSegment}
														>
															<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
																<path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
															</svg>
															Add path segment
														</button>
													</div>
												</div>
											</div>

											<div className="space-y-2">
												<div className="flex items-center gap-1">
													<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Record Filter</span>
													<InfoTooltip text="Keep only records where this Jinja expression evaluates to true." />
												</div>
												<textarea
													className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-3 py-2 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border focus-visible:ring-1 focus-visible:ring-blue-5 min-h-[96px]"
													placeholder="{{ record.status != 'expired' }}"
													value={state.recordFilter}
													onChange={(e) => onUpdateState({ recordFilter: e.target.value })}
												/>
													<p className="text-xs text-muted dark:text-drac-muted">
														Expressions can be wrapped in <code>{'{{'}</code>&nbsp;expression&nbsp;<code>{'}}'}</code> or entered directly.
													</p>
											</div>

											<label className="flex items-start gap-3 rounded-xl border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-3 text-left">
												<input
													type="checkbox"
													className="mt-1 h-4 w-4 rounded border border-border accent-blue-9"
													checked={state.castToSchemaTypes}
													onChange={(e) => onUpdateState({ castToSchemaTypes: e.target.checked })}
												/>
												<div className="space-y-1">
													<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cast record fields to schema types</span>
													<p className="text-xs text-muted dark:text-drac-muted">Applies declared schema types to each record before ingestion.</p>
												</div>
											</label>
										</div>
									)}
								</div>

								{/* Spark Reader Options */}
								<div className="space-y-3">
									<button
										type="button"
										className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
										onClick={() => setShowReaderOptions(v => !v)}
										aria-expanded={showReaderOptions}
										aria-controls="reader-options-section"
									>
										<span className="flex items-center gap-2">
											Spark Reader Options
											<span className="text-xs font-normal text-muted">({runtimeOptionSummary})</span>
										</span>
										<span className={"transition-transform duration-200 " + (showReaderOptions ? 'rotate-90' : '')}>
											<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
												<path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
											</svg>
										</span>
									</button>
									{showReaderOptions && (
										<div
											id="reader-options-section"
											className="space-y-4 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
										>
											<div className="flex items-center justify-between">
												<h4 className="text-sm font-semibold text-slate-12 dark:text-drac-foreground">Reader Options</h4>
												<button
													type="button"
													className="inline-flex items-center gap-1.5 rounded-full border border-border/60 dark:border-drac-border bg-background/70 dark:bg-[#242a33] px-4 py-1.5 text-xs font-medium text-slate-11 dark:text-drac-foreground shadow-sm transition-all duration-200 hover:border-blue-7 hover:text-blue-11 dark:hover:border-drac-accent dark:hover:text-drac-accent hover:scale-105 hover:shadow-md dark:hover:shadow-[0_0_8px_rgba(80,250,123,0.15)] hover:bg-blue-3/50 dark:hover:bg-[#273242] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-7 dark:focus-visible:ring-drac-accent"
													onClick={handleAddReaderOption}
												>
													<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
														<path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
													</svg>
													<span>Add Option</span>
												</button>
											</div>
											{Object.entries(readerOptions).length > 0 ? (
												<ul className="flex flex-col gap-2">
													{Object.entries(readerOptions).map(([key, value]) => (
														<ReaderOptionRow key={key} originalKey={key} value={String(value)} onUpdateKey={handleUpdateReaderOption} onUpdateValue={handleUpdateReaderOption} onRemove={handleRemoveReaderOption} />
													))}
												</ul>
											) : (
												<p className="text-sm text-muted dark:text-drac-muted">No reader options configured.</p>
											)}
										</div>
									)}
								</div> </Tabs.Content>
					</Tabs.Root></section>
							</div>

						<Tabs.Content value="schema" className="p-8 outline-none">
							<div className="space-y-8">
								<div className="space-y-4">
									<label className="flex items-center gap-2">
										<input
											type="checkbox"
											className="rounded border-border h-5 w-5 accent-blue-9 dark:accent-drac-accent focus:ring-blue-7 dark:focus:ring-drac-accent"
											checked={state.inferSchema}
											onChange={(e) => onUpdateState({ inferSchema: e.target.checked })}
										/>
										<span className="text-sm font-medium text-slate-11 flex items-center gap-1">
											Infer schema automatically
											<InfoTooltip text="Automatically infer columns and types from sample data." />
										</span>
									</label>

									{!state.inferSchema && (
										<label className="flex flex-col gap-2 mt-4">
											<div className="flex items-center gap-1">
												<span className="text-sm font-medium text-slate-11">Schema DDL</span>
												<InfoTooltip text="Explicit schema when inference is disabled. Format: name TYPE, ..." />
											</div>
											<textarea
												className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2 transition-all focus-visible:ring-1 focus-visible:ring-blue-5 font-mono"
												placeholder="id INT, name STRING, created_at TIMESTAMP"
												rows={8}
												value={state.schema}
												onChange={(e) => onUpdateState({ schema: e.target.value })}
											/>
											<p className="text-xs text-muted dark:text-drac-muted mt-1">
												Example: <code>id INTEGER, name STRING, created_at TIMESTAMP</code>
											</p>
										</label>
									)}
								</div>
							</div>
						</Tabs.Content> </div>
	);
};
