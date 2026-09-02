import React from "react";
import { clsx } from "clsx";
import { InfoTooltip } from "../InfoTooltip";

/*
 * The builder's form vocabulary. Every field in the configuration form,
 * the auth section and the deploy stepper is built from these so there is
 * exactly one label style, one input height (h-9) and one set of button
 * shapes. Colours come from the theme tokens (see styles/index.css), so
 * nothing here needs a `dark:` variant.
 */

export const cx = clsx;

export const LABEL = "text-xs font-medium text-fg-muted";
export const HELP = "text-xs leading-relaxed text-fg-muted";

const CONTROL_BASE =
	"w-full rounded-md border border-border bg-field text-sm text-fg shadow-none transition-colors " +
	"placeholder:text-fg-subtle hover:border-border-strong focus:border-accent focus:ring-2 focus:ring-accent/20 " +
	"disabled:cursor-not-allowed disabled:opacity-60";

export const INPUT = `${CONTROL_BASE} h-9 px-3`;
export const TEXTAREA = `${CONTROL_BASE} min-h-[84px] px-3 py-2 leading-relaxed`;
export const SELECT = `${CONTROL_BASE} h-9 appearance-none pl-3 pr-8`;
export const CHECKBOX = "h-4 w-4 shrink-0 rounded border-border-strong bg-field accent-accent";

const BTN_BASE =
	"inline-flex h-9 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3.5 text-sm font-medium transition-colors " +
	"disabled:cursor-not-allowed disabled:opacity-50";
export const BTN_PRIMARY = `${BTN_BASE} bg-accent text-accent-fg shadow-sm hover:bg-accent-hover`;
export const BTN_SECONDARY = `${BTN_BASE} border border-border bg-surface text-fg hover:border-border-strong hover:bg-raised`;
export const BTN_GHOST = `${BTN_BASE} text-fg-muted hover:bg-raised hover:text-fg`;
export const BTN_SMALL = "h-7 px-2.5 text-xs";
export const BTN_LINK =
	"inline-flex items-center gap-1 text-xs font-medium text-accent-text underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-fg-subtle disabled:no-underline";
export const ICON_BTN =
	"inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-fg-muted transition-colors hover:bg-raised hover:text-fg disabled:opacity-50";

export const EYEBROW = "text-[11px] font-semibold uppercase tracking-[0.12em] text-fg-muted";

/* ----------------------------------------------------------------- icons */

export const ChevronIcon: React.FC<{ className?: string; direction?: "right" | "down" | "left" }> = ({
	className,
	direction = "right",
}) => (
	<svg
		viewBox="0 0 16 16"
		fill="none"
		stroke="currentColor"
		strokeWidth="1.75"
		strokeLinecap="round"
		strokeLinejoin="round"
		className={cx(
			"h-3.5 w-3.5 transition-transform duration-150",
			direction === "down" && "rotate-90",
			direction === "left" && "rotate-180",
			className,
		)}
		aria-hidden="true"
	>
		<path d="M6 3.5 10.5 8 6 12.5" />
	</svg>
);

export const PlusIcon: React.FC<{ className?: string }> = ({ className }) => (
	<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={cx("h-3.5 w-3.5", className)} aria-hidden="true">
		<path d="M8 3.5v9M3.5 8h9" />
	</svg>
);

export const XIcon: React.FC<{ className?: string }> = ({ className }) => (
	<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={cx("h-3.5 w-3.5", className)} aria-hidden="true">
		<path d="m4.5 4.5 7 7m0-7-7 7" />
	</svg>
);

export const CheckIcon: React.FC<{ className?: string }> = ({ className }) => (
	<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={cx("h-3.5 w-3.5", className)} aria-hidden="true">
		<path d="m3.5 8.5 3 3 6-7" />
	</svg>
);

/* ---------------------------------------------------------------- fields */

