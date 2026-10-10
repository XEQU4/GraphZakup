import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ReviewPriority, SavedExplanation } from "./ClusterAnalysis";
import { setLanguage } from "../i18n";
import type {
  AnalysisSnapshot,
  Explanation,
  ExplanationDocument,
} from "../lib/types";

const document: ExplanationDocument = {
  version: "readable-explanation-5.2",
  summary: "Generic saved summary.",
  findings: [
    {
      finding_id: "f-director",
      title: "Shared director",
      fact: "Two companies list the same verified director.",
      details: ["Source address: Алматы, Достық 12"],
      meaning: "Generic prepared meaning.",
      companies: [{ id: 1, name: "Synthetic Riverstone", bin: "000000000001" }],
      additional_companies: 0,
      notes: ["Recorded dates must be checked."],
    },
  ],
  additional_findings: 0,
  checks: ["Generic saved check."],
  coverage: ["No successful current arrears checks are saved."],
  score: {
    value: 91,
    items: [{ finding_id: "f-director", label: "Shared director", points: 71 }],
    meaning: "Prepared rule interpretation.",
  },
  conclusion: "Generic saved conclusion.",
};
const explanation: Explanation = {
  id: 4,
  analysis_id: 2,
  text: "Original immutable text.\n\nOriginal second paragraph.",
  language: "en",
  provider: "template",
  model: "",
  prompt_version: "5.1",
  status: "ready",
  created_at: "2026-10-08T07:00:00Z",
  document: null,
};
const analysis: AnalysisSnapshot = {
  id: 2,
  version: 2,
  graph_snapshot_id: 2,
  graph_version: 2,
  analysis_hash: "a".repeat(64),
  rules_version: "review-rules-5.0",
  as_of: "2026-10-08",
  created_at: "2026-10-08T07:00:00Z",
  findings: [
    {
      id: "f-director",
      code: "shared_director",
      rule_version: "review-rules-5.0",
      company_ids: [1, 2],
      evidence: [],
      statements: ["Saved verified shared director."],
      candidate_contribution: 25,
      contribution: 25,
      dimension: "relationship",
      limitations: [],
    },
  ],
  limitations: [],
  metrics: {
    review_priority: 27,
    relationship_priority: 27,
    financial_priority: 0,
    link_strength: 95,
    behavioural_risk: null,
    behavioural_status: "not_assessable",
    company_count: 2,
    fresh_arrears_checks: 0,
    unknown_current_arrears: 2,
    retained_recent_arrears_results: 0,
    companies_with_fresh_arrears: [],
    score_interpretation: "uncalibrated_review_priority",
    stored_contract_count: 0,
    stored_contract_amount: "0.00",
    shared_customer_count: 0,
    score_categories: { director: 25, contacts: 2 },
    score_breakdown: [{ finding_id: "f-director", points: 25 }],
  },
};
afterEach(() => {
  cleanup();
  setLanguage("en");
  vi.unstubAllGlobals();
});
const show = (value: Explanation) =>
  render(
    <MemoryRouter>
      <SavedExplanation explanation={value} />
    </MemoryRouter>,
  );

