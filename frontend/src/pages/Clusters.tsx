import { useI18n, translate } from "../i18n";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { TechHeading } from "../components/motion/TechHeading";
import GroupGlyph from "../components/motion/GroupGlyph";
import { BorderGlowLink } from "../components/design/BorderGlowLink";
import {
  ArrowRightIcon,
  MagnifyingGlassIcon,
  MixerHorizontalIcon,
  Cross2Icon,
  ClockIcon,
  CheckCircledIcon,
  InfoCircledIcon,
  Link2Icon,
} from "@radix-ui/react-icons";
import { queryPath, useApi } from "../lib/api";
import { clusterDisplayTitle } from "../lib/clusterDirectory";
import type { Cluster, Paginated, ClusterConnectionType } from "../lib/types";
import { formatDate, formatCount } from "../lib/utils";
import { Badge, PageState, Pagination } from "../components/ui";
import "./Clusters.css";

const relationships: Record<ClusterConnectionType, string> = {
  director: "Shared director",
  owner: "Shared owner",
  address: "Shared address",
  phone: "Shared phone",
  email: "Shared email",
  mixed_roles: "Shared person across roles",
};
const coverages = {
  no_checks: "No usable checks",
  partial: "Some with usable checks",
  checked: "All with usable checks",
  not_assessed: "Not assessed",
};
const orderings = {
  "-review_priority": "Highest review priority",
  name: "Saved group name",
  "-created_at": "Newest groups",
  created_at: "Oldest groups",
};

function ConnectionSummary({ cluster }: { cluster: Cluster }) {
  useI18n();
  const directory = cluster.directory;
  const reason = directory?.primary_reason;
  if (!reason) {
    return (
      <p className="group-card-reason">
        {" "}
        {translate("Open the saved graph to inspect its connections.")}{" "}
      </p>
    );
  }
  const count = formatCount(reason.company_count);
  const detail: Record<ClusterConnectionType, string> = {
    director: "{count} company records have shared director connections.",
    owner: "{count} company records have shared owner connections.",
    address: "{count} company records have shared address connections.",
    phone: "{count} company records have shared phone connections.",
    email: "{count} company records have shared email connections.",
    mixed_roles:
      "{count} company records connect through verified people in different roles.",
  };
  return (
    <p className="group-card-reason">
      {translate(detail[reason.type], { count })}
    </p>
  );
}

