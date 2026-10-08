import { useRef, type ReactNode, type RefObject } from "react";
import { Link } from "react-router-dom";
import {
  ArrowTopRightIcon,
  CheckCircledIcon,
  CubeIcon,
  InfoCircledIcon,
  LightningBoltIcon,
  ReaderIcon,
  TargetIcon,
  ChevronDownIcon,
} from "@radix-ui/react-icons";
import type {
  AnalysisSnapshot,
  Explanation,
  ExplanationDocument,
  GraphNode,
} from "../lib/types";
import { formatDate, formatDateTime } from "../lib/utils";
import { Badge } from "./ui";
import "./ClusterAnalysis.css";

const findingLabels: Record<string, string> = {
  shared_director: "Shared director",
  shared_owner: "Shared owner",
  mixed_person_roles: "Ownership and management connection",
  shared_address: "Shared address",
  shared_phone: "Shared phone number",
  shared_email: "Shared email address",
  company_arrears: "Reported company arrears",
  company_zero_arrears: "Dated zero-arrears result",
  stored_contract_summary: "Available procurement records",
};
const findingTarget = (id: string) => "explanation-finding-" + id;

function SavedFacts({
  document,
  factsRef,
}: {
  document: ExplanationDocument;
  factsRef: RefObject<HTMLDetailsElement | null>;
}) {
  return (
    <details ref={factsRef} className="explanation-saved-facts">
      <summary>
        <ReaderIcon aria-hidden="true" />
        <span>Saved evidence and facts</span>
        <small>
          {document.findings.length}{" "}
          {document.findings.length === 1 ? "finding" : "findings"}
        </small>
        <ChevronDownIcon
          className="explanation-disclosure-arrow"
          aria-hidden="true"
        />
      </summary>
      <div className="explanation-facts-body">
        {document.findings.map((finding) => (
          <section
            className="explanation-finding"
            id={findingTarget(finding.finding_id)}
            key={finding.finding_id}
            tabIndex={-1}
          >
            <h3>{finding.title}</h3>
            <p>{finding.fact}</p>
            {finding.details?.length ? (
              <ul className="explanation-fact-details">
                {finding.details.map((detail, index) => (
                  <li key={index}>{detail}</li>
                ))}
              </ul>
            ) : null}
            {finding.meaning && (
              <p className="explanation-fact-context">{finding.meaning}</p>
            )}
            {finding.companies.length > 0 && (
              <div className="explanation-companies">
                {finding.companies.map((company) => (
                  <Link key={company.id} to={"/companies/" + company.id}>
                    {company.name}
                    <ArrowTopRightIcon aria-hidden="true" />
                  </Link>
                ))}
                {finding.additional_companies > 0 && (
                  <span>and {finding.additional_companies} more</span>
                )}
              </div>
            )}
            {finding.notes.length > 0 && (
              <details className="explanation-finding-limits">
                <summary>Evidence limits</summary>
                {finding.notes.map((note, index) => (
                  <p key={index}>{note}</p>
                ))}
              </details>
            )}
          </section>
        ))}
        {document.additional_findings > 0 && (
          <p>
            {document.additional_findings} additional findings are included in
            the saved evidence.
          </p>
        )}
      </div>
    </details>
  );
}