export interface FieldProps {
	label: React.ReactNode;
	tooltip?: string;
	help?: React.ReactNode;
	error?: React.ReactNode;
	className?: string;
	/** Render as a plain div instead of a <label> (for groups of controls). */
	as?: "label" | "div";
	children: React.ReactNode;
}

/** Label + optional tooltip above a control, optional helper/error line below. */
export const Field: React.FC<FieldProps> = ({ label, tooltip, help, error, className, as = "label", children }) => {
	const Tag = as;
	return (
		<Tag className={cx("flex min-w-0 flex-col gap-1.5", className)}>
			<span className="flex items-center gap-1.5">
				<span className={LABEL}>{label}</span>
				{tooltip && <InfoTooltip text={tooltip} />}
			</span>
			{children}
			{error ? <span className="text-xs text-error">{error}</span> : help ? <span className={HELP}>{help}</span> : null}
		</Tag>
	);
};

/** Native select with a consistent chevron. Keeps the platform popup. */
export const SelectInput = React.forwardRef<
	HTMLSelectElement,
	React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
	<span className="relative block w-full">
		<select ref={ref} className={cx(SELECT, className)} {...props}>
			{children}
		</select>
		<ChevronIcon direction="down" className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-fg-subtle" />
	</span>
));
SelectInput.displayName = "SelectInput";

export interface CheckboxRowProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
	label: React.ReactNode;
	tooltip?: string;
	description?: React.ReactNode;
}

/** A checkbox with its label on one line, optional description under it. */
export const CheckboxRow: React.FC<CheckboxRowProps> = ({ label, tooltip, description, className, ...props }) => (
	<label className={cx("flex cursor-pointer items-start gap-2.5", className)}>
		<input type="checkbox" className={cx(CHECKBOX, "mt-0.5")} {...props} />
		<span className="flex min-w-0 flex-col gap-0.5">
			<span className="flex items-center gap-1.5 text-sm text-fg">
				{label}
				{tooltip && <InfoTooltip text={tooltip} />}
			</span>
			{description && <span className={HELP}>{description}</span>}
		</span>
	</label>
);

/* ----------------------------------------------------- segmented control */

export interface SegmentOption<T extends string> {
	value: T;
	label: React.ReactNode;
	disabled?: boolean;
	testId?: string;
}

export interface SegmentedControlProps<T extends string> {
	value: T;
	options: Array<SegmentOption<T>>;
	onChange: (value: T) => void;
	"aria-label"?: string;
	size?: "sm" | "md";
	className?: string;
	/** Stretch to the container width with equal segments. */
	fill?: boolean;
}

/** Compact, keyboard-navigable radio group styled as a segmented control. */
export function SegmentedControl<T extends string>({
	value,
	options,
	onChange,
	size = "md",
	className,
	fill,
	...aria
}: SegmentedControlProps<T>) {
	const refs = React.useRef<Array<HTMLButtonElement | null>>([]);
	const handleKey = (event: React.KeyboardEvent, index: number) => {
		const enabled = options.map((o, i) => (o.disabled ? -1 : i)).filter((i) => i >= 0);
		if (!enabled.length) return;
		const pos = enabled.indexOf(index);
		let next: number | null = null;
		if (event.key === "ArrowRight" || event.key === "ArrowDown") next = enabled[(pos + 1) % enabled.length];
		if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = enabled[(pos - 1 + enabled.length) % enabled.length];
		if (event.key === "Home") next = enabled[0];
		if (event.key === "End") next = enabled[enabled.length - 1];
		if (next === null) return;
		event.preventDefault();
		onChange(options[next].value);
		refs.current[next]?.focus();
	};
	return (
		<div
			role="radiogroup"
			aria-label={aria["aria-label"]}
			className={cx(
				"inline-flex max-w-full rounded-md border border-border bg-field p-0.5",
				fill && "flex w-full",
				className,
			)}
		>
			{options.map((option, index) => {
				const active = option.value === value;
				return (
					<button
						key={option.value}
						ref={(el) => {
							refs.current[index] = el;
						}}
						type="button"
						role="radio"
						aria-checked={active}
						tabIndex={active ? 0 : -1}
						disabled={option.disabled}
						data-testid={option.testId}
						onClick={() => onChange(option.value)}
						onKeyDown={(event) => handleKey(event, index)}
						className={cx(
							"flex-1 whitespace-nowrap rounded-[5px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
							size === "sm" ? "h-6 px-2.5 text-xs" : "h-7 px-3 text-xs",
							active ? "bg-accent text-accent-fg shadow-sm" : "text-fg-muted hover:bg-raised hover:text-fg",
						)}
					>
						{option.label}
					</button>
				);
			})}
		</div>
	);
}