function GroupCard({
  cluster,
  directorySearch,
}: {
  cluster: Cluster;
  directorySearch: string;
}) {
  useI18n();
  const directory = cluster.directory;
  const status = directory?.analysis_status ?? "not_calculated";
  const score = directory?.review_priority ?? null;
  const coverage = directory?.coverage;
  const checked = coverage?.checked;
  const coverageKnown =
    coverage && coverage.status !== "not_assessed" && checked !== null;
  const evidenceDate = cluster.current_snapshot?.as_of;
  return (
    <BorderGlowLink
      className="panel group-directory-card"
      to={`/clusters/${cluster.uuid}`}
      state={{ directorySearch }}
    >
      <div className="group-card-top">
        <span className="group-card-emblem">
          <GroupGlyph size={34} />
        </span>
        <div className="group-card-state">
          <Badge tone={cluster.is_active ? "blue" : "neutral"}>
            {cluster.is_active
              ? translate("Active group")
              : translate("Archived group")}
          </Badge>
          {status === "stale" && (
            <span className="group-card-stale">
              <ClockIcon aria-hidden="true" />{" "}
              {translate("Earlier analysis")}{" "}
            </span>
          )}
        </div>
      </div>
      <div className="group-card-heading">
        <span className="group-card-kicker">
          {translate("Recorded connection")}
        </span>
        <h2>{clusterDisplayTitle(cluster)}</h2>
        <ConnectionSummary cluster={cluster} />
      </div>
      {directory && directory.reasons.length > 1 && (
        <div
          className="group-card-reasons"
          aria-label={translate("Recorded relationship types")}
        >
          {directory.reasons.map((reason) => (
            <span key={reason.type}>
              <Link2Icon aria-hidden="true" />
              {translate(relationships[reason.type] ?? reason.label)}
            </span>
          ))}
        </div>
      )}
      <div className="group-card-companies">
        <span className="group-card-kicker">
          {translate("Companies in this graph")}
        </span>
        {directory?.companies.length ? (
          <ul>
            {directory.companies.map((company) => (
              <li key={company.id}>
                <span aria-hidden="true" className="group-company-dot" />
                <span>
                  {company.name || `${translate("BIN")} ${company.bin}`}
                </span>
              </li>
            ))}
            {directory.additional_companies > 0 && (
              <li className="group-company-more">
                {translate(
                  directory.additional_companies === 1
                    ? "+ {count} more company"
                    : "+ {count} more companies",
                  { count: formatCount(directory.additional_companies) },
                )}
              </li>
            )}
          </ul>
        ) : (
          <p className="group-card-unavailable">
            {translate(
              cluster.company_count === 1
                ? "{count} company · Names available in the saved graph"
                : "{count} companies · Names available in the saved graph",
              { count: formatCount(cluster.company_count) },
            )}
          </p>
        )}
      </div>
      <div className="group-card-metrics">
        <div className="group-card-priority">
          <span className="group-card-metric-label">
            {translate("Review priority")}
          </span>
          <strong
            className={
              score === null ? "group-card-missing" : "group-card-number"
            }
          >
            {score === null ? (
              translate("Not calculated")
            ) : (
              <>
                {score}
                <small>/100</small>
              </>
            )}
          </strong>
          {score !== null && (
            <span className="group-card-priority-track" aria-hidden="true">
              <span
                style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
              />
            </span>
          )}
          <span className="group-card-metric-note">
            {status === "stale"
              ? translate("No score for this saved graph")
              : score === null
                ? translate("No score for this graph")
                : translate("Points for manual review")}
          </span>
        </div>
        <div className="group-card-coverage">
          <span className="group-card-metric-label">
            {translate("KGD arrears checks")}
          </span>
          <strong
            className={
              coverageKnown ? "group-card-number" : "group-card-missing"
            }
          >
            {coverageKnown ? (
              <>
                {formatCount(checked)}
                <small>
                  {translate("of {count}", {
                    count: formatCount(coverage.total),
                  })}
                </small>
              </>
            ) : (
              translate("Not assessed")
            )}
          </strong>
          <span className="group-card-metric-note">
            {coverageKnown ? (
              coverage.status === "checked" ? (
                <>
                  <CheckCircledIcon aria-hidden="true" />{" "}
                  {translate("Usable checks at this date")}{" "}
                </>
              ) : checked === 0 ? (
                translate("No usable checks at this date")
              ) : (
                translate("Some companies lack a usable check")
              )
            ) : (
              translate("No saved coverage available")
            )}
          </span>
          {coverageKnown && (
            <span className="group-card-coverage-date">
              {translate("At analysis date · {date}", {
                date: formatDate(coverage.as_of),
              })}
            </span>
          )}
        </div>
      </div>
      <div className="group-card-footer">
        <div>
          <span>
            {cluster.current_snapshot
              ? translate("Graph v{version}", {
                  version: cluster.current_snapshot.version,
                })
              : translate("No saved graph")}
          </span>
          <span>
            {evidenceDate
              ? translate("Evidence · {date}", {
                  date: formatDate(evidenceDate),
                })
              : translate("Evidence date not recorded")}
          </span>
        </div>
        <span className="group-card-open">
          {" "}
          {translate("Explore")} <ArrowRightIcon aria-hidden="true" />
        </span>
      </div>
    </BorderGlowLink>
  );
}

