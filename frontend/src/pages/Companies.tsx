import { useI18n } from "../i18n";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRightIcon,
  MagnifyingGlassIcon,
  ReloadIcon,
  Cross2Icon,
  CubeIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@radix-ui/react-icons";
import { useApi } from "../lib/api";
import type { Company, Paginated } from "../lib/types";
import CountUp from "../components/motion/CountUp";
import SectionEmblem from "../components/motion/SectionEmblem";
import { TechHeading } from "../components/motion/TechHeading";
import { useDecorationActive } from "../components/motion/useDecorationActive";
import "./entities.css";
import "./directory.css";

export function validPage(value: string | null): number {
  return value && /^[1-9]\d*$/.test(value)
    ? Math.min(Number(value), 1_000_000)
    : 1;
}

export function EntityState({
  loading,
  error,
  empty,
  onRetry,
  emptyTitle = "No records found",
  emptyText = "Try a different search or clear the filters.",
}: {
  loading: boolean;
  error: Error | string | null;
  empty: boolean;
  onRetry: () => void;
  emptyTitle?: string;
  emptyText?: string;
}) {
  const { t } = useI18n();
  if (loading)
    return (
      <div
        className="entity-loading"
        role="status"
        aria-label={t("Loading records")}
      >
        <div className="entity-loading-label">
          <ReloadIcon className="loading-spin" /> {t("Loading saved records")}
        </div>
        {[0, 1, 2, 3].map((i) => (
          <div className="entity-skeleton-row" key={i}>
            <span className="skeleton" />
            <span className="skeleton" />
            <span className="skeleton" />
          </div>
        ))}
      </div>
    );
  if (error)
    return (
      <div className="empty-state entity-state" role="alert">
        <span className="entity-state-icon">
          <Cross2Icon />
        </span>
        <h3>{t("We could not load these records")}</h3>
        <p className="muted">
          {t(typeof error === "string" ? error : error.message)}
        </p>
        <button className="button" onClick={onRetry}>
          <ReloadIcon /> {t("Try again")}
        </button>
      </div>
    );
  if (empty)
    return (
      <div className="empty-state entity-state">
        <span className="entity-state-icon">
          <MagnifyingGlassIcon />
        </span>
        <h3>{t(emptyTitle)}</h3>
        <p className="muted">{t(emptyText)}</p>
      </div>
    );
  return null;
}

