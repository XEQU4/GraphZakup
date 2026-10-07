import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRightIcon,
  Cross2Icon,
  MagnifyingGlassIcon,
  PersonIcon,
} from "@radix-ui/react-icons";
import { useApi } from "../lib/api";
import type { Paginated, Person } from "../lib/types";
import CountUp from "../components/motion/CountUp";
import SectionEmblem from "../components/motion/SectionEmblem";
import { TechHeading } from "../components/motion/TechHeading";
import { EntityPagination, EntityState, validPage } from "./Companies";
import { useDecorationActive } from "../components/motion/useDecorationActive";
import "./entities.css";
import "./directory.css";

export function People() {
  const decoration = useDecorationActive<HTMLDivElement>();
  const [params, setParams] = useSearchParams();
  const search = (params.get("search") || "").slice(0, 100);
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const page = validPage(params.get("page"));
  const verification = ["true", "false"].includes(
    params.get("is_verified") || "",
  )
    ? params.get("is_verified")!
    : "";
  const ordering = ["full_name", "-full_name"].includes(
    params.get("ordering") || "",
  )
    ? params.get("ordering")!
    : "full_name";
  const query = new URLSearchParams({
    page: String(page),
    page_size: "25",
    ordering,
  });
  if (search) query.set("search", search);
  if (verification) query.set("is_verified", verification);
  const { data, loading, error, reload } = useApi<Paginated<Person>>(
    `people/?${query}`,
  );
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    next.delete("page");
    setParams(next);
  }
  return (
    <div
      ref={decoration.ref}
      className="entity-page directory-page people-directory-page"
      data-decorative-active={decoration.active}
    >
      <header className="page-head entity-page-head">
        <div>
          <span className="eyebrow">PEOPLE & ROLES</span>
          <TechHeading as="h1" text="Follow the people behind the companies." />
          <p className="muted">
            Inspect saved identities and their directorship or ownership
            records.
          </p>
        </div>
        <SectionEmblem kind="people" />
      </header>
      <section className="panel entity-directory">
        <div className="entity-section-head">
          <div>
            <h2>
              People <CountUp className="entity-count" value={data?.count} />
            </h2>
            <p className="muted">
              Identity evidence is distinct from a person’s history.
            </p>
          </div>
          <span className="entity-data-label">
            <i /> SAVED IDENTITIES
          </span>
        </div>
        <div className="toolbar entity-toolbar">
          <form
            className="entity-search"
            onSubmit={(e) => {
              e.preventDefault();
              update("search", draft.trim());
            }}
          >
            <label className="sr-only" htmlFor="person-search">
              Search people by name
            </label>
            <MagnifyingGlassIcon aria-hidden="true" />
            <input
              id="person-search"
              value={draft}
              maxLength={100}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Search a saved name"
            />
            <button className="button entity-search-button" type="submit">
              Search
            </button>
          </form>
          <label className="entity-select-label">
            <span className="directory-control-label">
              Identity verification filter
            </span>
            <select
              className="field"
              value={verification}
              onChange={(e) => update("is_verified", e.target.value)}
            >
              <option value="">All identities</option>
              <option value="true">Verified records</option>
              <option value="false">Unverified records</option>
            </select>
          </label>
          <label className="entity-select-label">
            <span className="directory-control-label">People ordering</span>
            <select
              className="field"
              value={ordering}
              onChange={(e) => update("ordering", e.target.value)}
            >
              <option value="full_name">Name A–Z</option>
              <option value="-full_name">Name Z–A</option>
            </select>
          </label>
          {(search || verification || page > 1) && (
            <button
              className="button entity-clear"
              onClick={() => setParams({})}
            >
              <Cross2Icon /> Clear
            </button>
          )}
        </div>
        <EntityState
          loading={loading}
          error={error}
          empty={!!data && !data.results.length}
          onRetry={reload}
          emptyTitle="No saved identities match"
          emptyText="Try another name or clear the identity filter."
        />
        {!loading && !error && !!data?.results.length && (
          <>
            <div
              className="table-scroll directory-results"
              tabIndex={0}
              role="region"
              aria-label="People results"
            >
              <table className="data-table entity-table" role="table">
                <thead role="rowgroup">
                  <tr role="row">
                    <th scope="col" role="columnheader">
                      Person
                    </th>
                    <th scope="col" role="columnheader">
                      Identity evidence
                    </th>
                    <th scope="col" role="columnheader">
                      History coverage
                    </th>
                    <th scope="col" role="columnheader">
                      <span className="sr-only">Open person</span>
                    </th>
                  </tr>
                </thead>
                <tbody role="rowgroup">
                  {data.results.map((person) => (
                    <tr role="row" key={person.id}>
                      <td role="cell" data-label="Person">
                        <Link
                          className="entity-name-link"
                          to={`/people/${person.id}`}
                        >
                          <span
                            className="entity-company-symbol entity-person-avatar"
                            aria-hidden="true"
                          >
                            <PersonIcon />
                          </span>
                          <span className="directory-identity">
                            <strong>
                              {person.full_name || "Unnamed identity"}
                            </strong>
                            <span className="entity-subline">
                              Saved identity record
                            </span>
                          </span>
                        </Link>
                      </td>
                      <td role="cell" data-label="Identity evidence">
                        <span
                          className={`badge ${person.identity_status === "identifier_verified" ? "entity-badge-cyan" : "entity-badge-amber"}`}
                        >
                          {person.identity_status === "identifier_verified"
                            ? "Identifier verified"
                            : "Unverified identity"}
                        </span>
                      </td>
                      <td role="cell" data-label="History coverage">
                        <span className="muted">
                          Verified history not integrated
                        </span>
                      </td>
                      <td role="cell" className="directory-action-cell">
                        <Link
                          className="entity-row-open"
                          to={`/people/${person.id}`}
                          aria-label={`Open ${person.full_name}`}
                        >
                          <span className="directory-open-label">
                            Open person
                          </span>
                          <ArrowRightIcon aria-hidden="true" />
                        </Link>
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
        Matching names do not establish that two records describe the same
        person. Personal identifiers are not exposed in this directory.
      </p>
    </div>
  );
}
