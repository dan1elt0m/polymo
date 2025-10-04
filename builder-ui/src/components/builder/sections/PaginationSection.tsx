import React from "react";
import type { ConfigFormState } from "../../../types";
import { InfoTooltip } from "../../InfoTooltip";
import { InputWithCursorPosition } from "../../InputWithCursorPosition";

export interface PaginationSectionProps {
  state: ConfigFormState;
  onUpdateState: (patch: Partial<ConfigFormState>) => void;
}

const TOGGLE_ID = "pagination-section";

export const PaginationSection: React.FC<PaginationSectionProps> = ({ state, onUpdateState }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const paginationType = state.paginationType || "none";
  const isOffset = paginationType === "offset" || paginationType === "page";
  const isCursor = paginationType === "cursor";
  const isLinkHeader = paginationType === "link_header";

  return (
    <div className="space-y-3">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-slate-12 hover:border-blue-7 hover:bg-blue-3/20 dark:hover:bg-drac-selection/40 transition-colors duration-200"
        onClick={() => setIsOpen((value) => !value)}
        aria-expanded={isOpen}
        aria-controls={TOGGLE_ID}
      >
        <span className="flex items-center gap-2">
          Pagination
          <span className="text-xs font-normal text-muted">(optional)</span>
        </span>
        <span className={`transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}>
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path d="M7.25 3.75a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.25 5.56a.75.75 0 0 1 0-1.06Z" />
          </svg>
        </span>
      </button>

      {isOpen && (
        <div
          id={TOGGLE_ID}
          className="space-y-4 rounded-xl border border-border/60 dark:border-drac-border/60 bg-surface/70 dark:bg-[#1f232b]/80 backdrop-blur-sm p-5 shadow-inner transition ring-1 ring-border/40 dark:ring-drac-border/30 animate-in fade-in duration-200"
        >
          <div className="space-y-4">
            <label className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Pagination Type</span>
                <InfoTooltip text="Method used to paginate through multiple pages of results" />
              </div>
              <div className="relative">
                <select
                  className="w-full rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm appearance-none pr-9 transition-all focus:border-blue-7 dark:focus:border-drac-accent focus:outline-none"
                  value={paginationType}
                  onChange={(event) => onUpdateState({ paginationType: event.target.value as ConfigFormState["paginationType"] })}
                >
                  <option value="none">None</option>
                  <option value="offset">Offset-based</option>
                  <option value="cursor">Cursor-based</option>
                  <option value="page">Page-based</option>
                  <option value="link_header">Link header</option>
                </select>
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-10 dark:text-drac-muted">
                  <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                    <path d="M5.8 7.5a.75.75 0 0 1 1.05-.2L10 9.2l3.15-1.9a.75.75 0 0 1 .75 1.3l-3.5 2.11a.75.75 0 0 1-.76 0L5.99 8.6a.75.75 0 0 1-.2-1.1Z" />
                  </svg>
                </span>
              </div>
            </label>

            {(isOffset || isCursor || isLinkHeader) && (
              <label className="flex flex-col gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Page size</span>
                  <InfoTooltip text="Number of records fetched per request." />
                </div>
                <input
                  type="number"
                  min={1}
                  className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                  placeholder="100"
                  value={state.paginationPageSize || ""}
                  onChange={(event) => onUpdateState({ paginationPageSize: event.target.value })}
                />
              </label>
            )}

            {isOffset && (
              <div className="grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Limit parameter</span>
                    <InfoTooltip text="Query parameter controlling page size (e.g. limit, per_page)." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="limit"
                    value={state.paginationLimitParam || ""}
                    onChange={(event) => onUpdateState({ paginationLimitParam: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Offset parameter</span>
                    <InfoTooltip text="Query parameter that advances through results (e.g. offset)." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="offset"
                    value={state.paginationOffsetParam || ""}
                    onChange={(event) => onUpdateState({ paginationOffsetParam: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Start offset</span>
                    <InfoTooltip text="Initial offset for the first request." />
                  </div>
                  <input
                    type="number"
                    min={0}
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="0"
                    value={state.paginationStartOffset || ""}
                    onChange={(event) => onUpdateState({ paginationStartOffset: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Total records path</span>
                    <InfoTooltip text="Dotted path to the total number of records (optional)." />
                  </div>
                  <InputWithCursorPosition
                    className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="meta.total"
                    value={state.paginationTotalRecordsPath || ""}
                    onValueChange={(value) => onUpdateState({ paginationTotalRecordsPath: value })}
                  />
                </label>
              </div>
            )}

            {paginationType === "page" && (
              <div className="grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Page parameter</span>
                    <InfoTooltip text="Query parameter controlling page number." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="page"
                    value={state.paginationPageParam || ""}
                    onChange={(event) => onUpdateState({ paginationPageParam: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Start page</span>
                    <InfoTooltip text="Initial page number for the first request." />
                  </div>
                  <input
                    type="number"
                    min={1}
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="1"
                    value={state.paginationStartPage || ""}
                    onChange={(event) => onUpdateState({ paginationStartPage: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Total pages path</span>
                    <InfoTooltip text="Dotted path to the total number of pages (optional)." />
                  </div>
                  <InputWithCursorPosition
                    className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="meta.total_pages"
                    value={state.paginationTotalPagesPath || ""}
                    onValueChange={(value) => onUpdateState({ paginationTotalPagesPath: value })}
                  />
                </label>
              </div>
            )}

            {isCursor && (
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col gap-2">
                    <div className="flex items-center gap-1">
                      <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor parameter</span>
                      <InfoTooltip text="Query parameter carrying the cursor value sent to the API." />
                    </div>
                    <input
                      type="text"
                      className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                      placeholder="cursor"
                      value={state.paginationCursorParam || ""}
                      onChange={(event) => onUpdateState({ paginationCursorParam: event.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-2">
                    <div className="flex items-center gap-1">
                      <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor path</span>
                      <InfoTooltip text="Dotted path to the cursor in the response payload." />
                    </div>
                    <InputWithCursorPosition
                      className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5"
                      placeholder="meta.next_cursor"
                      value={state.paginationCursorPath || ""}
                      onValueChange={(value) => onUpdateState({ paginationCursorPath: value })}
                    />
                  </label>
                </div>
                <div className="grid gap-4 md:grid-cols-3">
                  <label className="flex flex-col gap-2">
                    <div className="flex items-center gap-1">
                      <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Next URL Path</span>
                      <InfoTooltip text="Dotted path to a fully qualified 'next' link in the payload (optional)." />
                    </div>
                    <InputWithCursorPosition
                      className="rounded-lg border border-border dark:border-drac-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:focus-visible:border-drac-accent focus-visible:ring-1 focus-visible:ring-blue-5"
                      placeholder="links.next"
                      value={state.paginationNextUrlPath || ""}
                      onValueChange={(value) => onUpdateState({ paginationNextUrlPath: value })}
                    />
                  </label>
                  <label className="flex flex-col gap-2">
                    <div className="flex items-center gap-1">
                      <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor Header</span>
                      <InfoTooltip text="Response header that carries the next cursor (optional)." />
                    </div>
                    <input
                      type="text"
                      className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                      placeholder="X-Next-Cursor"
                      value={state.paginationCursorHeader || ""}
                      onChange={(event) => onUpdateState({ paginationCursorHeader: event.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-2">
                    <div className="flex items-center gap-1">
                      <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Initial Cursor</span>
                      <InfoTooltip text="Fallback cursor value sent on the first request." />
                    </div>
                    <input
                      type="text"
                      className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                      placeholder="Provided by API"
                      value={state.paginationInitialCursor || ""}
                      onChange={(event) => onUpdateState({ paginationInitialCursor: event.target.value })}
                    />
                  </label>
                </div>
              </div>
            )}

            {isLinkHeader && (
              <div className="grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Link relation</span>
                    <InfoTooltip text="Value inside the rel attribute that identifies the next page." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="next"
                    value={state.paginationTotalPagesHeader || ""}
                    onChange={(event) => onUpdateState({ paginationTotalPagesHeader: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-slate-11 dark:text-drac-foreground/90">Cursor header</span>
                    <InfoTooltip text="Header inspected when parsing the link response (optional)." />
                  </div>
                  <input
                    type="text"
                    className="rounded-lg border border-border bg-background/70 dark:bg-[#272d38] px-4 py-2.5 text-sm text-slate-12 dark:text-drac-foreground shadow-sm focus-visible:border-blue-7 dark:border-drac-border transition-all focus-visible:ring-1 focus-visible:ring-blue-5"
                    placeholder="Link"
                    value={state.paginationTotalRecordsHeader || ""}
                    onChange={(event) => onUpdateState({ paginationTotalRecordsHeader: event.target.value })}
                  />
                </label>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border text-blue-7 focus:ring-blue-5"
              checked={state.paginationStopOnEmptyResponse}
              onChange={(event) => onUpdateState({ paginationStopOnEmptyResponse: event.target.checked })}
            />
            <span className="text-sm text-slate-11 dark:text-drac-foreground/90">Stop when the API returns no records</span>
          </div>
        </div>
      )}
    </div>
  );
};

