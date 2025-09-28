import React from "react";

interface YamlEditorProps {
	value: string;
	onChange: (value: string) => void;
	error: string | null;
	// errorLine / errorCol ignored now (highlighting removed)
	errorLine?: number | null;
	errorCol?: number | null;
}

export const YamlEditor: React.FC<YamlEditorProps> = ({ value, onChange, error }) => {
	return (
		<div className="space-y-3">
			<textarea
				spellCheck={false}
				className="yaml-editor-textarea h-[520px] w-full rounded-2xl border border-border bg-background dark:bg-drac-surface px-4 py-3 font-mono text-sm text-slate-12 dark:text-drac-foreground leading-5 shadow-soft focus-visible:border-blue-7 dark:focus-visible:border-drac-accent resize-none"
				value={value}
				onChange={(e) => onChange(e.target.value)}
				aria-label="YAML configuration editor"
			/>
			{error && (
				<div className="flex items-start gap-2 rounded-md border border-error/40 bg-red-3/60 dark:bg-drac-red/25 dark:border-drac-red/40 px-3 py-2 text-xs text-error shadow-sm" data-status="error">
					<span className="mt-0.5 inline-block h-2 w-2 flex-shrink-0 rounded-full bg-error" />
					<span className="whitespace-pre-wrap break-words leading-snug">{error}</span>
				</div>
			)}
		</div>
	);
};
