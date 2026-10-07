import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { TechHeading } from "../components/motion/TechHeading";
import GroupGlyph from "../components/motion/GroupGlyph";
import { BorderGlowLink } from "../components/design/BorderGlowLink";
import {
  ArrowRightIcon,
  MagnifyingGlassIcon,
  MixerHorizontalIcon,
  PersonIcon,
  ClockIcon,
} from "@radix-ui/react-icons";
import { queryPath, useApi } from "../lib/api";
import type { Cluster, Paginated } from "../lib/types";
import { formatDate, formatCount } from "../lib/utils";
import { Badge, PageState, Pagination } from "../components/ui";
import "../components/graph.css";

export function Clusters() {
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const [draft, setDraft] = useState(search);
  const page = Math.max(1, Number(params.get("page")) || 1);
  const ordering = params.get("ordering") ?? "-review_priority";
  const active = params.get("active") !== "false";
  const minimum = params.get("minimum_review_priority") ?? "";
  const records = useApi<Paginated<Cluster>>(
    queryPath("clusters/", {
      page,
      page_size: 12,
      search,
      ordering,
      active,
      minimum_review_priority: minimum,
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
  return (
    <div className="clusters-page">
      <header className="page-head">
        <div>
          <span className="eyebrow">Relationship intelligence</span>
          <TechHeading as="h1" text="Relationship groups." />
          <p>
            Explore saved company connections, their sources and analysis
            versions.
          </p>
        </div>
        <Badge tone="blue">
          <GroupGlyph />
          {records.data
            ? `${formatCount(records.data.count)} saved groups`
            : "Saved evidence"}
        </Badge>
      </header>
      <section
        className="panel clusters-tools"
        aria-label="Filter relationship groups"
      >
        <form
          className="cluster-search"
          onSubmit={(event) => {
            event.preventDefault();
            update({ search: draft, page: 1 });
          }}
        >
          <label className="sr-only" htmlFor="cluster-search">
            Search groups by company, BIN or name
          </label>
          <MagnifyingGlassIcon />
          <input
            id="cluster-search"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Search by company, BIN or group name"
            maxLength={100}
          />
          <button className="button button-quiet" type="submit">
            Search
          </button>
        </form>
        <div className="cluster-filter-row">
          <MixerHorizontalIcon aria-hidden="true" />
          <label>
            Sort by
            <select
              value={ordering}
              onChange={(event) =>
                update({ ordering: event.target.value, page: 1 })
              }
            >
              <option value="-review_priority">Review priority</option>
              <option value="name">Name</option>
              <option value="-created_at">Newest groups</option>
              <option value="created_at">Oldest groups</option>
            </select>
          </label>
          <label>
            Minimum priority
            <select
              value={minimum}
              onChange={(event) =>
                update({ minimum_review_priority: event.target.value, page: 1 })
              }
            >
              <option value="">Any priority</option>
              <option value="10">10+</option>
              <option value="25">25+</option>
              <option value="50">50+</option>
              <option value="75">75+</option>
            </select>
          </label>
          <label>
            Group state
            <select
              value={String(active)}
              onChange={(event) =>
                update({ active: event.target.value, page: 1 })
              }
            >
              <option value="true">Active</option>
              <option value="false">Archived</option>
            </select>
          </label>
        </div>
      </section>
      <PageState
        loading={records.loading && !records.data}
        error={records.error}
        onRetry={records.reload}
        empty={!records.loading && !records.error && records.data?.count === 0}
        emptyTitle="No matching relationship groups"
      />
      {records.data && !records.error && (
        <>
          <div className="cluster-grid">
            {records.data.results.map((cluster) => (
              <BorderGlowLink
                className="panel cluster-card"
                key={cluster.uuid}
                to={`/clusters/${cluster.uuid}`}
              >
                <div className="cluster-card-top">
                  <span className="cluster-symbol">
                    <GroupGlyph className="group-glyph-card" />
                  </span>
                  <Badge tone={cluster.is_active ? "cyan" : "neutral"}>
                    {cluster.is_active ? "Active group" : "Archived group"}
                  </Badge>
                </div>
                <div className="cluster-card-heading">
                  <h2>{cluster.name || "Unnamed relationship group"}</h2>
                  <ArrowRightIcon />
                </div>
                <div className="cluster-card-stats">
                  <span>
                    <PersonIcon />
                    {formatCount(cluster.company_count)}{" "}
                    {cluster.company_count === 1 ? "company" : "companies"}
                  </span>
                  <span>
                    <ClockIcon />
                    {cluster.current_snapshot
                      ? `Graph v${cluster.current_snapshot.version}`
                      : "No saved graph"}
                  </span>
                </div>
                <div className="cluster-priority">
                  <div>
                    <span>Review priority</span>
                    <strong>
                      {cluster.review_priority === null ? (
                        "Not calculated"
                      ) : (
                        <>
                          {cluster.review_priority}
                          <small>/100</small>
                        </>
                      )}
                    </strong>
                  </div>
                  <div className="priority-track" aria-hidden="true">
                    <span
                      style={{ width: `${cluster.review_priority ?? 0}%` }}
                    />
                  </div>
                </div>
                <div className="cluster-card-footer">
                  <span>
                    {cluster.current_snapshot
                      ? `Evidence ${formatDate(cluster.current_snapshot.as_of)}`
                      : `Created ${formatDate(cluster.created_at)}`}
                  </span>
                  <span>
                    Explore group <ArrowRightIcon />
                  </span>
                </div>
              </BorderGlowLink>
            ))}
          </div>
          <Pagination
            page={page}
            total={records.data.count}
            pageSize={12}
            onPage={(value) => update({ page: value })}
          />
        </>
      )}
      <p className="cluster-data-note">
        Groups describe saved relationships. Review priority is a heuristic for
        manual review and does not establish a violation.
      </p>
    </div>
  );
}
