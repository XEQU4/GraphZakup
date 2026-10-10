import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { SessionProvider, useSession } from "../components/Session";
import { Profile } from "./Profile";
import type { AccountProfile, Session } from "../lib/types";

const session: Session = {
  user: {
    id: 14,
    username: "reader",
    email: "reader@example.test",
    role: "user",
  },
  capabilities: { can_save_views: true, can_start_jobs: false },
  csrf_token: "session-csrf",
};
const account: AccountProfile = {
  username: "reader",
  email: "reader@example.test",
  role: "user",
  date_joined: "2026-10-07T00:00:00Z",
};
const emptyViews = { count: 0, next: null, previous: null, results: [] };
function withEmptySavedViews(
  fetcher: (path: string, options: RequestInit) => Promise<Response> | Response,
) {
  return (path: string, options: RequestInit) =>
    path.startsWith("/api/v1/account/views/")
      ? Promise.resolve(response(emptyViews))
      : fetcher(path, options);
}
function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}
function SessionProbe() {
  const { user, csrfToken } = useSession();
  return (
    <>
      <span data-testid="profile-session-name">{user.username}</span>
      <span data-testid="profile-session-csrf">{csrfToken}</span>
    </>
  );
}
function renderProfile() {
  return render(
    <MemoryRouter>
      <SessionProvider>
        <SessionProbe />
        <Profile />
      </SessionProvider>
    </MemoryRouter>,
  );
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function fillPassword() {
  fireEvent.change(screen.getByLabelText("Current password"), {
    target: { value: "old-test-password" },
  });
  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: "new-strong-password" },
  });
  fireEvent.change(screen.getByLabelText("Confirm new password"), {
    target: { value: "new-strong-password" },
  });
}

