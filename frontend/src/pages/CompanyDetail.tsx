import type { ReactNode } from "react";
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

const missing = "Not recorded";

export function ExternalSource({
  url,
  children = "Open source",
}: {
  url: string | null | undefined;
  children?: ReactNode;
}) {
  const safe = safeHttpUrl(url);
  return safe ? (
    <a
      className="entity-inline-link"
      href={safe}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
      <ArrowTopRightIcon aria-hidden="true" />
    </a>
  ) : null;
}

function KgdCheck({ check }: { check: KgdSummary }) {
  const arrears =
    check.source.includes("arrears") || check.source.includes("debt");
  const result = check.last_successful;
  const labels = {
    success: result?.stale ? "Dated result" : "Saved success",
    not_found: "No record returned",
    unavailable: "Source unavailable",
    invalid: "Unusable result",
    not_checked: "Not checked",
  };
  return (
    <div className="entity-kgd-check">
      <div className="entity-kgd-top">
        <h3>{arrears ? "Company tax arrears" : "Taxpayer registration"}</h3>
        <span
          className={`badge ${check.status === "success" && !result?.stale ? "entity-badge-success" : "entity-badge-amber"}`}
        >
          {labels[check.status]}
        </span>
      </div>
      {result ? (
        <>
          {arrears && result.total_arrears !== undefined ? (
            <>
              <p className="entity-kgd-amount">
                {formatMoney(result.total_arrears, "").trim()}{" "}
                <small>KZT</small>
              </p>
              <span className="muted" style={{ fontSize: 11 }}>
                Total in the last successful check
              </span>
            </>
          ) : (
            <p>
              {result.taxpayer_name || "Saved registration result"}
              {result.taxpayer_type && (
                <span className="entity-subline">
                  Entity type: {result.taxpayer_type}
                </span>
              )}
            </p>
          )}
          <div className="entity-kgd-meta">
            <span>Retrieved {formatDate(result.observed_at)}</span>
            {result.reporting_dates?.length ? (
              <span>
                Reporting dates:{" "}
                {result.reporting_dates
                  .map((date) => formatDate(date))
                  .join(", ")}
              </span>
            ) : (
              arrears && <span>Source reporting date not available</span>
            )}
            {!arrears && (
              <span>
                Registration:{" "}
                {result.registration_begin
                  ? formatDate(result.registration_begin)
                  : "start unknown"}
                {result.registration_end
                  ? ` to ${formatDate(result.registration_end)}`
                  : " · end not recorded"}
              </span>
            )}
          </div>
          {result.stale && (
            <p className="muted">
              This retained result does not establish the company’s current
              status.
            </p>
          )}
          {check.status !== "success" && (
            <p className="muted">
              The latest attempt did not produce a usable result. The earlier
              successful check is retained above.
            </p>
          )}
        </>
      ) : (
        <p className="muted">
          {check.status === "not_checked"
            ? "No check is saved for this company."
            : check.status === "not_found"
              ? "The source did not return a matching taxpayer record."
              : "No identity-validated successful result is available."}{" "}
          {arrears && "Current arrears remain unknown."}
        </p>
      )}
      {check.latest_observed_at && (
        <div className="entity-kgd-meta">
          Latest attempt: {formatDate(check.latest_observed_at)}
        </div>
      )}
      <ExternalSource url={check.source_url}>KGD source</ExternalSource>
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
  const [params, setParams] = useSearchParams();
  const owner = kind === "ownerships";
  const pageKey = owner ? "owners_page" : "directors_page";
  const page = validPage(params.get(pageKey));
  const query = new URLSearchParams({ page: String(page), page_size: "10" });
  if (companyId) query.set("company_id", companyId);
  if (personId) query.set("person_id", personId);
  const { data, loading, error, reload } = useApi<
    Paginated<Directorship | Ownership>
  >(`${kind}/?${query}`);
  return (
    <section
      className="panel entity-directory entity-role-section"
      aria-label={owner ? "Ownership records" : "Directorship records"}
    >
      <div className="entity-section-head">
        <div>
          <h2>
            {owner ? "Ownership records" : "Directorship records"}{" "}
            <span className="entity-count">
              {data?.count.toLocaleString("en-US") ?? "—"}
            </span>
          </h2>
          <p className="muted">
            Saved identities, observed roles, and recorded legal periods.
          </p>
        </div>
      </div>
      <EntityState
        loading={loading}
        error={error}
        empty={!!data && !data.results.length}
        onRetry={reload}
        emptyTitle={
          owner ? "No ownership records saved" : "No directorship records saved"
        }
        emptyText="This is a gap in saved data, not confirmation that no role exists."
      />
      {!loading && !error && !!data?.results.length && (
        <>
          <div className="table-scroll">
            <table className="data-table entity-table entity-role-table">
              <thead>
                <tr>
                  <th scope="col">{personId ? "Company" : "Person"}</th>
                  <th scope="col">Identity evidence</th>
                  {owner && <th scope="col">Share</th>}
                  <th scope="col">Legal period</th>
                  <th scope="col">Source</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((role) => (
                  <tr key={role.id}>
                    <td>
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
                          {role.observed_name || missing}
                        </span>
                      )}
                      <span className="entity-subline">
                        {personId
                          ? `BIN ${role.company.bin}`
                          : role.is_current
                            ? "Observed as current"
                            : "Observed as inactive"}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`badge ${role.identity_verified ? "entity-badge-cyan" : "entity-badge-amber"}`}
                      >
                        {role.identity_verified
                          ? "Verified identity"
                          : "Unverified identity"}
                      </span>
                      <span className="entity-subline">
                        {role.identity_verified
                          ? "Supported by identifier evidence"
                          : "Name alone does not verify identity"}
                      </span>
                    </td>
                    {owner && (
                      <td className="entity-mono">
                        {"share_percent" in role && role.share_percent !== null
                          ? `${role.share_percent}%`
                          : "Unknown"}
                      </td>
                    )}
                    <td className="entity-period">
                      {role.start_date || role.end_date ? (
                        <>
                          {role.start_date
                            ? formatDate(role.start_date)
                            : "Start unknown"}
                          <br />→{" "}
                          {role.end_date
                            ? formatDate(role.end_date)
                            : "End unknown"}
                        </>
                      ) : (
                        "Dates not recorded"
                      )}
                      <span className="entity-subline">
                        {role.temporal_status === "in_period"
                          ? "In recorded period"
                          : role.temporal_status === "not_in_period"
                            ? "Outside recorded period"
                            : role.temporal_status === "observed_inactive"
                              ? "Observed inactive"
                              : "Current applicability unknown"}
                      </span>
                    </td>
                    <td>
                      {role.source_reference ? (
                        <>
                          <ExternalSource url={role.source_reference.url}>
                            {role.source_reference.source || "Source record"}
                          </ExternalSource>
                          {!safeHttpUrl(role.source_reference.url) && (
                            <span>
                              {role.source_reference.source ||
                                "Saved observation"}
                            </span>
                          )}
                          <span className="entity-subline">
                            Observed{" "}
                            {formatDate(role.source_reference.observed_at)}
                          </span>
                        </>
                      ) : (
                        <>
                          <span>{role.source || "Legacy record"}</span>
                          <span className="entity-subline">
                            No linked source observation
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
            Identity verification and legal role applicability are separate.
            Missing dates remain unknown.
          </div>
        </>
      )}
    </section>
  );
}

export function ContractPreview({ companyId }: { companyId: string }) {
  const { data, loading, error, reload } = useApi<Paginated<Contract>>(
    `contracts/?supplier_id=${encodeURIComponent(companyId)}&page_size=5`,
  );
  return (
    <section className="panel entity-directory entity-contract-preview">
      <div className="entity-section-head">
        <div>
          <h2>
            Supplier contracts{" "}
            <span className="entity-count">
              {data?.count.toLocaleString("en-US") ?? "—"}
            </span>
          </h2>
          <p className="muted">
            Most recent saved contracts for this supplier.
          </p>
        </div>
        <Link
          className="entity-inline-link"
          to={`/contracts?supplier_id=${companyId}`}
        >
          View all <ArrowTopRightIcon />
        </Link>
      </div>
      <EntityState
        loading={loading}
        error={error}
        empty={!!data && !data.results.length}
        onRetry={reload}
        emptyTitle="No supplier contracts saved"
        emptyText="Contract coverage may be incomplete. Customer contracts can be inspected separately."
      />
      {!loading && !error && !!data?.results.length && (
        <div className="table-scroll">
          <table className="data-table entity-table entity-contract-table">
            <thead>
              <tr>
                <th scope="col">Contract</th>
                <th scope="col">Customer</th>
                <th scope="col">Date</th>
                <th scope="col">Amount, KZT</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((contract) => (
                <tr key={contract.id}>
                  <td className="entity-contract-title">
                    <strong>{contract.title || "Untitled contract"}</strong>
                    <span className="entity-subline entity-mono">
                      {contract.contract_number || "Number not recorded"}
                    </span>
                  </td>
                  <td>
                    {contract.customer ? (
                      <Link
                        className="entity-inline-link"
                        to={`/companies/${contract.customer.id}`}
                      >
                        {contract.customer.name}
                      </Link>
                    ) : (
                      contract.customer_name || "Not recorded"
                    )}
                  </td>
                  <td>{formatDate(contract.contract_date)}</td>
                  <td className="entity-money">
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
          <ArrowLeftIcon /> Companies
        </Link>
        <section className="panel">
          <EntityState
            loading={loading}
            error={error || (!validId ? "This company link is invalid." : null)}
            empty={!loading && !error && !company}
            onRetry={reload}
            emptyTitle="Company not available"
            emptyText="This saved company record could not be found."
          />
        </section>
      </div>
    );
  return (
    <div className="entity-page">
      <Link className="breadcrumb" to="/companies">
        <ArrowLeftIcon /> Companies
      </Link>
      <header className="page-head entity-detail-head">
        <div>
          <span className="eyebrow">COMPANY PROFILE</span>
          <h1>{company.name || "Unnamed company"}</h1>
          <div className="entity-identity-row">
            <span className="entity-mono">BIN {company.bin || missing}</span>
            <CompanyRoles company={company} />
          </div>
          <div className="entity-actions">
            <Link
              className="button button-primary"
              to={`/contracts?supplier_id=${id}`}
            >
              <FileTextIcon /> Supplier contracts
            </Link>
            {company.is_customer && (
              <Link className="button" to={`/contracts?customer_id=${id}`}>
                Customer contracts
              </Link>
            )}
            {company.website && (
              <ExternalSource url={company.website}>
                Company website
              </ExternalSource>
            )}
          </div>
        </div>
      </header>
      <div className="entity-detail-grid">
        <section className="panel entity-detail-panel">
          <h2>Registry information</h2>
          <dl className="entity-fact-grid">
            {[
              ["Registration date", formatDate(company.registration_date)],
              ["Company status", company.company_status || missing],
              ["Region", company.region || missing],
              ["City", company.city || missing],
              ["Address", company.address || missing],
              ["OKED", company.oked || missing],
              ["Phone", company.phone || missing],
              ["Email", company.email || missing],
              ["Company size", company.company_size || missing],
              ["Economic sector", company.economic_sector || missing],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          {company.description && (
            <p className="entity-description">{company.description}</p>
          )}
          <details style={{ marginTop: 24 }}>
            <summary
              className="muted"
              style={{ fontSize: 12, cursor: "pointer" }}
            >
              Record metadata
            </summary>
            <div className="entity-kgd-meta">
              <span>
                Saved {formatDate(company.created_at)} · Updated{" "}
                {formatDate(company.updated_at)}
              </span>
              <span>
                Legacy index: {company.legacy_risk_score}. An uncalibrated
                historical value, not a probability of wrongdoing.
              </span>
              {company.adata_updated_at && (
                <span>
                  Adata update: {formatDate(company.adata_updated_at)}
                </span>
              )}
            </div>
          </details>
        </section>
        <section className="panel entity-detail-panel">
          <h2>Saved KGD checks</h2>
          {company.kgd_checks.length ? (
            company.kgd_checks.map((check) => (
              <KgdCheck key={check.source} check={check} />
            ))
          ) : (
            <p className="muted">
              No KGD check is saved. Current tax arrears and registration status
              remain unknown.
            </p>
          )}
        </section>
      </div>
      <div className="entity-history-note">
        <InfoCircledIcon />
        <span>
          This profile reads saved records. A company’s arrears belong to the
          company and are not assigned to its directors or owners.
        </span>
      </div>
      <RoleSection kind="directorships" companyId={id} />
      <RoleSection kind="ownerships" companyId={id} />
      <ContractPreview companyId={id} />
    </div>
  );
}
