import { act, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Home from "./Home";
import { setLanguage } from "../i18n";

const fixtures = vi.hoisted(() => ({
  groups: [] as {
    uuid: string;
    name: string;
    company_count: number;
    review_priority: number;
  }[],
}));

vi.mock("../components/MotionPreferences", () => ({
  useMotionPreferences: () => ({ enabled: false, reduced: true }),
}));
vi.mock("../lib/api", () => ({
  useApi: (path: string) => ({
    data:
      path === "overview/"
        ? {
            company_count: 813,
            checked_company_count: 257,
            people_count: 1476,
            current_verified_people_count: 73,
            verified_people_count: 106,
            contract_count: 525,
            active_group_count: 14,
            companies_with_kgd_records: 202,
            legacy_observation_count: 1661,
            latest_saved_observation_at: null,
          }
        : path.startsWith("clusters/")
          ? { count: fixtures.groups.length, results: fixtures.groups }
          : { count: 0, results: [] },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

afterEach(() => {
  act(() => setLanguage("en"));
  fixtures.groups = [];
  vi.unstubAllGlobals();
});
describe("overview directory counts", () => {
  it("uses a complete company-count label for Russian group cards", () => {
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    fixtures.groups = [2, 5, 21].map((count) => ({
      uuid: `group-${count}`,
      name: `Saved source title ${count}`,
      company_count: count,
      review_priority: 2,
    }));
    act(() => setLanguage("ru"));
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    for (const count of [2, 5, 21])
      expect(screen.getByText(`Компаний: ${count}`)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Saved source title 5" }),
    ).toBeInTheDocument();
    act(() => setLanguage("en"));
    expect(screen.getByText("5 companies")).toBeInTheDocument();
  });
  it("links scoped counts to default lists and separately labels raw identity coverage", () => {
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    const totals = screen.getByRole("region", { name: "Directory totals" });
    const company = within(totals).getByRole("link", { name: /Companies/ });
    const person = within(totals).getByRole("link", { name: /People/ });
    expect(company).toHaveAttribute("href", "/companies");
    expect(company).toHaveTextContent("257");
    expect(company).not.toHaveTextContent("813");
    expect(person).toHaveAttribute("href", "/people");
    expect(person).toHaveTextContent("73");
    expect(person).not.toHaveTextContent("1,476");
    expect(person).toHaveTextContent("Verified identities with current roles");
    const coverage = screen.getByRole("meter", {
      name: "Saved identity records",
    });
    expect(coverage).toHaveAttribute("aria-valuenow", "106");
    expect(coverage).toHaveAttribute("aria-valuemax", "1476");
    expect(
      screen.getByText(/including earlier and unverified entries/),
    ).toBeVisible();
  });
});
