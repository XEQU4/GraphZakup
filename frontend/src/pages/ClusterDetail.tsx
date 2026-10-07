import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowLeftIcon,
  ArrowTopRightIcon,
  ClockIcon,
  ReloadIcon,
  FileTextIcon,
  ChevronDownIcon,
  CheckCircledIcon,
  Cross2Icon,
} from "@radix-ui/react-icons";
import { apiFetch, ApiError, getJson, queryPath, useApi } from "../lib/api";
import type {
  AnalysisResponse,
  AnalysisSnapshot,
  Cluster,
  Explanation,
  GraphResponse,
  GraphSnapshot,
  Job,
  Paginated,
  SnapshotDetail,
  SnapshotEvidence,
} from "../lib/types";
import { formatCount, formatDate, formatDateTime } from "../lib/utils";
import { Badge, PageState, Pagination } from "../components/ui";
import { useSession } from "../components/Session";
import { GraphExplorer, safeGraphLink } from "../components/GraphExplorer";
import { TechHeading } from "../components/motion/TechHeading";

function SavedExplanation({
  explanation,
}: {
  explanation: Explanation | null;
}) {
  if (!explanation)
    return (
      <div className="empty-state">
        <h3>No saved explanation</h3>
        <p>No explanation is published for this analysis version.</p>
      </div>
    );
  const document = explanation.document;
  return (
    <article className="panel cluster-explanation">
      <div className="cluster-section-heading">
        <span className="eyebrow">Saved explanation</span>
        <Badge tone="blue">{explanation.language.toUpperCase()}</Badge>
      </div>
      {document ? (
        <>
          <h2>Review summary</h2>
          <p className="explanation-summary">{document.summary}</p>
          <h3>What connects these companies</h3>
          {document.findings.map((finding) => (
            <section className="explanation-finding" key={finding.finding_id}>
              <h4>{finding.title}</h4>
              <p>{finding.fact}</p>
              {finding.meaning && <p className="muted">{finding.meaning}</p>}
              {finding.companies.length > 0 && (
                <div className="explanation-companies">
                  {finding.companies.map((company) => (
                    <Link key={company.id} to={`/companies/${company.id}`}>
                      {company.name}
                    </Link>
                  ))}
                  {finding.additional_companies > 0 && (
                    <span>and {finding.additional_companies} more</span>
                  )}
                </div>
              )}
              {finding.notes.length > 0 && (
                <details>
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
          <h3>What to check next</h3>
          <ol>
            {document.checks.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ol>
          <details>
            <summary>Data coverage and missing checks</summary>
            <ul>
              {document.coverage.map((text, index) => (
                <li key={index}>{text}</li>
              ))}
            </ul>
          </details>
          <p className="muted">{document.conclusion}</p>
        </>
      ) : (
        <>
          <h2>Saved explanation</h2>
          <div className="legacy-explanation">
            {explanation.text.split(/\n{2,}/).map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        </>
      )}
      <details className="cluster-technical">
        <summary>Explanation metadata</summary>
        <dl>
          <div>
            <dt>Provider</dt>
            <dd>
              {explanation.provider}
              {explanation.model ? ` · ${explanation.model}` : ""}
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

function StaffActions({
  uuid,
  historical,
  onRefresh,
}: {
  uuid: string;
  historical: boolean;
  onRefresh: () => void;
}) {
  const { capabilities, csrfToken } = useSession();
  const [pending, setPending] = useState(false),
    [job, setJob] = useState<Job | null>(null),
    [message, setMessage] = useState("");
  const [action, setAction] = useState<"graph" | "analysis" | null>(null);
  const active = useRef<AbortController | null>(null),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      active.current?.abort();
      if (timer.current) clearTimeout(timer.current);
    },
    [uuid, capabilities.can_start_jobs],
  );
  const start = async (kind: "graph" | "analysis") => {
    if (!csrfToken || pending || historical) return;
    active.current?.abort();
    if (timer.current) clearTimeout(timer.current);
    const abort = new AbortController();
    active.current = abort;
    setPending(true);
    setAction(null);
    setJob(null);
    setMessage("Requesting background task…");
    const poll = async (id: string) => {
      if (abort.signal.aborted) return;
      try {
        const result = await getJson<Job>(`jobs/${kind}/${id}/`, abort.signal);
        if (abort.signal.aborted) return;
        setJob(result);
        setMessage(
          `Background task: ${result.status.replaceAll("_", " ")}${result.error_code ? ` · ${result.error_code}` : ""}.`,
        );
        if (["pending", "running"].includes(result.status))
          timer.current = setTimeout(() => void poll(id), 2000);
        else setPending(false);
      } catch (error) {
        if (!abort.signal.aborted) {
          setMessage(
            error instanceof Error ? error.message : "Job status unavailable.",
          );
          setPending(false);
        }
      }
    };
    try {
      const result = await apiFetch<Job>(
        `clusters/${uuid}/${kind === "graph" ? "recalculate" : "explanations"}/`,
        {
          method: "POST",
          csrfToken,
          body:
            kind === "analysis" ? { use_model: false, retry_model: false } : {},
          signal: abort.signal,
        },
      );
      if (abort.signal.aborted) return;
      setJob(result);
      setMessage(
        result.created
          ? "Background task requested."
          : "The existing background task is being tracked.",
      );
      timer.current = setTimeout(() => void poll(result.job), 1000);
    } catch (error) {
      if (abort.signal.aborted) return;
      setMessage(
        error instanceof Error
          ? error.message
          : "The task could not be started.",
      );
      setPending(false);
      if (
        error instanceof ApiError &&
        error.details &&
        typeof error.details === "object" &&
        "job" in error.details
      ) {
        const id = (error.details as { job?: unknown }).job;
        if (typeof id === "string") void poll(id);
      }
    }
  };
  if (!capabilities.can_start_jobs) return null;
  return (
    <details className="panel cluster-operations">
      <summary>
        <ReloadIcon />
        Staff actions
        <ChevronDownIcon />
      </summary>
      <p>
        These actions use saved data. They do not start source collection or
        paid model inference.
      </p>
      <div className="toolbar">
        <button
          className="button button-quiet"
          disabled={pending || historical}
          onClick={() => setAction("graph")}
        >
          Recalculate saved relationships
        </button>
        <button
          className="button button-quiet"
          disabled={pending || historical}
          onClick={() => setAction("analysis")}
        >
          Prepare template explanation
        </button>
      </div>
      {action && (
        <div className="cluster-action-confirm">
          <p>
            {action === "graph"
              ? "Recalculate relationships using saved facts? A changed result can publish a new graph and analysis version."
              : "Prepare the saved template explanation for the current graph? Existing published text remains in its history."}
          </p>
          <button className="button" onClick={() => void start(action)}>
            Start background task
          </button>
          <button
            className="button button-quiet"
            onClick={() => setAction(null)}
          >
            Cancel
          </button>
        </div>
      )}
      {historical && <p>Open the current graph version to start a task.</p>}
      {message && <p role="status">{message}</p>}
      {job?.status === "succeeded" && (
        <button className="button" onClick={onRefresh}>
          <CheckCircledIcon />
          Open updated saved results
        </button>
      )}
    </details>
  );
}

function EvidenceRecords({ snapshot }: { snapshot: number }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const records = useApi<Paginated<SnapshotEvidence>>(
    queryPath(`snapshots/${snapshot}/evidence/`, { page, page_size: 20 }),
  );
  const evidence = useApi<SnapshotEvidence>(
    selected
      ? `snapshots/${snapshot}/evidence/${encodeURIComponent(selected)}/`
      : null,
  );
  return (
    <section className="panel cluster-evidence">
      <div className="cluster-section-heading">
        <div>
          <span className="eyebrow">Traceable sources</span>
          <h2>Saved evidence</h2>
        </div>
        <Badge>
          {records.data
            ? `${formatCount(records.data.count)} records`
            : "Snapshot evidence"}
        </Badge>
      </div>
      <PageState
        loading={records.loading && !records.data}
        error={records.error}
        onRetry={records.reload}
        empty={records.data?.count === 0}
        emptyTitle="No evidence records in this snapshot"
      />
      {records.data && !records.error && (
        <>
          <div className="cluster-evidence-list">
            {records.data.results.map((record) => (
              <div className="cluster-evidence-row" key={record.id}>
                <span className="cluster-evidence-icon">
                  <FileTextIcon />
                </span>
                <div>
                  <strong>
                    {record.graph_edge
                      ? `${record.graph_edge.type}: ${record.graph_edge.value}`
                      : record.source || record.kind.replaceAll("_", " ")}
                  </strong>
                  <small>
                    {record.quality ||
                      record.graph_edge?.confidence ||
                      record.kind.replaceAll("_", " ")}
                    {record.observed_at
                      ? ` · observed ${formatDate(record.observed_at)}`
                      : ""}
                    {record.status ? ` · ${record.status}` : ""}
                  </small>
                </div>
                <button
                  className="button button-quiet"
                  onClick={() => setSelected(record.id)}
                  aria-label={`Inspect saved evidence ${record.id}`}
                >
                  Inspect
                  <ArrowTopRightIcon />
                </button>
                {record.url && safeGraphLink(record.url) && (
                  <a
                    className="button button-quiet"
                    href={record.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Source
                    <ArrowTopRightIcon />
                  </a>
                )}
              </div>
            ))}
          </div>
          <Pagination
            page={page}
            total={records.data.count}
            pageSize={20}
            onPage={setPage}
          />
        </>
      )}
      <Dialog.Root
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content
            className="dialog-content cluster-evidence-dialog"
            onOpenAutoFocus={() => {
              returnFocus.current =
                document.activeElement instanceof HTMLElement
                  ? document.activeElement
                  : null;
            }}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              if (returnFocus.current?.isConnected) returnFocus.current.focus();
            }}
          >
            <Dialog.Close
              className="icon-button dialog-close"
              aria-label="Close saved evidence"
            >
              <Cross2Icon />
            </Dialog.Close>
            <span className="eyebrow">Snapshot evidence</span>
            <Dialog.Title>Saved evidence record</Dialog.Title>
            <Dialog.Description>
              This record belongs to the selected saved graph. Its original
              source and dates remain unchanged.
            </Dialog.Description>
            <PageState
              loading={evidence.loading}
              error={evidence.error}
              onRetry={evidence.reload}
            />
            {evidence.data && !evidence.loading && !evidence.error && (
              <>
                <dl>
                  <div>
                    <dt>Kind</dt>
                    <dd>{evidence.data.kind.replaceAll("_", " ")}</dd>
                  </div>
                  {evidence.data.source && (
                    <div>
                      <dt>Source</dt>
                      <dd>{evidence.data.source}</dd>
                    </div>
                  )}
                  {evidence.data.observed_at && (
                    <div>
                      <dt>Observed</dt>
                      <dd>{formatDateTime(evidence.data.observed_at)}</dd>
                    </div>
                  )}
                  {evidence.data.quality && (
                    <div>
                      <dt>Quality</dt>
                      <dd>{evidence.data.quality}</dd>
                    </div>
                  )}
                  {evidence.data.status && (
                    <div>
                      <dt>Source status</dt>
                      <dd>{evidence.data.status}</dd>
                    </div>
                  )}
                </dl>
                {evidence.data.graph_edge && (
                  <>
                    <h3>{evidence.data.graph_edge.type}</h3>
                    <p>{evidence.data.graph_edge.value}</p>
                    <dl>
                      <div>
                        <dt>Evidence confidence</dt>
                        <dd>{evidence.data.graph_edge.confidence}</dd>
                      </div>
                      <div>
                        <dt>Legal interval</dt>
                        <dd>
                          {formatDate(evidence.data.graph_edge.valid_from)} to{" "}
                          {formatDate(evidence.data.graph_edge.valid_until)}{" "}
                          (exclusive end)
                        </dd>
                      </div>
                      <div>
                        <dt>Temporal status</dt>
                        <dd>
                          {evidence.data.graph_edge.temporal_status.replaceAll(
                            "_",
                            " ",
                          )}
                        </dd>
                      </div>
                    </dl>
                    {evidence.data.graph_edge.limitations.map((text, index) => (
                      <p key={index}>{text}</p>
                    ))}
                    {evidence.data.graph_edge.evidence.map((ref, index) => (
                      <div className="evidence-dialog-source" key={index}>
                        <strong>{ref.source}</strong>
                        <p>
                          {ref.quality || "Unknown quality"} · observed{" "}
                          {formatDateTime(ref.observed_at)}
                        </p>
                        {safeGraphLink(ref.url) && (
                          <a
                            href={ref.url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            Open original source
                            <ArrowTopRightIcon />
                          </a>
                        )}
                      </div>
                    ))}
                  </>
                )}
                {evidence.data.url && safeGraphLink(evidence.data.url) && (
                  <a
                    className="button button-quiet"
                    href={evidence.data.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open original source
                    <ArrowTopRightIcon />
                  </a>
                )}
                <details>
                  <summary>Record identifiers</summary>
                  <dl>
                    <div>
                      <dt>Evidence</dt>
                      <dd>{evidence.data.id}</dd>
                    </div>
                    <div>
                      <dt>Graph snapshot</dt>
                      <dd>{evidence.data.graph_snapshot_id}</dd>
                    </div>
                    {evidence.data.parser_version && (
                      <div>
                        <dt>Parser version</dt>
                        <dd>{evidence.data.parser_version}</dd>
                      </div>
                    )}
                  </dl>
                </details>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}

export function ClusterDetail() {
  const route = useParams<{ uuid?: string; id?: string }>(),
    uuid = route.uuid ?? route.id ?? "";
  const [params, setParams] = useSearchParams();
  const version = params.get("version"),
    analysisVersion = params.get("analysis_version"),
    explanationId = params.get("explanation");
  const [historyPage, setHistoryPage] = useState(1),
    [analysisPage, setAnalysisPage] = useState(1),
    [explanationPage, setExplanationPage] = useState(1);
  const cluster = useApi<Cluster>(`clusters/${uuid}/`);
  const history = useApi<Paginated<GraphSnapshot>>(
    queryPath(`clusters/${uuid}/snapshots/`, {
      page: historyPage,
      page_size: 100,
    }),
  );
  const graph = useApi<GraphResponse>(
    queryPath(`clusters/${uuid}/graph/`, { version }),
  );
  const detail = useApi<SnapshotDetail>(
    graph.data?.snapshot_id ? `snapshots/${graph.data.snapshot_id}/` : null,
  );
  const analysis = useApi<AnalysisResponse>(
    graph.data?.version
      ? queryPath(`clusters/${uuid}/analysis/`, {
          version: graph.data.version,
          analysis_version: analysisVersion,
        })
      : null,
  );
  const analyses = useApi<Paginated<AnalysisSnapshot>>(
    queryPath(`clusters/${uuid}/analyses/`, {
      page: analysisPage,
      page_size: 100,
    }),
  );
  const explanations = useApi<Paginated<Explanation>>(
    analysis.data?.analysis
      ? queryPath(
          `clusters/${uuid}/analyses/${analysis.data.analysis.version}/explanations/`,
          { page: explanationPage, page_size: 100 },
        )
      : null,
  );
  const selectedExplanation = useApi<Explanation>(
    explanationId && analysis.data?.analysis
      ? `clusters/${uuid}/analyses/${analysis.data.analysis.version}/explanations/${explanationId}/`
      : null,
  );
  const update = (
    key: "version" | "analysis_version" | "explanation",
    value: string,
  ) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    if (key === "version") {
      next.delete("analysis_version");
      next.delete("explanation");
      setExplanationPage(1);
    }
    if (key === "analysis_version") {
      next.delete("explanation");
      setExplanationPage(1);
    }
    setParams(next);
  };
  const refresh = () => {
    setParams({});
    cluster.reload();
    graph.reload();
    history.reload();
    analyses.reload();
    analysis.reload();
    explanations.reload();
    detail.reload();
  };
  const currentAnalysis = analysis.data?.analysis;
  const explanation = explanationId
    ? selectedExplanation.data
    : (analysis.data?.explanation ?? null);
  const graphAnalyses =
    analyses.data?.results.filter(
      (item) => item.graph_version === graph.data?.version,
    ) ?? [];
  const companies =
    graph.data?.graph.nodes.filter((node) => node.kind === "company") ?? [];
  return (
    <div className="cluster-detail-page">
      <Link className="back-link" to="/clusters">
        <ArrowLeftIcon />
        All relationship groups
      </Link>
      <header className="page-head">
        <div>
          <span className="eyebrow">Saved relationship group</span>
          <TechHeading
            key={cluster.data?.name || uuid}
            as="h1"
            text={cluster.data?.name || "Relationship group"}
          />
          <p>
            Inspect saved relationships and their evidence. Group membership
            does not establish a violation.
          </p>
        </div>
        <div className="cluster-version-select">
          <label className="field">
            <span>Graph version</span>
            <select
              aria-label="Graph version"
              value={version ?? ""}
              onChange={(event) => update("version", event.target.value)}
            >
              <option value="">Current saved version</option>
              {version &&
                !history.data?.results.some(
                  (item) => String(item.version) === version,
                ) && <option value={version}>Graph v{version}</option>}
              {history.data?.results.map((item) => (
                <option key={item.id} value={item.version}>
                  v{item.version} · {item.state} · {formatDate(item.as_of)}
                </option>
              ))}
            </select>
          </label>
          {history.error && (
            <small role="alert">
              Version history unavailable.{" "}
              <button className="button button-quiet" onClick={history.reload}>
                Retry
              </button>
            </small>
          )}
        </div>
      </header>
      <PageState
        loading={(cluster.loading || graph.loading) && !graph.data}
        error={cluster.error || graph.error}
        onRetry={() => {
          cluster.reload();
          graph.reload();
        }}
      />
      {graph.data && !graph.error && (
        <>
          <div className="cluster-version-strip">
            <Badge tone={graph.data.historical ? "amber" : "cyan"}>
              {graph.data.historical
                ? "Historical saved version"
                : "Current saved version"}
            </Badge>
            <span>
              <ClockIcon />
              Graph v{graph.data.version ?? "—"}
              {detail.data
                ? ` · evidence ${formatDate(detail.data.as_of)}`
                : ""}
            </span>
            {!cluster.data?.is_active && cluster.data && (
              <Badge>Archived group</Badge>
            )}
          </div>
          <GraphExplorer
            key={`${uuid}:${graph.data.snapshot_id}`}
            graph={graph.data}
          />
          <div className="cluster-analysis-layout">
            <aside className="panel cluster-analysis-summary">
              <span className="eyebrow">Saved analysis</span>
              <h2>
                {currentAnalysis ? (
                  <>
                    Review priority{" "}
                    <strong>
                      {currentAnalysis.metrics.review_priority}
                      <small>/100</small>
                    </strong>
                  </>
                ) : (
                  "Not calculated"
                )}
              </h2>
              {currentAnalysis && (
                <>
                  <div className="priority-track">
                    <span
                      style={{
                        width: `${currentAnalysis.metrics.review_priority}%`,
                      }}
                    />
                  </div>
                  {explanation?.document ? (
                    <>
                      <ul>
                        {explanation.document.score.items.map((item) => (
                          <li key={item.finding_id}>
                            {item.label}: +{item.points} points
                          </li>
                        ))}
                      </ul>
                      <p className="muted">
                        {explanation.document.score.meaning}
                      </p>
                    </>
                  ) : (
                    <p className="muted">
                      Uncalibrated index for manual review. It is not a
                      probability of wrongdoing.
                    </p>
                  )}
                  <dl className="analysis-metrics">
                    <div>
                      <dt>Relationship strength</dt>
                      <dd>{currentAnalysis.metrics.link_strength}/100</dd>
                    </div>
                    <div>
                      <dt>Behavioural risk</dt>
                      <dd>
                        {currentAnalysis.metrics.behavioural_risk === null
                          ? "Not assessable"
                          : `${currentAnalysis.metrics.behavioural_risk}/100`}
                      </dd>
                    </div>
                    <div>
                      <dt>Fresh arrears checks</dt>
                      <dd>
                        {currentAnalysis.metrics.fresh_arrears_checks}/
                        {currentAnalysis.metrics.company_count}
                      </dd>
                    </div>
                  </dl>
                  <p className="muted">
                    Evidence date: {formatDate(currentAnalysis.as_of)}
                  </p>
                </>
              )}
              <h3>Companies ({companies.length})</h3>
              <ul className="analysis-company-list">
                {companies.map((company) => (
                  <li key={company.id}>
                    {company.company_id ? (
                      <Link to={`/companies/${company.company_id}`}>
                        {company.name}
                      </Link>
                    ) : (
                      company.name
                    )}
                  </li>
                ))}
              </ul>
              <details className="cluster-technical">
                <summary>Method and version history</summary>
                {currentAnalysis && (
                  <dl>
                    <div>
                      <dt>Analysis</dt>
                      <dd>
                        v{currentAnalysis.version} ·{" "}
                        {currentAnalysis.rules_version}
                      </dd>
                    </div>
                    <div>
                      <dt>Analysis hash</dt>
                      <dd>
                        <code>
                          {currentAnalysis.analysis_hash.slice(0, 12)}
                        </code>
                      </dd>
                    </div>
                  </dl>
                )}
                <label className="field">
                  <span>Analysis version</span>
                  <select
                    aria-label="Analysis version"
                    value={analysisVersion ?? ""}
                    onChange={(event) =>
                      update("analysis_version", event.target.value)
                    }
                  >
                    <option value="">Published analysis for this graph</option>
                    {analysisVersion &&
                      !graphAnalyses.some(
                        (item) => String(item.version) === analysisVersion,
                      ) && (
                        <option value={analysisVersion}>
                          Analysis v{analysisVersion}
                        </option>
                      )}
                    {graphAnalyses.map((item) => (
                      <option key={item.id} value={item.version}>
                        Analysis v{item.version} · {formatDate(item.as_of)}
                      </option>
                    ))}
                  </select>
                </label>
                {analyses.error && (
                  <p role="alert">Analysis history unavailable.</p>
                )}
                {analyses.data && analyses.data.count > 100 && (
                  <Pagination
                    page={analysisPage}
                    total={analyses.data.count}
                    pageSize={100}
                    onPage={setAnalysisPage}
                  />
                )}
                <label className="field">
                  <span>Explanation history</span>
                  <select
                    aria-label="Explanation history"
                    value={explanationId ?? ""}
                    onChange={(event) =>
                      update("explanation", event.target.value)
                    }
                  >
                    <option value="">Published explanation</option>
                    {explanationId &&
                      !explanations.data?.results.some(
                        (item) => String(item.id) === explanationId,
                      ) && (
                        <option value={explanationId}>
                          Explanation #{explanationId}
                        </option>
                      )}
                    {explanations.data?.results.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.provider} · {item.status} ·{" "}
                        {formatDateTime(item.created_at)}
                      </option>
                    ))}
                  </select>
                </label>
                {explanations.error && (
                  <p role="alert">Explanation history unavailable.</p>
                )}
                {explanations.data && explanations.data.count > 100 && (
                  <Pagination
                    page={explanationPage}
                    total={explanations.data.count}
                    pageSize={100}
                    onPage={setExplanationPage}
                  />
                )}
                <dl>
                  <div>
                    <dt>Graph hash</dt>
                    <dd>
                      <code>
                        {graph.data.graph_hash?.slice(0, 12) ?? "Unavailable"}
                      </code>
                    </dd>
                  </div>
                  <div>
                    <dt>Changes</dt>
                    <dd>
                      {detail.data?.changes.added_members?.length ?? 0} added ·{" "}
                      {detail.data?.changes.removed_members?.length ?? 0}{" "}
                      removed
                    </dd>
                  </div>
                </dl>
                {history.data && history.data.count > 100 && (
                  <Pagination
                    page={historyPage}
                    total={history.data.count}
                    pageSize={100}
                    onPage={setHistoryPage}
                  />
                )}
                {detail.data &&
                  [
                    ...detail.data.incoming_transitions,
                    ...detail.data.outgoing_transitions,
                  ].map((item, index) => (
                    <p key={index}>
                      <Link
                        to={`/clusters/${item.source_cluster}?version=${item.source_version}`}
                      >
                        v{item.source_version}
                      </Link>{" "}
                      →{" "}
                      <Link
                        to={`/clusters/${item.target_cluster}?version=${item.target_version}`}
                      >
                        v{item.target_version}
                      </Link>{" "}
                      · {item.kind}
                    </p>
                  ))}
              </details>
            </aside>
            <div>
              <PageState
                loading={analysis.loading || selectedExplanation.loading}
                error={analysis.error || selectedExplanation.error}
                onRetry={() => {
                  analysis.reload();
                  selectedExplanation.reload();
                }}
              />
              {!analysis.loading &&
                !analysis.error &&
                !selectedExplanation.loading &&
                !selectedExplanation.error && (
                  <>
                    <div className="cluster-analysis-status">
                      <Badge
                        tone={
                          analysis.data?.status === "stale" ? "amber" : "blue"
                        }
                      >
                        {analysis.data?.status === "stale"
                          ? "Saved analysis needs refresh"
                          : analysis.data?.status === "ready"
                            ? `Analysis v${currentAnalysis?.version}`
                            : "No saved analysis"}
                      </Badge>
                      {analysis.data?.historical && (
                        <Badge>Historical analysis</Badge>
                      )}
                    </div>
                    <SavedExplanation explanation={explanation} />
                  </>
                )}
            </div>
          </div>
          {graph.data.snapshot_id && (
            <EvidenceRecords
              key={graph.data.snapshot_id}
              snapshot={graph.data.snapshot_id}
            />
          )}
          <StaffActions
            key={uuid}
            uuid={uuid}
            historical={graph.data.historical}
            onRefresh={refresh}
          />
        </>
      )}
    </div>
  );
}
