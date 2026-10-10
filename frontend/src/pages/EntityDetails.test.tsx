import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { CompanyDetail, RoleSection } from "./CompanyDetail";
import { PersonDetail } from "./PersonDetail";

let reads: URL[];
const company = {
  id: 17,
  name: "Synthetic Example",
  bin: "000000000017",
  is_supplier: true,
  is_customer: true,
  address: "Synthetic address",
  phone: "123",
  created_at: "2026-10-01",
  updated_at: "2026-10-09",
  field_evidence: [
    {
      field: "name",
      source: "adata",
      status: "source_backed",
      observed_at: "2026-10-08",
      url: "https://example.test/record",
    },
    {
      field: "address",
      source: "legacy",
      status: "legacy",
      observed_at: null,
      url: null,
    },
  ],
  kgd_checks: [
    {
      source: "kgd_taxpayer",
      status: "success",
      source_url: "https://example.test/kgd",
      latest_observed_at: "2026-10-08",
      last_successful: {
        taxpayer_name: "Synthetic Example",
        taxpayer_type: "UL",
        stale: false,
        observed_at: "2026-10-08",
      },
    },
    {
      source: "kgd_tax_debt",
      status: "not_checked",
      source_url: "https://example.test/kgd",
      latest_observed_at: null,
      last_successful: null,
    },
  ],
};
beforeEach(() => {
  reads = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      expect(init?.method ?? "GET").toBe("GET");
      const url = new URL(input, "http://localhost");
      reads.push(url);
      const data = url.pathname.endsWith("/companies/17/")
        ? company
        : url.pathname.endsWith("/people/23/")
          ? {
              id: 23,
              full_name: "Synthetic Namesake",
              identity_status: "unverified",
              same_name_count: 2,
              pending_match_count: 1,
            }
          : { count: 0, results: [], next: null, previous: null };
      return new Response(JSON.stringify(data), {
        headers: { "content-type": "application/json" },
      });
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());
it("keeps saved ownership readable and does not hide source failures as empty data", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            count: 1,
            results: [
              {
                id: 1,
                company,
                person: { id: 23, full_name: "Synthetic recorded owner" },
                observed_name: "Synthetic recorded owner",
                is_current: true,
                identity_verified: false,
                source_reference: null,
                share_percent: "25.00",
              },
            ],
            next: null,
            previous: null,
          }),
          { headers: { "content-type": "application/json" } },
        ),
    ),
  );
  const mounted = render(
    <MemoryRouter>
      <RoleSection kind="ownerships" companyId="17" />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("link", { name: "Synthetic recorded owner" }),
  ).toBeInTheDocument();
  expect(screen.getByText("25.00%")).toBeInTheDocument();
  mounted.unmount();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response("{}", {
          status: 503,
          headers: { "content-type": "application/json" },
        }),
    ),
  );
  render(
    <MemoryRouter>
      <RoleSection kind="ownerships" companyId="17" />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("button", { name: "Try again" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("region", { name: "Ownership records" }),
  ).toBeInTheDocument();
});
function open(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/companies/:id" element={<CompanyDetail />} />
        <Route path="/people/:id" element={<PersonDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}
it("separates registration from unchecked debt and shows field provenance", async () => {
  open("/companies/17");
  expect(
    await screen.findByRole("heading", { name: "Synthetic Example" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Legacy record · not rechecked")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Adata" })).toHaveAttribute(
    "href",
    "https://example.test/record",
  );
  expect(
    screen.getByText(/Current arrears remain unknown/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/This check does not establish the absence of debt/),
  ).toBeInTheDocument();
  expect(screen.queryByText("KZT")).toBeNull();
  expect(screen.queryByText("Company size")).toBeNull();
  expect(screen.getByText("Synthetic address")).toBeInTheDocument();
  await waitFor(() =>
    expect(
      reads.some(
        (url) =>
          url.pathname.endsWith("/directorships/") &&
          url.searchParams.get("company_id") === "17" &&
          url.searchParams.get("is_current") === "true",
      ),
    ).toBe(true),
  );
  await waitFor(() =>
    expect(
      reads.some(
        (url) =>
          url.searchParams.get("company_id") === "17" &&
          url.pathname.endsWith("/clusters/"),
      ),
    ).toBe(true),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("region", { name: "Ownership records" }),
    ).toBeNull(),
  );
  expect(
    screen.getByText("What the current sources cover"),
  ).toBeInTheDocument();
});
it("switches contract role and role history without starting jobs", async () => {
  open("/companies/17?directors_page=3&owners_page=2");
  await screen.findByRole("heading", { name: "Synthetic Example" });
  fireEvent.change(screen.getByLabelText("Company acts as"), {
    target: { value: "customer" },
  });
  await waitFor(() =>
    expect(
      reads.some(
        (url) =>
          url.pathname.endsWith("/contracts/") &&
          url.searchParams.get("customer_id") === "17",
      ),
    ).toBe(true),
  );
  fireEvent.change(screen.getAllByLabelText("Show roles")[0], {
    target: { value: "historical" },
  });
  await waitFor(() =>
    expect(
      reads.some(
        (url) =>
          url.pathname.endsWith("/directorships/") &&
          url.searchParams.get("is_current") === "false" &&
          url.searchParams.get("page") === "1",
      ),
    ).toBe(true),
  );
});
it("explains separate identities and links search without merging names", async () => {
  open("/people/23");
  await screen.findByRole("heading", { name: "Synthetic Namesake" });
  expect(screen.getByText("Identity remains unverified")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Ownership" })).toBeNull();
  expect(screen.queryByText("Verified history not integrated")).toBeNull();
  expect(screen.getByText("What is not covered")).toBeInTheDocument();
  expect(
    screen.getByText(/Counts are records, not a count of distinct people/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Compare name search results" }),
  ).toHaveAttribute(
    "href",
    "/people?roles=all&is_verified=all&search=Synthetic%20Namesake",
  );
  await waitFor(() =>
    expect(
      reads.some(
        (url) =>
          url.searchParams.get("person_id") === "23" &&
          url.pathname.endsWith("/clusters/"),
      ),
    ).toBe(true),
  );
  expect(
    await screen.findByText(/No saved group includes this identity/),
  ).toBeInTheDocument();
});