describe("personal account profile", () => {
  it("loads the account privately, keeps email read-only and updates only username with CSRF", async () => {
    let currentAccount = { ...account };
    const fetcher = vi.fn(async (path: string, options: RequestInit) => {
      if (path === "/api/v1/session/")
        return response({
          ...session,
          user: { ...session.user, username: currentAccount.username },
        });
      if (path === "/api/v1/account/profile/" && options.method === "PATCH") {
        currentAccount = {
          ...currentAccount,
          ...JSON.parse(options.body as string),
        };
        return response(currentAccount);
      }
      if (path === "/api/v1/account/profile/") return response(currentAccount);
      throw new Error("Unexpected API request");
    });
    vi.stubGlobal("fetch", withEmptySavedViews(fetcher));
    renderProfile();
    await waitFor(() =>
      expect(screen.getByLabelText("Email")).toHaveValue("reader@example.test"),
    );
    expect(screen.getByLabelText("Email")).toHaveAttribute("readonly");
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "new-reader" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save username" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Your username has been saved.",
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("profile-session-name")).toHaveTextContent(
        "new-reader",
      ),
    );
    const patch = fetcher.mock.calls.find(
      ([, options]) => options.method === "PATCH",
    )!;
    expect(patch[0]).toBe("/api/v1/account/profile/");
    expect(JSON.parse(patch[1].body as string)).toEqual({
      username: "new-reader",
    });
    expect((patch[1].headers as Record<string, string>)["X-CSRFToken"]).toBe(
      "session-csrf",
    );
  });

  it("shows a rejected username on its field without changing the active session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, options: RequestInit) =>
        path.startsWith("/api/v1/account/views/")
          ? response(emptyViews)
          : path === "/api/v1/session/"
            ? response(session)
            : options.method === "PATCH"
              ? response(
                  {
                    error: {
                      message: "Check the submitted fields.",
                      code: "invalid_request",
                      details: {
                        username: ["This username is already in use."],
                      },
                    },
                  },
                  400,
                )
              : response(account),
      ),
    );
    renderProfile();
    await waitFor(() =>
      expect(screen.getByLabelText("Username")).toHaveValue("reader"),
    );
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "taken-reader" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save username" }));
    await waitFor(() =>
      expect(
        screen.getByText("This username is already in use."),
      ).toBeVisible(),
    );
    expect(screen.getByLabelText("Username")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByTestId("profile-session-name")).toHaveTextContent(
      "reader",
    );
  });

  it("rejects mismatched confirmation before a password write and clears all submitted secrets after a server rejection", async () => {
    const fetcher = vi.fn(async (path: string, options: RequestInit) =>
      path === "/api/v1/session/"
        ? response(session)
        : path === "/api/v1/account/password/"
          ? response(
              {
                error: {
                  message: "Check the submitted fields.",
                  code: "invalid_request",
                  details: {
                    current_password: ["Your current password is incorrect."],
                  },
                },
              },
              400,
            )
          : response(account),
    );
    vi.stubGlobal("fetch", withEmptySavedViews(fetcher));
    renderProfile();
    await waitFor(() =>
      expect(screen.getByLabelText("Username")).toHaveValue("reader"),
    );
    fillPassword();
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: "different-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    expect(screen.getByText("Passwords do not match.")).toBeVisible();
    expect(
      fetcher.mock.calls.filter(([, options]) => options.method === "POST"),
    ).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: "new-strong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    await waitFor(() =>
      expect(
        screen.getByText("Your current password is incorrect."),
      ).toBeVisible(),
    );
    expect(screen.getByLabelText("Current password")).toHaveValue("");
    expect(screen.getByLabelText("New password")).toHaveValue("");
    expect(screen.getByLabelText("Confirm new password")).toHaveValue("");
    expect(screen.getByTestId("profile-session-name")).toHaveTextContent(
      "reader",
    );
  });

  it("keeps the current session after a password change and signs out with its newly rotated CSRF", async () => {
    let signedIn = true;
    const fetcher = vi.fn(async (path: string, options: RequestInit) => {
      if (path === "/api/v1/session/")
        return response(
          signedIn
            ? session
            : {
                ...session,
                user: {
                  id: null,
                  username: null,
                  email: null,
                  role: "anonymous",
                },
                capabilities: { can_save_views: false, can_start_jobs: false },
                csrf_token: "anonymous-new-token",
              },
        );
      if (path === "/api/v1/account/profile/") return response(account);
      if (path === "/api/v1/account/password/")
        return response({ ...session, csrf_token: "password-new-token" });
      if (path === "/api/v1/session/logout/") {
        signedIn = false;
        return new Response(null, { status: 204 });
      }
      throw new Error("Unexpected API request");
    });
    vi.stubGlobal("fetch", withEmptySavedViews(fetcher));
    renderProfile();
    await waitFor(() =>
      expect(screen.getByLabelText("Username")).toHaveValue("reader"),
    );
    fillPassword();
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Password changed. You are still signed in here.",
      ),
    );
    expect(screen.getByTestId("profile-session-csrf")).toHaveTextContent(
      "password-new-token",
    );
    expect(screen.getByLabelText("Current password")).toHaveValue("");
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Your account starts here." }),
      ).toBeVisible(),
    );
    const write = fetcher.mock.calls.find(
      ([path]) => path === "/api/v1/session/logout/",
    )!;
    expect((write[1].headers as Record<string, string>)["X-CSRFToken"]).toBe(
      "password-new-token",
    );
  });

  it("does not request a profile for anonymous visitors and cancels an unfinished profile read on unmount", async () => {
    const anonymousFetcher = vi.fn().mockResolvedValue(
      response({
        ...session,
        user: { id: null, username: null, role: "anonymous" },
        capabilities: { can_save_views: false, can_start_jobs: false },
      }),
    );
    vi.stubGlobal("fetch", anonymousFetcher);
    const first = renderProfile();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Your account starts here." }),
      ).toBeVisible(),
    );
    expect(anonymousFetcher).toHaveBeenCalledTimes(1);
    first.unmount();
    const fetcher = vi.fn((path: string) =>
      path === "/api/v1/session/"
        ? Promise.resolve(response(session))
        : new Promise<Response>(() => {}),
    );
    vi.stubGlobal("fetch", withEmptySavedViews(fetcher));
    const second = renderProfile();
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    const read = fetcher.mock.calls[1] as unknown as [string, RequestInit];
    second.unmount();
    expect((read[1].signal as AbortSignal).aborted).toBe(true);
  });
});

