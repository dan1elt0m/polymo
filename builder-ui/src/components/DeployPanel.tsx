import React from "react";
import { useAtom, useAtomValue } from "jotai";
import { configFormStateAtom, configPayloadAtom, databricksProfileAtom, streamOptionsAtom } from "../atoms";
import {
	ApiError,
	bootstrapDatabricksProject,
	deployDatabricksBundle,
	listDatabricksCatalogs,
	listDatabricksProfiles,
	listDatabricksSchemas,
	runDatabricksPipeline,
} from "../lib/api";
import { validateFormState } from "../lib/transform";
import {
	BTN_GHOST,
	BTN_LINK,
	BTN_PRIMARY,
	BTN_SMALL,
	Callout,
	CheckIcon,
	CheckboxRow,
	Field,
	INPUT,
	SelectInput,
	cx,
} from "./ui/primitives";

const DEFAULT_PROJECT_DIR = "~/polymo-projects";
// Sentinel <option> value that swaps the schema field from a select (list of
// existing schemas) to a free-text input — pipelines can create a schema
// that doesn't exist yet, so the user needs a way to name one, unlike
// catalog, which must already exist.
const CUSTOM_SCHEMA_VALUE = "__custom__";

function describeError(error: unknown): string {
	if (error instanceof ApiError && error.status === 501) {
		return error.message;
	}
	return error instanceof Error ? error.message : String(error ?? "Request failed");
}

type StepStatus = "done" | "active" | "blocked";

interface StepProps {
	index: number;
	title: string;
	status: StepStatus;
	/** Short state line under the title (e.g. the chosen profile). */
	detail?: React.ReactNode;
	/** Why the step is blocked, shown instead of the body. */
	blockedHint?: string;
	last?: boolean;
	children?: React.ReactNode;
}

const Step: React.FC<StepProps> = ({ index, title, status, detail, blockedHint, last, children }) => (
	<li className="relative flex gap-4" data-step-status={status}>
		{!last && (
			<span
				className={cx("absolute left-[11px] top-7 h-[calc(100%-12px)] w-px", status === "done" ? "bg-accent/60" : "bg-border")}
				aria-hidden="true"
			/>
		)}
		<span
			className={cx(
				"relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold tabular-nums",
				status === "done" && "border-accent bg-accent text-accent-fg",
				status === "active" && "border-accent bg-surface text-accent-text ring-4 ring-accent/15",
				status === "blocked" && "border-border bg-surface text-fg-subtle",
			)}
			aria-hidden="true"
		>
			{status === "done" ? <CheckIcon className="h-3 w-3" /> : index}
		</span>
		<div className={cx("min-w-0 flex-1", last ? "pb-1" : "pb-6")}>
			<div className="flex min-h-[28px] flex-wrap items-baseline gap-x-3 gap-y-0.5">
				<h3 className={cx("text-sm font-semibold", status === "blocked" ? "text-fg-muted" : "text-fg")}>{title}</h3>
				<span className="sr-only">{status === "done" ? "completed" : status === "active" ? "current step" : "not yet available"}</span>
				{detail && <span className="truncate font-mono text-[11px] text-fg-muted">{detail}</span>}
			</div>
			{status === "blocked" ? (
				blockedHint && <p className="mt-1 text-xs text-fg-subtle">{blockedHint}</p>
			) : (
				<div className="mt-3 space-y-3">{children}</div>
			)}
		</div>
	</li>
);

