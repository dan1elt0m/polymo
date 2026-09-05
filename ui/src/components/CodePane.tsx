import React from "react";
import { slugifyStreamName } from "../lib/filename";
import { BTN_SECONDARY, BTN_SMALL, Callout, cx } from "./ui/primitives";

interface CodePaneProps {
	script: string;
	stream: string;
	error: string | null;
	loading: boolean;
	/** Overrides the placeholder shown when there is no script yet (e.g. no base URL configured). */
	emptyMessage?: string;
}

export const CodePane: React.FC<CodePaneProps> = ({ script, stream, error, loading, emptyMessage }) => {
	const [copyLabel, setCopyLabel] = React.useState<string>("Copy");
	const copyResetRef = React.useRef<number | undefined>(undefined);

	React.useEffect(() => {
		return () => {
			if (copyResetRef.current) window.clearTimeout(copyResetRef.current);
		};
	}, []);

	const handleCopy = React.useCallback(async () => {
		if (!script) return;
		try {
			await navigator.clipboard.writeText(script);
			setCopyLabel("Copied!");
		} catch {
			try {
				const temp = document.createElement("textarea");
				temp.value = script;
				temp.style.position = "fixed";
				temp.style.left = "-9999px";
				document.body.appendChild(temp);
				temp.select();
				document.execCommand("copy");
				document.body.removeChild(temp);
				setCopyLabel("Copied!");
			} catch {
				setCopyLabel("Copy failed");
			}
		}
		if (copyResetRef.current) window.clearTimeout(copyResetRef.current);
		copyResetRef.current = window.setTimeout(() => setCopyLabel("Copy"), 1800);
	}, [script]);

	const handleDownload = React.useCallback(() => {
		if (!script) return;
		const fileName = `${slugifyStreamName(stream)}.py`;
		const blob = new Blob([script], { type: "text/x-python" });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = fileName;
		document.body.appendChild(anchor);
		anchor.click();
		document.body.removeChild(anchor);
		URL.revokeObjectURL(url);
	}, [script, stream]);

	const hasScript = script.trim().length > 0;

	return (
		<div className="flex h-full min-h-0 flex-col gap-3">
			<div className="flex shrink-0 items-center justify-between gap-3">
				<p className="text-xs text-fg-muted">
					{loading ? "Generating…" : "Generated PySpark script for the current configuration."}
				</p>
				<div className="flex items-center gap-2">
					<button type="button" className={cx(BTN_SECONDARY, BTN_SMALL)} onClick={handleCopy} disabled={!hasScript}>
						{copyLabel}
					</button>
					<button type="button" className={cx(BTN_SECONDARY, BTN_SMALL)} onClick={handleDownload} disabled={!hasScript}>
						Download
					</button>
				</div>
			</div>
			<pre
				className="code-pane-pre scroll-thin m-0 min-h-[240px] flex-1 overflow-auto rounded-lg border border-border bg-field px-4 py-3 font-mono text-xs leading-5 text-fg"
				aria-label="Generated PySpark script"
				aria-busy={loading}
			>
				<code>
					{hasScript
						? script
						: loading
							? ""
							: <span className="text-fg-subtle">{emptyMessage ?? "// Configure a stream to see the generated script."}</span>}
				</code>
			</pre>
			{error && (
				<Callout tone="error">
					<span className="whitespace-pre-wrap break-words">{error}</span>
				</Callout>
			)}
		</div>
	);
};
