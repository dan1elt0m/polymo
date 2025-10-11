import type { RestSourceConfig } from "../types";

const indent = (level: number) => "    ".repeat(level);

const asString = (value: unknown): string => String(value ?? "");

const escapeString = (value: unknown): string => asString(value).replace(/'/g, "\\'");

const formatPrimitive = (value: unknown): string => {
    if (value === null || value === undefined) return "None";
    if (typeof value === "string") return `'${escapeString(value)}'`;
    if (typeof value === "number" || typeof value === "bigint") return String(value);
    if (typeof value === "boolean") return value ? "True" : "False";
    return `'${escapeString(asString(value))}'`;
};

const formatList = (values: unknown[], level: number): string => {
    if (!values.length) return "[]";
    const inner = values
        .map((item) => `${indent(level + 1)}${formatValue(item, level + 1)},`)
        .join("\n");
    return "[\n" + inner + "\n" + `${indent(level)}]`;
};

const formatDict = (obj: Record<string, unknown>, level: number): string => {
    const entries = Object.entries(obj);
    if (!entries.length) return "{}";
    const inner = entries
        .map(([key, value]) => `${indent(level + 1)}'${escapeString(key)}': ${formatValue(value, level + 1)},`)
        .join("\n");
    return "{\n" + inner + "\n" + `${indent(level)}}`;
};

const formatValue = (value: unknown, level: number): string => {
    if (Array.isArray(value)) return formatList(value, level);
    if (value && typeof value === "object" && !(value instanceof Date)) {
        return formatDict(value as Record<string, unknown>, level);
    }
    return formatPrimitive(value);
};

const buildImportList = (config: RestSourceConfig | any): string => {
    const imports = new Set<string>(["ApiReader", "PolymoConfig"]);

    const stream = getStream(config);
    const auth = getAuth(config);
    const pagination = stream.pagination;
    const incremental = stream.incremental;
    const selector = stream.record_selector;
    const partition = stream.partition;
    const handler = stream.error_handler as any;
    const backoff = handler?.backoff as any;

    if (auth && auth.type && auth.type !== "none") imports.add("AuthModel");

    const usePagination =
        pagination?.type &&
        (pagination.type !== "none" || Object.values(pagination).some((value) => value && value !== "none"));
    if (usePagination) imports.add("PaginationModel");

    const useIncremental = Boolean(
        incremental?.cursor_param || incremental?.cursor_field || incremental?.mode,
    );
    if (useIncremental) imports.add("IncrementalModel");

    const useSelector = Boolean(
        selector?.field_path?.length || selector?.record_filter || selector?.cast_to_schema_types,
    );
    if (useSelector) imports.add("RecordSelectorModel");

    const usePartition = Boolean(partition && partition.strategy && partition.strategy !== "none");
    if (usePartition) imports.add("PartitionModel");

    const sameRetryStatuses = (() => {
        const statuses = toArray(handler?.retry_statuses);
        if (!statuses.length) return false;
        const normalised = statuses.map((status) => String(status));
        return normalised.length === 2 && normalised.includes("5XX") && normalised.includes("429");
    })();

    const useErrorHandler = Boolean(
        handler &&
            (
                handler.max_retries !== 5 ||
                handler.retry_on_timeout !== true ||
                handler.retry_on_connection_errors !== true ||
                !sameRetryStatuses ||
                (backoff &&
                    (backoff.initial_delay_seconds !== 1 ||
                        backoff.max_delay_seconds !== 30 ||
                        backoff.multiplier !== 2))
            ),
    );
    if (useErrorHandler) {
        imports.add("ErrorHandlerModel");
        imports.add("BackoffModel");
    }

    return Array.from(imports)
        .sort()
        .join(", ");
};

const cleanToken = (token: string): string => token.trim().replace(/^['"]+|['"]+$/g, "");

const coerceScalar = (value: unknown): unknown => {
    if (typeof value === "string") {
        const cleaned = cleanToken(value);
        if (!cleaned) return cleaned;
        if (/^-?\d+$/.test(cleaned)) return Number(cleaned);
        if (/^-?\d*\.\d+$/.test(cleaned)) return Number(cleaned);
        return cleaned;
    }
    return value;
};

const toArray = (value: unknown): unknown[] => {
    if (Array.isArray(value)) return value.map(coerceScalar);
    if (value === null || value === undefined) return [];

    if (typeof value === "string") {
        const trimmed = cleanToken(value);
        if (!trimmed) return [];

        try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) return parsed.map(coerceScalar);
        } catch {

        }

        if (trimmed.includes("\n") || trimmed.includes(",")) {
            const split = trimmed
                .split(/[\n,]+/)
                .map((entry) => cleanToken(entry))
                .filter((entry) => entry.length > 0)
                .map(coerceScalar);
            if (split.length) return split;
        }

        return [coerceScalar(trimmed)];
    }

    if (typeof (value as any)[Symbol.iterator] === "function") {
        return Array.from(value as Iterable<unknown>).map(coerceScalar);
    }

    return [coerceScalar(value)];
};

const getAuth = (config: any) => config.auth ?? config.source?.auth ?? null;

const getStream = (config: any) => config.stream ?? {};

const getBaseUrl = (config: any): string => {
    if (typeof config.base_url === "string" && config.base_url.trim()) return config.base_url;
    if (config.source && typeof config.source.base_url === "string") return config.source.base_url;
    return "";
};

const buildAuthBlock = (config: RestSourceConfig | any): string | undefined => {
    const auth = getAuth(config);
    if (!auth || auth.type === "none") return undefined;
    const lines: string[] = [];
    lines.push("auth=AuthModel(");
    lines.push(`${indent(2)}type='${escapeString(auth.type)}',`);
    if (auth.token) {
        lines.push(`${indent(2)}token='${escapeString(auth.token)}',`);
    } else if (auth.type === "bearer") {
        lines.push(`${indent(2)}token='YOUR_TOKEN',`);
    }
    if (auth.token_url) lines.push(`${indent(2)}token_url='${escapeString(auth.token_url)}',`);
    if (auth.client_id) lines.push(`${indent(2)}client_id='${escapeString(auth.client_id)}',`);
    if (auth.client_secret) {
        lines.push(`${indent(2)}client_secret='${escapeString(auth.client_secret)}',`);
    } else if (auth.type === "oauth2") {
        lines.push(`${indent(2)}client_secret='YOUR_CLIENT_SECRET',`);
    }
    const scopes = toArray(auth.scope);
    if (scopes.length) {
        lines.push(`${indent(2)}scope=${formatValue(scopes, 2)},`);
    }
    if (auth.audience) lines.push(`${indent(2)}audience='${escapeString(auth.audience)}',`);
    if (auth.extra_params && Object.keys(auth.extra_params).length) {
        lines.push(`${indent(2)}extra_params=${formatValue(auth.extra_params as Record<string, unknown>, 2)},`);
    }
    lines.push(`${indent(1)}),`);
    return lines.join("\n");
};

const buildPaginationBlock = (config: RestSourceConfig): string | undefined => {
    const pagination = config.stream.pagination;
    const usePagination =
        pagination?.type &&
        (pagination.type !== "none" || Object.values(pagination).some((value) => value && value !== "none"));
    if (!usePagination) return undefined;
    const lines: string[] = [];
    lines.push("pagination=PaginationModel(");
    lines.push(`${indent(2)}type='${escapeString(pagination.type)}',`);
    if (pagination.page_size != null) lines.push(`${indent(2)}page_size=${pagination.page_size},`);
    if (pagination.limit_param) lines.push(`${indent(2)}limit_param='${escapeString(pagination.limit_param)}',`);
    if (pagination.offset_param) lines.push(`${indent(2)}offset_param='${escapeString(pagination.offset_param)}',`);
    if (pagination.start_offset != null) lines.push(`${indent(2)}start_offset=${pagination.start_offset},`);
    if (pagination.page_param) lines.push(`${indent(2)}page_param='${escapeString(pagination.page_param)}',`);
    if (pagination.start_page != null) lines.push(`${indent(2)}start_page=${pagination.start_page},`);
    if (pagination.cursor_param) lines.push(`${indent(2)}cursor_param='${escapeString(pagination.cursor_param)}',`);
    const cursorPath = toArray(pagination.cursor_path);
    if (cursorPath.length) lines.push(`${indent(2)}cursor_path=${formatValue(cursorPath, 2)},`);
    const nextUrlPath = toArray(pagination.next_url_path);
    if (nextUrlPath.length) lines.push(`${indent(2)}next_url_path=${formatValue(nextUrlPath, 2)},`);
    if (pagination.cursor_header) lines.push(`${indent(2)}cursor_header='${escapeString(pagination.cursor_header)}',`);
    if (pagination.initial_cursor) lines.push(`${indent(2)}initial_cursor='${escapeString(pagination.initial_cursor)}',`);
    if (pagination.stop_on_empty_response != null)
        lines.push(`${indent(2)}stop_on_empty_response=${pagination.stop_on_empty_response ? "True" : "False"},`);
    const totalPagesPath = toArray(pagination.total_pages_path);
    if (totalPagesPath.length)
        lines.push(`${indent(2)}total_pages_path=${formatValue(totalPagesPath, 2)},`);
    if (pagination.total_pages_header)
        lines.push(`${indent(2)}total_pages_header='${escapeString(pagination.total_pages_header)}',`);
    const totalRecordsPath = toArray(pagination.total_records_path);
    if (totalRecordsPath.length)
        lines.push(`${indent(2)}total_records_path=${formatValue(totalRecordsPath, 2)},`);
    if (pagination.total_records_header)
        lines.push(`${indent(2)}total_records_header='${escapeString(pagination.total_records_header)}',`);
    lines.push(`${indent(1)}),`);
    return lines.join("\n");
};

const buildIncrementalBlock = (config: RestSourceConfig): string | undefined => {
    const inc = config.stream.incremental;
    if (!inc) return undefined;
    const fields: string[] = [];
    if (inc.mode) fields.push(`${indent(2)}mode='${escapeString(inc.mode)}',`);
    if (inc.cursor_param) fields.push(`${indent(2)}cursor_param='${escapeString(inc.cursor_param)}',`);
    if (inc.cursor_field) fields.push(`${indent(2)}cursor_field='${escapeString(inc.cursor_field)}',`);
    if (!fields.length) return undefined;
    return ["incremental=IncrementalModel(", ...fields, `${indent(1)}),`].join("\n");
};

const buildRecordSelectorBlock = (config: RestSourceConfig): string | undefined => {
    const selector = config.stream.record_selector;
    if (!selector) return undefined;
    const fields: string[] = [];
    const fieldPath = toArray(selector.field_path);
    if (fieldPath.length) fields.push(`${indent(2)}field_path=${formatValue(fieldPath, 2)},`);
    if (selector.record_filter)
        fields.push(`${indent(2)}record_filter='${escapeString(selector.record_filter)}',`);
    if (selector.cast_to_schema_types)
        fields.push(`${indent(2)}cast_to_schema_types=True,`);
    if (!fields.length) return undefined;
    return ["record_selector=RecordSelectorModel(", ...fields, `${indent(1)}),`].join("\n");
};

const buildErrorHandlerBlock = (config: RestSourceConfig): string | undefined => {
    const handler = config.stream.error_handler as any;
    if (!handler) return undefined;
    const backoff = handler.backoff as any;
    const sameStatuses = handler.retry_statuses && toArray(handler.retry_statuses).sort().join("|") === "429|5XX";
    const isDefault =
        handler.max_retries === 5 &&
        handler.retry_on_timeout === true &&
        handler.retry_on_connection_errors === true &&
        sameStatuses &&
        (!backoff ||
            (backoff.initial_delay_seconds === 1 &&
                backoff.max_delay_seconds === 30 &&
                backoff.multiplier === 2));
    if (isDefault) return undefined;

    const lines: string[] = [];
    lines.push("error_handler=ErrorHandlerModel(");
    if (handler.max_retries !== undefined) lines.push(`${indent(2)}max_retries=${handler.max_retries},`);
    const retryStatuses = toArray(handler.retry_statuses);
    if (retryStatuses.length)
        lines.push(`${indent(2)}retry_statuses=${formatValue(retryStatuses, 2)},`);
    if (handler.retry_on_timeout !== undefined)
        lines.push(`${indent(2)}retry_on_timeout=${handler.retry_on_timeout ? "True" : "False"},`);
    if (handler.retry_on_connection_errors !== undefined)
        lines.push(`${indent(2)}retry_on_connection_errors=${handler.retry_on_connection_errors ? "True" : "False"},`);
    if (backoff) {
        lines.push(`${indent(2)}backoff=BackoffModel(`);
        if (backoff.initial_delay_seconds !== undefined)
            lines.push(`${indent(3)}initial_delay_seconds=${backoff.initial_delay_seconds},`);
        if (backoff.max_delay_seconds !== undefined)
            lines.push(`${indent(3)}max_delay_seconds=${backoff.max_delay_seconds},`);
        if (backoff.multiplier !== undefined)
            lines.push(`${indent(3)}multiplier=${backoff.multiplier},`);
        lines.push(`${indent(2)}),`);
    }
    lines.push(`${indent(1)}),`);
    return lines.join("\n");
};

const buildPartitionBlock = (config: RestSourceConfig): string | undefined => {
    const partition = config.stream.partition;
    if (!partition || partition.strategy === "none") return undefined;
    const lines: string[] = [];
    lines.push("partition=PartitionModel(");
    lines.push(`${indent(2)}strategy='${escapeString(partition.strategy)}',`);
    if (partition.param) lines.push(`${indent(2)}param='${escapeString(partition.param)}',`);
    const partitionValues = toArray(partition.values);
    if (partitionValues.length)
        lines.push(`${indent(2)}values=${formatValue(partitionValues, 2)},`);
    if (partition.range_start != null)
        lines.push(`${indent(2)}range_start=${formatPrimitive(partition.range_start)},`);
    if (partition.range_end != null)
        lines.push(`${indent(2)}range_end=${formatPrimitive(partition.range_end)},`);
    if (partition.range_step != null) lines.push(`${indent(2)}range_step=${partition.range_step},`);
    if (partition.range_kind)
        lines.push(`${indent(2)}range_kind='${escapeString(partition.range_kind)}',`);
    if (partition.value_template)
        lines.push(`${indent(2)}value_template='${escapeString(partition.value_template)}',`);
    if (partition.extra_template)
        lines.push(`${indent(2)}extra_template='${escapeString(partition.extra_template)}',`);
    const endpoints = toArray(partition.endpoints);
    if (endpoints.length)
        lines.push(`${indent(2)}endpoints=${formatValue(endpoints, 2)},`);
    lines.push(`${indent(1)}),`);
    return lines.join("\n");
};

export const buildPysparkScript = (config: RestSourceConfig): string => {
    const imports = buildImportList(config);
    const lines: string[] = [];

    const baseUrl = config.source?.base_url ?? "";
    const stream = config.stream;

    lines.push("from pyspark.sql import SparkSession");
    lines.push(`from polymo import ${imports}`);
    lines.push("");
    lines.push("config = PolymoConfig(");
    lines.push(`${indent(1)}base_url='${escapeString(baseUrl)}',`);
    lines.push(`${indent(1)}path='${escapeString(stream.path)}',`);
    if (stream.params && Object.keys(stream.params).length)
        lines.push(`${indent(1)}params=${formatValue(stream.params, 1)},`);
    if (stream.headers && Object.keys(stream.headers).length)
        lines.push(`${indent(1)}headers=${formatValue(stream.headers, 1)},`);

    const blocks: (string | undefined)[] = [
        buildAuthBlock(config),
        buildPaginationBlock(config),
        buildIncrementalBlock(config),
        buildRecordSelectorBlock(config),
        buildErrorHandlerBlock(config),
        buildPartitionBlock(config),
    ];

    for (const block of blocks) {
        if (block) lines.push(`${indent(1)}${block}`);
    }

    if (stream.infer_schema === false)
        lines.push(`${indent(1)}infer_schema=False,`);
    if (stream.schema)
        lines.push(`${indent(1)}schema_ddl='${escapeString(stream.schema)}',`);

    lines.push(")");
    lines.push("");
    lines.push("spark = SparkSession.builder.getOrCreate()");
    lines.push("spark.dataSource.register(ApiReader)");
    lines.push("");
    const authType = getAuth(config)?.type ?? "none";
    const authOptionLine = (() => {
        if (authType === "bearer") return `.option('token', 'YOUR_TOKEN')`;
        if (authType === "api_key") return `.option('api_key', 'YOUR_API_KEY')`;
        if (authType === "oauth2") return `.option('oauth_client_secret', 'YOUR_CLIENT_SECRET')`;
        return undefined;
    })();
    lines.push("df = (");
    lines.push(`${indent(1)}spark.read.format('polymo')`);
    if (authOptionLine) lines.push(`${indent(1)}${authOptionLine}`);
    lines.push(`${indent(1)}.option('config_json', config.config_json())`);
    lines.push(`${indent(1)}.load()`);
    lines.push(")");
    lines.push("");
    lines.push("df.show()");

    return lines.join("\n");
};

export const buildScriptFileName = (rawName?: string): string => {
    const normalized = (rawName ?? 'config').toString();
    const base = normalized.replace(/\.[^.]+$/, '') || 'config';
    const slug = base.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'config';
    return `${slug}.py`;
};