describe("saved explanation presentation", () => {
  it("localizes controls while preserving immutable model prose, source names and open evidence", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const original = structuredClone(document);
    show({ ...explanation, document });
    fireEvent.click(screen.getByText("Saved evidence and facts"));
    act(() => setLanguage("ru"));
    expect(
      screen.getByRole("heading", { name: "Сохранённое резюме" }),
    ).toBeVisible();
    expect(
      screen.getByText(/Это объяснение сохранено на английском языке/),
    ).toBeVisible();
    expect(screen.getByText("Generic saved summary.")).toBeVisible();
    expect(
      screen.getByText("Two companies list the same verified director."),
    ).toBeVisible();
    expect(screen.getByText("Source address: Алматы, Достық 12")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Synthetic Riverstone" }),
    ).toBeVisible();
    expect(document).toEqual(original);
    expect(fetcher).not.toHaveBeenCalled();
    act(() => setLanguage("en"));
    expect(
      screen.getByRole("heading", { name: "Saved summary" }),
    ).toBeVisible();
    expect(
      screen.queryByText(/Это объяснение сохранено/),
    ).not.toBeInTheDocument();
  });
  it("identifies a rejected model answer as a saved template fallback", () => {
    show({
      ...explanation,
      provider: "ollama",
      model: "qwen3:4b",
      status: "fallback",
      document,
    });
    expect(screen.getByText("Saved template fallback")).toBeVisible();
    expect(
      screen.getByText(/Model generation did not produce an accepted answer/),
    ).toBeVisible();
    expect(
      screen.queryByText("Saved model-assisted summary"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("AI-written from saved facts"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Generic saved summary.")).toBeVisible();
  });

  it("preserves original legacy paragraphs without requesting generation", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    show(explanation);
    expect(screen.getByText("Original immutable text.")).toBeVisible();
    expect(screen.getByText("Original second paragraph.")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Saved summary" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "AI explanation" }),
    ).not.toBeInTheDocument();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("keeps existing structured documents readable with prepared summary and checks", () => {
    show({ ...explanation, document });
    expect(screen.getByText("Generic saved summary.")).toBeVisible();
    expect(screen.getByText("Generic saved check.")).toBeVisible();
    expect(
      screen.getByText("Two companies list the same verified director."),
    ).not.toBeVisible();
    fireEvent.click(screen.getByText("Saved evidence and facts"));
    expect(
      screen.getByText("Two companies list the same verified director."),
    ).toBeVisible();
    expect(screen.getByText("Source address: Алматы, Достық 12")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Synthetic Riverstone" }),
    ).toHaveAttribute("href", "/companies/1");
  });

  it("uses saved narrative and follow-up checks without repeating generic summary, and opens cited facts", () => {
    const narrative = {
      paragraphs: [
        {
          text: "Synthetic Riverstone shares a verified director with another company; check who makes their bidding decisions.",
          finding_ids: ["f-director", "unknown-id"],
        },
      ],
      checks: [
        {
          text: "Compare the recorded director dates with the tenders under review.",
          finding_ids: ["f-director"],
        },
      ],
    };
    const { container } = show({
      ...explanation,
      provider: "ollama",
      model: "qwen3:4b",
      document: { ...document, narrative },
    });
    expect(
      screen.getByRole("heading", { name: "AI explanation" }),
    ).toBeVisible();
    expect(screen.getByText(narrative.paragraphs[0].text)).toBeVisible();
    expect(screen.getByText(narrative.checks[0].text)).toBeVisible();
    expect(
      screen.queryByText("Generic saved summary."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Generic saved check.")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Generic saved conclusion."),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Generic prepared meaning.")).not.toBeVisible();
    const citations = screen.getAllByRole("link", {
      name: "Read evidence for Shared director",
    });
    expect(citations).toHaveLength(2);
    expect(citations[0]).toHaveAttribute(
      "href",
      "#explanation-finding-f-director",
    );
    fireEvent.click(citations[0]);
    expect(container.querySelector(".explanation-saved-facts")).toHaveAttribute(
      "open",
    );
    expect(
      screen.getByText("Two companies list the same verified director."),
    ).toBeVisible();
    expect(screen.queryByText("unknown-id")).not.toBeInTheDocument();
    expect(screen.getAllByText("ollama · qwen3:4b")[0]).toBeVisible();
  });

  it("renders model text and original source values as escaped text, never HTML", () => {
    const untrusted = "<img src=x onerror=alert(1)>";
    const { container } = show({
      ...explanation,
      document: {
        ...document,
        narrative: {
          paragraphs: [{ text: untrusted, finding_ids: [] }],
          checks: [],
        },
      },
    });
    expect(screen.getByText(untrusted)).toBeVisible();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });
});

describe("rule-priority presentation", () => {
  it("uses saved rule scores and credits even when an explanation contains different values", () => {
    const { container } = render(
      <MemoryRouter>
        <ReviewPriority
          analysis={analysis}
          explanation={{ ...explanation, document }}
          companies={[
            {
              id: "company:1",
              kind: "company",
              name: "Synthetic Riverstone",
              company_id: 1,
            },
          ]}
          loading={false}
          unavailable={false}
        >
          <details>
            <summary>Method and version history</summary>
          </details>
        </ReviewPriority>
      </MemoryRouter>,
    );
    expect(container.querySelector(".priority-score")).toHaveTextContent(
      "27/100",
    );
    expect(
      container.querySelector(".priority-contributions"),
    ).toHaveTextContent("+25 points");
    expect(container.querySelector(".priority-score")).not.toHaveTextContent(
      "91",
    );
    expect(
      container.querySelector(".priority-contributions"),
    ).not.toHaveTextContent("+71");
    expect(screen.getByText("Not assessable")).toBeVisible();
    expect(
      screen.getByText(/not a percentage chance of wrongdoing/),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Synthetic Riverstone" }),
    ).toHaveAttribute("href", "/companies/1");
  });

  it("distinguishes an unavailable read from a missing saved calculation", () => {
    const { rerender } = render(
      <MemoryRouter>
        <ReviewPriority
          analysis={null}
          explanation={null}
          companies={[]}
          loading={false}
          unavailable
          children={null}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("Score unavailable")).toBeVisible();
    expect(screen.queryByText("Not calculated")).not.toBeInTheDocument();
    rerender(
      <MemoryRouter>
        <ReviewPriority
          analysis={null}
          explanation={null}
          companies={[]}
          loading={false}
          unavailable={false}
          children={null}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("Not calculated")).toBeVisible();
  });
});
