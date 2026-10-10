import { useI18n } from "../i18n";
import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, InfoCircledIcon } from "@radix-ui/react-icons";
import { useApi } from "../lib/api";
import type { PersonDetail as Person } from "../lib/types";
import { EntityState } from "./Companies";
import { RoleSection } from "./CompanyDetail";
import { RelatedGroups } from "./EntityEvidence";
import "./entities.css";

export function PersonDetail() {
  const { t } = useI18n();
  const { id = "" } = useParams();
  const validId = /^[1-9]\d*$/.test(id);
  const {
    data: person,
    loading,
    error,
    reload,
  } = useApi<Person>(validId ? `people/${id}/` : null);
  if (!validId || loading || error || !person)
    return (
      <div className="entity-page">
        <Link className="breadcrumb" to="/people">
          <ArrowLeftIcon /> {t("People")}
        </Link>
        <section className="panel">
          <EntityState
            loading={loading}
            error={
              error || (!validId ? t("This person link is invalid.") : null)
            }
            empty={!loading && !error && !person}
            onRetry={reload}
            emptyTitle={t("Identity not available")}
            emptyText={t("This saved identity record could not be found.")}
          />
        </section>
      </div>
    );
  const verified = person.identity_status === "identifier_verified";
  return (
    <div className="entity-page">
      <Link className="breadcrumb" to="/people">
        <ArrowLeftIcon /> {t("People")}
      </Link>
      <header className="page-head entity-detail-head">
        <div>
          <span className="eyebrow">{t("PERSON PROFILE")}</span>
          <h1>{person.full_name || t("Unnamed identity")}</h1>
          <div className="entity-identity-row">
            <span
              className={`badge ${verified ? "entity-badge-cyan" : "entity-badge-amber"}`}
            >
              {verified ? t("Identifier verified") : t("Unverified identity")}
            </span>
            <span className="entity-mono">
              {t("Saved identity #")}
              {person.id}
            </span>
          </div>
        </div>
      </header>
      <nav className="entity-section-nav" aria-label={t("Person sections")}>
        <a href="#identity-evidence">{t("Identity evidence")}</a>
        <a href="#directorships">{t("Directorships")}</a>
        <a href="#related-groups">{t("Related groups")}</a>
      </nav>
      <div className="entity-person-overview entity-person-focused">
        <section className="panel" id="identity-evidence">
          <span className="eyebrow">{t("IDENTITY EVIDENCE")}</span>
          <h2>
            {verified
              ? t("Supported by an identifier")
              : t("Identity remains unverified")}
          </h2>
          <p className="muted">
            {verified
              ? t(
                  "The saved identity has identifier evidence. Each company role still needs its own source and applicable dates.",
                )
              : t(
                  "The recorded name alone does not confirm an identity or a relationship between companies.",
                )}
          </p>
          <div className="entity-identity-explainer">
            <strong>{t("Why can the same name appear more than once?")}</strong>
            <p>
              {t(
                "Different source records, companies or historical roles can carry the same name. IZ2 keeps these identities separate until identifier evidence supports a match.",
              )}
            </p>
            <dl className="entity-match-counts">
              <div>
                <dt>{t("Other records with this exact name")}</dt>
                <dd>{person.same_name_count ?? 0}</dd>
              </div>
              <div>
                <dt>{t("Candidate matches awaiting review")}</dt>
                <dd>{person.pending_match_count ?? 0}</dd>
              </div>
            </dl>
            {!!person.same_name_count && (
              <Link
                className="entity-inline-link"
                to={`/people?roles=all&is_verified=all&search=${encodeURIComponent(person.full_name)}`}
              >
                {t("Compare name search results")}
              </Link>
            )}
            <small>
              {t(
                "Name search may also include partial matches. Counts are records, not a count of distinct people.",
              )}
            </small>
          </div>
        </section>
      </div>
      <div className="entity-history-note">
        <InfoCircledIcon />
        <span>
          {t(
            "A role record describes a company connection. It does not establish wrongdoing, and company tax arrears are not this person’s personal debt.",
          )}
        </span>
      </div>
      <RoleSection kind="directorships" personId={id} />
      <RoleSection kind="ownerships" personId={id} />
      <details className="entity-coverage-note">
        <summary>{t("What is not covered")}</summary>
        <p>
          {t(
            "This page describes recorded company roles. The current collectors do not establish ownership or provide verified personal tax-debt, court, bankruptcy or restricted-participant history. Missing history does not establish a clean record.",
          )}
        </p>
        <p>
          {t(
            "Company KGD checks are available from the company links above. They do not describe this person’s personal debt.",
          )}
        </p>
      </details>
      <RelatedGroups key={`person-${id}`} personId={id} />
    </div>
  );
}
