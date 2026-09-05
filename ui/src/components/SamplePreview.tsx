import React from "react";
import * as Select from "@radix-ui/react-select";
import { clsx } from "clsx";
import { collectColumns, formatCell, truncate } from "../lib/table";
import { PAGE_SIZE_OPTIONS, SAMPLE_VIEWS } from "../lib/constants";
import type { RawPagePayload, StatusState } from "../types";
import { BTN_PRIMARY, BTN_SECONDARY, BTN_SMALL, Callout, ChevronIcon, INPUT, LABEL, SegmentedControl, cx } from "./ui/primitives";

interface SamplePreviewProps {
	status: StatusState;
	limit: number;
	onLimitChange: (value: number) => void;
	onPreview: () => void;
	isBusy: boolean;
	view: "table" | "json" | "raw";
	onViewChange: (value: "table" | "json" | "raw") => void;
	wrap: boolean;
	onWrapToggle: () => void;
	page: number;
	pageSize: number;
	onPageSizeChange: (value: number) => void;
	onPageChange: (value: number) => void;
	data: Array<Record<string, unknown>>;
	dtypes: Array<{ column: string; type: string }>;
	rawPages: RawPagePayload[];
	restError: string | null;
	onCopySchema: () => void;
	placeholderNotice?: string | null;
	/** Focus mode: the preview owns the full width. */
	focus: boolean;
	onToggleFocus: () => void;
}

