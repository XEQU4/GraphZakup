import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { About } from "./pages/About";
import WorkspaceFooter from "./components/WorkspaceFooter";
import { Pagination } from "./components/ui";
import { LanguageSwitch, setLanguage } from "./i18n";

vi.mock("./components/Session", () => ({
  useSession: () => ({
    session: {},
    user: { role: "anonymous" },
    loading: false,
  }),
  LoginDialog: () => null,
}));
vi.mock("./components/MotionPreferences", () => ({
  useMotionPreferences: () => ({
    enabled: false,
    reduced: true,
    toggle: vi.fn(),
  }),
}));
vi.mock("./components/effects/Particles", () => ({ default: () => null }));
vi.mock("./pages/Profile", () => ({
  default: () => <div>Profile fixture</div>,
}));

beforeEach(() => {
  act(() => setLanguage("en"));
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});
afterEach(() => {
  act(() => setLanguage("en"));
  vi.unstubAllGlobals();
});

it("changes shell titles and navigation without resetting the search or scrolling", async () => {
  render(
    <MemoryRouter initialEntries={["/profile"]}>
      <App />
    </MemoryRouter>,
  );
  await screen.findByText("Profile fixture");
  expect(document.title).toBe("Profile · IZ2");
  const search = screen.getByRole("textbox", { name: "Search companies" });
  fireEvent.change(search, { target: { value: "Исходное имя" } });
  vi.mocked(window.scrollTo).mockClear();
  fireEvent.click(screen.getByRole("button", { name: "Switch to Russian" }));
  expect(document.title).toBe("Профиль · IZ2");
  expect(screen.getByRole("textbox", { name: "Поиск компаний" })).toHaveValue(
    "Исходное имя",
  );
  expect(window.scrollTo).not.toHaveBeenCalled();
  const nav = screen.getByRole("navigation", { name: "Основная навигация" });
  expect(within(nav).getByRole("link", { name: /Компании/ })).toHaveAttribute(
    "href",
    "/companies",
  );
  fireEvent.click(screen.getByRole("button", { name: "Открыть меню" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  act(() => setLanguage("en"));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(document.title).toBe("Profile · IZ2");
  expect(window.scrollTo).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Close navigation" }));
});

it("translates About arrays and footer navigation while preserving authors and contacts", () => {
  act(() => setLanguage("ru"));
  render(
    <MemoryRouter>
      <About />
      <WorkspaceFooter />
    </MemoryRouter>,
  );
  expect(
    screen.getByRole("heading", { name: "Найдите участника" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Специалисты по проверке закупок" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Идентификаторы, контакты и происхождение сведений"),
  ).toBeInTheDocument();
  const footer = screen.getByRole("contentinfo");
  expect(
    within(footer).getByRole("heading", { name: "Разделы" }),
  ).toBeInTheDocument();
  expect(within(footer).getByText("Yestay Arnuruly")).toBeInTheDocument();
  expect(
    within(footer).getByRole("link", { name: "Estay-2020@bk.ru" }),
  ).toHaveAttribute("href", "mailto:Estay-2020@bk.ru");
  expect(
    within(footer).getByRole("link", { name: "Компании" }),
  ).toHaveAttribute("href", "/companies");
  expect(within(footer).getByText("React + TypeScript")).toBeInTheDocument();
});

it("localizes shared pagination as a full phrase and keeps actions intact", () => {
  const onPage = vi.fn();
  render(
    <>
      <LanguageSwitch />
      <Pagination page={2} total={1200} onPage={onPage} />
    </>,
  );
  expect(screen.getByText("26–50 of 1,200")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Switch to Russian" }));
  expect(screen.getByText(/26–50 из 1[\s,]200/)).toBeInTheDocument();
  expect(screen.getByText("Страница 2 из 48")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Следующая страница" }));
  expect(onPage).toHaveBeenCalledWith(3);
});
