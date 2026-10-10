import { useI18n } from "../i18n";
import { useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeftIcon,
  ArrowTopRightIcon,
  FileTextIcon,
  InfoCircledIcon,
} from "@radix-ui/react-icons";
import { useApi, formatDate, formatMoney, safeHttpUrl } from "../lib/api";
import type {
  CompanyDetail as CompanyRecord,
  Contract,
  Directorship,
  Ownership,
  KgdSummary,
  Paginated,
} from "../lib/types";
import {
  CompanyRoles,
  EntityPagination,
  EntityState,
  validPage,
} from "./Companies";
import "./entities.css";
import { FactEvidence, RelatedGroups, sourceName } from "./EntityEvidence";

const missing = "Not recorded";

export function ExternalSource({
  url,
  children,
}: {
  url: string | null | undefined;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  const safe = safeHttpUrl(url);
  return safe ? (
    <a
      className="entity-inline-link"
      href={safe}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children ?? t("Open source")}
      <ArrowTopRightIcon aria-hidden="true" />
    </a>
  ) : null;
}

function KgdCheck({ check }: { check: KgdSummary }) {
  const { t } = useI18n();
  const arrears =
    check.source.includes("arrears") || check.source.includes("debt");
  const result = check.last_successful;
  const labels = {
    success: result?.stale ? t("Past result retained") : t("Successful check"),
    not_found: t("No record returned"),
    unavailable: t("Source unavailable"),
    invalid: t("Unusable result"),
    not_checked: t("Not checked"),
  };
  return (
    <div className="entity-kgd-check">
      <div className="entity-kgd-top">
        <h3>
          {arrears ? t("Company tax arrears") : t("Taxpayer registration")}
        </h3>
        <span
          className={`badge ${check.status === "success" && !result?.stale ? "entity-badge-success" : "entity-badge-amber"}`}
        >
          {labels[check.status]}
        </span>
      </div>
      <p className="entity-check-purpose">
        {arrears
          ? t("Amounts returned by the separate tax-debt service.")
          : t(
              "Taxpayer identity and registration details. This check does not establish the absence of debt.",
            )}
      </p>
      {result ? (
        <>
          {arrears && result.total_arrears !== undefined ? (
            <>
              <p className="entity-kgd-amount">
                {formatMoney(result.total_arrears, "").trim()}{" "}
                <small>KZT</small>
              </p>
              <span className="muted" style={{ fontSize: 11 }}>
                {t("Total in the last successful check")}
              </span>
            </>
          ) : (
            <p>
              {result.taxpayer_name || t("Saved registration result")}
              {result.taxpayer_type && (
                <span className="entity-subline">
                  {t("Entity type:")} {result.taxpayer_type}
                </span>
              )}
            </p>
          )}
          <div className="entity-kgd-meta">
            <span>
              {t("Retrieved")} {formatDate(result.observed_at)}
            </span>
            {result.reporting_dates?.length ? (
              <span>
                {t("Reporting dates:")}{" "}
                {result.reporting_dates
                  .map((date) => formatDate(date))
                  .join(", ")}
              </span>
            ) : (
              arrears && <span>{t("Source reporting date not available")}</span>
            )}
            {!arrears && (
              <span>
                {t("Registration:")}{" "}
                {result.registration_begin
                  ? formatDate(result.registration_begin)
                  : t("start unknown")}
                {result.registration_end
                  ? t(" to {date}", {
                      date: formatDate(result.registration_end),
                    })
                  : t(" · end not recorded")}
              </span>
            )}
          </div>
          {result.stale && (
            <p className="muted">
              {t(
                "This retained result does not establish the company’s current status.",
              )}
            </p>
          )}
          {check.status !== "success" && (
            <p className="muted">
              {t(
                "The latest attempt did not produce a usable result. The earlier successful check is retained above.",
              )}
            </p>
          )}
        </>
      ) : (
        <p className="muted">
          {check.status === "not_checked"
            ? t("No check is saved for this company.")
            : check.status === "not_found"
              ? t("The source did not return a matching taxpayer record.")
              : t("No identity-validated successful result is available.")}{" "}
          {arrears && t("Current arrears remain unknown.")}
        </p>
      )}
      {check.latest_observed_at && (
        <div className="entity-kgd-meta">
          {t("Latest attempt:")} {formatDate(check.latest_observed_at)}
        </div>
      )}
      <ExternalSource url={check.source_url}>{t("KGD source")}</ExternalSource>
    </div>
  );
}