export const SamplePreview: React.FC<SamplePreviewProps> = ({
	status,
	limit,
	onLimitChange,
	onPreview,
	isBusy,
	view,
	onViewChange,
	wrap,
	onWrapToggle,
	page,
	pageSize,
	onPageSizeChange,
	onPageChange,
	data,
	dtypes,
	rawPages,
	restError,
	onCopySchema,
	placeholderNotice,
	focus,
	onToggleFocus,
}) => {
	const hasTableData = data.length > 0;
	const hasRawData = rawPages.length > 0 || Boolean(restError);
	const totalPages = hasTableData ? Math.max(1, Math.ceil(data.length / pageSize)) : 0;
	const safePage = hasTableData ? Math.min(Math.max(page, 1), totalPages) : 1;
	const rows =
		hasTableData && view === SAMPLE_VIEWS.TABLE
			? data.slice((safePage - 1) * pageSize, safePage * pageSize)
			: [];
	const columns = hasTableData && view === SAMPLE_VIEWS.TABLE ? collectColumns(rows) : [];
	const isTable = hasTableData && view === SAMPLE_VIEWS.TABLE;

	return (
		<div className="flex h-full min-h-0 w-full min-w-0 flex-col">
			<header className="flex min-h-12 shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-border px-4 py-2">
				<h2 className="shrink-0 text-sm font-semibold text-fg">Data preview</h2>
				<span className="status-slot flex min-w-0 flex-1 items-center">
					<StatusPill status={status} />
				</span>
				<div className="ml-auto flex shrink-0 items-center gap-2">
					<label className="flex items-center gap-1.5">
						<span className={cx(LABEL, "label-long")}>Limit</span>
						<input
							type="number"
							min={1}
							max={1000}
							className={cx(INPUT, "h-8 max-w-[4.5rem] px-2 text-xs tabular-nums")}
							value={limit}
							onChange={(event) => onLimitChange(Number(event.target.value))}
							aria-label="Sample row limit"
						/>
					</label>
					<button
						type="button"
						className={cx(BTN_SECONDARY, "h-8 px-3 text-xs")}
						onClick={onCopySchema}
						disabled={!dtypes.length && !data.length}
						aria-label="Copy schema in DDL format"
						title="Copy schema as DDL"
					>
						<span className="label-long">Copy schema</span>
						<span className="label-short">DDL</span>
					</button>
					<button
						type="button"
						className={cx(BTN_PRIMARY, "h-8 px-3.5 text-xs")}
						onClick={onPreview}
						disabled={isBusy}
						data-testid="data-preview-button"
					>
						{isBusy ? "Working…" : "Preview"}
					</button>
					<button
						type="button"
						className={cx(
							"inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors",
							focus
								? "border-accent bg-accent-soft text-accent-text"
								: "border-border bg-surface text-fg-muted hover:border-border-strong hover:text-fg",
						)}
						onClick={onToggleFocus}
						aria-pressed={focus}
						aria-label={focus ? "Exit focus mode" : "Focus preview (hide configuration)"}
						title={focus ? "Exit focus mode" : "Focus preview"}
						data-testid="focus-preview-toggle"
					>
						{focus ? (
							<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true">
								<path d="M6.5 2.5v4h-4M9.5 13.5v-4h4M2.5 9.5h4v4M13.5 6.5h-4v-4" />
							</svg>
						) : (
							<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true">
								<path d="M2.5 6.5v-4h4M13.5 9.5v4h-4M2.5 9.5v4h4M13.5 6.5v-4h-4" />
							</svg>
						)}
					</button>
				</div>
			</header>

			<div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
				{status.tone === "error" && (
					<Callout tone="error" testId="preview-error-notice">
						{status.message}
					</Callout>
				)}
				{placeholderNotice && (
					<Callout tone="info" testId="option-placeholder-notice">
						{placeholderNotice}
					</Callout>
				)}

				<div className="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-2">
					<div className="flex items-center gap-2">
						<SegmentedControl
							aria-label="Preview view"
							size="sm"
							value={view}
							onChange={onViewChange}
							options={[
								{ value: SAMPLE_VIEWS.TABLE, label: "DataFrame", disabled: !hasTableData || isBusy, testId: "view-tab-dataframe" },
								{ value: SAMPLE_VIEWS.JSON, label: "Records", disabled: !hasTableData || isBusy, testId: "view-tab-records" },
								{ value: SAMPLE_VIEWS.RAW, label: "Raw API", disabled: !hasRawData || isBusy, testId: "view-tab-raw" },
							]}
						/>
						<button
							type="button"
							className={cx(
								"inline-flex h-7 items-center rounded-md border px-2.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
								wrap && isTable ? "border-accent bg-accent-soft text-accent-text" : "border-border bg-field text-fg-muted hover:text-fg",
							)}
							onClick={onWrapToggle}
							disabled={!hasTableData || view !== SAMPLE_VIEWS.TABLE || isBusy}
							aria-pressed={wrap && isTable}
						>
							Wrap text
						</button>
					</div>
					<div className="flex items-center gap-2 text-xs text-fg-muted">
						{hasTableData && (
							<span className="tabular-nums">
								{data.length} row{data.length === 1 ? "" : "s"}
							</span>
						)}
						<SelectPageSize value={pageSize} onValueChange={onPageSizeChange} disabled={!hasTableData || isBusy} />
						<div className="inline-flex items-center rounded-md border border-border bg-field">
							<button
								type="button"
								className="inline-flex h-7 w-7 items-center justify-center rounded-l-md text-fg-muted transition-colors hover:bg-raised hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
								onClick={() => onPageChange(Math.max(1, safePage - 1))}
								disabled={!hasTableData || safePage <= 1 || isBusy}
								aria-label="Previous page"
							>
								<ChevronIcon direction="left" />
							</button>
							<span className="min-w-[4.5rem] border-x border-border px-2 text-center tabular-nums">
								{totalPages ? `${safePage} / ${totalPages}` : "0 / 0"}
							</span>
							<button
								type="button"
								className="inline-flex h-7 w-7 items-center justify-center rounded-r-md text-fg-muted transition-colors hover:bg-raised hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
								onClick={() => onPageChange(Math.min(totalPages, safePage + 1))}
								disabled={!hasTableData || safePage >= totalPages || isBusy}
								aria-label="Next page"
							>
								<ChevronIcon />
							</button>
						</div>
					</div>
				</div>

				<div
					className={cx(
						"scroll-thin relative min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-field",
						!isTable && "p-4",
					)}
					data-testid="preview-viewport"
				>
					{renderOutput({ view, data, rows, columns, dtypes, wrap, rawPages, restError })}
				</div>
			</div>
		</div>
	);
};

interface SelectPageSizeProps {
	value: number;
	onValueChange: (value: number) => void;
	disabled: boolean;
}

const SelectPageSize: React.FC<SelectPageSizeProps> = ({ value, onValueChange, disabled }) => (
	<Select.Root
		value={String(value)}
		onValueChange={(next) => onValueChange(Number(next))}
		disabled={disabled}
	>
		<Select.Trigger
			className="inline-flex h-7 items-center gap-1.5 rounded-md border border-border bg-field px-2.5 text-xs text-fg-muted transition-colors hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
			aria-label="Rows per page"
		>
			<Select.Value />
			<ChevronIcon direction="down" className="h-3 w-3" />
		</Select.Trigger>
		<Select.Portal>
			<Select.Content className="z-50 overflow-hidden rounded-md border border-border bg-surface shadow-card" position="popper" sideOffset={4}>
				<Select.Viewport className="p-1">
					{PAGE_SIZE_OPTIONS.map((option) => (
						<Select.Item
							key={option}
							value={String(option)}
							className="flex cursor-pointer select-none items-center gap-2 rounded px-2 py-1.5 text-xs text-fg outline-none data-[highlighted]:bg-raised data-[state=checked]:text-accent-text"
						>
							<Select.ItemText>{option} rows</Select.ItemText>
						</Select.Item>
					))}
				</Select.Viewport>
			</Select.Content>
		</Select.Portal>
	</Select.Root>
);

