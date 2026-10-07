import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { motion } from "motion/react";
import {
  ArrowRightIcon,
  ArrowTopRightIcon,
  CubeIcon,
  FileTextIcon,
  LayersIcon,
  PersonIcon,
  CheckCircledIcon,
  InfoCircledIcon,
} from "@radix-ui/react-icons";
import { useApi } from "../lib/api";
import { formatCount, formatDate } from "../lib/utils";
import type { Cluster, Contract, Paginated } from "../lib/types";
import { Badge, PageState, Skeleton } from "../components/ui";
import { useMotionPreferences } from "../components/MotionPreferences";
import { AuroraAtmosphere } from "../components/effects/AuroraAtmosphere";
import { EvidenceSculpture } from "../components/design/EvidenceSculpture";
import { useSpotlight } from "../components/design/SpotlightSurface";
import { BorderGlowLink } from "../components/design/BorderGlowLink";
import { EvidenceMeter } from "../components/design/EvidenceMeter";
import { BorderBeam } from "../components/effects/BorderBeam";
import { TechHeading } from "../components/motion/TechHeading";
import CountUp from "../components/motion/CountUp";
import GroupGlyph from "../components/motion/GroupGlyph";
interface Overview {
  company_count: number;
  supplier_count: number;
  customer_count: number;
  contract_count: number;
  people_count: number;
  verified_people_count: number;
  active_group_count: number;
  snapshot_count: number;
  total_contract_amount: string;
  contract_date_from: string | null;
  contract_date_to: string | null;
  latest_saved_observation_at: string | null;
  legacy_observation_count: number;
  nonlegacy_success_count: number;
  companies_with_kgd_records: number;
}
function CardLink({
  to,
  className,
  children,
}: {
  to: string;
  className: string;
  children: ReactNode;
}) {
  const { surfaceProps } = useSpotlight<HTMLAnchorElement>();
  return (
    <Link
      {...surfaceProps}
      to={to}
      className={className + " " + surfaceProps.className}
    >
      {children}
    </Link>
  );
}
function GroupMotif({ count }: { count: number }) {
  return (
    <div className="group-motif" aria-hidden="true">
      <span className="motif-core">
        <GroupGlyph size={20} />
      </span>
      {Array.from({ length: Math.min(count, 5) }, (_, i) => (
        <span className={"motif-node motif-node-" + i} key={i}>
          <CubeIcon />
        </span>
      ))}
      <i />
      <b />
    </div>
  );
}
export default function Home() {
  const overview = useApi<Overview>("overview/");
  const groups = useApi<Paginated<Cluster>>(
    "clusters/?page_size=3&ordering=-review_priority",
  );
  const contracts = useApi<Paginated<Contract>>(
    "contracts/?page_size=4&ordering=-contract_date",
  );
  const { enabled } = useMotionPreferences();
  const data = overview.data;
  const stats = [
    {
      label: "Companies",
      value: data?.company_count,
      detail: "Suppliers and customers",
      path: "/companies",
      icon: CubeIcon,
    },
    {
      label: "Saved contracts",
      value: data?.contract_count,
      detail: "Procurement records",
      path: "/contracts",
      icon: FileTextIcon,
    },
    {
      label: "Relationship groups",
      value: data?.active_group_count,
      detail: "Saved evidence networks",
      path: "/clusters",
      icon: LayersIcon,
    },
    {
      label: "People",
      value: data?.people_count,
      detail: "Recorded identity profiles",
      path: "/people",
      icon: PersonIcon,
    },
  ];
  return (
    <div className="overview-page">
      <div className="overview-heading">
        <div>
          <span className="eyebrow">
            YOUR PROCUREMENT INTELLIGENCE WORKSPACE
          </span>
          <TechHeading as="h1" text="Overview." enabled={enabled} />
        </div>
        <span className="date-stamp">
          {new Intl.DateTimeFormat("en-GB", {
            day: "2-digit",
            month: "short",
            year: "numeric",
          })
            .format(new Date())
            .toUpperCase()}
        </span>
      </div>
      <motion.section
        className="hero panel hero-rich"
        initial={enabled ? { opacity: 0, y: 12 } : false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55 }}
        aria-labelledby="hero-title"
      >
        <AuroraAtmosphere enabled={enabled} />
        <div className="hero-grid" aria-hidden="true" />
        <BorderBeam enabled={enabled} />
        <div className="hero-copy">
          <div className="hero-label">
            <span className="label-line" /> EVIDENCE, CONNECTED{" "}
            <span className="label-index">/ IZ2</span>
          </div>
          <TechHeading
            as="h2"
            id="hero-title"
            text={["See the connections.", "Find the context."]}
            enabled={enabled}
          />
          <p>
            Explore the companies, people and records behind Kazakhstan’s public
            procurement.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary hero-primary" to="/clusters">
              Explore relationships <ArrowRightIcon aria-hidden="true" />
            </Link>
            <Link className="hero-secondary" to="/companies">
              Find a company <ArrowTopRightIcon aria-hidden="true" />
            </Link>
          </div>
          <div className="hero-footnote">
            <span className="tiny-line" />
            <span>SAVED SOURCES</span>
            <span className="tiny-plus">+</span>
            <span>VERIFIABLE CONNECTIONS</span>
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <EvidenceSculpture enabled={enabled} />
        </div>
        <div className="hero-pills">
          <span>
            <CheckCircledIcon /> Source-linked evidence
          </span>
          <span>
            <LayersIcon /> Saved graph versions
          </span>
          <span>
            <FileTextIcon /> Clear explanations
          </span>
        </div>
      </motion.section>
      {overview.error ? (
        <div className="panel">
          <PageState error={overview.error} onRetry={overview.reload} />
        </div>
      ) : (
        <section
          className="stat-grid overview-stats"
          aria-label="Saved workspace totals"
        >
          {stats.map(({ label, value, detail, path, icon: Icon }, i) => (
            <motion.div
              key={label}
              initial={enabled ? { opacity: 0, y: 10 } : false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 * i, duration: 0.4 }}
            >
              <CardLink className={"stat-card stat-tone-" + i} to={path}>
                <Icon className="stat-watermark" aria-hidden="true" />
                <div className="stat-top">
                  <span className="stat-icon">
                    {path === "/clusters" ? (
                      <GroupGlyph size={20} />
                    ) : (
                      <Icon aria-hidden="true" />
                    )}
                  </span>
                  <ArrowTopRightIcon
                    className="stat-arrow"
                    aria-hidden="true"
                  />
                </div>
                <strong className="stat-number">
                  {value === undefined ? (
                    <Skeleton style={{ width: 90, height: 42 }} />
                  ) : (
                    <CountUp value={value} />
                  )}
                </strong>
                <span className="stat-label">{label}</span>
                <span className="stat-detail">{detail}</span>
              </CardLink>
            </motion.div>
          ))}
        </section>
      )}
      <div className="overview-body">
        <section className="groups-section">
          <div className="section-head">
            <div>
              <span className="eyebrow">THE BIGGER PICTURE</span>
              <h2>Relationship groups</h2>
            </div>
            <Link className="text-link" to="/clusters">
              View all <ArrowRightIcon aria-hidden="true" />
            </Link>
          </div>
          <PageState
            loading={groups.loading}
            error={groups.error}
            onRetry={groups.reload}
            empty={!groups.loading && !groups.data?.count}
            emptyTitle="No saved relationship groups"
            emptyMessage="Groups appear here when evidence has been collected and explicitly analysed."
          />
          {groups.data?.results.length ? (
            <div className="home-group-grid">
              {groups.data.results.map((group, i) => (
                <BorderGlowLink
                  to={"/clusters/" + group.uuid}
                  className={"home-group-card panel group-tone-" + i}
                  key={group.uuid}
                >
                  <div className="group-card-head">
                    <span className="mono">NETWORK / 0{i + 1}</span>
                    <Badge tone="blue">{group.company_count} companies</Badge>
                  </div>
                  <GroupMotif count={group.company_count} />
                  <h3>{group.name}</h3>
                  <div className="group-card-bottom">
                    <span>
                      <span className="muted">Review priority</span>
                      <strong>
                        {group.review_priority === null
                          ? "Unassessed"
                          : group.review_priority + " / 100"}
                      </strong>
                    </span>
                    <span className="group-open">
                      <ArrowTopRightIcon aria-hidden="true" />
                    </span>
                  </div>
                </BorderGlowLink>
              ))}
            </div>
          ) : null}
          <div className="section-note">
            <InfoCircledIcon aria-hidden="true" />
            Connections guide review. They do not establish wrongdoing.
          </div>
        </section>
        <section
          className="coverage-card panel"
          aria-labelledby="coverage-title"
        >
          <div className="coverage-top">
            <span className="stat-icon">
              <CheckCircledIcon aria-hidden="true" />
            </span>
            <Badge>Saved dataset</Badge>
          </div>
          <h2 id="coverage-title">Evidence coverage</h2>
          <p className="muted">
            A clear view of what is recorded and what still needs checking.
          </p>
          <EvidenceMeter
            label="Identity verification"
            value={data?.verified_people_count ?? null}
            total={data?.people_count ?? null}
            description="Verified identifiers in saved person records"
          />
          <div className="coverage-item">
            <div>
              <span>KGD company records</span>
              <strong>
                {data ? formatCount(data.companies_with_kgd_records) : "—"}
              </strong>
            </div>
            <small>
              Saved attempts; successful and failed checks remain separate.
            </small>
          </div>
          <div className="coverage-item">
            <div>
              <span>Legacy observations</span>
              <strong>
                {data ? formatCount(data.legacy_observation_count) : "—"}
              </strong>
            </div>
            <small>Historical records awaiting source verification</small>
          </div>
          <div className="coverage-footer">
            <span className="orbit-dot" />{" "}
            {data?.latest_saved_observation_at
              ? "Last saved " + formatDate(data.latest_saved_observation_at)
              : "No saved observation date"}
          </div>
        </section>
      </div>
      <section className="recent-records panel">
        <div className="section-head">
          <div>
            <span className="eyebrow">FROM THE SAVED REGISTRY</span>
            <h2>Latest contract dates</h2>
          </div>
          <Link className="text-link" to="/contracts">
            All contracts <ArrowRightIcon aria-hidden="true" />
          </Link>
        </div>
        <PageState
          loading={contracts.loading}
          error={contracts.error}
          onRetry={contracts.reload}
          empty={!contracts.loading && !contracts.data?.count}
          emptyTitle="No contracts saved"
        />
        {contracts.data?.results.length ? (
          <div
            className="table-scroll home-contract-desktop"
            tabIndex={0}
            role="region"
            aria-label="Latest contracts"
          >
            <table className="data-table home-contract-table">
              <thead>
                <tr>
                  <th>Contract / supplier</th>
                  <th>Customer</th>
                  <th>Date</th>
                  <th aria-label="Open company" />
                </tr>
              </thead>
              <tbody>
                {contracts.data.results.map((contract) => (
                  <tr key={contract.id}>
                    <td>
                      <Link to={"/companies/" + contract.supplier.id}>
                        <span className="record-icon">
                          <FileTextIcon aria-hidden="true" />
                        </span>
                        <span>
                          <strong>{contract.supplier.name}</strong>
                          <small className="mono">
                            {contract.contract_number}
                          </small>
                        </span>
                      </Link>
                    </td>
                    <td>
                      {contract.customer_name ||
                        contract.customer?.name ||
                        "Not recorded"}
                    </td>
                    <td className="nowrap mono">
                      {formatDate(contract.contract_date)}
                    </td>
                    <td>
                      <Link
                        className="icon-button"
                        aria-label={"Open " + contract.supplier.name}
                        to={"/companies/" + contract.supplier.id}
                      >
                        <ArrowTopRightIcon />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {contracts.data?.results.length ? (
          <div className="home-contract-mobile" aria-label="Latest contracts">
            {contracts.data.results.map((contract) => (
              <article className="mobile-contract" key={contract.id}>
                <div className="mobile-contract-supplier">
                  <span className="record-icon">
                    <FileTextIcon aria-hidden="true" />
                  </span>
                  <div>
                    <Link to={"/companies/" + contract.supplier.id}>
                      {contract.supplier.name}
                    </Link>
                    <small className="mono">{contract.contract_number}</small>
                  </div>
                </div>
                <dl>
                  <div>
                    <dt>Customer</dt>
                    <dd>
                      {contract.customer_name ||
                        contract.customer?.name ||
                        "Not recorded"}
                    </dd>
                  </div>
                  <div>
                    <dt>Contract date</dt>
                    <dd>{formatDate(contract.contract_date)}</dd>
                  </div>
                </dl>
                <Link
                  className="mobile-contract-open"
                  to={"/companies/" + contract.supplier.id}
                >
                  Open supplier <ArrowTopRightIcon aria-hidden="true" />
                </Link>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
