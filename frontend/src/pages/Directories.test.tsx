import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Companies } from "./Companies";
import { People } from "./People";
import { Contracts } from "./Contracts";
import type { Company, Contract, Person } from "../lib/types";

const company: Company = {
  id: 17,
  name: "Synthetic <North> Services",
  bin: "000000000017",
  is_supplier: true,
  is_customer: false,
  city: "Synthetic City",
  region: "Synthetic Region",
  legacy_risk_score: 0,
  legacy_score_interpretation: "legacy",
};
const person: Person = {
  id: 23,
  full_name: "Synthetic Jordan Example",
  is_verified: false,
  identity_status: "unverified",
  history_status: "not_integrated",
};
const contract: Contract = {
  id: 31,
  contract_number: "SYN-31",
  contract_gos_id: null,
  tender_id: "SYN-TENDER",
  title: "Synthetic procurement record",
  amount: "9007199254740993.37",
  contract_date: "2026-10-01",
  winner: false,
  supplier: company,
  customer: null,
  customer_name: "Synthetic customer",
  customer_bin: "",
  source_url: "https://example.com/synthetic-source",
  source_observation_id: null,
  created_at: "2026-10-07T10:00:00Z",
};
let reads: URL[];
beforeEach(() => {
  reads = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      expect(init?.method ?? "GET").toBe("GET");
      const url = new URL(input, "http://localhost");
      reads.push(url);
      const results = url.pathname.includes("/contracts/")
        ? [contract]
        : url.pathname.includes("/people/")
          ? url.searchParams.get("is_verified") === "true"
            ? []
            : [person]
          : [company];
      return new Response(
        JSON.stringify({
          count: results.length ? 51 : 0,
          results,
          next: null,
          previous: null,
        }),
        { headers: { "content-type": "application/json" } },
      );
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe("directory presentation preserves saved-data actions", () => {
  it("keeps native company links and resets pagination when applying a role or search", async () => {
    render(
      <MemoryRouter initialEntries={["/companies?role=supplier&page=2"]}>
        <Companies />
      </MemoryRouter>,
    );
    const results = await screen.findByRole("region", {
      name: "Companies results",
    });
    expect(within(results).getByRole("table")).toBeInTheDocument();
    expect(
      within(results).getByRole("link", {
        name: /Synthetic <North> Services.*000000000017/,
      }),
    ).toHaveAttribute("href", "/companies/17");
    expect(results.querySelector("north")).toBeNull();
    expect(reads[0].searchParams.get("page")).toBe("2");
    expect(reads[0].searchParams.get("is_supplier")).toBe("true");

    fireEvent.change(screen.getByRole("combobox", { name: "Company role" }), {
      target: { value: "customer" },
    });
    await waitFor(() => {
      expect(reads.at(-1)?.searchParams.get("is_customer")).toBe("true");
      expect(reads.at(-1)?.searchParams.get("page")).toBe("1");
    });
    const search = screen.getByRole("textbox", {
      name: "Search companies by name or BIN",
    });
    fireEvent.change(search, { target: { value: " 000000000017 " } });
    fireEvent.submit(search.closest("form")!);
    await waitFor(() =>
      expect(reads.at(-1)?.searchParams.get("search")).toBe("000000000017"),
    );
  });

  it("keeps identity uncertainty visible and does not invent verified people", async () => {
    render(
      <MemoryRouter initialEntries={["/people"]}>
        <People />
      </MemoryRouter>,
    );
    const results = await screen.findByRole("region", {
      name: "People results",
    });
    expect(
      within(results).getByText("Unverified identity"),
    ).toBeInTheDocument();
    expect(
      within(results).getByText("Verified history not integrated"),
    ).toBeInTheDocument();
    expect(
      within(results).getByRole("link", {
        name: "Open Synthetic Jordan Example",
      }),
    ).toHaveAttribute("href", "/people/23");
    fireEvent.change(
      screen.getByRole("combobox", { name: "Identity verification filter" }),
      { target: { value: "true" } },
    );
    expect(
      await screen.findByText("No saved identities match"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "People results" })).toBeNull();
  });

  it("preserves exact money, source disclosure and date filters in contract cards", async () => {
    render(
      <MemoryRouter initialEntries={["/contracts"]}>
        <Contracts />
      </MemoryRouter>,
    );
    const results = await screen.findByRole("region", {
      name: "Contracts results",
    });
    const amount = results.querySelector("[data-label='Amount, KZT']");
    expect(amount?.textContent?.replace(/[\s,]/g, "")).toBe(
      "9007199254740993.37",
    );
    const disclosure = within(results).getByText("Record details");
    fireEvent.click(disclosure);
    expect(disclosure.closest("details")).toHaveAttribute("open");
    expect(
      within(results).getByRole("link", { name: "Procurement source" }),
    ).toHaveAttribute("href", "https://example.com/synthetic-source");
    fireEvent.change(screen.getByLabelText("Contract date from"), {
      target: { value: "2026-10-01" },
    });
    fireEvent.change(screen.getByLabelText("Contract date to"), {
      target: { value: "2026-10-07" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply dates" }));
    await waitFor(() => {
      expect(reads.at(-1)?.searchParams.get("date_from")).toBe("2026-10-01");
      expect(reads.at(-1)?.searchParams.get("date_to")).toBe("2026-10-07");
      expect(reads.at(-1)?.searchParams.get("page")).toBe("1");
    });
  });
});
