import { useI18n, translate, type MessageValues } from "../i18n";
import { useEffect, useRef, useState } from "react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
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
import { clusterDisplayTitle } from "../lib/clusterDirectory";
import "./ClusterDetailHeader.css";
import { useSession } from "../components/Session";
import { GraphExplorer, safeGraphLink } from "../components/GraphExplorer";
import { TechHeading } from "../components/motion/TechHeading";
import {
  SavedExplanation,
  ReviewPriority,
} from "../components/ClusterAnalysis";

function StaffActions({
  uuid,
  historical,
  onRefresh,
}: {
  uuid: string;
  historical: boolean;
  onRefresh: () => void;
}) {
  useI18n();
  const { capabilities, csrfToken } = useSession();
  const [pending, setPending] = useState(false),
    [job, setJob] = useState<Job | null>(null),
    [message, setMessageState] = useState<{
      key: string;
      values?: MessageValues;
    }>({ key: "" });
  const setMessage = (key: string, values?: MessageValues) =>
    setMessageState({ key, values });
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
        setMessage("Background task: {status}{error}.", {
          status: result.status,
          error: result.error_code ? ` · ${result.error_code}` : "",
        });
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
        <ReloadIcon /> {translate("Staff actions")} <ChevronDownIcon />
      </summary>
      <p>
        {" "}
        {translate(
          "These actions use saved data. They do not start source collection or paid model inference.",
        )}{" "}
      </p>
      <div className="toolbar">
        <button
          className="button button-quiet"
          disabled={pending || historical}
          onClick={() => setAction("graph")}
        >
          {" "}
          {translate("Recalculate saved relationships")}{" "}
        </button>
        <button
          className="button button-quiet"
          disabled={pending || historical}
          onClick={() => setAction("analysis")}
        >
          {" "}
          {translate("Prepare template explanation")}{" "}
        </button>
      </div>
      {action && (
        <div className="cluster-action-confirm">
          <p>
            {action === "graph"
              ? translate(
                  "Recalculate relationships using saved facts? A changed result can publish a new graph and analysis version.",
                )
              : translate(
                  "Prepare the saved template explanation for the current graph? Existing published text remains in its history.",
                )}
          </p>
          <button className="button" onClick={() => void start(action)}>
            {" "}
            {translate("Start background task")}{" "}
          </button>
          <button
            className="button button-quiet"
            onClick={() => setAction(null)}
          >
            {" "}
            {translate("Cancel")}{" "}
          </button>
        </div>
      )}
      {historical && (
        <p>{translate("Open the current graph version to start a task.")}</p>
      )}
      {message.key && (
        <p role="status">
          {translate(
            message.key,
            message.values && {
              ...message.values,
              ...(typeof message.values.status === "string"
                ? { status: translate(message.values.status) }
                : {}),
            },
          )}
        </p>
      )}
      {job?.status === "succeeded" && (
        <button className="button" onClick={onRefresh}>
          <CheckCircledIcon /> {translate("Open updated saved results")}{" "}
        </button>
      )}
    </details>
  );
}