/* ------------------------------------------------------------- radio row */

export interface RadioRowOption<T extends string> {
	value: T;
	label: React.ReactNode;
	description?: React.ReactNode;
}

export interface RadioRowProps<T extends string> {
	name: string;
	value: T;
	options: Array<RadioRowOption<T>>;
	onChange: (value: T) => void;
	className?: string;
}

/**
 * Horizontal radio group. Deliberately `flex-nowrap` with short labels —
 * the description of the selected option renders underneath instead of
 * being crammed into the pill, so the row keeps its shape at any pane
 * width.
 */
export function RadioRow<T extends string>({ name, value, options, onChange, className }: RadioRowProps<T>) {
	const selected = options.find((option) => option.value === value);
	return (
		<div className={cx("flex flex-col gap-1.5", className)}>
			<div className="flex flex-nowrap items-center gap-4 overflow-x-auto">
				{options.map((option) => {
					const active = option.value === value;
					return (
						<label
							key={option.value}
							className={cx(
								"inline-flex shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap text-sm",
								active ? "text-fg" : "text-fg-muted hover:text-fg",
							)}
						>
							<input
								type="radio"
								name={name}
								value={option.value}
								checked={active}
								onChange={() => onChange(option.value)}
								className="h-3.5 w-3.5 accent-accent"
							/>
							{option.label}
						</label>
					);
				})}
			</div>
			{selected?.description && <p className={HELP}>{selected.description}</p>}
		</div>
	);
}

/* ------------------------------------------------------------ disclosure */

export interface DisclosureProps {
	id: string;
	title: React.ReactNode;
	/** One-line state summary shown next to the title (mono, muted). */
	summary?: React.ReactNode;
	open: boolean;
	onToggle: () => void;
	testId?: string;
	/** Optional control rendered in the header (e.g. an "Add" button). */
	action?: React.ReactNode;
	children: React.ReactNode;
}

/**
 * Compact collapsible section for the "Advanced" tier. Header is a single
 * 40px row: chevron, title, summary; content is flat (no nested card).
 */
export const Disclosure: React.FC<DisclosureProps> = ({ id, title, summary, open, onToggle, testId, action, children }) => (
	<section className="border-b border-border last:border-b-0">
		<div className="flex items-center gap-1">
			<button
				type="button"
				className="group -mx-2 flex h-10 min-w-0 flex-1 items-center gap-2 rounded-md px-2 text-left transition-colors hover:bg-raised"
				onClick={onToggle}
				aria-expanded={open}
				aria-controls={id}
				data-testid={testId}
			>
				<ChevronIcon direction={open ? "down" : "right"} className="shrink-0 text-fg-subtle group-hover:text-fg" />
				<span className="shrink-0 text-sm font-medium text-fg">{title}</span>
				{summary && (
					<span className="min-w-0 flex-1 truncate font-mono text-[11px] text-fg-muted" title={typeof summary === "string" ? summary : undefined}>
						{summary}
					</span>
				)}
			</button>
			{action}
		</div>
		{open && (
			<div id={id} className="animate-disclosure-in space-y-4 pb-5 pl-[22px] pt-1">
				{children}
			</div>
		)}
	</section>
);

