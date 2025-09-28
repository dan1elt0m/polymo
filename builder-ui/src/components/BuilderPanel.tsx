import React from "react";
import type { ConfigFormState } from "../types";
import { InfoTooltip } from "./InfoTooltip";

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
						<p className="text-sm text-muted">Configure your REST API stream endpoint and authentication.</p>
					</div>

					<div className="space-y-6 rounded-2xl border border-border bg-background p-6">
						{/* API Configuration */}
						<div className="space-y-4">
							<h3 className="text-base font-semibold text-slate-12">API Settings</h3>
							<div className="grid gap-4 md:grid-cols-2">
								<label className="flex flex-col gap-2">
									<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Base URL</span><InfoTooltip text="Root HTTPS endpoint of the API. Exclude the trailing slash." /></div>
									<input
										type="url"
										className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2"
										placeholder="https://api.example.com"
										value={state.baseUrl}
										onChange={(event) => onUpdateState({ baseUrl: event.target.value })}
									/>
								</label>
								<label className="flex flex-col gap-2">
									<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Stream Name</span><InfoTooltip text="Internal name for this stream. Lowercase, no spaces." /></div>
									<input
										type="text"
										className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2"
										placeholder="orders"
										value={state.streamName}
										onChange={(event) => onUpdateState({ streamName: event.target.value })}
									/>
								</label>
							</div>
							<div className="grid gap-4 md:grid-cols-2">
								<label className="flex flex-col gap-2">
									<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Stream Path</span><InfoTooltip text="Endpoint path appended to the base URL. Must start with /" /></div>
									<input
										type="text"
										className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2"
										placeholder="/v1/orders"
										value={state.streamPath}
										onChange={(event) => onUpdateState({ streamPath: event.target.value })}
									/>
								</label>
								<label className="flex flex-col gap-2">
									<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Pagination Type</span><InfoTooltip text="Strategy for requesting additional pages (none or RFC5988 Link)." /></div>
									<div className="relative">
										<select
											className="modern-select pr-9"
											value={state.paginationType}
											onChange={(event) => onUpdateState({ paginationType: event.target.value as 'none' | 'link_header' })}
										>
											<option value="none">None</option>
											<option value="link_header">Link Header</option>
										</select>
										<span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10 dark:text-slate-11"><svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4"><path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" /></svg></span>
									</div>
								</label>
							</div>
						</div>

						{/* Authentication */}
						<div className="space-y-4">
							<h3 className="text-base font-semibold text-slate-12">Authentication</h3>
							<div className="grid gap-4 md:grid-cols-2">
								<label className="flex flex-col gap-2">
									<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Auth Type</span><InfoTooltip text="Authentication method applied to each request. Only for previewing data: Auth details aren't stored in YAML file, but should be provided as options to the reader" /></div>
									<div className="relative">
										<select
											className="modern-select pr-9"
											value={state.authType}
											onChange={(event) => onUpdateState({ authType: event.target.value as 'none' | 'bearer' })}
										>
											<option value="none">None</option>
											<option value="bearer">Bearer Token</option>
										</select>
										<span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10 dark:text-slate-11"><svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4"><path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" /></svg></span>
									</div>
								</label>
								{state.authType === 'bearer' && (
									<label className="flex flex-col gap-2">
										<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Bearer Token</span><InfoTooltip text="Secret token sent as Authorization header." /></div>
										<input
											type="password"
											className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2"
											placeholder="your-token-here"
											value={state.authToken}
											onChange={(event) => onUpdateState({ authToken: event.target.value })}
										/>
									</label>
								)}
							</div>
						</div>

						{/* Incremental Configuration */}
						<div className="space-y-4">
							<h3 className="text-base font-semibold text-slate-12">Incremental Loading</h3>
							<div className="grid gap-4 md:grid-cols-3">
								<label className="flex flex-col gap-2">
									<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Mode</span><InfoTooltip text="Incremental strategy, e.g. append." /></div>
									<input
										type="text"
										className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2"
										placeholder="append"
										value={state.incrementalMode}
										onChange={(event) => onUpdateState({ incrementalMode: event.target.value })}
									/>
								</label>
								<label className="flex flex-col gap-2">
									<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Cursor Param</span><InfoTooltip text="Query parameter that advances the cursor." /></div>
									<input
										type="text"
										className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2"
										placeholder="since"
										value={state.incrementalCursorParam}
										onChange={(event) => onUpdateState({ incrementalCursorParam: event.target.value })}
									/>
								</label>
								<label className="flex flex-col gap-2">
									<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Cursor Field</span><InfoTooltip text="Field in responses used to resume later requests." /></div>
									<input
										type="text"
										className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2"
										placeholder="updated_at"
										value={state.incrementalCursorField}
										onChange={(event) => onUpdateState({ incrementalCursorField: event.target.value })}
									/>
								</label>
							</div>
						</div>

						{/* Schema Configuration */}
						<div className="space-y-4">
							<h3 className="text-base font-semibold text-slate-12">Schema</h3>
							<div className="space-y-4">
								<label className="flex items-center gap-2">
									<input
										type="checkbox"
										className="rounded border-border"
										checked={state.inferSchema}
										onChange={(event) => onUpdateState({ inferSchema: event.target.checked })}
									/>
									<span className="text-sm font-medium text-slate-11 flex items-center gap-1">Infer schema automatically<InfoTooltip text="Automatically infer columns and types from sample data." /></span>
								</label>
								{!state.inferSchema && (
									<label className="flex flex-col gap-2">
										<div className="flex items-center gap-1"><span className="text-sm font-medium text-slate-11">Schema DDL</span><InfoTooltip text="Explicit schema when inference is disabled. Format: name TYPE, ..." /></div>
										<textarea
											className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7 dark:border-slate-6 dark:bg-slate-2"
											placeholder="id INT, name STRING, created_at TIMESTAMP"
											rows={3}
											value={state.schema}
											onChange={(event) => onUpdateState({ schema: event.target.value })}
										/>
									</label>
								)}
							</div>
						</div>

						{/* Parameters */}
						<div className="space-y-4">
							<div className="flex items-center justify-between">
								<h3 className="text-base font-semibold text-slate-12 flex items-center gap-2">Query Parameters <InfoTooltip text="Key/value query string arguments included with every request." /></h3>
								<button
									type="button"
									className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-3 py-1.5 text-sm font-medium text-slate-11 shadow-sm transition hover:border-blue-7 hover:text-blue-11 focus-visible:ring-2 focus-visible:ring-blue-7"
									onClick={onAddParam}
								>
									<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4"><path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" /></svg>
									<span>Add</span>
								</button>
							</div>
							{Object.entries(state.params).length > 0 ? (
								<ul className="flex flex-col gap-2">
									{Object.entries(state.params).map(([key, value]) => (
										<li key={key} className="group relative rounded-xl border border-border/70 bg-background/60 backdrop-blur-sm px-3 py-3 shadow-inner transition hover:border-blue-7/60 hover:bg-background/80 dark:border-drac-border/50 dark:bg-drac-surface/40 dark:hover:bg-drac-surface/60 dark:shadow-none">
											<div className="grid gap-3 md:grid-cols-2">
												<div className="flex flex-col gap-1.5">
													<label className="text-[11px] tracking-wide text-muted font-medium flex items-center gap-1">Name <InfoTooltip text="Parameter key sent with request." /></label>
													<input
														type="text"
														className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm transition focus-visible:border-blue-7 group-hover:border-blue-7/50 dark:border-slate-6 dark:bg-slate-2"
														placeholder="param_name"
														value={key}
														onChange={(event) => onUpdateParam(key, event.target.value, value)}
													/>
												</div>
												<div className="flex flex-col gap-1.5">
													<label className="text-[11px] tracking-wide text-muted font-medium flex items-center gap-1">Value <InfoTooltip text="Parameter value associated with the key." /></label>
													<input
														type="text"
														className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm transition focus-visible:border-blue-7 group-hover:border-blue-7/50 dark:border-slate-6 dark:bg-slate-2"
														placeholder="value"
														value={value}
														onChange={(event) => onUpdateParam(key, key, event.target.value)}
													/>
												</div>
											</div>
											<button
												type="button"
												className="absolute -right-2 -top-2 inline-flex h-7 w-7 items-center justify-center rounded-full border border-border/60 bg-background/80 text-slate-11 opacity-0 shadow-sm backdrop-blur transition hover:text-red-10 hover:border-red-7 hover:bg-red-3/60 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-red-7"
												onClick={() => onRemoveParam(key)}
												aria-label={`Remove parameter ${key}`}
											>
												<svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4"><path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" /></svg>
											</button>
										</li>
									))}
								</ul>
							) : (
								<p className="text-sm text-muted">No parameters configured.</p>
							)}
						</div>
					</div>
				</section>
			</div>
		</div>
	);
};
