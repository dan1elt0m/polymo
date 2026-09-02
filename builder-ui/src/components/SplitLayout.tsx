import React from "react";
import { cx, ChevronIcon } from "./ui/primitives";
import { DEFAULT_LAYOUT, MAX_RATIO, MIN_RATIO, clampRatio, loadLayout, saveLayout } from "../lib/layout";

/** Hard pixel floors so neither pane collapses into an unusable strip. */
const MIN_PRIMARY_PX = 400;
const MIN_SECONDARY_PX = 420;
const RAIL_WIDTH_PX = 44;
const KEYBOARD_STEP = 0.02;

export interface SplitLayoutProps {
	/** Left pane: configuration / code / deploy. */
	primary: React.ReactNode;
	/** Right pane: data preview. */
	secondary: React.ReactNode;
	/** Give the secondary pane the full width (primary unmounted from view). */
	focus: boolean;
	/** Label shown on the collapsed rail. */
	railLabel?: string;
}

export interface SplitLayoutHandle {
	collapsed: boolean;
	toggleCollapsed: () => void;
}

/**
 * Two-pane split with a draggable, keyboard-operable divider, a one-click
 * collapse of the primary pane to a slim rail, and a focus mode that hands
 * the entire width to the secondary pane. Ratio and collapsed state are
 * persisted under `polymo.layout.v1`.
 */