/* --------------------------------------------------------------- eyebrow */

export const Eyebrow: React.FC<{ children: React.ReactNode; className?: string; trailing?: React.ReactNode }> = ({
	children,
	className,
	trailing,
}) => (
	<div className={cx("flex items-center gap-3", className)}>
		<span className={EYEBROW}>{children}</span>
		<span className="h-px flex-1 bg-border" aria-hidden="true" />
		{trailing}
	</div>
);

/* ----------------------------------------------------------- key/value */

export interface KeyValueRowProps {
	keyLabel: string;
	keyPlaceholder: string;
	valuePlaceholder: string;
	keyTooltip?: string;
	valueTooltip?: string;
	tempKey: string;
	value: string;
	onTempKeyChange: (value: string) => void;
	onCommitKey: () => void;
	onValueChange: (value: string) => void;
	onRemove: () => void;
	removeLabel: string;
	testIdPrefix?: string;
	rowTestId?: string;
	/** Optional replacement for the value control (defaults to a text input). */
	renderValue?: (className: string) => React.ReactNode;
	renderKey?: (className: string) => React.ReactNode;
}

/** Single-line key → value editor row used by headers, params and reader options. */
export const KeyValueRow: React.FC<KeyValueRowProps> = ({
	keyLabel,
	keyPlaceholder,
	valuePlaceholder,
	keyTooltip,
	valueTooltip,
	tempKey,
	value,
	onTempKeyChange,
	onCommitKey,
	onValueChange,
	onRemove,
	removeLabel,
	testIdPrefix,
	rowTestId,
	renderValue,
	renderKey,
}) => (
	<li className="animate-param-enter grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto] items-center gap-2" data-testid={rowTestId}>
		{renderKey ? (
			renderKey(cx(INPUT, "font-mono text-xs"))
		) : (
			<input
				type="text"
				className={cx(INPUT, "font-mono text-xs")}
				placeholder={keyPlaceholder}
				aria-label={keyLabel}
				title={keyTooltip}
				value={tempKey}
				onChange={(event) => onTempKeyChange(event.target.value)}
				onBlur={onCommitKey}
				onKeyDown={(event) => {
					if (event.key === "Enter") {
						event.preventDefault();
						(event.target as HTMLInputElement).blur();
					}
				}}
				data-testid={testIdPrefix ? `${testIdPrefix}-name-input` : undefined}
			/>
		)}
		{renderValue ? (
			renderValue(cx(INPUT, "font-mono text-xs"))
		) : (
			<input
				type="text"
				className={cx(INPUT, "font-mono text-xs")}
				placeholder={valuePlaceholder}
				aria-label="Value"
				title={valueTooltip}
				value={value}
				onChange={(event) => onValueChange(event.target.value)}
				data-testid={testIdPrefix ? `${testIdPrefix}-value-input` : undefined}
			/>
		)}
		<button type="button" className={ICON_BTN} onClick={onRemove} aria-label={removeLabel}>
			<XIcon />
		</button>
	</li>
);

/* ------------------------------------------------------------- callouts */

export const Callout: React.FC<{ tone: "info" | "error" | "warning" | "success"; children: React.ReactNode; testId?: string }> = ({
	tone,
	children,
	testId,
}) => (
	<div
		className={cx(
			"flex items-start gap-2 rounded-md border px-3 py-2 text-xs leading-relaxed",
			tone === "info" && "border-accent-ring/60 bg-accent-soft text-accent-text",
			tone === "error" && "border-error/40 bg-error/10 text-error",
			tone === "warning" && "border-warning/40 bg-warning/10 text-warning",
			tone === "success" && "border-success/40 bg-success/10 text-success",
		)}
		data-status={tone}
		data-testid={testId}
	>
		<span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
		<div className="min-w-0 flex-1">{children}</div>
	</div>
);