export function RoleSection({
  kind,
  companyId,
  personId,
}: {
  kind: "directorships" | "ownerships";
  companyId?: string;
  personId?: string;
}) {
  const { t, locale } = useI18n();
  const [params, setParams] = useSearchParams();
  const owner = kind === "ownerships";
  const pageKey = owner ? "owners_page" : "directors_page";
  const page = validPage(params.get(pageKey));
  const filterKey = owner ? "owners_state" : "directors_state";
  const defaultRoleState = owner || personId ? "all" : "current";
  const roleState = ["all", "current", "historical"].includes(
    params.get(filterKey) || "",
  )
    ? params.get(filterKey)!
    : defaultRoleState;
  const query = new URLSearchParams({
    page: String(page),
    page_size: "10",
    ordering: "-id",
  });
  if (roleState === "current" || roleState === "historical")
    query.set("is_current", String(roleState === "current"));
  if (companyId) query.set("company_id", companyId);
  if (personId) query.set("person_id", personId);
  const { data, loading, error, reload } = useApi<
    Paginated<Directorship | Ownership>
  >(`${kind}/?${query}`);
  // Future ownership evidence remains readable, without advertising an empty integration.
  if (
    owner &&
    !error &&
    (loading || (data?.count === 0 && roleState === "all"))
  )
    return null;
  return (
    <section
      className="panel entity-directory entity-role-section"
      aria-label={owner ? t("Ownership records") : t("Directorship records")}
      id={kind}
    >
      <div className="entity-section-head">
        <div>
          <h2>
            {owner ? t("Ownership records") : t("Directorship records")}{" "}
            <span className="entity-count">
              {data?.count.toLocaleString(locale) ?? "—"}
            </span>
          </h2>
          <p className="muted">
            {t(
              "Recorded roles and their evidence. An observed current role may still have unknown legal dates.",
            )}
          </p>
        </div>
        <label className="entity-role-filter">
          {t("Show roles")}
          <select
            value={roleState}
            onChange={(event) => {
              const next = new URLSearchParams(params);
              next.set(filterKey, event.target.value);
              next.delete(pageKey);
              setParams(next);
            }}
          >
            <option value="current">{t("Current records")}</option>
            <option value="historical">{t("Earlier records")}</option>
            <option value="all">{t("Source history (all records)")}</option>
          </select>
        </label>
      </div>
      <EntityState
        loading={loading}
        error={error}
        empty={!!data && !data.results.length}
        onRetry={reload}
        emptyTitle={
          owner
            ? t("No ownership records saved")
            : t("No directorship records saved")
        }
        emptyText={t(
          "No records match this view. Missing ownership or directorship data does not establish the absence of a role.",
        )}
      />
      {!loading && !error && !!data?.results.length && (
        <>
          <div className="table-scroll">
            <table className="data-table entity-table entity-role-table">
              <thead>
                <tr>
                  <th scope="col">{personId ? t("Company") : t("Person")}</th>
                  <th scope="col">{t("Identity evidence")}</th>
                  {owner && <th scope="col">{t("Share")}</th>}
                  <th scope="col">{t("Legal period")}</th>
                  <th scope="col">{t("Source")}</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((role) => (
                  <tr key={role.id}>
                    <td data-label={personId ? t("Company") : t("Person")}>
                      {personId ? (
                        <Link
                          className="entity-inline-link entity-role-title"
                          to={`/companies/${role.company.id}`}
                        >
                          {role.company.name}
                        </Link>
                      ) : role.person ? (
                        <Link
                          className="entity-inline-link entity-role-title"
                          to={`/people/${role.person.id}`}
                        >
                          {role.person.full_name || role.observed_name}
                        </Link>
                      ) : (
                        <span className="entity-role-title">
                          {role.observed_name || t(missing)}
                        </span>
                      )}
                      <span className="entity-subline">
                        {personId
                          ? `${t("BIN")} ${role.company.bin}`
                          : role.is_current
                            ? t("Observed as current")
                            : t("Observed as inactive")}
                      </span>
                    </td>
                    <td data-label={t("Identity evidence")}>
                      <span
                        className={`badge ${role.identity_verified ? "entity-badge-cyan" : "entity-badge-amber"}`}
                      >
                        {role.identity_verified
                          ? t("Verified identity")
                          : t("Unverified identity")}
                      </span>
                      <span className="entity-subline">
                        {role.identity_verified
                          ? t("Supported by identifier evidence")
                          : t("Name alone does not verify identity")}
                      </span>
                    </td>
                    {owner && (
                      <td className="entity-mono" data-label={t("Share")}>
                        {"share_percent" in role && role.share_percent !== null
                          ? `${role.share_percent}%`
                          : t("Unknown")}
                      </td>
                    )}
                    <td
                      className="entity-period"
                      data-label={t("Legal period")}
                    >
                      {role.start_date || role.end_date ? (
                        <>
                          {role.start_date
                            ? formatDate(role.start_date)
                            : t("Start unknown")}
                          <br />→{" "}
                          {role.end_date
                            ? formatDate(role.end_date)
                            : t("End unknown")}
                        </>
                      ) : (
                        t("Dates not recorded")
                      )}
                      <span className="entity-subline">
                        {role.temporal_status === "in_period"
                          ? t("In recorded period")
                          : role.temporal_status === "not_in_period"
                            ? t("Outside recorded period")
                            : role.temporal_status === "observed_inactive"
                              ? t("Observed inactive")
                              : t("Current applicability unknown")}
                      </span>
                    </td>
                    <td data-label={t("Source")}>
                      {role.source_reference ? (
                        <>
                          <ExternalSource url={role.source_reference.url}>
                            {sourceName(role.source_reference.source)}
                          </ExternalSource>
                          {!safeHttpUrl(role.source_reference.url) && (
                            <span>
                              {sourceName(role.source_reference.source)}
                            </span>
                          )}
                          <span className="entity-subline">
                            {role.source_reference.source === "legacy"
                              ? t("Not rechecked · source date unknown")
                              : `${role.source_reference.status === "success" ? t("Retrieved") : t("Attempted")} ${formatDate(role.source_reference.observed_at)}`}
                          </span>
                        </>
                      ) : (
                        <>
                          <span>{role.source || t("Legacy record")}</span>
                          <span className="entity-subline">
                            {t("No linked source observation")}
                          </span>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <EntityPagination
            page={page}
            count={data.count}
            pageSize={10}
            onPage={(p) => {
              const next = new URLSearchParams(params);
              next.set(pageKey, String(p));
              setParams(next);
            }}
          />
          <div className="entity-inset-notice">
            {t(
              "Identity verification and legal role applicability are separate. Missing dates remain unknown.",
            )}
          </div>
        </>
      )}
    </section>
  );
}

export function ContractPreview({ companyId }: { companyId: string }) {
  const { t, locale } = useI18n();
  const [role, setRole] = useState("supplier");
  const { data, loading, error, reload } = useApi<Paginated<Contract>>(
    `contracts/?${role}_id=${encodeURIComponent(companyId)}&page_size=5`,
  );
  return (
    <section
      className="panel entity-directory entity-contract-preview"
      id="contracts"
    >
      <div className="entity-section-head">
        <div>
          <h2>
            {role === "supplier"
              ? t("Supplier contracts")
              : t("Customer contracts")}{" "}
            <span className="entity-count">
              {data?.count.toLocaleString(locale) ?? "—"}
            </span>
          </h2>
          <p className="muted">
            {t(
              "Latest saved contracts by signing date. The catalogue may be incomplete.",
            )}
          </p>
        </div>
        <label className="entity-role-filter">
          {t("Company acts as")}
          <select
            value={role}
            onChange={(event) => setRole(event.target.value)}
          >
            <option value="supplier">{t("Supplier")}</option>
            <option value="customer">{t("Customer")}</option>
          </select>
        </label>
        <Link
          className="entity-inline-link"
          to={`/contracts?${role}_id=${companyId}`}
        >
          {t("View all")} <ArrowTopRightIcon />
        </Link>
      </div>
      <EntityState
        loading={loading}
        error={error}
        empty={!!data && !data.results.length}
        onRetry={reload}
        emptyTitle={
          role === "supplier"
            ? t("No supplier contracts saved")
            : t("No customer contracts saved")
        }
        emptyText={t(
          "Try the other company role. Missing contracts do not establish that the company has never participated.",
        )}
      />
      {!loading && !error && !!data?.results.length && (
        <div className="table-scroll">
          <table className="data-table entity-table entity-contract-table">
            <thead>
              <tr>
                <th scope="col">{t("Contract")}</th>
                <th scope="col">
                  {role === "supplier" ? t("Customer") : t("Supplier")}
                </th>
                <th scope="col">{t("Date")}</th>
                <th scope="col">{t("Amount, KZT")}</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((contract) => (
                <tr key={contract.id}>
                  <td
                    className="entity-contract-title"
                    data-label={t("Contract")}
                  >
                    <strong>{contract.title || t("Untitled contract")}</strong>
                    <span className="entity-subline entity-mono">
                      {contract.contract_number || t("Number not recorded")}
                    </span>
                    <ExternalSource url={contract.source_url}>
                      {t("Procurement source")}
                    </ExternalSource>
                    <span className="entity-subline">
                      {contract.source_observed_at
                        ? t("Retrieved {date}", {
                            date: formatDate(contract.source_observed_at),
                          })
                        : t("Source retrieval date not verified")}
                    </span>
                  </td>
                  <td
                    data-label={
                      role === "supplier" ? t("Customer") : t("Supplier")
                    }
                  >
                    {role === "customer" ? (
                      <Link
                        className="entity-inline-link"
                        to={`/companies/${contract.supplier.id}`}
                      >
                        {contract.supplier.name}
                      </Link>
                    ) : contract.customer ? (
                      <Link
                        className="entity-inline-link"
                        to={`/companies/${contract.customer.id}`}
                      >
                        {contract.customer.name}
                      </Link>
                    ) : (
                      contract.customer_name || t("Not recorded")
                    )}
                  </td>
                  <td data-label={t("Signing date")}>
                    {formatDate(contract.contract_date)}
                  </td>
                  <td className="entity-money" data-label={t("Amount, KZT")}>
                    {formatMoney(contract.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function CompanyDetail() {
  const { t } = useI18n();
  const { id = "" } = useParams();
  const validId = /^[1-9]\d*$/.test(id);
  const {
    data: company,
    loading,
    error,
    reload,
  } = useApi<CompanyRecord>(validId ? `companies/${id}/` : null);
  if (!validId || loading || error || !company)
    return (
      <div className="entity-page">
        <Link className="breadcrumb" to="/companies">
          <ArrowLeftIcon /> {t("Companies")}
        </Link>
        <section className="panel">
          <EntityState
            loading={loading}
            error={
              error || (!validId ? t("This company link is invalid.") : null)
            }
            empty={!loading && !error && !company}
            onRetry={reload}
            emptyTitle={t("Company not available")}
            emptyText={t("This saved company record could not be found.")}
          />
        </section>
      </div>
    );
  return (
    <div className="entity-page">
      <Link className="breadcrumb" to="/companies">
        <ArrowLeftIcon /> {t("Companies")}
      </Link>
      <header className="page-head entity-detail-head">
        <div>
          <span className="eyebrow">{t("COMPANY PROFILE")}</span>
          <h1>{company.name || t("Unnamed company")}</h1>
          <div className="entity-identity-row">
            <span className="entity-mono">
              {t("BIN")} {company.bin || t(missing)}
            </span>
            <CompanyRoles company={company} />
          </div>
          <FactEvidence
            evidence={company.field_evidence?.find(
              (item) => item.field === "name",
            )}
          />
          <div className="entity-actions">
            <Link
              className="button button-primary"
              to={`/contracts?supplier_id=${id}`}
            >
              <FileTextIcon /> {t("Supplier contracts")}
            </Link>
            {company.is_customer && (
              <Link className="button" to={`/contracts?customer_id=${id}`}>
                {t("Customer contracts")}
              </Link>
            )}
            {company.website && (
              <ExternalSource url={company.website}>
                {t("Company website")}
              </ExternalSource>
            )}
          </div>
        </div>
      </header>
      <nav className="entity-section-nav" aria-label={t("Company sections")}>
        <a href="#company-facts">{t("Company facts")}</a>
        <a href="#tax-checks">{t("KGD checks")}</a>
        <a href="#related-groups">{t("Related groups")}</a>
        <a href="#directorships">{t("People & roles")}</a>
        <a href="#contracts">{t("Contracts")}</a>
      </nav>
      <div className="entity-detail-grid">
        <section className="panel entity-detail-panel" id="company-facts">
          <span className="eyebrow">{t("PROFILE EVIDENCE")}</span>
          <h2>{t("Company facts")}</h2>
          <p className="entity-section-intro">
            {t(
              "Saved values with their sources and retrieval dates. Fields without a saved value are omitted; missing information has not been verified.",
            )}
          </p>
          <dl className="entity-fact-grid">
            {[
              [
                "registration_date",
                t("Registration date"),
                company.registration_date
                  ? formatDate(company.registration_date)
                  : missing,
              ],
              [
                "company_status",
                t("Company status"),
                company.company_status || missing,
              ],
              ["region", t("Region"), company.region || missing],
              ["city", t("City"), company.city || missing],
              ["address", t("Address"), company.address || missing],
              ["oked", t("OKED"), company.oked || missing],
              ["phone", t("Phone"), company.phone || missing],
              ["email", t("Email"), company.email || missing],
              [
                "company_size",
                t("Company size"),
                company.company_size || missing,
              ],
              [
                "economic_sector",
                t("Economic sector"),
                company.economic_sector || missing,
              ],
            ]
              .filter(([, , value]) => value !== missing)
              .map(([field, label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>
                    {value}
                    <FactEvidence
                      evidence={company.field_evidence?.find(
                        (item) => item.field === field,
                      )}
                      hasValue={value !== missing}
                    />
                  </dd>
                </div>
              ))}
          </dl>
          {![
            company.registration_date,
            company.company_status,
            company.region,
            company.city,
            company.address,
            company.oked,
            company.phone,
            company.email,
            company.company_size,
            company.economic_sector,
          ].some(Boolean) && (
            <p className="muted">
              {t(
                "Only basic identification is saved. No profile details are available yet.",
              )}
            </p>
          )}
          {company.description && (
            <div className="entity-description">
              <p>{company.description}</p>
              <FactEvidence
                evidence={company.field_evidence?.find(
                  (item) => item.field === "description",
                )}
              />
            </div>
          )}
          <details style={{ marginTop: 24 }}>
            <summary
              className="muted"
              style={{ fontSize: 12, cursor: "pointer" }}
            >
              {t("Record metadata")}
            </summary>
            <div className="entity-kgd-meta">
              <span>
                {t("Saved")} {formatDate(company.created_at)} {t("· Updated")}{" "}
                {formatDate(company.updated_at)}
              </span>
              <span>
                {t("Database timestamps are not source verification dates.")}
              </span>
              {company.adata_updated_at && (
                <span>
                  {t("Adata update:")} {formatDate(company.adata_updated_at)}
                </span>
              )}
            </div>
          </details>
        </section>
        <section className="panel entity-detail-panel" id="tax-checks">
          <span className="eyebrow">{t("TWO SEPARATE CHECKS")}</span>
          <h2>{t("Saved KGD checks")}</h2>
          {company.kgd_checks.length ? (
            company.kgd_checks.map((check) => (
              <KgdCheck key={check.source} check={check} />
            ))
          ) : (
            <p className="muted">
              {t(
                "No KGD check is saved. Current tax arrears and registration status remain unknown.",
              )}
            </p>
          )}
        </section>
      </div>
      <RelatedGroups key={`company-${id}`} companyId={id} />
      <div className="entity-history-note">
        <InfoCircledIcon />
        <span>
          {t(
            "This profile reads saved records. A company’s arrears belong to the company and are not assigned to its directors or owners.",
          )}
        </span>
      </div>
      <RoleSection kind="directorships" companyId={id} />
      <RoleSection kind="ownerships" companyId={id} />
      <details className="entity-coverage-note">
        <summary>{t("What the current sources cover")}</summary>
        <p>
          {t(
            "Goszakup and Adata provide company profiles and recorded directors. The current collectors do not establish ownership or ownership shares. An ownership section appears only when saved ownership records exist.",
          )}
        </p>
        <p>
          {t(
            "KGD registration and company arrears are separate checks. Debt coverage depends on access for the company being checked; registration alone does not establish that it has no debt.",
          )}
        </p>
      </details>
      <ContractPreview key={id} companyId={id} />
    </div>
  );
}
