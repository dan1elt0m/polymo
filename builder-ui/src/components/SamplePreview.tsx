import React from "react";
import * as Select from "@radix-ui/react-select";
import { clsx } from "clsx";
import { collectColumns, formatCell, truncate } from "../lib/table";
import { PAGE_SIZE_OPTIONS, SAMPLE_VIEWS } from "../lib/constants";
import type { RawPagePayload, StatusState } from "../types";

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
	onCopySchema: () => void; // new
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

	return (
		<div className="flex h-full flex-col gap-4 min-w-0 w-full max-w-full">
			<header className="flex flex-col gap-3 min-w-0">
				<div className="flex items-center justify-between gap-3 min-w-0 flex-wrap">
					<h2 className="text-lg font-semibold text-slate-12 truncate">Data Preview</h2>
					<div className="flex items-center gap-2">
					<button
						type="button"
						className="rounded-full border border-border px-4 py-2 text-sm font-semibold text-slate-12 transition hover:border-blue-7 hover:text-blue-11 disabled:opacity-50"
						onClick={onPreview}
						disabled={isBusy}
						data-testid="data-preview-button"
					>
							{isBusy ? "Working…" : "Preview"}
						</button>
						<button
							type="button"
							className="rounded-full border border-border px-4 py-2 text-sm font-medium text-slate-11 hover:border-blue-7 hover:text-blue-11 disabled:opacity-50"
							onClick={onCopySchema}
							disabled={(!dtypes.length && !data.length)}
							aria-label="Copy schema in DDL format"
						>
							Copy Schema
						</button>
					</div>
				</div>
				<div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(200px,auto)] lg:items-end min-w-0">
					<div className="flex flex-wrap items-end gap-3 min-w-0">
						<label className="flex flex-col gap-1">
							<span className="text-xs font-semibold uppercase tracking-wide text-muted">
								Limit
							</span>
							<input
								type="number"
								min={1}
								max={1000}
								className="w-24 rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7"
								value={limit}
								onChange={(event) => onLimitChange(Number(event.target.value))}
							/>
						</label>
					</div>
					<div className="flex justify-end">
						<StatusPill status={status} />
					</div>
				</div>
			</header>

			<div className="flex flex-col gap-3 min-w-0 w-full">
				<div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-background px-3 py-2 min-w-0">
					<div className="inline-flex rounded-full border border-border bg-surface p-1 text-xs font-semibold">
						<button
							type="button"
							className={clsx(
								"rounded-full px-3 py-1 transition",
								view === SAMPLE_VIEWS.TABLE ? "bg-blue-9 text-white" : "text-slate-11",
							)}
							onClick={() => onViewChange(SAMPLE_VIEWS.TABLE)}
							disabled={!hasTableData || isBusy}
							data-testid="view-tab-dataframe"
						>
							DataFrame
						</button>
						<button
							type="button"
							className={clsx(
								"rounded-full px-3 py-1 transition",
								view === SAMPLE_VIEWS.JSON ? "bg-blue-9 text-white" : "text-slate-11",
							)}
							onClick={() => onViewChange(SAMPLE_VIEWS.JSON)}
							disabled={!hasTableData || isBusy}
							data-testid="view-tab-records"
						>
							Records
						</button>
						<button
							type="button"
							className={clsx(
								"rounded-full px-3 py-1 transition",
								view === SAMPLE_VIEWS.RAW ? "bg-blue-9 text-white" : "text-slate-11",
							)}
							onClick={() => onViewChange(SAMPLE_VIEWS.RAW)}
							disabled={!hasRawData || isBusy}
							data-testid="view-tab-raw"
						>
							Raw API
						</button>
						<button
							type="button"
							className={clsx(
								"rounded-full px-3 py-1 transition",
								wrap && view === SAMPLE_VIEWS.TABLE ? "bg-blue-9 text-white" : "text-slate-11",
							)}
							onClick={onWrapToggle}
							disabled={!hasTableData || view !== SAMPLE_VIEWS.TABLE || isBusy}
						>
							Wrap Text
						</button>
					</div>
					<div className="flex items-center gap-3 text-sm text-slate-11">
						<SelectPageSize
							value={pageSize}
							onValueChange={onPageSizeChange}
							disabled={!hasTableData || isBusy}
						/>
						<div className="flex items-center gap-1">
							<button
								type="button"
								className="rounded-full border border-border px-2 py-1 text-xs font-semibold text-slate-12 transition hover:border-blue-7 hover:text-blue-11 disabled:opacity-50"
								onClick={() => onPageChange(Math.max(1, safePage - 1))}
								disabled={!hasTableData || safePage <= 1 || isBusy}
							>
								Prev
							</button>
							<span className="text-xs text-muted">
								{totalPages ? `Page ${safePage} of ${totalPages}` : "Page 0 of 0"}
							</span>
							<button
								type="button"
								className="rounded-full border border-border px-2 py-1 text-xs font-semibold text-slate-12 transition hover:border-blue-7 hover:text-blue-11 disabled:opacity-50"
								onClick={() => onPageChange(Math.min(totalPages, safePage + 1))}
								disabled={!hasTableData || safePage >= totalPages || isBusy}
							>
								Next
							</button>
						</div>
					</div>
				</div>

				<div className="min-h-[260px] rounded-2xl border border-border bg-background overflow-hidden w-full">
					{hasTableData && view === SAMPLE_VIEWS.TABLE ? (
						<div className="w-full h-full overflow-auto relative">
							<div className="p-4 w-max min-w-full">
								{renderOutput({ view, data, rows, columns, dtypes, wrap, rawPages, restError })}
							</div>
						</div>
					) : (
						<div className="p-4 overflow-x-auto w-full">
							{renderOutput({ view, data, rows, columns, dtypes, wrap, rawPages, restError })}
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

interface SelectRootProps {
	value: string;
	options: string[];
	onValueChange: (value: string) => void;
	placeholder: string;
}

const SelectRoot: React.FC<SelectRootProps> = ({ value, onValueChange, options, placeholder }) => (
	<Select.Root value={value} onValueChange={onValueChange}>
		<Select.Trigger className="inline-flex items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-12 shadow-sm focus-visible:border-blue-7">
			<Select.Value placeholder={placeholder} />
			<ChevronDownIcon className="h-4 w-4 text-slate-9" />
		</Select.Trigger>
		<Select.Content className="z-20 overflow-hidden rounded-xl border border-border bg-surface shadow-soft">
			<Select.Viewport className="p-1">
				{!options.length && (
					<Select.Item value="" disabled className="rounded-lg px-3 py-2 text-sm text-muted">
						No streams
					</Select.Item>
				)}
				{options.map((option) => (
					<Select.Item
						key={option}
						value={option}
						className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-12 outline-none data-[state=checked]:bg-blue-4"
					>
						<Select.ItemText>{option}</Select.ItemText>
					</Select.Item>
				))}
			</Select.Viewport>
		</Select.Content>
	</Select.Root>
);

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
		<Select.Trigger className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-1 text-xs text-slate-11 shadow-sm focus-visible:border-blue-7 disabled:opacity-50">
			<Select.Value />
			<ChevronDownIcon className="h-3 w-3" />
		</Select.Trigger>
		<Select.Content className="z-20 overflow-hidden rounded-xl border border-border bg-surface shadow-soft">
			<Select.Viewport className="p-1">
				{PAGE_SIZE_OPTIONS.map((option) => (
					<Select.Item
						key={option}
						value={String(option)}
						className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-slate-11 outline-none data-[state=checked]:bg-blue-4"
					>
						<Select.ItemText>{option} rows</Select.ItemText>
					</Select.Item>
				))}
			</Select.Viewport>
		</Select.Content>
	</Select.Root>
);

const StatusPill: React.FC<{ status: StatusState }> = ({ status }) => (
	<span
		className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 text-xs font-semibold"
		data-status={status.tone}
	>
		<span className="inline-block h-2 w-2 rounded-full bg-current" />
		{status.message}
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
			return (
				<p className="text-sm text-muted" data-status="info">
					REST client did not return any data.
				</p>
			);
		}

		return (
			<div className="space-y-3">
				{restError && (
					<p className="text-sm font-medium text-red-11" data-status="error">
						{restError}
					</p>
				)}
				<pre
					data-status={restError ? "error" : "info"}
					className="whitespace-pre-wrap break-words text-xs"
				>
					{JSON.stringify({ pages: rawPages }, null, 2)}
				</pre>
			</div>
		);
	}

	if (!data.length) {
		return (
			<p className="text-sm text-muted" data-status="info">
				Preview will appear here after sampling.
			</p>
		);
	}

	if (view === SAMPLE_VIEWS.JSON) {
		return <pre data-status="info">{JSON.stringify({ records: data }, null, 2)}</pre>;
	}

	return (
		<table
			className={clsx(
				"w-full min-w-max border-collapse text-sm",
				wrap ? "[&_td]:whitespace-pre-wrap" : "[&_td]:whitespace-nowrap",
			)}
		>
			<thead>
				<tr className="bg-slate-2 dark:bg-drac-surface/60">
					{columns.map((column) => (
						<th
							key={column}
							className="border-b border-border px-3 py-2 align-bottom text-left text-slate-12 sticky top-0 z-10 bg-slate-2 dark:bg-drac-surface/80 backdrop-blur supports-[backdrop-filter]:bg-slate-2/75 dark:supports-[backdrop-filter]:bg-drac-surface/70"
						>
							<div className="flex flex-col gap-0.5">
								<span className="font-semibold">{column}</span>
								{renderColumnType(column, dtypes)}
							</div>
						</th>
					))}
				</tr>
			</thead>
			<tbody>
				{rows.map((row, rowIndex) => (
					<tr
						key={rowIndex}
						className="even:bg-slate-2/40 hover:bg-blue-3/40"
					>
						{columns.map((column) => {
							const value = column in row ? row[column] : "";
							const text = formatCell(value);
							const needsTooltip = text.length > 500;
							return (
								<td
									key={column}
									className="border-b border-border px-3 py-2 align-top text-slate-11"
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

function renderColumnType(column: string, dtypes: Array<{ column: string; type: string }>) {
	const dtype = dtypes.find((entry) => entry.column === column);
	if (!dtype) {
		return null;
	}
	return (
		<span className="text-xs font-medium uppercase tracking-wide text-muted">{dtype.type}</span>
	);
}

const ChevronDownIcon: React.FC<{ className?: string }> = ({ className }) => (
	<svg
		className={className}
		xmlns="http://www.w3.org/2000/svg"
		width="16"
		height="16"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		strokeWidth="2"
		strokeLinecap="round"
		strokeLinejoin="round"
	>
		<polyline points="6 9 12 15 18 9" />
	</svg>
);