export function SavedExplanation({
  explanation,
}: {
  explanation: Explanation | null;
}) {
  const factsRef = useRef<HTMLDetailsElement>(null);
  if (!explanation)
    return (
      <article className="panel cluster-explanation cluster-explanation-empty">
        <div className="cluster-review-card-heading">
          <span className="cluster-review-card-icon">
            <ReaderIcon aria-hidden="true" />
          </span>
          <div>
            <span className="eyebrow">SAVED RESULTS</span>
            <h2>No saved explanation</h2>
          </div>
        </div>
        <p>No explanation is published for this analysis version.</p>
      </article>
    );
  const document = explanation.document;
  const narrative = document?.narrative?.paragraphs.length
    ? document.narrative
    : null;
  function evidenceLinks(ids: string[]) {
    if (!document) return null;
    const findings = Array.from(new Set(ids))
      .map((id) =>
        document.findings.find((finding) => finding.finding_id === id),
      )
      .filter((finding) => finding !== undefined);
    if (!findings.length) return null;
    return (
      <div
        className="explanation-references"
        aria-label="Supporting saved evidence"
      >
        {findings.map((finding) => (
          <a
            key={finding.finding_id}
            href={"#" + encodeURIComponent(findingTarget(finding.finding_id))}
            aria-label={"Read evidence for " + finding.title}
            onClick={() => {
              if (factsRef.current) factsRef.current.open = true;
            }}
          >
            <ReaderIcon aria-hidden="true" />
            {finding.title}
          </a>
        ))}
      </div>
    );
  }
  return (
    <article className="panel cluster-explanation">
      <header className="cluster-review-card-heading">
        <span className="cluster-review-card-icon">
          <ReaderIcon aria-hidden="true" />
        </span>
        <div>
          <span className="eyebrow">
            {narrative ? "BASED ON SAVED EVIDENCE" : "SAVED EXPLANATION"}
          </span>
          <h2>{narrative ? "AI explanation" : "Saved summary"}</h2>
        </div>
        <Badge tone="blue">{explanation.language.toUpperCase()}</Badge>
      </header>
      {document ? (
        <>
          {narrative ? (
            <div className="explanation-narrative">
              {narrative.paragraphs.map((paragraph, index) => (
                <section key={index}>
                  <p>{paragraph.text}</p>
                  {evidenceLinks(paragraph.finding_ids)}
                </section>
              ))}
            </div>
          ) : (
            <p className="explanation-summary">{document.summary}</p>
          )}
          <section
            className="explanation-next-checks"
            aria-labelledby="explanation-next-title"
          >
            <h3 id="explanation-next-title">
              <TargetIcon aria-hidden="true" />
              What to check next
            </h3>
            <ol>
              {narrative
                ? narrative.checks.map((check, index) => (
                    <li key={index}>
                      <p>{check.text}</p>
                      {evidenceLinks(check.finding_ids)}
                    </li>
                  ))
                : document.checks.map((text, index) => (
                    <li key={index}>{text}</li>
                  ))}
            </ol>
          </section>
          <SavedFacts document={document} factsRef={factsRef} />
          <details className="explanation-coverage">
            <summary>
              <InfoCircledIcon aria-hidden="true" />
              <span>Data coverage and missing checks</span>
              <ChevronDownIcon
                className="explanation-disclosure-arrow"
                aria-hidden="true"
              />
            </summary>
            <ul>
              {document.coverage.map((text, index) => (
                <li key={index}>{text}</li>
              ))}
            </ul>
          </details>
          {!narrative && (
            <p className="explanation-conclusion">{document.conclusion}</p>
          )}
        </>
      ) : (
        <div className="legacy-explanation">
          {explanation.text.split(/\n{2,}/).map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
      )}
      <footer className="explanation-source">
        <span>
          <CheckCircledIcon aria-hidden="true" />
          Saved {formatDate(explanation.created_at)}
        </span>
        <span>
          {explanation.status === "fallback"
            ? "Saved template fallback"
            : narrative
              ? "AI-written from saved facts"
              : explanation.provider === "template"
                ? "Prepared from saved facts"
                : "Saved model-assisted summary"}
        </span>
        {narrative && (
          <span className="explanation-model-name">
            {explanation.provider}
            {explanation.model ? " · " + explanation.model : ""}
          </span>
        )}
        {explanation.status === "fallback" && (
          <p className="explanation-fallback-note">
            Model generation did not produce an accepted answer. This
            explanation uses the saved template.
          </p>
        )}
      </footer>
      <details className="cluster-technical">
        <summary>Explanation metadata</summary>
        <dl>
          <div>
            <dt>Provider</dt>
            <dd>
              {explanation.provider}
              {explanation.model ? " · " + explanation.model : ""}
            </dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{explanation.status}</dd>
          </div>
          <div>
            <dt>Prompt version</dt>
            <dd>{explanation.prompt_version}</dd>
          </div>
          <div>
            <dt>Saved</dt>
            <dd>{formatDateTime(explanation.created_at)}</dd>
          </div>
        </dl>
      </details>
    </article>
  );
}

export function ReviewPriority({
  analysis,
  explanation,
  companies,
  loading,
  unavailable,
  children,
}: {
  analysis: AnalysisSnapshot | null | undefined;
  explanation: Explanation | null;
  companies: GraphNode[];
  loading: boolean;
  unavailable: boolean;
  children: ReactNode;
}) {
  const breakdown = analysis?.metrics.score_breakdown ?? [];
  const score = analysis?.metrics.review_priority;
  return (
    <aside className="panel cluster-analysis-summary">
      <header className="cluster-review-card-heading">
        <span className="cluster-review-card-icon">
          <TargetIcon aria-hidden="true" />
        </span>
        <div>
          <span className="eyebrow">SAVED RULE RESULTS</span>
          <h2>Review priority</h2>
        </div>
      </header>
      <p className="priority-purpose">
        A guide to which connections deserve a closer look.
      </p>
      {analysis ? (
        <>
          <div className="priority-score">
            <strong>
              {score}
              <span>/100</span>
            </strong>
            <small>Manual review index</small>
          </div>
          <div className="priority-track" aria-hidden="true">
            <span
              style={{ width: Math.max(0, Math.min(100, score ?? 0)) + "%" }}
            />
          </div>
          <p className="priority-interpretation">
            <InfoCircledIcon aria-hidden="true" />
            <span>
              Points come from saved facts and fixed rules. They are not a
              percentage chance of wrongdoing.
            </span>
          </p>
          <section className="priority-contributions">
            <h3>What adds points</h3>
            {breakdown.length ? (
              <ul>
                {breakdown.map((item) => {
                  const finding = analysis.findings.find(
                    (entry) => entry.id === item.finding_id,
                  );
                  const label =
                    explanation?.document?.score.items.find(
                      (entry) => entry.finding_id === item.finding_id,
                    )?.label ||
                    (finding
                      ? findingLabels[finding.code] ||
                        finding.code.replaceAll("_", " ")
                      : "Saved finding");
                  return (
                    <li key={item.finding_id}>
                      <span>{label}</span>
                      <strong>
                        +{item.points}
                        <small> points</small>
                      </strong>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p>No credited finding is listed in this saved analysis.</p>
            )}
          </section>
          <dl className="analysis-metrics">
            <div>
              <dt>
                Relationship strength
                <small>Strength of the saved connection evidence</small>
              </dt>
              <dd>
                {analysis.metrics.link_strength}
                <small>/100</small>
              </dd>
            </div>
            <div>
              <dt>
                Behavioural risk
                <small>A separate assessment from relationships</small>
              </dt>
              <dd>
                {analysis.metrics.behavioural_risk === null
                  ? "Not assessable"
                  : analysis.metrics.behavioural_risk + "/100"}
              </dd>
            </div>
            <div>
              <dt>
                Fresh arrears checks
                <small>Successful current company checks</small>
              </dt>
              <dd>
                {analysis.metrics.fresh_arrears_checks}
                <small>/{analysis.metrics.company_count}</small>
              </dd>
            </div>
          </dl>
          <p className="priority-evidence-date">
            Evidence date <strong>{formatDate(analysis.as_of)}</strong>
          </p>
        </>
      ) : (
        <div className="priority-unavailable">
          <LightningBoltIcon aria-hidden="true" />
          <strong>
            {loading
              ? "Loading saved analysis"
              : unavailable
                ? "Score unavailable"
                : "Not calculated"}
          </strong>
          <p>
            {unavailable
              ? "Retry the analysis read to view saved rule results."
              : loading
                ? "Reading the saved rule result for this graph."
                : "This graph has no saved review-priority result to display yet."}
          </p>
        </div>
      )}
      <details className="priority-companies" open={companies.length <= 6}>
        <summary>
          <CubeIcon aria-hidden="true" />
          <span>Companies</span>
          <strong>{companies.length}</strong>
        </summary>
        <ul className="analysis-company-list">
          {companies.map((company) => (
            <li key={company.id}>
              {company.company_id ? (
                <Link to={"/companies/" + company.company_id}>
                  {company.name}
                  <ArrowTopRightIcon aria-hidden="true" />
                </Link>
              ) : (
                company.name
              )}
            </li>
          ))}
        </ul>
      </details>
      {children}
    </aside>
  );
}
