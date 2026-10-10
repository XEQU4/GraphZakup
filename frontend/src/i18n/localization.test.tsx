import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LanguageProvider,
  LanguageSwitch,
  LANGUAGE_STORAGE_KEY,
  getLanguage,
  setLanguage,
  translate,
} from ".";
import {
  formatCount,
  formatDate,
  formatDateTime,
  formatMoney,
} from "../lib/utils";
import { LoginDialog, SessionProvider } from "../components/Session";
import { translateAccountMessage } from "../lib/accountForms";

beforeEach(() => {
  setLanguage("en");
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  setLanguage("en");
});

describe("Language preference", () => {
  it("persists the choice, updates document language and follows another tab", () => {
    render(
      <LanguageProvider>
        <LanguageSwitch />
      </LanguageProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Switch to Russian" }));
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("ru");
    expect(document.documentElement.lang).toBe("ru");
    for (const unknown of ["constructor", "toString", "__proto__"])
      expect(translate(unknown)).toBe(unknown);
    expect(
      translate("Remove saved view for {name}", {
        name: "Original Company {name}",
      }),
    ).toBe("Удалить сохранённую раскладку: Original Company {name}");
    act(() => {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, "en");
      window.dispatchEvent(
        new StorageEvent("storage", { key: LANGUAGE_STORAGE_KEY }),
      );
    });
    expect(document.documentElement.lang).toBe("en");
    expect(
      screen.getByRole("button", { name: "Switch to Russian" }),
    ).toBeVisible();
  });
  it("keeps the switch usable when preference storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Blocked", "SecurityError");
    });
    render(
      <LanguageProvider>
        <LanguageSwitch />
      </LanguageProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Switch to Russian" }));
    expect(getLanguage()).toBe("ru");
    expect(document.documentElement.lang).toBe("ru");
    fireEvent.click(
      screen.getByRole("button", { name: "Переключить на английский" }),
    );
    expect(getLanguage()).toBe("en");
  });
});

describe("Business dates and exact amounts", () => {
  it.each(["en", "ru"] as const)(
    "keeps calendar dates and local midnight boundaries in %s",
    (language) => {
      setLanguage(language);
      expect(formatDate("2026-12-31T18:59:59Z")).toBe(formatDate("2026-12-31"));
      expect(formatDate("2026-12-31T19:00:00Z")).toBe(formatDate("2027-01-01"));
      expect(formatDate("2026-10-09T23:10:00-05:00")).toBe(
        formatDate("2026-10-10"),
      );
      expect(formatDateTime("2026-10-10T04:10:00Z")).toContain("09:10");
      expect(formatDate("2024-02-29")).not.toBe(translate("Not recorded"));
      expect(formatDate("2025-02-29")).toBe(translate("Not recorded"));
      expect(formatDate("2026-13-01")).toBe(translate("Not recorded"));
      expect(formatDate(null)).toBe(translate("Not recorded"));
    },
  );
  it("localizes separators without losing Decimal precision or modifying currency codes", () => {
    const value = "99999999999999999999.123400";
    expect(formatMoney(value)).toBe("99,999,999,999,999,999,999.123400 KZT");
    setLanguage("ru");
    expect(formatMoney(value)).toBe(
      "99\u00a0999\u00a0999\u00a0999\u00a0999\u00a0999\u00a0999,123400 KZT",
    );
    expect(formatMoney("-0.00")).toBe("0,00 KZT");
    expect(formatMoney(null)).toBe(translate("Not available"));
    expect(formatCount(12345)).toBe("12\u00a0345");
  });
});

describe("Account localization", () => {
  it("retains form values across language changes without another request", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user: { id: null, username: null, role: "anonymous" },
          csrf_token: "synthetic-token",
          capabilities: { can_save_views: false, can_start_jobs: false },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    render(
      <SessionProvider>
        <LoginDialog open initialMode="register" onOpenChange={() => {}} />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Username")).toBeEnabled(),
    );
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "original_reader" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "reader@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password", { exact: true }), {
      target: { value: "synthetic password" },
    });
    act(() => setLanguage("ru"));
    expect(screen.getByLabelText("Имя пользователя")).toHaveValue(
      "original_reader",
    );
    expect(screen.getByLabelText("Пароль", { exact: true })).toHaveValue(
      "synthetic password",
    );
    expect(screen.getByLabelText(translate("Email"))).toHaveValue(
      "reader@example.test",
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("translates compound validation messages at display time and preserves unknown errors", () => {
    const message =
      "This password is too short. It must contain at least 8 characters. This password is entirely numeric.";
    expect(translateAccountMessage(message)).toBe(message);
    setLanguage("ru");
    expect(translateAccountMessage(message)).toBe(
      "Пароль должен содержать не менее 8 символов. Пароль не должен состоять только из цифр.",
    );
    expect(translateAccountMessage("Unrecognised provider message")).toBe(
      "Unrecognised provider message",
    );
  });
});