const StatusPill: React.FC<{ status: StatusState }> = ({ status }) => (
	<span
		className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-border bg-field px-2.5 py-0.5 text-xs font-medium"
		data-status={status.tone}
		title={status.message}
	>
		<span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
		<span className="truncate">{status.message}</span>
	</span>
);

function renderOutput({
	view,
	data,
	rows,
	columns,
	dtypes,
	wrap,
	rawPages,
	restError,
}: {
	view: "table" | "json" | "raw";
	data: Array<Record<string, unknown>>;
	rows: Array<Record<string, unknown>>;
	columns: string[];
	dtypes: Array<{ column: string; type: string }>;
	wrap: boolean;
	rawPages: RawPagePayload[];
	restError: string | null;
}) {
	if (view === SAMPLE_VIEWS.RAW) {
		if (!rawPages.length && !restError) {
			return <EmptyState>REST client did not return any data.</EmptyState>;
		}

		return (
			<div className="space-y-3">
				{restError && (
					<p className="text-sm font-medium text-error" data-status="error">
						{restError}
					</p>
				)}
				<pre
					data-status={restError ? "error" : "info"}
					className="m-0 whitespace-pre-wrap break-words bg-transparent p-0 font-mono text-xs leading-5 text-fg"
				>
					{JSON.stringify({ pages: rawPages }, null, 2)}
				</pre>
			</div>
		);
	}

	if (!data.length) {
		return (
			<EmptyState>
				<span className="text-sm text-fg-muted">Preview will appear here after sampling.</span>
				<span className="text-xs text-fg-subtle">Fill in a base URL and stream path, then press Preview.</span>
			</EmptyState>
		);
	}

	if (view === SAMPLE_VIEWS.JSON) {
		return (
			<pre data-status="info" className="m-0 whitespace-pre-wrap break-words bg-transparent p-0 font-mono text-xs leading-5 text-fg">
				{JSON.stringify({ records: data }, null, 2)}
			</pre>
		);
	}

	return (
		<table
			className={clsx(
				"w-full min-w-max border-separate border-spacing-0 text-[13px]",
				wrap ? "[&_td]:whitespace-pre-wrap" : "[&_td]:whitespace-nowrap",
			)}
		>
			<thead>
				<tr>
					{columns.map((column) => (
						<th
							key={column}
							className="sticky top-0 z-10 border-b border-border bg-raised px-3 py-2 text-left align-bottom"
						>
							<div className="flex flex-col gap-0.5">
								<span className="text-xs font-semibold text-fg">{column}</span>
								{renderColumnType(column, dtypes)}
							</div>
						</th>
					))}
				</tr>
			</thead>
			<tbody>
				{rows.map((row, rowIndex) => (
					<tr key={rowIndex} className="group">
						{columns.map((column) => {
							const value = column in row ? row[column] : "";
							const text = formatCell(value);
							const needsTooltip = text.length > 500;
							return (
								<td
									key={column}
									className="border-b border-border/70 px-3 py-1.5 align-top font-mono text-xs text-fg-muted transition-colors group-hover:bg-accent-soft/60 group-hover:text-fg"
									title={needsTooltip ? text : undefined}
								>
									{needsTooltip ? truncate(text, 500) : text}
								</td>
							);
						})}
					</tr>
				))}
			</tbody>
		</table>
	);
}

const EmptyState: React.FC<{ children: React.ReactNode }> = ({ children }) => (
	<div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-1 text-center" data-status="info">
		<span className="mb-2 flex h-9 w-9 items-center justify-center rounded-full border border-dashed border-border-strong text-fg-subtle" aria-hidden="true">
			<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="h-4 w-4">
				<path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />
			</svg>
		</span>
		{children}
	</div>
);

function renderColumnType(column: string, dtypes: Array<{ column: string; type: string }>) {
	const dtype = dtypes.find((entry) => entry.column === column);
	if (!dtype) {
		return null;
	}
	return <span className="font-mono text-[10px] font-medium uppercase tracking-wide text-fg-subtle">{dtype.type}</span>;
}