export const DeployPanel: React.FC = () => {
	const configFormState = useAtomValue(configFormStateAtom);
	const configPayload = useAtomValue(configPayloadAtom);
	const streamOptions = useAtomValue(streamOptionsAtom);
	const [profile, setProfile] = useAtom(databricksProfileAtom);

	const [profiles, setProfiles] = React.useState<string[]>([]);
	const [profilesLoading, setProfilesLoading] = React.useState(false);
	const [profilesError, setProfilesError] = React.useState<string | null>(null);
	const [profilesLoaded, setProfilesLoaded] = React.useState(false);

	const [catalogs, setCatalogs] = React.useState<string[]>([]);
	const [catalogsLoading, setCatalogsLoading] = React.useState(false);
	const [catalogsError, setCatalogsError] = React.useState<string | null>(null);
	const [catalog, setCatalog] = React.useState("");

	const [schemas, setSchemas] = React.useState<string[]>([]);
	const [schemasLoading, setSchemasLoading] = React.useState(false);
	const [schemasError, setSchemasError] = React.useState<string | null>(null);
	const [schema, setSchema] = React.useState("");
	const [schemaMode, setSchemaMode] = React.useState<"select" | "custom">("select");

	const defaultProjectName = (configFormState.streamName?.trim() || streamOptions[0] || "").trim();
	const [projectName, setProjectName] = React.useState(defaultProjectName);
	const [projectNameTouched, setProjectNameTouched] = React.useState(false);
	const [projectDir, setProjectDir] = React.useState(DEFAULT_PROJECT_DIR);
	const [overwrite, setOverwrite] = React.useState(false);

	const [bootstrapping, setBootstrapping] = React.useState(false);
	const [projectPath, setProjectPath] = React.useState<string | null>(null);
	const [deploying, setDeploying] = React.useState(false);
	const [lastDeployOk, setLastDeployOk] = React.useState(false);
	const [running, setRunning] = React.useState(false);
	const [lastRunOk, setLastRunOk] = React.useState(false);

	const [validationErrors, setValidationErrors] = React.useState<string[]>([]);

	const [log, setLog] = React.useState<string[]>([]);
	const logRef = React.useRef<HTMLPreElement | null>(null);

	React.useEffect(() => {
		if (!projectNameTouched) {
			setProjectName(defaultProjectName);
		}
	}, [defaultProjectName, projectNameTouched]);

	// A bootstrapped project_path/deploy result is only valid for the
	// project name + directory it was created with. If either changes
	// (directly, or via the default-name sync above) after a successful
	// bootstrap, the old path no longer refers to what the user is about
	// to deploy/run — drop it so Deploy/Run re-disable until the user
	// bootstraps again at the new location.
	React.useEffect(() => {
		setProjectPath(null);
		setLastDeployOk(false);
		setLastRunOk(false);
	}, [projectName, projectDir]);

	// Clear a stale bootstrap validation message once the underlying
	// config actually changes, so it doesn't linger after the user fixes
	// the issue elsewhere in the builder. Guarded so this doesn't force a
	// re-render on every keystroke across the whole builder once the
	// message is already cleared.
	React.useEffect(() => {
		setValidationErrors((prev) => (prev.length > 0 ? [] : prev));
	}, [configFormState]);

	const appendLog = React.useCallback((line: string) => {
		setLog((prev) => [...prev, line]);
	}, []);

	React.useEffect(() => {
		if (logRef.current) {
			logRef.current.scrollTop = logRef.current.scrollHeight;
		}
	}, [log]);

	const fetchProfiles = React.useCallback(async () => {
		setProfilesLoading(true);
		setProfilesError(null);
		try {
			const res = await listDatabricksProfiles();
			setProfiles(res.profiles);
		} catch (err) {
			setProfilesError(describeError(err));
		} finally {
			setProfilesLoading(false);
			setProfilesLoaded(true);
		}
	}, []);

	// Loads profiles when the Deploy tab first mounts (Radix unmounts inactive
	// tab content by default, so this fires each time the tab is opened).
	React.useEffect(() => {
		fetchProfiles();
	}, [fetchProfiles]);

	React.useEffect(() => {
		setCatalog("");
		setCatalogs([]);
		setCatalogsError(null);
		setSchema("");
		setSchemas([]);
		setSchemasError(null);
		setSchemaMode("select");
		if (!profile) return;
		let cancelled = false;
		setCatalogsLoading(true);
		listDatabricksCatalogs(profile)
			.then((res) => {
				if (!cancelled) setCatalogs(res.catalogs);
			})
			.catch((err) => {
				if (!cancelled) setCatalogsError(describeError(err));
			})
			.finally(() => {
				if (!cancelled) setCatalogsLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [profile]);

	React.useEffect(() => {
		setSchema("");
		setSchemas([]);
		setSchemasError(null);
		setSchemaMode("select");
		if (!profile || !catalog) return;
		let cancelled = false;
		setSchemasLoading(true);
		listDatabricksSchemas(catalog, profile)
			.then((res) => {
				if (!cancelled) setSchemas(res.schemas);
			})
			.catch((err) => {
				if (!cancelled) setSchemasError(describeError(err));
			})
			.finally(() => {
				if (!cancelled) setSchemasLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [profile, catalog]);

	const canBootstrap =
		!!catalog && !!schema && !!projectName.trim() && !!projectDir.trim() && !bootstrapping;
	const canDeploy = !!projectPath && !deploying;
	const canRun = !!projectPath && lastDeployOk && !running;

	const handleBootstrap = React.useCallback(async () => {
		if (!catalog || !schema || !projectName.trim() || !projectDir.trim()) return;

		// Gate on the same client-side validation the rest of the builder
		// uses before hitting the backend, so an incomplete configuration
		// surfaces as a clear inline message here instead of a raw 400 in
		// the output log.
		const errors = validateFormState(configFormState);
		if (errors.length > 0) {
			setValidationErrors(errors);
			return;
		}
		setValidationErrors([]);

		setBootstrapping(true);
		setProjectPath(null);
		setLastDeployOk(false);
		setLastRunOk(false);
		appendLog(`$ bootstrap ${projectName.trim()} into ${projectDir.trim()}`);
		try {
			const res = await bootstrapDatabricksProject({
				config_dict: configPayload.config_dict,
				project_dir: projectDir.trim(),
				project_name: projectName.trim(),
				catalog,
				schema,
				overwrite,
			});
			setProjectPath(res.project_path);
			appendLog(
				`Bootstrapped ${res.project_path}\nWrote ${res.files.length} file(s):\n  ${res.files.join("\n  ")}`,
			);
		} catch (err) {
			appendLog(`Bootstrap failed: ${describeError(err)}`);
		} finally {
			setBootstrapping(false);
		}
	}, [catalog, schema, projectName, projectDir, overwrite, configPayload, configFormState, appendLog]);

	const handleDeploy = React.useCallback(async () => {
		if (!projectPath) return;
		setDeploying(true);
		setLastDeployOk(false);
		setLastRunOk(false);
		appendLog(`$ databricks bundle deploy${profile ? ` --profile ${profile}` : ""}`);
		try {
			const res = await deployDatabricksBundle({ project_path: projectPath, profile: profile || undefined });
			appendLog(res.output || "(no output)");
			appendLog(res.ok ? "Deploy succeeded." : "Deploy failed.");
			setLastDeployOk(res.ok);
		} catch (err) {
			appendLog(`Deploy failed: ${describeError(err)}`);
		} finally {
			setDeploying(false);
		}
	}, [projectPath, profile, appendLog]);

	const handleRun = React.useCallback(async () => {
		if (!projectPath) return;
		setRunning(true);
		setLastRunOk(false);
		appendLog(`$ databricks bundle run${profile ? ` --profile ${profile}` : ""}`);
		try {
			const res = await runDatabricksPipeline({ project_path: projectPath, profile: profile || undefined });
			appendLog(res.output || "(no output)");
			appendLog(res.ok ? "Run succeeded." : "Run failed.");
			setLastRunOk(res.ok);
		} catch (err) {
			appendLog(`Run failed: ${describeError(err)}`);
		} finally {
			setRunning(false);
		}
	}, [projectPath, profile, appendLog]);

	// Step statuses derive purely from the existing state — nothing new is
	// tracked beyond `lastRunOk`, which only paints the last step green.
	const targetDone = !!catalog && !!schema;
	const profileStatus: StepStatus = profile ? "done" : "active";
	const targetStatus: StepStatus = !profile ? "blocked" : targetDone ? "done" : "active";
	const bootstrapStatus: StepStatus = !targetDone ? "blocked" : projectPath ? "done" : "active";
	const deployStatus: StepStatus = !projectPath ? "blocked" : lastDeployOk ? "done" : "active";
	const runStatus: StepStatus = !lastDeployOk ? "blocked" : lastRunOk ? "done" : "active";

	return (
		<div className="flex h-full min-h-0 flex-col gap-5">
			<p className="text-xs leading-relaxed text-fg-muted">
				Bootstraps a Databricks Asset Bundle project from the current configuration, then deploys and runs it
				via the local <code className="font-mono">databricks</code> CLI (reads <code className="font-mono">~/.databrickscfg</code>).
			</p>

			<ol className="flex flex-col" aria-label="Deployment steps">
				<Step index={1} title="Profile" status={profileStatus} detail={profile || undefined}>
					<Field
						as="div"
						label="Databricks CLI profile"
						tooltip="Databricks CLI profile from ~/.databrickscfg, used to browse catalogs/schemas and to run deploy/run."
						error={profilesError ?? undefined}
					>
						<SelectInput value={profile} disabled={profilesLoading} onChange={(event) => setProfile(event.target.value)}>
							<option value="">{profilesLoading ? "Loading…" : "Select profile"}</option>
							{profiles.map((name) => (
								<option key={name} value={name}>
									{name}
								</option>
							))}
						</SelectInput>
					</Field>
					{profilesLoaded && !profilesLoading && !profilesError && profiles.length === 0 && (
						<Callout tone="warning">
							No profiles found in <code className="font-mono">~/.databrickscfg</code>. Run{" "}
							<code className="font-mono">databricks configure</code> (or add a profile manually), then{" "}
							<button type="button" className="underline" onClick={fetchProfiles}>
								retry
							</button>
							.
						</Callout>
					)}
				</Step>

				<Step
					index={2}
					title="Target"
					status={targetStatus}
					detail={targetDone ? `${catalog}.${schema}` : undefined}
					blockedHint="Pick a profile first."
				>
					<div className="grid grid-cols-2 gap-4">
						<Field label="Catalog" tooltip="Unity Catalog catalog the bundled pipeline writes to." error={catalogsError ?? undefined}>
							<SelectInput value={catalog} disabled={!profile || catalogsLoading} onChange={(event) => setCatalog(event.target.value)}>
								<option value="">{catalogsLoading ? "Loading…" : "Select catalog"}</option>
								{catalogs.map((name) => (
									<option key={name} value={name}>
										{name}
									</option>
								))}
							</SelectInput>
						</Field>
						<Field
							label="Schema"
							tooltip="Unity Catalog schema (within the selected catalog) the bundled pipeline writes to. Pipelines can create a schema that doesn't exist yet — pick 'Custom schema…' to name a new one."
							error={schemasError ?? undefined}
							help={schemaMode === "custom" ? "Created on deploy if it doesn't exist yet." : undefined}
						>
							{schemaMode === "custom" ? (
								<div className="flex items-center gap-2">
									<input
										type="text"
										className={cx(INPUT, "font-mono text-xs")}
										placeholder="new-schema-name"
										value={schema}
										autoFocus
										disabled={!catalog}
										onChange={(event) => setSchema(event.target.value)}
									/>
									<button
										type="button"
										className={cx(BTN_LINK, "shrink-0")}
										onClick={() => {
											setSchemaMode("select");
											setSchema("");
										}}
									>
										List
									</button>
								</div>
							) : (
								<SelectInput
									value={schema}
									disabled={!catalog || schemasLoading}
									onChange={(event) => {
										if (event.target.value === CUSTOM_SCHEMA_VALUE) {
											setSchemaMode("custom");
											setSchema("");
										} else {
											setSchema(event.target.value);
										}
									}}
								>
									<option value="">{schemasLoading ? "Loading…" : "Select schema"}</option>
									{schemas.map((name) => (
										<option key={name} value={name}>
											{name}
										</option>
									))}
									<option value={CUSTOM_SCHEMA_VALUE}>Custom schema… (create new)</option>
								</SelectInput>
							)}
						</Field>
					</div>
				</Step>

				<Step
					index={3}
					title="Bootstrap"
					status={bootstrapStatus}
					detail={projectPath ?? undefined}
					blockedHint="Choose a catalog and schema first."
				>
					<div className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-4">
						<Field label="Project name" tooltip="Name of the bundle project directory and pipeline. Defaults to the stream's table name.">
							<input
								type="text"
								className={cx(INPUT, "font-mono text-xs")}
								placeholder="my-connector"
								value={projectName}
								onChange={(event) => {
									setProjectNameTouched(true);
									setProjectName(event.target.value);
								}}
							/>
						</Field>
						<Field label="Project directory" tooltip="Local directory the bundle project is written into, under a folder named after the project.">
							<input
								type="text"
								className={cx(INPUT, "font-mono text-xs")}
								placeholder={DEFAULT_PROJECT_DIR}
								value={projectDir}
								onChange={(event) => setProjectDir(event.target.value)}
							/>
						</Field>
					</div>
					<CheckboxRow
						label="Overwrite bundle files in an existing folder"
						description="Other files in the folder are left in place."
						checked={overwrite}
						onChange={(event) => setOverwrite(event.target.checked)}
					/>
					{validationErrors.length > 0 && (
						<Callout tone="error">
							<p className="font-medium">Fix the configuration before bootstrapping:</p>
							<ul className="list-disc pl-4">
								{validationErrors.map((error) => (
									<li key={error}>{error}</li>
								))}
							</ul>
						</Callout>
					)}
					<div className="flex items-center gap-3">
						<button
							type="button"
							className={cx(projectPath ? BTN_GHOST : BTN_PRIMARY, BTN_SMALL)}
							onClick={handleBootstrap}
							disabled={!canBootstrap}
						>
							{bootstrapping ? "Bootstrapping…" : projectPath ? "Bootstrap again" : "Bootstrap project"}
						</button>
					</div>
				</Step>

				<Step index={4} title="Deploy" status={deployStatus} blockedHint="Bootstrap the project first.">
					<div className="flex flex-wrap items-center gap-3">
						<button
							type="button"
							className={cx(lastDeployOk ? BTN_GHOST : BTN_PRIMARY, BTN_SMALL)}
							onClick={handleDeploy}
							disabled={!canDeploy}
						>
							{deploying ? "Deploying…" : lastDeployOk ? "Deploy again" : "Deploy bundle"}
						</button>
						<code className="truncate font-mono text-[11px] text-fg-muted">
							databricks bundle deploy{profile ? ` --profile ${profile}` : ""}
						</code>
					</div>
				</Step>

				<Step index={5} title="Run" status={runStatus} blockedHint="Deploy the bundle first." last>
					<div className="flex flex-wrap items-center gap-3">
						<button
							type="button"
							className={cx(lastRunOk ? BTN_GHOST : BTN_PRIMARY, BTN_SMALL)}
							onClick={handleRun}
							disabled={!canRun}
						>
							{running ? "Running…" : lastRunOk ? "Run again" : "Run pipeline"}
						</button>
						<code className="truncate font-mono text-[11px] text-fg-muted">
							databricks bundle run{profile ? ` --profile ${profile}` : ""}
						</code>
					</div>
				</Step>
			</ol>

			<div className="flex min-h-[200px] flex-1 flex-col overflow-hidden rounded-lg border border-border bg-field">
				<div className="flex h-8 shrink-0 items-center justify-between border-b border-border px-3">
					<span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-fg-muted">CLI output</span>
					<button
						type="button"
						className={cx(BTN_LINK, "text-fg-muted")}
						onClick={() => setLog([])}
						disabled={log.length === 0}
					>
						Clear
					</button>
				</div>
				<pre
					ref={logRef}
					className="scroll-thin m-0 min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded-none border-0 bg-transparent px-3 py-2.5 font-mono text-xs leading-5 text-fg"
					aria-label="Deploy output log"
				>
					{log.length > 0 ? log.join("\n\n") : <span className="text-fg-subtle">// Bootstrap, deploy, and run output will appear here.</span>}
				</pre>
			</div>
		</div>
	);
};
