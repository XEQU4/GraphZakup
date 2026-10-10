import { translate as t, useI18n } from "../i18n";
import { Link } from "react-router-dom";
import {
  ArrowRightIcon,
  ArrowTopRightIcon,
  CheckCircledIcon,
  CubeIcon,
  FileTextIcon,
  LayersIcon,
  MagnifyingGlassIcon,
  PersonIcon,
  ReaderIcon,
  TargetIcon,
} from "@radix-ui/react-icons";
import { BorderGlow } from "../components/design/BorderGlow";
import { TechHeading } from "../components/motion/TechHeading";
import { useDecorationActive } from "../components/motion/useDecorationActive";
import { projectInfo } from "../lib/projectInfo";
import "./About.css";

const reviewSteps = [
  {
    number: "01",
    title: "Find a participant",
    text: "Search a company name or BIN. Open its saved profile and check which source records are available.",
    label: "Search companies",
    to: "/companies",
    icon: MagnifyingGlassIcon,
  },
  {
    number: "02",
    title: "Check the context",
    text: "Review suppliers, customers and contracts. Read source dates and coverage before comparing records.",
    label: "Browse contracts",
    to: "/contracts",
    icon: FileTextIcon,
  },
  {
    number: "03",
    title: "Follow the evidence",
    text: "Open a relationship group. Filter connections, highlight neighbours and inspect the evidence behind each link.",
    label: "Explore groups",
    to: "/clusters",
    icon: LayersIcon,
  },
  {
    number: "04",
    title: "Read, then review",
    text: "Read the saved explanation and follow-up checks. Compare saved versions and keep a graph layout for your next visit.",
    label: "Open saved analyses",
    to: "/clusters",
    icon: ReaderIcon,
  },
] as const;

const audiences = [
  {
    icon: TargetIcon,
    title: "Procurement reviewers",
    text: "A place to examine participant relationships and decide which records deserve a closer look.",
  },
  {
    icon: MagnifyingGlassIcon,
    title: "Researchers",
    text: "A way to trace a connection to its source, compare saved evidence and keep gaps in coverage visible.",
  },
  {
    icon: PersonIcon,
    title: "Students and learners",
    text: "A working thesis prototype that makes procurement data, graph analysis and explanations easier to explore.",
  },
] as const;

function EvidenceFlow() {
  useI18n();
  const { ref, active } = useDecorationActive<HTMLDivElement>();
  const stages = [
    {
      label: "Source records",
      detail: "Companies and contracts",
      icon: FileTextIcon,
    },
    {
      label: "Relationship evidence",
      detail: "Identifiers, contacts and provenance",
      icon: CubeIcon,
    },
    {
      label: "Saved graph",
      detail: "Connections with an inspectable history",
      icon: LayersIcon,
    },
    {
      label: "Explanation",
      detail: "Findings, meaning and follow-up checks",
      icon: ReaderIcon,
    },
  ];
  return (
    <div ref={ref} className="about-evidence-flow" data-active={active}>
      <div className="about-flow-heading">
        <span className="eyebrow">{t("FROM RECORD TO REVIEW")}</span>
        <span className="about-flow-signal" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </div>
      <ol className="about-flow-stages">
        {stages.map(({ label, detail, icon: Icon }, index) => (
          <li key={label}>
            <span className="about-flow-node" aria-hidden="true">
              <Icon />
            </span>
            <div>
              <strong>{t(label)}</strong>
              <span>{t(detail)}</span>
            </div>
            <span className="about-flow-index" aria-hidden="true">
              0{index + 1}
            </span>
          </li>
        ))}
      </ol>
      <p className="about-flow-caption">
        {t("A connection becomes useful when you can see what supports it.")}
      </p>
    </div>
  );
}

