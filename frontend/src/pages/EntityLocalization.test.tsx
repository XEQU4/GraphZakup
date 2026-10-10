import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LanguageSwitch, setLanguage } from "../i18n";
import { Companies, EntityPagination } from "./Companies";
import { People } from "./People";
import { CompanyDetail } from "./CompanyDetail";
import { Contracts } from "./Contracts";

const company = {
  id: 17,
  name: "Not recorded",
  bin: "000000000017",
  is_supplier: true,
  is_customer: false,
  address: "Адрес из источника",
  description: "Original source description",
  field_evidence: [
    {
      field: "name",
      source: "adata",
      status: "source_backed",
      observed_at: "2026-10-10",
      url: "https://example.test/company/17",
    },
    { field: "address", source: "legacy", status: "legacy", observed_at: null },
  ],
  kgd_checks: [
    {
      source: "kgd_taxpayer",
      status: "success",
      last_successful: {
        taxpayer_name: "Not recorded",
        taxpayer_type: "UL",
        stale: false,
        observed_at: "2026-10-10",
      },
    },
    { source: "kgd_tax_debt", status: "not_checked", last_successful: null },
  ],
};
let requests: URL[];
beforeEach(() => {
  act(() => setLanguage("en"));
  requests = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      expect(init?.method ?? "GET").toBe("GET");
      const url = new URL(input, "http://localhost");
      requests.push(url);
      const data = url.pathname.endsWith("/companies/17/")
        ? company
        : url.pathname.endsWith("/companies/")
          ? { count: 1, results: [company] }
          : url.pathname.endsWith("/people/")
            ? {
                count: 1,
                results: [
                  {
                    id: 23,
                    full_name: "АБДИР КАЙСАР",
                    identity_status: "identifier_verified",
                    role_context: {
                      companies: [company],
                      company_count: 1,
                      has_current_role: true,
                    },
                  },
                ],
              }
            : { count: 0, results: [] };
      return new Response(JSON.stringify(data), {
        headers: { "content-type": "application/json" },
      });
    }),
  );
});
afterEach(() => {
  act(() => setLanguage("en"));
  vi.unstubAllGlobals();
});

it("switches a directory in place without translating source names or changing its query", async () => {
  render(
    <MemoryRouter initialEntries={["/companies?search=Source&role=supplier"]}>
      <LanguageSwitch />
      <Companies />
    </MemoryRouter>,
  );
  await screen.findByRole("link", { name: "Open Not recorded" });
  fireEvent.change(
    screen.getByRole("textbox", { name: "Search companies by name or BIN" }),
    { target: { value: "Несохранённый запрос" } },
  );
  const countBeforeSwitch = requests.length;
  fireEvent.click(screen.getByRole("button", { name: "Switch to Russian" }));
  expect(
    screen.getByRole("textbox", { name: "Поиск компаний по названию или БИН" }),
  ).toHaveValue("Несохранённый запрос");
  expect(
    screen.getByRole("link", { name: "Открыть: Not recorded" }),
  ).toHaveAttribute("href", "/companies/17");
  expect(screen.getByText("Not recorded")).toBeInTheDocument();
  expect(screen.getByLabelText("Роль компании")).toHaveValue("supplier");
  expect(requests).toHaveLength(countBeforeSwitch);
  fireEvent.click(screen.getByRole("button", { name: "Найти" }));
  await waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("search")).toBe(
      "Несохранённый запрос",
    ),
  );
  expect(requests.at(-1)?.searchParams.get("is_supplier")).toBe("true");
  fireEvent.click(
    screen.getByRole("button", { name: "Переключить на английский" }),
  );
  expect(
    screen.getByRole("textbox", { name: "Search companies by name or BIN" }),
  ).toHaveValue("Несохранённый запрос");
});

it("keeps Russian profile registration, debt and provenance distinct", async () => {
  act(() => setLanguage("ru"));
  render(
    <MemoryRouter initialEntries={["/companies/17"]}>
      <Routes>
        <Route path="/companies/:id" element={<CompanyDetail />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "Not recorded" });
  expect(
    screen.getByRole("heading", { name: "Регистрация налогоплательщика" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Налоговая задолженность компании" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Не проверено")).toBeInTheDocument();
  expect(
    screen.getByText(/Текущая задолженность неизвестна/),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Прежняя запись · повторно не проверено"),
  ).toBeInTheDocument();
  expect(screen.getByText("Адрес из источника")).toBeInTheDocument();
  expect(screen.getByText("Original source description")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Adata" })).toHaveAttribute(
    "href",
    "https://example.test/company/17",
  );
  fireEvent.change(screen.getByLabelText("Компания выступает как"), {
    target: { value: "customer" },
  });
  await waitFor(() =>
    expect(
      requests.some(
        (url) =>
          url.pathname.endsWith("/contracts/") &&
          url.searchParams.get("customer_id") === "17",
      ),
    ).toBe(true),
  );
});

it("localizes people filters while preserving identifiers, names and canonical query values", async () => {
  act(() => setLanguage("ru"));
  render(
    <MemoryRouter>
      <People />
    </MemoryRouter>,
  );
  await screen.findByRole("link", { name: "Открыть: АБДИР КАЙСАР" });
  expect(screen.getByText("Идентификатор подтверждён")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Подтверждение личности"), {
    target: { value: "false" },
  });
  await waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("is_verified")).toBe("false"),
  );
  expect(requests.at(-1)?.searchParams.get("has_current_role")).toBe("true");
});

it("submits Russian contract date controls using unchanged ISO query values", async () => {
  act(() => setLanguage("ru"));
  render(
    <MemoryRouter>
      <Contracts />
    </MemoryRouter>,
  );
  await screen.findByText("По этим фильтрам контрактов нет");
  fireEvent.change(screen.getByLabelText("Дата контракта с"), {
    target: { value: "2026-10-01" },
  });
  fireEvent.change(screen.getByLabelText("Дата контракта по"), {
    target: { value: "2026-10-10" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Применить даты" }));
  await waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("date_to")).toBe("2026-10-10"),
  );
  expect(requests.at(-1)?.searchParams.get("date_from")).toBe("2026-10-01");
});

it("updates localized pagination without losing page actions", () => {
  const onPage = vi.fn();
  render(
    <>
      <LanguageSwitch />
      <EntityPagination page={2} pageSize={25} count={1200} onPage={onPage} />
    </>,
  );
  expect(screen.getByText("26–50 of 1,200 records")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Switch to Russian" }));
  expect(screen.getByText(/26–50 из 1\s200 записей/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Далее" }));
  expect(onPage).toHaveBeenCalledWith(3);
});
