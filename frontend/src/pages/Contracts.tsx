import { useI18n } from "../i18n";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Cross2Icon,
  FileTextIcon,
  MagnifyingGlassIcon,
} from "@radix-ui/react-icons";
import { useApi, formatDate, formatMoney } from "../lib/api";
import type { Company, Contract, Paginated } from "../lib/types";
import CountUp from "../components/motion/CountUp";
import SectionEmblem from "../components/motion/SectionEmblem";
import { TechHeading } from "../components/motion/TechHeading";
import { EntityPagination, EntityState, validPage } from "./Companies";
import { ExternalSource } from "./CompanyDetail";
import { useDecorationActive } from "../components/motion/useDecorationActive";
import "./entities.css";
import "./directory.css";

function positiveId(value: string | null): string {
  return value && /^[1-9]\d*$/.test(value) ? value : "";
}
function dateValue(value: string | null): string {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";
}

export function Contracts() {
  const { t } = useI18n();
  const decoration = useDecorationActive<HTMLDivElement>();
  const [params, setParams] = useSearchParams();
  const page = validPage(params.get("page"));
  const search = (params.get("search") || "").slice(0, 100);
  const supplierId = positiveId(params.get("supplier_id"));
  const customerId = positiveId(params.get("customer_id"));
  const from = dateValue(params.get("date_from"));
  const to = dateValue(params.get("date_to"));
  const winner = ["true", "false"].includes(params.get("winner") || "")
    ? params.get("winner")!
    : "";
  const ordering = [
    "-contract_date",
    "contract_date",
    "-amount",
    "amount",
    "contract_number",
    "-contract_number",
  ].includes(params.get("ordering") || "")
    ? params.get("ordering")!
    : "-contract_date";
  const [draft, setDraft] = useState(search);
  const [dates, setDates] = useState({ from, to });
  useEffect(() => setDraft(search), [search]);
  useEffect(() => setDates({ from, to }), [from, to]);
  const query = new URLSearchParams({
    page: String(page),
    page_size: "25",
    ordering,
  });
  if (search) query.set("search", search);
  if (supplierId) query.set("supplier_id", supplierId);
  if (customerId) query.set("customer_id", customerId);
  if (from) query.set("date_from", from);
  if (to) query.set("date_to", to);
  if (winner) query.set("winner", winner);
  const { data, loading, error, reload } = useApi<Paginated<Contract>>(
    `contracts/?${query}`,
  );
  const supplier = useApi<Company>(
    supplierId ? `companies/${supplierId}/` : null,
  ).data;
  const customer = useApi<Company>(
    customerId ? `companies/${customerId}/` : null,
  ).data;
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    next.delete("page");
    setParams(next);
  }
  function updateDates() {
    const next = new URLSearchParams(params);
    dates.from ? next.set("date_from", dates.from) : next.delete("date_from");
    dates.to ? next.set("date_to", dates.to) : next.delete("date_to");
    next.delete("page");
    setParams(next);
  }
  const filtered = !!(
    search ||
    supplierId ||
    customerId ||
    from ||
    to ||
    winner ||
    page > 1
  );
  return (
    <div
      ref={decoration.ref}
      className="entity-page directory-page contracts-directory-page"
      data-decorative-active={decoration.active}
    >
      <header className="page-head entity-page-head">
        <div>
          <span className="eyebrow">{t("PROCUREMENT RECORDS")}</span>
          <TechHeading as="h1" text={t("Every contract leaves a trail.")} />
          <p className="muted">
            {t(
              "Explore saved procurement records, their counterparties, amounts, and sources.",
            )}
          </p>
        </div>
        <SectionEmblem kind="contracts" />
      </header>
      <section className="panel entity-directory">
        <div className="entity-section-head">
          <div>
            <h2>
              {t("Contracts")}{" "}
              <CountUp className="entity-count" value={data?.count} />
            </h2>
            <p className="muted">
              {t(
                "Exact saved amounts in Kazakhstani tenge. Source coverage may be incomplete.",
              )}
            </p>
          </div>
          <span className="entity-data-label">
            <i /> {t("SAVED CONTRACTS")}
          </span>
        </div>
        {(supplierId || customerId) && (
          <div className="entity-filter-note">
            <FileTextIcon />
            <span>
              {supplierId && (
                <>
                  {t("Supplier:")}{" "}
                  <Link
                    className="entity-inline-link"
                    to={`/companies/${supplierId}`}
                  >
                    {supplier?.name || t("Company #{id}", { id: supplierId })}
                  </Link>
                </>
              )}
              {supplierId && customerId && " · "}
              {customerId && (
                <>
                  {t("Customer:")}{" "}
                  <Link
                    className="entity-inline-link"
                    to={`/companies/${customerId}`}
                  >
                    {customer?.name || t("Company #{id}", { id: customerId })}
                  </Link>
                </>
              )}
            </span>
            <button
              className="button"
              style={{ marginLeft: "auto" }}
              onClick={() => {
                const next = new URLSearchParams(params);
                next.delete("supplier_id");
                next.delete("customer_id");
                next.delete("page");
                setParams(next);
              }}
              aria-label={t("Clear company filters")}
            >
              <Cross2Icon />
            </button>
          </div>
        )}
        <div className="toolbar entity-toolbar">
          <form
            className="entity-search"
            onSubmit={(e) => {
              e.preventDefault();
              update("search", draft.trim());
            }}
          >
            <label className="sr-only" htmlFor="contract-search">
              {t("Search contracts by title, contract number or tender ID")}
            </label>
            <MagnifyingGlassIcon aria-hidden="true" />
            <input
              id="contract-search"
              value={draft}
              maxLength={100}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={t("Title, contract number or tender ID")}
            />
            <button className="button entity-search-button" type="submit">
              {t("Search")}
            </button>
          </form>
          <label className="entity-select-label">
            <span className="directory-control-label">
              {t("Contract ordering")}
            </span>
            <select
              className="field"
              value={ordering}
              onChange={(e) => update("ordering", e.target.value)}
            >
              <option value="-contract_date">{t("Newest first")}</option>
              <option value="contract_date">{t("Oldest first")}</option>
              <option value="-amount">{t("Highest amount")}</option>
              <option value="amount">{t("Lowest amount")}</option>
              <option value="contract_number">
                {t("Contract number A–Z")}
              </option>
            </select>
          </label>
          <label className="entity-select-label">
            <span className="directory-control-label">{t("Winner flag")}</span>
            <select
              className="field"
              value={winner}
              onChange={(e) => update("winner", e.target.value)}
            >
              <option value="">{t("All winner flags")}</option>
              <option value="true">{t("Flagged as winner")}</option>
              <option value="false">{t("Not flagged as winner")}</option>
            </select>
          </label>
          {filtered && (
            <button
              className="button entity-clear"
              onClick={() => setParams({})}
            >
              <Cross2Icon /> {t("Clear")}
            </button>
          )}
        </div>
        <form
          className="entity-contract-filters"
          onSubmit={(e) => {
            e.preventDefault();
            updateDates();
          }}
        >
          <label htmlFor="contract-date-from">
            {t("Contract date from")}
            <input
              id="contract-date-from"
              className="field"
              type="date"
              value={dates.from}
              max={dates.to || undefined}
              onChange={(e) => setDates({ ...dates, from: e.target.value })}
            />
          </label>
          <label htmlFor="contract-date-to">
            {t("Contract date to")}
            <input
              id="contract-date-to"
              className="field"
              type="date"
              value={dates.to}
              min={dates.from || undefined}
              onChange={(e) => setDates({ ...dates, to: e.target.value })}
            />
          </label>
          <button className="button" type="submit">
            {t("Apply dates")}
          </button>
        </form>
        <EntityState
          loading={loading}
          error={error}
          empty={!!data && !data.results.length}
          onRetry={reload}
          emptyTitle={t("No contracts match these filters")}
          emptyText={t(
            "Try a broader date range or clear the filters. This search only covers saved records.",
          )}
        />
        {!loading && !error && !!data?.results.length && (
          <>
            <div
              className="table-scroll directory-results"
              tabIndex={0}
              role="region"
              aria-label={t("Contracts results")}
            >
              <table
                className="data-table entity-table entity-contract-table"
                role="table"
              >
                <thead role="rowgroup">
                  <tr role="row">
                    <th scope="col" role="columnheader">
                      {t("Contract / source")}
                    </th>
                    <th scope="col" role="columnheader">
                      {t("Supplier / customer")}
                    </th>
                    <th scope="col" role="columnheader">
                      {t("Date")}
                    </th>
                    <th scope="col" role="columnheader">
                      {t("Amount, KZT")}
                    </th>
                  </tr>
                </thead>
                <tbody role="rowgroup">
                  {data.results.map((contract) => (
                    <tr role="row" key={contract.id}>
                      <td
                        role="cell"
                        data-label={t("Contract / source")}
                        className="entity-contract-title"
                      >
                        <div className="directory-contract-identity">
                          <span
                            className="entity-company-symbol"
                            aria-hidden="true"
                          >
                            <FileTextIcon />
                          </span>
                          <div className="directory-identity">
                            <strong>
                              {contract.title || t("Untitled contract")}
                            </strong>
                            <span className="entity-subline entity-mono">
                              № {contract.contract_number || t("not recorded")}
                            </span>
                          </div>
                        </div>
                        <details>
                          <summary>{t("Record details")}</summary>
                          <p>
                            {t("Tender ID:")}{" "}
                            <span className="entity-mono">
                              {contract.tender_id || t("not recorded")}
                            </span>
                            <br />
                            {t("Winner flag:")}{" "}
                            {contract.winner ? t("Yes") : t("No")}
                            <br />
                            {contract.source_observation_id
                              ? t("Saved observation #{id}", {
                                  id: contract.source_observation_id,
                                })
                              : t("No linked source observation")}
                          </p>
                          <ExternalSource url={contract.source_url}>
                            {t("Procurement source")}
                          </ExternalSource>
                        </details>
                      </td>
                      <td role="cell" data-label={t("Supplier / customer")}>
                        <span className="directory-party-label">
                          {t("Supplier")}
                        </span>
                        <Link
                          className="entity-inline-link"
                          to={`/companies/${contract.supplier.id}`}
                        >
                          {contract.supplier.name || t("Unnamed supplier")}
                        </Link>
                        <span className="entity-subline">{t("Customer")}</span>
                        {contract.customer ? (
                          <Link
                            className="entity-inline-link"
                            to={`/companies/${contract.customer.id}`}
                          >
                            {contract.customer.name}
                          </Link>
                        ) : (
                          <span>
                            {contract.customer_name || t("Not recorded")}
                          </span>
                        )}
                      </td>
                      <td
                        role="cell"
                        data-label={t("Date")}
                        className="directory-date"
                      >
                        {formatDate(contract.contract_date)}
                      </td>
                      <td
                        role="cell"
                        data-label={t("Amount, KZT")}
                        className="entity-money"
                      >
                        {formatMoney(contract.amount, "").trim()}
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
          "Contract value is a recorded procurement amount. It does not establish damage, independent bidding, or coordinated conduct.",
        )}
      </p>
    </div>
  );
}
