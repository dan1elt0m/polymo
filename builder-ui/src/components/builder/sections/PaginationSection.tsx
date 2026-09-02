import React from "react";
import type { ConfigFormState } from "../../../types";
import { InputWithCursorPosition } from "../../InputWithCursorPosition";
import { Disclosure, Field, INPUT, SelectInput } from "../../ui/primitives";

export interface PaginationSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "pagination-section";

const TYPE_LABELS: Record<string, string> = {
  none: "none",
  offset: "offset",
  cursor: "cursor",
  page: "page",
  link_header: "link header",
};

export const PaginationSection: React.FC<PaginationSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const paginationType = state.paginationType || "none";
  const isOffset = paginationType === "offset" || paginationType === "page";
  const isCursor = paginationType === "cursor";
  const isLinkHeader = paginationType === "link_header";

  React.useEffect(() => {
    if (paginationType !== "none") setIsOpen(true);
  }, [paginationType]);

  const summary = React.useMemo(() => {
    const parts = [TYPE_LABELS[paginationType] ?? paginationType];
    if (paginationType !== "none" && state.paginationPageSize) parts.push(`${state.paginationPageSize}/page`);
    return parts.join(" · ");
  }, [paginationType, state.paginationPageSize]);

  return (
    <Disclosure id={TOGGLE_ID} title="Pagination" summary={summary} open={isOpen} onToggle={() => setIsOpen((v) => !v)}>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Pagination type" tooltip="Method used to paginate through multiple pages of results">
          <SelectInput
            value={paginationType}
            onChange={(event) => onUpdateState({ paginationType: event.target.value as ConfigFormState["paginationType"] })}
          >
            <option value="none">None</option>
            <option value="offset">Offset-based</option>
            <option value="cursor">Cursor-based</option>
            <option value="page">Page-based</option>
            <option value="link_header">Link header</option>
          </SelectInput>
        </Field>

        {(isOffset || isCursor || isLinkHeader) && (
          <Field label="Page size" tooltip="Number of records fetched per request.">
            <input
              type="number"
              min={1}
              className={INPUT}
              placeholder="100"
              value={state.paginationPageSize || ""}
              onChange={(event) => onUpdateState({ paginationPageSize: event.target.value })}
            />
          </Field>
        )}
      </div>

      {isOffset && (
        <div className="grid grid-cols-2 gap-4">
          <Field label="Limit parameter" tooltip="Query parameter controlling page size (e.g. limit, per_page).">
            <input
              type="text"
              className={INPUT}
              placeholder="limit"
              value={state.paginationLimitParam || ""}
              onChange={(event) => onUpdateState({ paginationLimitParam: event.target.value })}
            />
          </Field>
          <Field label="Offset parameter" tooltip="Query parameter that advances through results (e.g. offset).">
            <input
              type="text"
              className={INPUT}
              placeholder="offset"
              value={state.paginationOffsetParam || ""}
              onChange={(event) => onUpdateState({ paginationOffsetParam: event.target.value })}
            />
          </Field>
          <Field label="Start offset" tooltip="Initial offset for the first request.">
            <input
              type="number"
              min={0}
              className={INPUT}
              placeholder="0"
              value={state.paginationStartOffset || ""}
              onChange={(event) => onUpdateState({ paginationStartOffset: event.target.value })}
            />
          </Field>
          <Field label="Total records path" tooltip="Dotted path to the total number of records (optional).">
            <InputWithCursorPosition
              className={INPUT}
              placeholder="meta.total"
              value={state.paginationTotalRecordsPath || ""}
              onValueChange={(value) => onUpdateState({ paginationTotalRecordsPath: value })}
            />
          </Field>
        </div>
      )}

      {paginationType === "page" && (
        <div className="grid grid-cols-2 gap-4">
          <Field label="Page parameter" tooltip="Query parameter controlling page number.">
            <input
              type="text"
              className={INPUT}
              placeholder="page"
              value={state.paginationPageParam || ""}
              onChange={(event) => onUpdateState({ paginationPageParam: event.target.value })}
            />
          </Field>
          <Field label="Start page" tooltip="Initial page number for the first request.">
            <input
              type="number"
              min={1}
              className={INPUT}
              placeholder="1"
              value={state.paginationStartPage || ""}
              onChange={(event) => onUpdateState({ paginationStartPage: event.target.value })}
            />
          </Field>
          <Field label="Total pages path" tooltip="Dotted path to the total number of pages (optional).">
            <InputWithCursorPosition
              className={INPUT}
              placeholder="meta.total_pages"
              value={state.paginationTotalPagesPath || ""}
              onValueChange={(value) => onUpdateState({ paginationTotalPagesPath: value })}
            />
          </Field>
        </div>
      )}

      {isCursor && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Cursor parameter" tooltip="Query parameter carrying the cursor value sent to the API.">
              <input
                type="text"
                className={INPUT}
                placeholder="cursor"
                value={state.paginationCursorParam || ""}
                onChange={(event) => onUpdateState({ paginationCursorParam: event.target.value })}
              />
            </Field>
            <Field label="Cursor path" tooltip="Dotted path to the cursor in the response payload.">
              <InputWithCursorPosition
                className={INPUT}
                placeholder="meta.next_cursor"
                value={state.paginationCursorPath || ""}
                onValueChange={(value) => onUpdateState({ paginationCursorPath: value })}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Next URL path" tooltip="Dotted path to a fully qualified 'next' link in the payload (optional).">
              <InputWithCursorPosition
                className={INPUT}
                placeholder="links.next"
                value={state.paginationNextUrlPath || ""}
                onValueChange={(value) => onUpdateState({ paginationNextUrlPath: value })}
              />
            </Field>
            <Field label="Cursor header" tooltip="Response header that carries the next cursor (optional).">
              <input
                type="text"
                className={INPUT}
                placeholder="X-Next-Cursor"
                value={state.paginationCursorHeader || ""}
                onChange={(event) => onUpdateState({ paginationCursorHeader: event.target.value })}
              />
            </Field>
            <Field label="Initial cursor" tooltip="Fallback cursor value sent on the first request.">
              <input
                type="text"
                className={INPUT}
                placeholder="Provided by API"
                value={state.paginationInitialCursor || ""}
                onChange={(event) => onUpdateState({ paginationInitialCursor: event.target.value })}
              />
            </Field>
          </div>
        </>
      )}

      {isLinkHeader && (
        <div className="grid grid-cols-2 gap-4">
          <Field label="Link relation" tooltip="Value inside the rel attribute that identifies the next page.">
            <input
              type="text"
              className={INPUT}
              placeholder="next"
              value={state.paginationTotalPagesHeader || ""}
              onChange={(event) => onUpdateState({ paginationTotalPagesHeader: event.target.value })}
            />
          </Field>
          <Field label="Cursor header" tooltip="Header inspected when parsing the link response (optional).">
            <input
              type="text"
              className={INPUT}
              placeholder="Link"
              value={state.paginationTotalRecordsHeader || ""}
              onChange={(event) => onUpdateState({ paginationTotalRecordsHeader: event.target.value })}
            />
          </Field>
        </div>
      )}
    </Disclosure>
  );
};
