import React from "react";

interface CodePaneProps {
	script: string;
	stream: string;
	error: string | null;
	loading: boolean;
}

const slugifyStreamName = (value: string): string => {
	const slug = value
		.toLowerCase()
		.trim()
		.replace(/[^a-z0-9]+/g, "_")
		.replace(/^_+|_+$/g, "");
	return slug || "connector";
};

export const CodePane: React.FC<CodePaneProps> = ({ script, stream, error, loading }) => {
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
		<div className="space-y-3">
			<div className="flex items-center justify-between gap-3">
				<p className="text-xs text-muted dark:text-drac-muted">
					{loading ? "Generating…" : "Generated PySpark script for the current configuration."}
				</p>
				<div className="flex items-center gap-2">
					<button
						type="button"
						className="rounded-full px-3 py-1.5 text-xs font-medium border border-border bg-background text-slate-12 hover:border-blue-7 hover:text-blue-11 disabled:opacity-50 disabled:cursor-not-allowed dark:border-drac-border/60 dark:bg-[#1f232b] dark:text-drac-foreground transition"
						onClick={handleCopy}
						disabled={!hasScript}
					>
						{copyLabel}
					</button>
					<button
						type="button"
						className="rounded-full px-3 py-1.5 text-xs font-medium border border-border bg-background text-slate-12 hover:border-blue-7 hover:text-blue-11 disabled:opacity-50 disabled:cursor-not-allowed dark:border-drac-border/60 dark:bg-[#1f232b] dark:text-drac-foreground transition"
						onClick={handleDownload}
						disabled={!hasScript}
					>
						Download
					</button>
				</div>
			</div>
			<pre
				className="code-pane-pre h-[520px] w-full overflow-auto rounded-2xl border border-border bg-background dark:bg-drac-surface px-4 py-3 font-mono text-sm text-slate-12 dark:text-drac-foreground leading-5 shadow-soft"
				aria-label="Generated PySpark script"
				aria-busy={loading}
			>
				<code>{hasScript ? script : loading ? "" : "// Configure a stream to see the generated script."}</code>
			</pre>
			{error && (
				<div
					className="flex items-start gap-2 rounded-md border border-error/40 bg-red-3/60 dark:bg-drac-red/25 dark:border-drac-red/40 px-3 py-2 text-xs text-error shadow-sm"
					data-status="error"
				>
					<span className="mt-0.5 inline-block h-2 w-2 flex-shrink-0 rounded-full bg-error" />
					<span className="whitespace-pre-wrap break-words leading-snug">{error}</span>
				</div>
			)}
		</div>
	);
};