function EvidenceRecords({ snapshot }: { snapshot: number }) {
  useI18n();
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
          <span className="eyebrow">{translate("Traceable sources")}</span>
          <h2>{translate("Saved evidence")}</h2>
        </div>
        <Badge>
          {records.data
            ? translate("{count} records", {
                count: formatCount(records.data.count),
              })
            : translate("Snapshot evidence")}
        </Badge>
      </div>
      <PageState
        loading={records.loading && !records.data}
        error={records.error}
        onRetry={records.reload}
        empty={records.data?.count === 0}
        emptyTitle={translate("No evidence records in this snapshot")}
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
                      ? `${translate(record.graph_edge.type)}: ${record.graph_edge.value}`
                      : record.source ||
                        translate(record.kind.replaceAll("_", " "))}
                  </strong>
                  <small>
                    {translate(
                      record.quality ||
                        record.graph_edge?.confidence ||
                        record.kind.replaceAll("_", " "),
                    )}
                    {record.observed_at
                      ? translate(" · observed {date}", {
                          date: formatDate(record.observed_at),
                        })
                      : ""}
                    {record.status ? ` · ${translate(record.status)}` : ""}
                  </small>
                </div>
                <button
                  className="button button-quiet"
                  onClick={() => setSelected(record.id)}
                  aria-label={translate("Inspect saved evidence {id}", {
                    id: record.id,
                  })}
                >
                  {" "}
                  {translate("Inspect")} <ArrowTopRightIcon />
                </button>
                {record.url && safeGraphLink(record.url) && (
                  <a
                    className="button button-quiet"
                    href={record.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {" "}
                    {translate("Source")} <ArrowTopRightIcon />
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
              aria-label={translate("Close saved evidence")}
            >
              <Cross2Icon />
            </Dialog.Close>
            <span className="eyebrow">{translate("Snapshot evidence")}</span>
            <Dialog.Title>{translate("Saved evidence record")}</Dialog.Title>
            <Dialog.Description>
              {" "}
              {translate(
                "This record belongs to the selected saved graph. Its original source and dates remain unchanged.",
              )}{" "}
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
                    <dt>{translate("Kind")}</dt>
                    <dd>
                      {translate(evidence.data.kind.replaceAll("_", " "))}
                    </dd>
                  </div>
                  {evidence.data.source && (
                    <div>
                      <dt>{translate("Source")}</dt>
                      <dd>{evidence.data.source}</dd>
                    </div>
                  )}
                  {evidence.data.observed_at && (
                    <div>
                      <dt>{translate("Observed")}</dt>
                      <dd>{formatDateTime(evidence.data.observed_at)}</dd>
                    </div>
                  )}
                  {evidence.data.quality && (
                    <div>
                      <dt>{translate("Quality")}</dt>
                      <dd>{translate(evidence.data.quality)}</dd>
                    </div>
                  )}
                  {evidence.data.status && (
                    <div>
                      <dt>{translate("Source status")}</dt>
                      <dd>{translate(evidence.data.status)}</dd>
                    </div>
                  )}
                </dl>
                {evidence.data.graph_edge && (
                  <>
                    <h3>{evidence.data.graph_edge.type}</h3>
                    <p>{evidence.data.graph_edge.value}</p>
                    <dl>
                      <div>
                        <dt>{translate("Evidence confidence")}</dt>
                        <dd>{evidence.data.graph_edge.confidence}</dd>
                      </div>
                      <div>
                        <dt>{translate("Legal interval")}</dt>
                        <dd>
                          {translate("{from} to {until} (exclusive end)", {
                            from: formatDate(
                              evidence.data.graph_edge.valid_from,
                            ),
                            until: formatDate(
                              evidence.data.graph_edge.valid_until,
                            ),
                          })}
                        </dd>
                      </div>
                      <div>
                        <dt>{translate("Temporal status")}</dt>
                        <dd>
                          {translate(
                            evidence.data.graph_edge.temporal_status.replaceAll(
                              "_",
                              " ",
                            ),
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
                          {translate("{quality} · observed {date}", {
                            quality: translate(
                              ref.quality || "Unknown quality",
                            ),
                            date: formatDateTime(ref.observed_at),
                          })}
                        </p>
                        {safeGraphLink(ref.url) && (
                          <a
                            href={ref.url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {" "}
                            {translate("Open original source")}{" "}
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
                    {" "}
                    {translate("Open original source")} <ArrowTopRightIcon />
                  </a>
                )}
                <details>
                  <summary>{translate("Record identifiers")}</summary>
                  <dl>
                    <div>
                      <dt>{translate("Evidence")}</dt>
                      <dd>{evidence.data.id}</dd>
                    </div>
                    <div>
                      <dt>{translate("Graph snapshot")}</dt>
                      <dd>{evidence.data.graph_snapshot_id}</dd>
                    </div>
                    {evidence.data.parser_version && (
                      <div>
                        <dt>{translate("Parser version")}</dt>
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
  useI18n();
  const location = useLocation();
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
    setParams(next, { state: location.state });
  };
  const refresh = () => {
    setParams({}, { state: location.state });
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
  const currentTitleApplies =
    !version || Number(version) === cluster.data?.current_snapshot?.version;
  const displayTitle = cluster.data?.directory
    ? currentTitleApplies
      ? clusterDisplayTitle(cluster.data)
      : graph.data
        ? translate(
            companies.length === 1
              ? "Historical group · {count} company"
              : "Historical group · {count} companies",
            { count: formatCount(companies.length) },
          )
        : translate("Historical relationship group")
    : cluster.data?.name || translate("Relationship group");
  const headingCompanies = graph.data
    ? companies.slice(0, 3).map((company) => ({
        id: company.company_id,
        name: company.name,
      }))
    : currentTitleApplies
      ? (cluster.data?.directory?.companies ?? [])
      : [];
  const originSearch =
    typeof location.state?.directorySearch === "string" &&
    location.state.directorySearch.length <= 2000
      ? new URLSearchParams(location.state.directorySearch).toString()
      : "";
  return (
    <div className="cluster-detail-page">
      <Link
        className="back-link"
        to={originSearch ? `/clusters?${originSearch}` : "/clusters"}
      >
        <ArrowLeftIcon />
        {originSearch
          ? translate("Back to results")
          : translate("All relationship groups")}
      </Link>
      <header className="page-head">
        <div>
          <span className="eyebrow">
            {translate("Saved relationship group")}
          </span>
          <TechHeading
            key={`${uuid}:${displayTitle}`}
            as="h1"
            text={displayTitle}
          />
          {headingCompanies.length > 0 && (
            <div
              className="cluster-heading-companies"
              aria-label={translate("Companies in this saved group")}
            >
              {headingCompanies.map((company, index) =>
                company.id ? (
                  <Link key={company.id} to={`/companies/${company.id}`}>
                    {company.name}
                  </Link>
                ) : (
                  <span key={index}>{company.name}</span>
                ),
              )}
              {companies.length > 3 && (
                <span className="cluster-heading-more">
                  {translate("+{count} more", { count: companies.length - 3 })}
                </span>
              )}
            </div>
          )}
          <p>
            {" "}
            {translate(
              "Inspect saved relationships and their evidence. Group membership does not establish a violation.",
            )}{" "}
          </p>
        </div>
        <div className="cluster-version-select">
          <label className="field">
            <span>{translate("Graph version")}</span>
            <select
              aria-label={translate("Graph version")}
              value={version ?? ""}
              onChange={(event) => update("version", event.target.value)}
            >
              <option value="">{translate("Current saved version")}</option>
              {version &&
                !history.data?.results.some(
                  (item) => String(item.version) === version,
                ) && (
                  <option value={version}>
                    {translate("Graph v{version}", { version })}
                  </option>
                )}
              {history.data?.results.map((item) => (
                <option key={item.id} value={item.version}>
                  v{item.version} · {translate(item.state)} ·{" "}
                  {formatDate(item.as_of)}
                </option>
              ))}
            </select>
          </label>
          {history.error && (
            <small role="alert">
              {" "}
              {translate("Version history unavailable.")}{" "}
              <button className="button button-quiet" onClick={history.reload}>
                {" "}
                {translate("Retry")}{" "}
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
                ? translate("Historical saved version")
                : translate("Current saved version")}
            </Badge>
            <span>
              <ClockIcon />
              {translate("Graph v{version}", {
                version: graph.data.version ?? "—",
              })}
              {detail.data
                ? translate(" · evidence {date}", {
                    date: formatDate(detail.data.as_of),
                  })
                : ""}
            </span>
            {!cluster.data?.is_active && cluster.data && (
              <Badge>{translate("Archived group")}</Badge>
            )}
          </div>
          <GraphExplorer
            key={`${uuid}:${graph.data.snapshot_id}`}
            graph={graph.data}
          />
          <div className="cluster-analysis-layout cluster-review-layout">
            <div className="cluster-analysis-status" role="status">
              <Badge
                tone={
                  analysis.error || selectedExplanation.error
                    ? "amber"
                    : analysis.data?.status === "stale"
                      ? "amber"
                      : "blue"
                }
              >
                {analysis.loading || selectedExplanation.loading
                  ? translate("Loading saved analysis")
                  : analysis.error || selectedExplanation.error
                    ? translate("Saved analysis unavailable")
                    : analysis.data?.status === "stale"
                      ? translate("Saved analysis needs refresh")
                      : analysis.data?.status === "ready"
                        ? translate("Analysis v{version}", {
                            version: currentAnalysis?.version ?? "—",
                          })
                        : translate("No saved analysis")}
              </Badge>
              {analysis.data?.historical && (
                <Badge>{translate("Historical analysis")}</Badge>
              )}
              {currentAnalysis && (
                <span className="cluster-review-status-note">
                  {translate("Graph v{version} · evidence {date}", {
                    version: currentAnalysis.graph_version,
                    date: formatDate(currentAnalysis.as_of),
                  })}
                </span>
              )}
            </div>
            <ReviewPriority
              analysis={currentAnalysis}
              explanation={explanation}
              companies={companies}
              loading={analysis.loading}
              unavailable={Boolean(analysis.error)}
            >
              <details className="cluster-technical">
                <summary>{translate("Method and version history")}</summary>
                {currentAnalysis && (
                  <dl>
                    <div>
                      <dt>{translate("Analysis")}</dt>
                      <dd>
                        v{currentAnalysis.version} ·{" "}
                        {currentAnalysis.rules_version}
                      </dd>
                    </div>
                    <div>
                      <dt>{translate("Analysis hash")}</dt>
                      <dd>
                        <code>
                          {currentAnalysis.analysis_hash.slice(0, 12)}
                        </code>
                      </dd>
                    </div>
                  </dl>
                )}
                <label className="field">
                  <span>{translate("Analysis version")}</span>
                  <select
                    aria-label={translate("Analysis version")}
                    value={analysisVersion ?? ""}
                    onChange={(event) =>
                      update("analysis_version", event.target.value)
                    }
                  >
                    <option value="">
                      {translate("Published analysis for this graph")}
                    </option>
                    {analysisVersion &&
                      !graphAnalyses.some(
                        (item) => String(item.version) === analysisVersion,
                      ) && (
                        <option value={analysisVersion}>
                          {translate("Analysis v{version}", {
                            version: analysisVersion,
                          })}
                        </option>
                      )}
                    {graphAnalyses.map((item) => (
                      <option key={item.id} value={item.version}>
                        {translate("Analysis v{version}", {
                          version: item.version,
                        })}{" "}
                        · {formatDate(item.as_of)}
                      </option>
                    ))}
                  </select>
                </label>
                {analyses.error && (
                  <p role="alert">
                    {translate("Analysis history unavailable.")}
                  </p>
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
                  <span>{translate("Explanation history")}</span>
                  <select
                    aria-label={translate("Explanation history")}
                    value={explanationId ?? ""}
                    onChange={(event) =>
                      update("explanation", event.target.value)
                    }
                  >
                    <option value="">
                      {translate("Published explanation")}
                    </option>
                    {explanationId &&
                      !explanations.data?.results.some(
                        (item) => String(item.id) === explanationId,
                      ) && (
                        <option value={explanationId}>
                          {translate("Explanation #{id}", {
                            id: explanationId,
                          })}
                        </option>
                      )}
                    {explanations.data?.results.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.provider} · {translate(item.status)} ·{" "}
                        {formatDateTime(item.created_at)}
                      </option>
                    ))}
                  </select>
                </label>
                {explanations.error && (
                  <p role="alert">
                    {translate("Explanation history unavailable.")}
                  </p>
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
                    <dt>{translate("Graph hash")}</dt>
                    <dd>
                      <code>
                        {graph.data.graph_hash?.slice(0, 12) ??
                          translate("Unavailable")}
                      </code>
                    </dd>
                  </div>
                  <div>
                    <dt>{translate("Changes")}</dt>
                    <dd>
                      {translate("{added} added · {removed} removed", {
                        added: detail.data?.changes.added_members?.length ?? 0,
                        removed:
                          detail.data?.changes.removed_members?.length ?? 0,
                      })}
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
                      · {translate(item.kind)}
                    </p>
                  ))}
              </details>
            </ReviewPriority>
            <div className="cluster-review-main">
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
                  <SavedExplanation explanation={explanation} />
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
