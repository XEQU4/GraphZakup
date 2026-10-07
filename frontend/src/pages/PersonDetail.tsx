import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, InfoCircledIcon } from "@radix-ui/react-icons";
import { useApi } from "../lib/api";
import type { Person } from "../lib/types";
import { EntityState } from "./Companies";
import { RoleSection } from "./CompanyDetail";
import "./entities.css";

export function PersonDetail() {
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
          <ArrowLeftIcon /> People
        </Link>
        <section className="panel">
          <EntityState
            loading={loading}
            error={error || (!validId ? "This person link is invalid." : null)}
            empty={!loading && !error && !person}
            onRetry={reload}
            emptyTitle="Identity not available"
            emptyText="This saved identity record could not be found."
          />
        </section>
      </div>
    );
  const verified = person.identity_status === "identifier_verified";
  return (
    <div className="entity-page">
      <Link className="breadcrumb" to="/people">
        <ArrowLeftIcon /> People
      </Link>
      <header className="page-head entity-detail-head">
        <div>
          <span className="eyebrow">PERSON PROFILE</span>
          <h1>{person.full_name || "Unnamed identity"}</h1>
          <div className="entity-identity-row">
            <span
              className={`badge ${verified ? "entity-badge-cyan" : "entity-badge-amber"}`}
            >
              {verified ? "Identifier verified" : "Unverified identity"}
            </span>
            <span className="entity-mono">Saved identity #{person.id}</span>
          </div>
        </div>
      </header>
      <div className="entity-person-overview">
        <section className="panel">
          <span className="eyebrow">IDENTITY EVIDENCE</span>
          <h2>
            {verified
              ? "Supported by an identifier"
              : "Identity remains unverified"}
          </h2>
          <p className="muted">
            {verified
              ? "The saved identity has identifier evidence. Each company role still needs its own source and applicable dates."
              : "The recorded name alone does not confirm an identity or a relationship between companies."}
          </p>
        </section>
        <section className="panel">
          <span className="eyebrow">HISTORY COVERAGE</span>
          <h2>Verified history not integrated</h2>
          <p className="muted">
            Court, bankruptcy and restricted-participant history are not
            included. Missing checks do not establish a clean history.
          </p>
        </section>
      </div>
      <div className="entity-history-note">
        <InfoCircledIcon />
        <span>
          A role record describes a company connection. It does not establish
          wrongdoing, and company tax arrears are not this person’s personal
          debt.
        </span>
      </div>
      <RoleSection kind="directorships" personId={id} />
      <RoleSection kind="ownerships" personId={id} />
    </div>
  );
}