export function Clusters() {
  useI18n();
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const [draft, setDraft] = useState(search);
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const ordering = params.get("ordering") ?? "-review_priority";
  const active = params.get("active") ?? "true";
  const minimum = params.get("minimum_review_priority") ?? "";
  const relationship = params.get("relationship") ?? "";
  const coverage = params.get("coverage") ?? "";
  const records = useApi<Paginated<Cluster>>(
    queryPath("clusters/", {
      page,
      page_size: 12,
      search: search.trim(),
      ordering,
      active,
      minimum_review_priority: minimum,
      relationship,
      coverage,
    }),
  );
  useEffect(() => {
    setDraft(search);
  }, [search]);
  const update = (values: Record<string, string | number>) => {
    const next = new URLSearchParams(params);
    Object.entries(values).forEach(([key, value]) =>
      value === "" || (value === 1 && key === "page")
        ? next.delete(key)
        : next.set(key, String(value)),
    );
    setParams(next);
  };
  const reset = () => {
    setDraft("");
    setParams(new URLSearchParams());
  };
  const filters = [
    ...(search
      ? [
          {
            key: "search",
            label: translate("Search: {query}", { query: search }),
            reset: "",
          },
        ]
      : []),
    ...(relationship
      ? [
          {
            key: "relationship",
            label: translate(
              relationships[relationship as ClusterConnectionType] ??
                relationship,
            ),
            reset: "",
          },
        ]
      : []),
    ...(coverage
      ? [
          {
            key: "coverage",
            label: translate("KGD: {coverage}", {
              coverage: translate(
                coverages[coverage as keyof typeof coverages] ?? coverage,
              ),
            }),
            reset: "",
          },
        ]
      : []),
    ...(minimum
      ? [
          {
            key: "minimum_review_priority",
            label: translate("Priority: {minimum}+", { minimum }),
            reset: "",
          },
        ]
      : []),
    ...(active !== "true"
      ? [
          {
            key: "active",
            label: translate("Archived groups"),
            reset: "",
          },
        ]
      : []),
    ...(ordering !== "-review_priority"
      ? [
          {
            key: "ordering",
            label: translate("Sort: {ordering}", {
              ordering: translate(
                orderings[ordering as keyof typeof orderings] ?? ordering,
              ),
            }),
            reset: "",
          },
        ]
      : []),
  ];
  const hasFilters = filters.length > 0;
  const empty =
    !records.loading && !records.error && records.data?.results.length === 0;
  return (
    <div className="clusters-page group-directory">
      <header className="page-head group-directory-head">
        <div>
          <span className="eyebrow">
            {translate("Relationship intelligence")}
          </span>
          <TechHeading as="h1" text={translate("Follow the connection.")} />
          <p>
            {" "}
            {translate(
              "See why companies are grouped, what deserves a closer look and which checks are still missing.",
            )}{" "}
          </p>
        </div>
        <span className="group-directory-head-mark" aria-hidden="true">
          <GroupGlyph size={56} />
        </span>
      </header>
      <section
        className="panel group-directory-tools"
        aria-label={translate("Filter relationship groups")}
      >
        <form
          className="group-directory-search"
          onSubmit={(event) => {
            event.preventDefault();
            setDraft(draft.trim());
            update({ search: draft.trim(), page: 1 });
          }}
        >
          <label className="sr-only" htmlFor="group-directory-search">
            {" "}
            {translate("Search groups by company, BIN or connection")}{" "}
          </label>
          <MagnifyingGlassIcon aria-hidden="true" />
          <input
            id="group-directory-search"
            type="search"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={translate("Company name, BIN or connection")}
            maxLength={100}
            autoComplete="off"
          />
          <button className="button button-secondary" type="submit">
            {" "}
            {translate("Search")} <ArrowRightIcon aria-hidden="true" />
          </button>
        </form>
        <div className="group-directory-filters">
          <label>
            {" "}
            {translate("Connection")}{" "}
            <select
              aria-label={translate("Connection")}
              value={relationship}
              onChange={(event) =>
                update({ relationship: event.target.value, page: 1 })
              }
            >
              <option value="">{translate("Any connection")}</option>
              {Object.entries(relationships).map(([value, label]) => (
                <option key={value} value={value}>
                  {translate(label)}
                </option>
              ))}
            </select>
          </label>
          <label>
            {" "}
            {translate("Saved KGD coverage")}{" "}
            <select
              aria-label={translate("Saved KGD coverage")}
              value={coverage}
              onChange={(event) =>
                update({ coverage: event.target.value, page: 1 })
              }
            >
              <option value="">{translate("Any coverage")}</option>
              {Object.entries(coverages).map(([value, label]) => (
                <option key={value} value={value}>
                  {translate(label)}
                </option>
              ))}
            </select>
          </label>
          <label>
            {" "}
            {translate("Minimum priority")}{" "}
            <select
              aria-label={translate("Minimum priority")}
              value={minimum}
              onChange={(event) =>
                update({ minimum_review_priority: event.target.value, page: 1 })
              }
            >
              <option value="">{translate("Any priority")}</option>
              {[5, 10, 25, 50, 75].map((value) => (
                <option key={value} value={value}>
                  {translate("{count}+ points", { count: value })}
                </option>
              ))}
            </select>
          </label>
          <label>
            {" "}
            {translate("Group state")}{" "}
            <select
              aria-label={translate("Group state")}
              value={active}
              onChange={(event) =>
                update({ active: event.target.value, page: 1 })
              }
            >
              <option value="true">{translate("Active")}</option>
              <option value="false">{translate("Archived")}</option>
            </select>
          </label>
          <label>
            {" "}
            {translate("Sort by")}{" "}
            <select
              aria-label={translate("Sort by")}
              value={ordering}
              onChange={(event) =>
                update({ ordering: event.target.value, page: 1 })
              }
            >
              {Object.entries(orderings).map(([value, label]) => (
                <option key={value} value={value}>
                  {translate(label)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {hasFilters && (
          <div
            className="group-directory-active"
            aria-label={translate("Applied filters")}
          >
            <MixerHorizontalIcon aria-hidden="true" />
            {filters.map((filter) => (
              <button
                type="button"
                className="group-filter-chip"
                key={filter.key}
                aria-label={translate("Remove {filter}", {
                  filter: filter.label,
                })}
                onClick={() => update({ [filter.key]: filter.reset, page: 1 })}
              >
                {filter.label}
                <Cross2Icon aria-hidden="true" />
              </button>
            ))}
            <button
              type="button"
              className="group-filter-reset"
              onClick={reset}
            >
              {" "}
              {translate("Reset filters")}{" "}
            </button>
          </div>
        )}
      </section>
      <div className="group-directory-results-head">
        <div aria-live="polite" role="status">
          <h2>
            {" "}
            {translate("Relationship groups")}{" "}
            {records.data && !records.error && (
              <span>{formatCount(records.data.count)}</span>
            )}
          </h2>
          <p>
            {records.loading
              ? translate("Reading saved groups…")
              : records.error
                ? translate("Saved results unavailable")
                : hasFilters
                  ? translate("Matching your current filters")
                  : translate("Saved connections, ordered for review")}
          </p>
        </div>
        <span className="group-directory-evidence-note">
          <InfoCircledIcon aria-hidden="true" />{" "}
          {translate(
            "Shared contacts alone do not establish common control.",
          )}{" "}
        </span>
      </div>
      <PageState
        loading={records.loading && !records.data}
        error={records.error}
        onRetry={records.reload}
        empty={empty}
        emptyTitle={
          hasFilters
            ? translate("No groups match these filters")
            : active === "true"
              ? translate("No active relationship groups saved")
              : translate("No relationship groups saved")
        }
        emptyMessage={
          hasFilters ? (
            <>
              <p>
                {" "}
                {translate(
                  "Try another company or broaden the connection and coverage filters.",
                )}{" "}
              </p>
              <button
                type="button"
                className="button button-secondary"
                onClick={reset}
              >
                {" "}
                {translate("Reset filters")}{" "}
              </button>
            </>
          ) : (
            translate(
              "Groups appear here after an authorised analysis saves a company connection.",
            )
          )
        }
      />
      {records.error?.status === 404 && page > 1 && (
        <button
          type="button"
          className="button button-secondary"
          onClick={() => update({ page: 1 })}
        >
          {" "}
          {translate("Return to first page")}{" "}
        </button>
      )}
      {records.data && !records.error && !empty && (
        <section
          aria-label={translate("Relationship group results")}
          aria-busy={records.loading}
        >
          <div className="group-directory-grid">
            {records.data.results.map((cluster) => (
              <GroupCard
                key={cluster.uuid}
                cluster={cluster}
                directorySearch={params.toString()}
              />
            ))}
          </div>
          <Pagination
            page={page}
            total={records.data.count}
            pageSize={12}
            onPage={(value) => update({ page: value })}
          />
        </section>
      )}
      <p className="group-directory-note">
        {" "}
        {translate(
          "Review priority is a rule-based index for manual review, not a probability of wrongdoing. KGD coverage describes usable arrears checks at the saved analysis date; it does not cover every source or confirm the absence of debt.",
        )}{" "}
      </p>
    </div>
  );
}