export function EntityPagination({
  page,
  count,
  pageSize,
  onPage,
}: {
  page: number;
  count: number;
  pageSize: number;
  onPage: (page: number) => void;
}) {
  const { t, locale } = useI18n();
  const pages = Math.max(1, Math.ceil(count / pageSize));
  const start = count ? (page - 1) * pageSize + 1 : 0;
  const end = Math.min(page * pageSize, count);
  return (
    <nav className="entity-pagination" aria-label={t("Results pagination")}>
      <span className="muted">
        {t("{start}–{end} of {count} records", {
          start: start.toLocaleString(locale),
          end: end.toLocaleString(locale),
          count: count.toLocaleString(locale),
        })}
      </span>
      <div>
        <button
          className="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeftIcon aria-hidden="true" /> {t("Previous")}
        </button>
        <span className="directory-page-indicator" aria-live="polite">
          <span className="sr-only">{t("Page")} </span>
          <strong>{page}</strong> <span className="muted">/ {pages}</span>
        </span>
        <button
          className="button"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          {t("Next")} <ChevronRightIcon aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}

export function CompanyRoles({ company }: { company: Company }) {
  const { t } = useI18n();
  return (
    <div className="entity-badges">
      {company.is_supplier && (
        <span className="badge entity-badge-blue">{t("Supplier")}</span>
      )}
      {company.is_customer && (
        <span className="badge entity-badge-cyan">{t("Customer")}</span>
      )}
      {!company.is_supplier && !company.is_customer && (
        <span className="badge">{t("Unspecified role")}</span>
      )}
    </div>
  );
}

export function Companies() {
  const { t } = useI18n();
  const decoration = useDecorationActive<HTMLDivElement>();
  const [params, setParams] = useSearchParams();
  const search = (params.get("search") || "").slice(0, 100);
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const page = validPage(params.get("page"));
  const profiles = ["all", "pending"].includes(params.get("profiles") || "")
    ? params.get("profiles")!
    : "checked";
  const role = ["supplier", "customer"].includes(params.get("role") || "")
    ? params.get("role")!
    : "";
  const ordering = ["name", "-name", "bin", "-bin"].includes(
    params.get("ordering") || "",
  )
    ? params.get("ordering")!
    : "name";
  const query = new URLSearchParams({
    page: String(page),
    page_size: "25",
    ordering,
  });
  if (search) query.set("search", search);
  if (role) query.set(`is_${role}`, "true");
  if (profiles !== "all") query.set("profile_status", profiles);
  const { data, loading, error, reload } = useApi<Paginated<Company>>(
    `companies/?${query}`,
  );
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    next.delete("page");
    setParams(next);
  }
  return (
    <div
      ref={decoration.ref}
      className="entity-page directory-page companies-directory-page"
      data-decorative-active={decoration.active}
    >
      <header className="page-head entity-page-head">
        <div>
          <span className="eyebrow">{t("COMPANY DIRECTORY")}</span>
          <TechHeading as="h1" text={t("Know who is behind the contract.")} />
          <p className="muted">
            {t(
              "Search saved company records, inspect their roles, and follow the evidence.",
            )}
          </p>
        </div>
        <SectionEmblem kind="companies" />
      </header>
      <section
        className="panel entity-directory"
        aria-label={t("Company directory")}
      >
        <div className="entity-section-head">
          <div>
            <h2>
              {t("Companies")}{" "}
              <CountUp className="entity-count" value={data?.count} />
            </h2>
            <p className="muted">
              {t(
                "Source-checked profiles appear here after collection. A checked profile does not mean every field or tax check is complete.",
              )}
            </p>
          </div>
          <span className="entity-data-label">
            <i /> {t("SAVED RECORDS")}
          </span>
        </div>
        <div className="toolbar entity-toolbar">
          <form
            className="entity-search"
            onSubmit={(e) => {
              e.preventDefault();
              update("search", draft.trim());
            }}
          >
            <label className="sr-only" htmlFor="company-search">
              {t("Search companies by name or BIN")}
            </label>
            <MagnifyingGlassIcon aria-hidden="true" />
            <input
              id="company-search"
              value={draft}
              maxLength={100}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={t("Company name or BIN")}
            />
            <button className="button entity-search-button" type="submit">
              {t("Search")}
            </button>
          </form>
          <label className="entity-select-label">
            <span className="directory-control-label">
              {t("Profile evidence")}
            </span>
            <select
              className="field"
              value={profiles}
              onChange={(e) =>
                update(
                  "profiles",
                  e.target.value === "checked" ? "" : e.target.value,
                )
              }
            >
              <option value="checked">{t("Source-checked profiles")}</option>
              <option value="pending">{t("Awaiting profile evidence")}</option>
              <option value="all">{t("All collected records")}</option>
            </select>
          </label>
          <label className="entity-select-label">
            <span className="directory-control-label">{t("Company role")}</span>
            <select
              className="field"
              value={role}
              onChange={(e) => update("role", e.target.value)}
            >
              <option value="">{t("All roles")}</option>
              <option value="supplier">{t("Suppliers")}</option>
              <option value="customer">{t("Customers")}</option>
            </select>
          </label>
          <label className="entity-select-label">
            <span className="directory-control-label">
              {t("Company ordering")}
            </span>
            <select
              className="field"
              value={ordering}
              onChange={(e) => update("ordering", e.target.value)}
            >
              <option value="name">{t("Name A–Z")}</option>
              <option value="-name">{t("Name Z–A")}</option>
              <option value="bin">{t("BIN ascending")}</option>
              <option value="-bin">{t("BIN descending")}</option>
            </select>
          </label>
          {(search || role || profiles !== "checked" || page > 1) && (
            <button
              className="button entity-clear"
              onClick={() => setParams({})}
            >
              <Cross2Icon /> {t("Clear")}
            </button>
          )}
        </div>
        <EntityState
          loading={loading}
          error={error}
          empty={!!data && data.results.length === 0}
          onRetry={reload}
        />
        {!loading && !error && !!data?.results.length && (
          <>
            <div
              className="table-scroll directory-results"
              tabIndex={0}
              role="region"
              aria-label={t("Companies results")}
            >
              <table className="data-table entity-table" role="table">
                <thead role="rowgroup">
                  <tr role="row">
                    <th scope="col" role="columnheader">
                      {t("Company")}
                    </th>
                    <th scope="col" role="columnheader">
                      {t("Business role")}
                    </th>
                    <th scope="col" role="columnheader">
                      {t("Location")}
                    </th>
                    <th scope="col" role="columnheader">
                      <span className="sr-only">{t("Open company")}</span>
                    </th>
                  </tr>
                </thead>
                <tbody role="rowgroup">
                  {data.results.map((company) => (
                    <tr role="row" key={company.id}>
                      <td role="cell" data-label={t("Company")}>
                        <Link
                          className="entity-name-link"
                          to={`/companies/${company.id}`}
                        >
                          <span
                            className="entity-company-symbol"
                            aria-hidden="true"
                          >
                            <CubeIcon />
                          </span>
                          <span className="directory-identity">
                            <strong>
                              {company.name || t("Unnamed company")}
                            </strong>
                            <span className="entity-subline entity-mono">
                              {t("BIN")} {company.bin || t("not recorded")}
                            </span>
                          </span>
                        </Link>
                      </td>
                      <td role="cell" data-label={t("Business role")}>
                        <CompanyRoles company={company} />
                      </td>
                      <td role="cell" data-label={t("Location")}>
                        <span>
                          {company.city || company.region || t("Not recorded")}
                        </span>
                        {company.city && company.region && (
                          <span className="entity-subline">
                            {company.region}
                          </span>
                        )}
                      </td>
                      <td role="cell" className="directory-action-cell">
                        <Link
                          className="entity-row-open"
                          to={`/companies/${company.id}`}
                          aria-label={t("Open {name}", { name: company.name })}
                        >
                          <span className="directory-open-label">
                            {t("Open company")}
                          </span>
                          <ArrowRightIcon aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <EntityPagination
              page={page}
              count={data.count}
              pageSize={25}
              onPage={(p) => {
                const next = new URLSearchParams(params);
                next.set("page", String(p));
                setParams(next);
              }}
            />
          </>
        )}
      </section>
      <p className="entity-footnote muted">
        {t(
          "Directory entries reflect saved source data. Company names and contact details alone do not establish a relationship.",
        )}
      </p>
    </div>
  );
}
