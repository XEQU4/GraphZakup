import { translate as t, useI18n } from "../i18n";
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
  checked_company_count: number;
  supplier_count: number;
  customer_count: number;
  contract_count: number;
  people_count: number;
  current_verified_people_count: number;
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
  useI18n();
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
  useI18n();
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
  const { language } = useI18n();
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
      value: data?.checked_company_count,
      detail: "Source-checked profiles",
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
      value: data?.current_verified_people_count,
      detail: "Verified identities with current roles",
      path: "/people",
      icon: PersonIcon,
    },
  ];
  return (
    <div className="overview-page">
      <div className="overview-heading">
        <div>
          <span className="eyebrow">
            {t("YOUR PROCUREMENT INTELLIGENCE WORKSPACE")}
          </span>
          <TechHeading as="h1" text={t("Overview.")} enabled={enabled} />
        </div>
        <span className="date-stamp">
          {new Intl.DateTimeFormat(language === "ru" ? "ru-RU" : "en-GB", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            timeZone: "Asia/Qyzylorda",
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
            <span className="label-line" /> {t("EVIDENCE, CONNECTED")}{" "}
            <span className="label-index">{t("/ IZ2")}</span>
          </div>
          <TechHeading
            as="h2"
            id="hero-title"
            text={[t("See the connections."), t("Find the context.")]}
            enabled={enabled}
          />
          <p>
            {t(
              "Explore the companies, people and records behind Kazakhstan’s public procurement.",
            )}
          </p>
          <div className="hero-actions">
            <Link className="button button-primary hero-primary" to="/clusters">
              {t("Explore relationships")} <ArrowRightIcon aria-hidden="true" />
            </Link>
            <Link className="hero-secondary" to="/companies">
              {t("Find a company")} <ArrowTopRightIcon aria-hidden="true" />
            </Link>
          </div>
          <div className="hero-footnote">
            <span className="tiny-line" />
            <span>{t("SAVED SOURCES")}</span>
            <span className="tiny-plus">+</span>
            <span>{t("VERIFIABLE CONNECTIONS")}</span>
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <EvidenceSculpture enabled={enabled} />
        </div>
        <div className="hero-pills">
          <span>
            <CheckCircledIcon /> {t("Source-linked evidence")}
          </span>
          <span>
            <LayersIcon /> {t("Saved graph versions")}
          </span>
          <span>
            <FileTextIcon /> {t("Clear explanations")}
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
          aria-label={t("Directory totals")}
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
                <span className="stat-label">{t(label)}</span>
                <span className="stat-detail">{t(detail)}</span>
              </CardLink>
            </motion.div>
          ))}
        </section>
      )}
      <div className="overview-body">
        <section className="groups-section">
          <div className="section-head">
            <div>
              <span className="eyebrow">{t("THE BIGGER PICTURE")}</span>
              <h2>{t("Relationship groups")}</h2>
            </div>
            <Link className="text-link" to="/clusters">
              {t("View all")} <ArrowRightIcon aria-hidden="true" />
            </Link>
          </div>
          <PageState
            loading={groups.loading}
            error={groups.error}
            onRetry={groups.reload}
            empty={!groups.loading && !groups.data?.count}
            emptyTitle={t("No saved relationship groups")}
            emptyMessage={t(
              "Groups appear here when evidence has been collected and explicitly analysed.",
            )}
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
                    <span className="mono">
                      {t("NETWORK / 0")}
                      {i + 1}
                    </span>
                    <Badge tone="blue">
                      {t("{count} companies", { count: group.company_count })}
                    </Badge>
                  </div>
                  <GroupMotif count={group.company_count} />
                  <h3>{group.name}</h3>
                  <div className="group-card-bottom">
                    <span>
                      <span className="muted">{t("Review priority")}</span>
                      <strong>
                        {group.review_priority === null
                          ? t("Unassessed")
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
            {t("Connections guide review. They do not establish wrongdoing.")}
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
            <Badge>{t("Saved dataset")}</Badge>
          </div>
          <h2 id="coverage-title">{t("Evidence coverage")}</h2>
          <p className="muted">
            {t(
              "A clear view of what is recorded and what still needs checking.",
            )}
          </p>
          <EvidenceMeter
            label={t("Saved identity records")}
            value={data?.verified_people_count ?? null}
            total={data?.people_count ?? null}
            description={t(
              "Verified records out of all saved identity records, including earlier and unverified entries. The People directory shows verified identities with current roles by default.",
            )}
          />
          <div className="coverage-item">
            <div>
              <span>{t("KGD company records")}</span>
              <strong>
                {data ? formatCount(data.companies_with_kgd_records) : "—"}
              </strong>
            </div>
            <small>
              {t(
                "Saved attempts; successful and failed checks remain separate.",
              )}
            </small>
          </div>
          <div className="coverage-item">
            <div>
              <span>{t("Legacy observations")}</span>
              <strong>
                {data ? formatCount(data.legacy_observation_count) : "—"}
              </strong>
            </div>
            <small>
              {t("Historical records awaiting source verification")}
            </small>
          </div>
          <div className="coverage-footer">
            <span className="orbit-dot" />{" "}
            {data?.latest_saved_observation_at
              ? t("Last saved {date}", {
                  date: formatDate(data.latest_saved_observation_at),
                })
              : t("No saved observation date")}
          </div>
        </section>
      </div>
      <section className="recent-records panel">
        <div className="section-head">
          <div>
            <span className="eyebrow">{t("FROM THE SAVED REGISTRY")}</span>
            <h2>{t("Latest contract dates")}</h2>
          </div>
          <Link className="text-link" to="/contracts">
            {t("All contracts")} <ArrowRightIcon aria-hidden="true" />
          </Link>
        </div>
        <PageState
          loading={contracts.loading}
          error={contracts.error}
          onRetry={contracts.reload}
          empty={!contracts.loading && !contracts.data?.count}
          emptyTitle={t("No contracts saved")}
        />
        {contracts.data?.results.length ? (
          <div
            className="table-scroll home-contract-desktop"
            tabIndex={0}
            role="region"
            aria-label={t("Latest contracts")}
          >
            <table className="data-table home-contract-table">
              <thead>
                <tr>
                  <th>{t("Contract / supplier")}</th>
                  <th>{t("Customer")}</th>
                  <th>{t("Date")}</th>
                  <th aria-label={t("Open company")} />
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
                        t("Not recorded")}
                    </td>
                    <td className="nowrap mono">
                      {formatDate(contract.contract_date)}
                    </td>
                    <td>
                      <Link
                        className="icon-button"
                        aria-label={t("Open {name}", {
                          name: contract.supplier.name,
                        })}
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
          <div
            className="home-contract-mobile"
            aria-label={t("Latest contracts")}
          >
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
                    <dt>{t("Customer")}</dt>
                    <dd>
                      {contract.customer_name ||
                        contract.customer?.name ||
                        t("Not recorded")}
                    </dd>
                  </div>
                  <div>
                    <dt>{t("Contract date")}</dt>
                    <dd>{formatDate(contract.contract_date)}</dd>
                  </div>
                </dl>
                <Link
                  className="mobile-contract-open"
                  to={"/companies/" + contract.supplier.id}
                >
                  {t("Open supplier")} <ArrowTopRightIcon aria-hidden="true" />
                </Link>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