export const SplitLayout: React.FC<SplitLayoutProps> = ({ primary, secondary, focus, railLabel = "Configuration" }) => {
	const containerRef = React.useRef<HTMLDivElement | null>(null);
	const [layout, setLayout] = React.useState(() => loadLayout());
	const [dragging, setDragging] = React.useState(false);
	const persistTimer = React.useRef<number | undefined>(undefined);

	// Persist: collapse toggles immediately, ratio changes debounced so a
	// drag doesn't hammer localStorage on every pointer move.
	React.useEffect(() => {
		if (persistTimer.current) window.clearTimeout(persistTimer.current);
		persistTimer.current = window.setTimeout(() => saveLayout(layout), dragging ? 250 : 0);
		return () => {
			if (persistTimer.current) window.clearTimeout(persistTimer.current);
		};
	}, [layout, dragging]);

	const boundsFor = React.useCallback(() => {
		const width = containerRef.current?.getBoundingClientRect().width ?? 0;
		if (!width) return { min: MIN_RATIO, max: MAX_RATIO };
		const min = Math.max(MIN_RATIO, MIN_PRIMARY_PX / width);
		const max = Math.min(MAX_RATIO, 1 - MIN_SECONDARY_PX / width);
		return min <= max ? { min, max } : { min: 0.5, max: 0.5 };
	}, []);

	const applyRatio = React.useCallback(
		(next: number) => {
			const { min, max } = boundsFor();
			const ratio = Math.min(max, Math.max(min, clampRatio(next)));
			setLayout((prev) => (prev.ratio === ratio ? prev : { ...prev, ratio }));
		},
		[boundsFor],
	);

	const setCollapsed = React.useCallback((collapsed: boolean) => {
		setLayout((prev) => (prev.collapsed === collapsed ? prev : { ...prev, collapsed }));
	}, []);

	const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
		if (event.button !== 0) return;
		event.preventDefault();
		const container = containerRef.current;
		if (!container) return;
		const rect = container.getBoundingClientRect();
		const target = event.currentTarget;
		target.setPointerCapture(event.pointerId);
		setDragging(true);
		const onMove = (move: PointerEvent) => {
			applyRatio((move.clientX - rect.left) / rect.width);
		};
		const onUp = () => {
			setDragging(false);
			target.removeEventListener("pointermove", onMove);
			target.removeEventListener("pointerup", onUp);
			target.removeEventListener("pointercancel", onUp);
		};
		target.addEventListener("pointermove", onMove);
		target.addEventListener("pointerup", onUp);
		target.addEventListener("pointercancel", onUp);
	};

	const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
		const { min, max } = boundsFor();
		switch (event.key) {
			case "ArrowLeft":
				event.preventDefault();
				applyRatio(layout.ratio - KEYBOARD_STEP);
				break;
			case "ArrowRight":
				event.preventDefault();
				applyRatio(layout.ratio + KEYBOARD_STEP);
				break;
			case "Home":
				event.preventDefault();
				applyRatio(min);
				break;
			case "End":
				event.preventDefault();
				applyRatio(max);
				break;
			case "Enter":
			case " ":
				event.preventDefault();
				setCollapsed(true);
				break;
			default:
				break;
		}
	};

	// Re-clamp when the window shrinks below the pixel floors.
	React.useEffect(() => {
		const onResize = () => applyRatio(layout.ratio);
		window.addEventListener("resize", onResize);
		return () => window.removeEventListener("resize", onResize);
	}, [applyRatio, layout.ratio]);

	const collapsed = layout.collapsed && !focus;
	const primaryStyle: React.CSSProperties = collapsed
		? { width: RAIL_WIDTH_PX, flex: "0 0 auto" }
		: { width: `${layout.ratio * 100}%`, flex: "0 0 auto" };

	return (
		<div
			ref={containerRef}
			className={cx("flex h-full min-h-0 w-full items-stretch", dragging && "cursor-col-resize select-none")}
			data-layout-collapsed={collapsed || undefined}
			data-layout-focus={focus || undefined}
		>
			{!focus && (
				<div
					className={cx("flex min-h-0 min-w-0 flex-col", !dragging && "transition-[width] duration-200 ease-out")}
					style={primaryStyle}
					data-testid="split-primary"
				>
					{collapsed ? (
						<button
							type="button"
							className="group flex h-full w-full flex-col items-center gap-3 rounded-xl border border-border bg-surface py-3 text-fg-muted shadow-card transition-colors hover:border-border-strong hover:text-fg"
							onClick={() => setCollapsed(false)}
							aria-label={`Expand ${railLabel.toLowerCase()} panel`}
							title="Expand panel"
							data-testid="split-expand"
						>
							<span className="flex h-7 w-7 items-center justify-center rounded-md bg-raised text-fg-muted group-hover:bg-accent group-hover:text-accent-fg">
								<ChevronIcon />
							</span>
							<span className="mt-1 select-none whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.14em] [writing-mode:vertical-rl]">
								{railLabel}
							</span>
						</button>
					) : (
						primary
					)}
				</div>
			)}

			{!focus && !collapsed && (
				<div
					role="separator"
					aria-orientation="vertical"
					aria-label="Resize configuration panel"
					aria-valuemin={Math.round(MIN_RATIO * 100)}
					aria-valuemax={Math.round(MAX_RATIO * 100)}
					aria-valuenow={Math.round(layout.ratio * 100)}
					tabIndex={0}
					className={cx(
						"group relative mx-1 flex w-3 shrink-0 cursor-col-resize touch-none items-center justify-center rounded-md outline-none",
					)}
					onPointerDown={handlePointerDown}
					onKeyDown={handleKeyDown}
					onDoubleClick={() => applyRatio(DEFAULT_LAYOUT.ratio)}
					title="Drag to resize · double-click to reset · Enter to collapse"
					data-testid="split-handle"
				>
					<span
						className={cx(
							"absolute inset-y-3 left-1/2 w-px -translate-x-1/2 rounded-full bg-border transition-colors group-hover:bg-accent group-focus-visible:bg-accent",
							dragging && "bg-accent",
						)}
					/>
					<span
						className={cx(
							"relative z-10 flex h-8 w-3 items-center justify-center rounded-full border border-border bg-surface text-fg-subtle shadow-sm transition-colors group-hover:border-accent group-hover:text-accent group-focus-visible:border-accent",
							dragging && "border-accent text-accent",
						)}
						aria-hidden="true"
					>
						<svg viewBox="0 0 6 16" className="h-3 w-1.5" fill="currentColor">
							<circle cx="1.5" cy="3" r="1" />
							<circle cx="4.5" cy="3" r="1" />
							<circle cx="1.5" cy="8" r="1" />
							<circle cx="4.5" cy="8" r="1" />
							<circle cx="1.5" cy="13" r="1" />
							<circle cx="4.5" cy="13" r="1" />
						</svg>
					</span>
					<button
						type="button"
						tabIndex={-1}
						className="absolute -top-0.5 left-1/2 z-20 flex h-5 w-5 -translate-x-1/2 items-center justify-center rounded-full border border-border bg-surface text-fg-muted opacity-0 shadow-sm transition-opacity hover:border-accent hover:text-accent group-hover:opacity-100 group-focus-visible:opacity-100"
						onPointerDown={(event) => event.stopPropagation()}
						onClick={(event) => {
							event.stopPropagation();
							setCollapsed(true);
						}}
						aria-label={`Collapse ${railLabel.toLowerCase()} panel`}
						title="Collapse panel"
						data-testid="split-collapse"
					>
						<ChevronIcon direction="left" className="h-3 w-3" />
					</button>
				</div>
			)}

			{collapsed && <div className="w-2 shrink-0" aria-hidden="true" />}

			<div className="flex min-h-0 min-w-0 flex-1 flex-col" data-testid="split-secondary">
				{secondary}
			</div>
		</div>
	);
};
