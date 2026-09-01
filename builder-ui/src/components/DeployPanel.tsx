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
import { InfoTooltip } from "./InfoTooltip";

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

const SELECT_CLASS =
	"w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm appearance-none pr-9 transition-all focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed";
const INPUT_CLASS =
	"rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5 disabled:opacity-60 disabled:cursor-not-allowed";
const BUTTON_CLASS =
	"inline-flex items-center gap-1 rounded-full bg-blue-9 px-5 py-2 text-sm font-semibold text-white shadow-soft transition hover:bg-blue-10 disabled:opacity-50 disabled:cursor-not-allowed";

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
		appendLog(`$ databricks bundle run${profile ? ` --profile ${profile}` : ""}`);
		try {
			const res = await runDatabricksPipeline({ project_path: projectPath, profile: profile || undefined });
			appendLog(res.output || "(no output)");
			appendLog(res.ok ? "Run succeeded." : "Run failed.");
		} catch (err) {
			appendLog(`Run failed: ${describeError(err)}`);
		} finally {
			setRunning(false);
		}
	}, [projectPath, profile, appendLog]);

	return (
		<div className="space-y-5">
			<p className="text-xs text-muted dark:text-drac-muted">
				Bootstraps a Databricks Asset Bundle project from the current configuration, then deploys and runs
				it via the local <code>databricks</code> CLI (reads <code>~/.databrickscfg</code>).
			</p>

			<div className="grid gap-5 md:grid-cols-2">
				<label className="flex flex-col gap-2">
					<div className="flex items-center gap-1">
						<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Profile</span>
						<InfoTooltip text="Databricks CLI profile from ~/.databrickscfg, used to browse catalogs/schemas and to run deploy/run." />
					</div>
					<select
						className={SELECT_CLASS}
						value={profile}
						disabled={profilesLoading}
						onChange={(event) => setProfile(event.target.value)}
					>
						<option value="">{profilesLoading ? "Loading…" : "Select profile"}</option>
						{profiles.map((name) => (
							<option key={name} value={name}>
								{name}
							</option>
						))}
					</select>
					{profilesError && <span className="text-xs text-error">{profilesError}</span>}
					{profilesLoaded && !profilesLoading && !profilesError && profiles.length === 0 && (
						<span className="text-xs text-warning">
							No profiles found in <code>~/.databrickscfg</code>. Run{" "}
							<code>databricks configure</code> (or add a profile manually), then{" "}
							<button type="button" className="underline" onClick={fetchProfiles}>
								retry
							</button>
							.
						</span>
					)}
				</label>

				<label className="flex flex-col gap-2">
					<div className="flex items-center gap-1">
						<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Catalog</span>
						<InfoTooltip text="Unity Catalog catalog the bundled pipeline writes to." />
					</div>
					<select
						className={SELECT_CLASS}
						value={catalog}
						disabled={!profile || catalogsLoading}
						onChange={(event) => setCatalog(event.target.value)}
					>
						<option value="">{catalogsLoading ? "Loading…" : "Select catalog"}</option>
						{catalogs.map((name) => (
							<option key={name} value={name}>
								{name}
							</option>
						))}
					</select>
					{catalogsError && <span className="text-xs text-error">{catalogsError}</span>}
				</label>

				<label className="flex flex-col gap-2">
					<div className="flex items-center gap-1">
						<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Schema</span>
						<InfoTooltip text="Unity Catalog schema (within the selected catalog) the bundled pipeline writes to. Pipelines can create a schema that doesn't exist yet — pick 'Custom schema…' to name a new one." />
					</div>
					{schemaMode === "custom" ? (
						<div className="flex items-center gap-2">
							<input
								type="text"
								className={`${INPUT_CLASS} flex-1`}
								placeholder="new-schema-name"
								value={schema}
								autoFocus
								disabled={!catalog}
								onChange={(event) => setSchema(event.target.value)}
							/>
							<button
								type="button"
								className="whitespace-nowrap text-xs text-muted underline dark:text-drac-muted"
								onClick={() => {
									setSchemaMode("select");
									setSchema("");
								}}
							>
								Back to list
							</button>
						</div>
					) : (
						<select
							className={SELECT_CLASS}
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
						</select>
					)}
					{schemaMode === "custom" && (
						<span className="text-xs text-muted dark:text-drac-muted">
							This schema will be created on deploy if it doesn't already exist.
						</span>
					)}
					{schemasError && <span className="text-xs text-error">{schemasError}</span>}
				</label>

				<label className="flex flex-col gap-2">
					<div className="flex items-center gap-1">
						<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Project name</span>
						<InfoTooltip text="Name of the bundle project directory and pipeline. Defaults to the stream's table name." />
					</div>
					<input
						type="text"
						className={INPUT_CLASS}
						placeholder="my-connector"
						value={projectName}
						onChange={(event) => {
							setProjectNameTouched(true);
							setProjectName(event.target.value);
						}}
					/>
				</label>

				<label className="flex flex-col gap-2 md:col-span-2">
					<div className="flex items-center gap-1">
						<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">
							Project directory
						</span>
						<InfoTooltip text="Local directory the bundle project is written into, under a folder named after the project." />
					</div>
					<input
						type="text"
						className={INPUT_CLASS}
						placeholder={DEFAULT_PROJECT_DIR}
						value={projectDir}
						onChange={(event) => setProjectDir(event.target.value)}
					/>
				</label>
			</div>

			<label className="flex items-center gap-2 text-sm text-slate-11 dark:text-drac-foreground/80">
				<input
					type="checkbox"
					checked={overwrite}
					onChange={(event) => setOverwrite(event.target.checked)}
					className="h-4 w-4 rounded border-border"
				/>
				Overwrite bundle files in existing folder — other files are left in place
			</label>

			{validationErrors.length > 0 && (
				<div
					className="flex items-start gap-2 rounded-md border border-error/40 bg-red-3/60 dark:bg-drac-red/25 dark:border-drac-red/40 px-3 py-2 text-xs text-error shadow-sm"
					data-status="error"
				>
					<span className="mt-0.5 inline-block h-2 w-2 flex-shrink-0 rounded-full bg-error" />
					<div className="leading-snug">
						<p className="font-medium">Fix the configuration before bootstrapping:</p>
						<ul className="list-disc pl-4">
							{validationErrors.map((error) => (
								<li key={error}>{error}</li>
							))}
						</ul>
					</div>
				</div>
			)}

			<div className="flex flex-wrap items-center gap-3">
				<button type="button" className={BUTTON_CLASS} onClick={handleBootstrap} disabled={!canBootstrap}>
					{bootstrapping ? "Bootstrapping…" : "Bootstrap"}
				</button>
				<button type="button" className={BUTTON_CLASS} onClick={handleDeploy} disabled={!canDeploy}>
					{deploying ? "Deploying…" : "Deploy"}
				</button>
				<button type="button" className={BUTTON_CLASS} onClick={handleRun} disabled={!canRun}>
					{running ? "Running…" : "Run"}
				</button>
				{projectPath && (
					<span className="text-xs text-muted dark:text-drac-muted truncate" title={projectPath}>
						{projectPath}
					</span>
				)}
			</div>

			<div className="flex flex-col gap-2">
				<span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Output</span>
				<pre
					ref={logRef}
					className="h-64 w-full overflow-auto rounded-2xl border border-border bg-background dark:bg-drac-surface px-4 py-3 font-mono text-xs text-slate-12 dark:text-drac-foreground leading-5 shadow-soft whitespace-pre-wrap break-words"
					aria-label="Deploy output log"
				>
					{log.length > 0 ? log.join("\n\n") : "// Bootstrap, deploy, and run output will appear here."}
				</pre>
			</div>
		</div>
	);
};