export function About() {
  useI18n();
  return (
    <div className="about-page">
      <header className="about-page-header">
        <span className="eyebrow">{t("ABOUT IZ2")}</span>
        <span className="about-project-tag">
          <i aria-hidden="true" /> {t("THESIS PROTOTYPE")}
        </span>
      </header>

      <BorderGlow
        as="section"
        className="about-hero"
        aria-labelledby="about-title"
        fillOpacity={0.1}
      >
        <div className="about-hero-copy">
          <span className="about-section-index">
            {t("EVIDENCE / CONTEXT / REVIEW")}
          </span>
          <TechHeading
            as="h1"
            id="about-title"
            text={[t("Understand the links."), t("Inspect the evidence.")]}
          />
          <p>
            {t(
              "IZ2 brings saved company, contract and relationship records into one workspace for reviewing Kazakhstan public procurement.",
            )}
          </p>
          <p className="about-hero-detail">
            {t(
              "Explore who is connected, see why a connection appears and read what still needs checking.",
            )}
          </p>
          <div className="about-actions">
            <Link className="button button-primary" to="/companies">
              {t("Find a company")} <ArrowRightIcon aria-hidden="true" />
            </Link>
            <Link className="button button-secondary" to="/clusters">
              {t("Explore groups")} <LayersIcon aria-hidden="true" />
            </Link>
          </div>
        </div>
        <EvidenceFlow />
      </BorderGlow>

      <section className="about-section" aria-labelledby="about-purpose-title">
        <div className="about-section-heading">
          <span className="about-section-index">{t("01 / PURPOSE")}</span>
          <TechHeading
            as="h2"
            id="about-purpose-title"
            text={t("Give each connection its context.")}
          />
        </div>
        <div className="about-purpose-grid">
          <p className="about-lead">
            {t(
              "A company record tells one part of a story. Procurement records, shared contacts and dated source evidence help you examine the wider picture.",
            )}
          </p>
          <div className="about-purpose-detail">
            <p>
              {t(
                "IZ2 connects those records in a graph and keeps the supporting evidence close to the result. Saved versions let you return to the same analysis instead of receiving a newly generated account on every visit.",
              )}
            </p>
            <p>
              {t(
                "Review priority helps organise follow-up work. It is not a probability of wrongdoing, and a shared contact or relationship does not establish a violation.",
              )}
            </p>
          </div>
        </div>
      </section>

      <section className="about-section" aria-labelledby="about-audience-title">
        <div className="about-section-heading">
          <span className="about-section-index">{t("02 / WHO IT IS FOR")}</span>
          <TechHeading
            as="h2"
            id="about-audience-title"
            text={t("Built for careful review.")}
          />
          <p>{t("Designed to support examination, research and learning.")}</p>
        </div>
        <div className="about-audience-grid">
          {audiences.map(({ title, text, icon: Icon }) => (
            <BorderGlow
              as="article"
              className="about-audience-card"
              key={title}
              fillOpacity={0.08}
            >
              <span className="about-card-icon" aria-hidden="true">
                <Icon />
              </span>
              <h3>{t(title)}</h3>
              <p>{t(text)}</p>
            </BorderGlow>
          ))}
        </div>
      </section>

      <section className="about-section" aria-labelledby="about-how-title">
        <div className="about-section-heading">
          <span className="about-section-index">
            {t("03 / HOW TO USE IZ2")}
          </span>
          <TechHeading
            as="h2"
            id="about-how-title"
            text={t("Start with a company. Follow the facts.")}
          />
        </div>
        <ol className="about-steps">
          {reviewSteps.map(({ number, title, text, label, to, icon: Icon }) => (
            <li key={number}>
              <BorderGlow
                as="article"
                className="about-step"
                fillOpacity={0.08}
              >
                <div className="about-step-top">
                  <span>{number}</span>
                  <Icon aria-hidden="true" />
                </div>
                <h3>{t(title)}</h3>
                <p>{t(text)}</p>
                <Link to={to}>
                  {t(label)}
                  <ArrowRightIcon aria-hidden="true" />
                </Link>
              </BorderGlow>
            </li>
          ))}
        </ol>
        <p className="about-small-note">
          {t(
            "Browsing reads saved results. Anonymous graph layouts stay in this browser; signed-in users can save their own views.",
          )}
        </p>
      </section>

      <section className="about-section" aria-labelledby="about-scope-title">
        <div className="about-section-heading">
          <span className="about-section-index">{t("04 / CURRENT SCOPE")}</span>
          <TechHeading
            as="h2"
            id="about-scope-title"
            text={t("What you can explore today.")}
          />
        </div>
        <div className="about-scope-grid">
          <BorderGlow
            as="article"
            className="about-scope-card"
            aria-labelledby="about-available-title"
            fillOpacity={0.08}
          >
            <span className="about-scope-label">
              <CheckCircledIcon aria-hidden="true" /> {t("IMPLEMENTED")}
            </span>
            <h3 id="about-available-title">{t("Saved evidence, connected")}</h3>
            <ul>
              <li>
                {t(
                  "Company, person and procurement contract records with available source context.",
                )}
              </li>
              <li>
                {t(
                  "Interactive relationship graphs, evidence inspection, saved versions and personal layouts.",
                )}
              </li>
              <li>
                {t(
                  "Rule-based review priority and saved explanations with remaining checks.",
                )}
              </li>
              <li>
                {t(
                  "Stored State Revenue Committee (KGD) checks where available; missing and unavailable results remain explicit.",
                )}
              </li>
            </ul>
          </BorderGlow>
          <BorderGlow
            as="article"
            className="about-scope-card about-scope-planned"
            aria-labelledby="about-planned-title"
            fillOpacity={0.06}
          >
            <span className="about-scope-label">
              {t("PLANNED / NOT CURRENT FINDINGS")}
            </span>
            <h3 id="about-planned-title">{t("A broader verified history")}</h3>
            <ul>
              <li>
                {t(
                  "Verified court, bankruptcy and restricted-participant integrations.",
                )}
              </li>
              <li>
                {t(
                  "Richer ownership history and procurement behaviour analysis when supporting records are available.",
                )}
              </li>
              <li>
                {t(
                  "Independent evaluation and the operational work needed for a future pilot.",
                )}
              </li>
            </ul>
            <p>
              {t(
                "These plans do not establish findings about any company in the current workspace.",
              )}
            </p>
          </BorderGlow>
        </div>
      </section>

      <BorderGlow
        as="section"
        className="about-principles"
        aria-labelledby="about-principles-title"
        fillOpacity={0.06}
      >
        <div className="about-section-heading">
          <span className="about-section-index">
            {t("05 / HOW TO READ THE RESULT")}
          </span>
          <TechHeading
            as="h2"
            id="about-principles-title"
            text={t("Keep the evidence in view.")}
          />
        </div>
        <dl className="about-principle-grid">
          <div>
            <dt>{t("Inspect the source")}</dt>
            <dd>
              {t(
                "Use evidence, dates and coverage to understand what a connection means.",
              )}
            </dd>
          </div>
          <div>
            <dt>{t("Keep uncertainty visible")}</dt>
            <dd>
              {t(
                "An unavailable check is not a confirmed absence. Similar names alone do not establish identity.",
              )}
            </dd>
          </div>
          <div>
            <dt>{t("Return to saved versions")}</dt>
            <dd>
              {t(
                "Graphs and explanations share saved evidence. Opening a page does not regenerate them.",
              )}
            </dd>
          </div>
        </dl>
      </BorderGlow>

      <section className="about-project" aria-labelledby="about-project-title">
        <div>
          <span className="about-section-index">
            {t("A THESIS PROJECT WITH A FUTURE PILOT IN MIND")}
          </span>
          <TechHeading
            as="h2"
            id="about-project-title"
            text={t("Made to be examined.")}
          />
          <p>
            {t("Independently developed by")} {projectInfo.developer}{" "}
            {t("for a thesis at")} {projectInfo.university}.{" "}
            {projectInfo.articleAuthor}{" "}
            {t(
              "is preparing a related article. The repository is available for exploring the implementation and its documented limits.",
            )}
          </p>
        </div>
        <div className="about-project-links">
          <a
            className="button button-secondary"
            href={projectInfo.repositoryUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("View on GitHub")} <ArrowTopRightIcon aria-hidden="true" />
          </a>
          <a
            className="about-contact-link"
            href={`mailto:${projectInfo.email}`}
          >
            {t("Contact the developer")}{" "}
            <ArrowTopRightIcon aria-hidden="true" />
          </a>
          <a
            className="about-contact-link"
            href={`mailto:${projectInfo.articleEmail}`}
          >
            {t("Contact the article author")}{" "}
            <ArrowTopRightIcon aria-hidden="true" />
          </a>
        </div>
      </section>
    </div>
  );
}

export default About;
