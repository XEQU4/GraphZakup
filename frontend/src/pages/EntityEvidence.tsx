import { useI18n, translate } from "../i18n";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRightIcon, Link2Icon, ClockIcon } from "@radix-ui/react-icons";
import { useApi, formatDate } from "../lib/api";
import { clusterDisplayTitle } from "../lib/clusterDirectory";
import type { Cluster, FieldEvidence, Paginated } from "../lib/types";
import { EntityPagination, EntityState } from "./Companies";
import { ExternalSource } from "./CompanyDetail";

export function sourceName(source: string | null) {
  return (
    (
      {
        adata: "Adata",
        goszakup: translate("Goszakup registry"),
        goszakup_company: translate("Goszakup registry"),
        goszakup_registry: translate("Goszakup registry"),
        goszakup_supplier: translate("Goszakup registry"),
        goszakup_contracts: translate("Goszakup contracts"),
        legacy: translate("Legacy record"),
      } as Record<string, string>
    )[source || ""] ||
    source ||
    translate("Source not recorded")
  );
}

export function FactEvidence({
  evidence,
  hasValue = true,
}: {
  evidence?: FieldEvidence;
  hasValue?: boolean;
}) {
  const { t } = useI18n();
  if (!hasValue)
    return <span className="entity-fact-source">{t("No value saved")}</span>;
  if (!evidence || evidence.status !== "source_backed")
    return (
      <span className="entity-fact-source entity-fact-unconfirmed">
        {evidence?.status === "legacy"
          ? t("Legacy record · not rechecked")
          : t("Source not confirmed for this value")}
      </span>
    );
  return (
    <span className="entity-fact-source">
      {evidence.url ? (
        <ExternalSource url={evidence.url}>
          {sourceName(evidence.source)}
        </ExternalSource>
      ) : (
        sourceName(evidence.source)
      )}
      <span>
        <ClockIcon aria-hidden="true" /> {t("Retrieved")}{" "}
        {formatDate(evidence.observed_at)}
      </span>
    </span>
  );
}

export function RelatedGroups({
  companyId,
  personId,
}: {
  companyId?: string;
  personId?: string;
}) {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const query = new URLSearchParams({ page: String(page), page_size: "4" });
  if (companyId) query.set("company_id", companyId);
  if (personId) query.set("person_id", personId);
  const { data, loading, error, reload } = useApi<Paginated<Cluster>>(
    `clusters/?${query}`,
  );
  return (
    <section
      className="panel entity-related"
      id="related-groups"
      aria-label={t("Related groups")}
    >
      <div className="entity-section-head">
        <div>
          <span className="eyebrow">{t("SAVED NETWORK")}</span>
          <h2>
            {t("Related groups")}{" "}
            <span className="entity-count">{data?.count ?? "—"}</span>
          </h2>
          <p className="muted">
            {personId
              ? t(
                  "Groups with this exact verified person in their saved graph.",
                )
              : t(
                  "Active groups containing this company in their saved graph.",
                )}
          </p>
        </div>
        <Link2Icon className="entity-section-symbol" aria-hidden="true" />
      </div>
      <EntityState
        loading={loading}
        error={error}
        empty={false}
        onRetry={reload}
        emptyTitle={t("No related saved groups")}
        emptyText={
          personId
            ? t(
                "Unverified names are not used to connect companies. A role can be listed below without creating a graph connection.",
              )
            : t(
                "No active saved group currently includes this company. This does not establish that it has no relationships.",
              )
        }
      />
      {!loading && !error && data?.count === 0 && (
        <p className="muted entity-related-empty">
          {personId
            ? t(
                "No saved group includes this identity. A director appears in a group only when the collected evidence connects companies; a name alone is not enough.",
              )
            : t("No active saved group currently includes this company.")}
        </p>
      )}
      {!loading && !error && !!data?.results.length && (
        <>
          <div className="entity-group-grid">
            {data.results.map((group) => (
              <Link
                className="entity-group-card"
                key={group.uuid}
                to={`/clusters/${group.uuid}`}
              >
                <span className="eyebrow">
                  {t("{count} companies · graph v{version}", {
                    count: group.company_count,
                    version: group.current_snapshot?.version ?? "—",
                  })}
                </span>
                <h3>{clusterDisplayTitle(group)}</h3>
                <p>
                  {group.directory?.companies
                    .map((company) => company.name)
                    .join(" · ") || group.name}
                </p>
                <span className="entity-group-bottom">
                  {t("Review priority")}{" "}
                  {group.directory?.review_priority ?? t("not assessed")}
                  {group.directory?.review_priority != null ? "/100" : ""}
                  <ArrowRightIcon aria-hidden="true" />
                </span>
              </Link>
            ))}
          </div>
          <EntityPagination
            page={page}
            count={data.count}
            pageSize={4}
            onPage={setPage}
          />
        </>
      )}
    </section>
  );
}