describe("saved account graph views", () => {
  it("removes a saved view from the profile and refreshes the list", async () => {
    let removed = false;
    const fetcher = vi.fn(async (path: string, options: RequestInit) => {
      if (path === "/api/v1/session/") return response(session);
      if (path === "/api/v1/account/profile/") return response(account);
      if (options.method === "DELETE") {
        expect(path).toBe("/api/v1/clusters/" + uuid + "/view/");
        expect(JSON.parse(String(options.body))).toEqual({ revision: 4 });
        removed = true;
        return response({ revision: 5, payload: null });
      }
      return response(
        removed
          ? emptyViews
          : { ...emptyViews, count: 1, results: [savedView] },
      );
    });
    vi.stubGlobal("fetch", fetcher);
    renderProfile();
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Remove saved view for Synthetic shared director group",
      }),
    );
    await screen.findByText("No graph views saved yet.");
    expect(screen.getByRole("status")).toHaveTextContent("Saved view removed");
  });

  const uuid = "46b7d331-54f0-463a-b333-4f725e292ebc";
  const savedView = {
    cluster_uuid: uuid,
    cluster_name: "Synthetic shared director group",
    cluster_is_active: true,
    saved_snapshot_version: 2,
    current_snapshot_version: 3,
    revision: 4,
    updated_at: "2026-10-07T12:00:00Z",
  };

  it("reopens the exact saved graph version and offers the current graph only when a newer version exists", async () => {
    const fetcher = vi.fn(async (path: string) =>
      path === "/api/v1/session/"
        ? response(session)
        : path === "/api/v1/account/profile/"
          ? response(account)
          : response({ ...emptyViews, count: 1, results: [savedView] }),
    );
    vi.stubGlobal("fetch", fetcher);
    renderProfile();
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: "Open saved view" }),
      ).toBeVisible(),
    );
    expect(
      screen.getByRole("link", { name: "Open saved view" }),
    ).toHaveAttribute("href", "/clusters/" + uuid + "?version=2");
    expect(
      screen.getByRole("link", { name: "Open current graph" }),
    ).toHaveAttribute("href", "/clusters/" + uuid);
    expect(screen.getByText("Newer graph available")).toBeVisible();
    expect(screen.getByText("1 saved view")).toBeVisible();
    expect(fetcher.mock.calls.map(([path]) => path)).toContain(
      "/api/v1/account/views/?page=1&page_size=6",
    );
  });

  it("makes the first useful account action explicit when no view has been saved", async () => {
    const fetcher = vi.fn(async (path: string) =>
      path === "/api/v1/session/"
        ? response(session)
        : path === "/api/v1/account/profile/"
          ? response(account)
          : response(emptyViews),
    );
    vi.stubGlobal("fetch", fetcher);
    renderProfile();
    await waitFor(() =>
      expect(screen.getByText("No graph views saved yet.")).toBeVisible(),
    );
    expect(
      screen.getByText(
        /Open a relationship group, arrange or pin nodes, choose filters/,
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Explore relationship groups" }),
    ).toHaveAttribute("href", "/clusters");
    expect(screen.getByText(/on another browser or device/)).toBeVisible();
  });

  it("paginates private views with bounded reads and labels archived groups without implying new features", async () => {
    const fetcher = vi.fn(async (path: string, options: RequestInit) => {
      if (path === "/api/v1/session/") return response(session);
      if (path === "/api/v1/account/profile/") return response(account);
      return response({
        count: 7,
        next: null,
        previous: null,
        results: [
          {
            ...savedView,
            saved_snapshot_version: 3,
            current_snapshot_version: 3,
            cluster_name: path.includes("page=2")
              ? "Archived saved group"
              : "Current saved group",
            cluster_is_active: !path.includes("page=2"),
          },
        ],
      });
    });
    vi.stubGlobal("fetch", fetcher);
    renderProfile();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Current saved group" }),
      ).toBeVisible(),
    );
    expect(
      screen.queryByRole("link", { name: "Open current graph" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Archived saved group" }),
      ).toBeVisible(),
    );
    expect(screen.getByText("Archived group")).toBeVisible();
    expect(fetcher.mock.calls.map(([path]) => path)).toContain(
      "/api/v1/account/views/?page=2&page_size=6",
    );
    expect(
      fetcher.mock.calls.every(([, options]) => options.method === "GET"),
    ).toBe(true);
    expect(
      screen.getByRole("link", { name: "Open saved view" }),
    ).toHaveAttribute("href", "/clusters/" + uuid + "?version=3");
  });
});
