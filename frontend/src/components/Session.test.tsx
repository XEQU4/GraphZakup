import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StrictMode, useState } from "react";
import { LoginDialog, SessionProvider, useSession } from "./Session";
import type { Session } from "../lib/types";

const anonymous: Session = {
  user: { id: null, username: null, role: "anonymous" },
  csrf_token: "anonymous-token",
  capabilities: { can_save_views: false, can_start_jobs: false },
};
const authenticated: Session = {
  user: { id: 12, username: "reviewer", role: "user" },
  csrf_token: "login-rotated-token",
  capabilities: { can_save_views: true, can_start_jobs: false },
};
function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function Probe() {
  const value = useSession();
  return (
    <div>
      <span data-testid="role">{value.user.role}</span>
      <span data-testid="csrf">{value.csrfToken ?? "none"}</span>
      <span data-testid="views">
        {String(value.capabilities.can_save_views)}
      </span>
      <span data-testid="jobs">
        {String(value.capabilities.can_start_jobs)}
      </span>
      <span data-testid="session-error">{value.error?.code ?? "none"}</span>
      <button
        onClick={() =>
          void value.login("reviewer", "test-password").catch(() => undefined)
        }
      >
        Test login
      </button>
      <button onClick={() => void value.logout().catch(() => undefined)}>
        Test logout
      </button>
      <button
        onClick={() =>
          void value
            .register({
              username: "new-reviewer",
              email: "reader@example.test",
              password: "strong-test-password",
              password_confirm: "strong-test-password",
            })
            .catch(() => undefined)
        }
      >
        Test registration
      </button>
      <button
        onClick={() =>
          void value
            .changePassword({
              current_password: "test-password",
              new_password: "strong-new-password",
              new_password_confirm: "strong-new-password",
            })
            .catch(() => undefined)
        }
      >
        Test password change
      </button>
      <button onClick={() => void value.refresh().catch(() => undefined)}>
        Test refresh
      </button>
    </div>
  );
}

describe("Django session state", () => {
  it("cancels the discarded StrictMode CSRF bootstrap rather than allowing its cookie response to win later", async () => {
    let resolveFirst!: (value: Response) => void;
    const first = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    const fetcher = vi
      .fn()
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce(response(anonymous));
    vi.stubGlobal("fetch", fetcher);
    const { unmount } = render(
      <StrictMode>
        <SessionProvider>
          <Probe />
        </SessionProvider>
      </StrictMode>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("csrf")).toHaveTextContent("anonymous-token"),
    );
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect((fetcher.mock.calls[0][1].signal as AbortSignal).aborted).toBe(true);
    expect((fetcher.mock.calls[1][1].signal as AbortSignal).aborted).toBe(
      false,
    );
    await act(async () =>
      resolveFirst(response({ ...anonymous, csrf_token: "discarded-token" })),
    );
    expect(screen.getByTestId("csrf")).toHaveTextContent("anonymous-token");
    unmount();
  });

  it("bootstraps with a read, uses CSRF on anonymous login, then rotates tokens on login and logout", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response(anonymous))
      .mockResolvedValueOnce(response(authenticated))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        response({ ...anonymous, csrf_token: "logout-rotated-token" }),
      );
    vi.stubGlobal("fetch", fetcher);
    const localStorage = vi.spyOn(Storage.prototype, "setItem");
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("csrf")).toHaveTextContent("anonymous-token"),
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe("/api/v1/session/");
    expect(fetcher.mock.calls[0][1].method).toBe("GET");
    fireEvent.click(screen.getByText("Test login"));
    await waitFor(() =>
      expect(screen.getByTestId("role")).toHaveTextContent("user"),
    );
    expect(fetcher.mock.calls[1][1].headers["X-CSRFToken"]).toBe(
      "anonymous-token",
    );
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({
      username: "reviewer",
      password: "test-password",
    });
    expect(screen.getByTestId("views")).toHaveTextContent("true");
    expect(screen.getByTestId("jobs")).toHaveTextContent("false");
    fireEvent.click(screen.getByText("Test logout"));
    await waitFor(() =>
      expect(screen.getByTestId("csrf")).toHaveTextContent(
        "logout-rotated-token",
      ),
    );
    expect(fetcher.mock.calls[2][1].headers["X-CSRFToken"]).toBe(
      "login-rotated-token",
    );
    expect(fetcher.mock.calls[2][1].body).toBeUndefined();
    expect(fetcher.mock.calls[3][1].method).toBe("GET");
    expect(screen.getByTestId("role")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("views")).toHaveTextContent("false");
    expect(localStorage).not.toHaveBeenCalled();
  });

  it("fails closed when bootstrap fails and never turns a failed login into an authenticated session", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(response(anonymous))
      .mockResolvedValueOnce(
        response(
          {
            error: {
              code: "invalid_credentials",
              message: "Invalid username or password.",
            },
          },
          403,
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("session-error")).toHaveTextContent(
        "network_error",
      ),
    );
    expect(screen.getByTestId("role")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("views")).toHaveTextContent("false");
    fireEvent.click(screen.getByText("Test login"));
    await waitFor(() =>
      expect(screen.getByTestId("session-error")).toHaveTextContent(
        "invalid_credentials",
      ),
    );
    expect(screen.getByTestId("role")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("jobs")).toHaveTextContent("false");
    expect(fetcher.mock.calls[2][1].headers["X-CSRFToken"]).toBe(
      "anonymous-token",
    );
  });

  it("ignores an older bootstrap response after a newer login succeeds", async () => {
    let resolveInitial!: (response: Response) => void;
    const initial = new Promise<Response>((resolve) => {
      resolveInitial = resolve;
    });
    const fetcher = vi
      .fn()
      .mockReturnValueOnce(initial)
      .mockResolvedValueOnce(response(anonymous))
      .mockResolvedValueOnce(response(authenticated));
    vi.stubGlobal("fetch", fetcher);
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    fireEvent.click(screen.getByText("Test login"));
    expect((fetcher.mock.calls[0][1].signal as AbortSignal).aborted).toBe(true);
    await waitFor(() =>
      expect(screen.getByTestId("role")).toHaveTextContent("user"),
    );
    await act(async () => resolveInitial(response(anonymous)));
    expect(screen.getByTestId("role")).toHaveTextContent("user");
    expect(screen.getByTestId("csrf")).toHaveTextContent("login-rotated-token");
  });

  it("clears local authority after a completed logout even when the anonymous re-bootstrap fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(authenticated))
        .mockResolvedValueOnce(new Response(null, { status: 204 }))
        .mockRejectedValueOnce(new TypeError("offline")),
    );
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("role")).toHaveTextContent("user"),
    );
    fireEvent.click(screen.getByText("Test logout"));
    await waitFor(() =>
      expect(screen.getByTestId("session-error")).toHaveTextContent(
        "network_error",
      ),
    );
    expect(screen.getByTestId("role")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("csrf")).toHaveTextContent("none");
    expect(screen.getByTestId("views")).toHaveTextContent("false");
  });
});

describe("accessible account dialog", () => {
  it("focuses the username and returns keyboard focus to the opener", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(anonymous)));
    function DialogProbe() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Open account</button>
          <LoginDialog open={open} onOpenChange={setOpen} />
        </>
      );
    }
    render(
      <SessionProvider>
        <DialogProbe />
      </SessionProvider>,
    );
    const opener = screen.getByRole("button", { name: "Open account" });
    opener.focus();
    fireEvent.click(opener);
    await waitFor(() =>
      expect(screen.getByLabelText("Username")).toHaveFocus(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Close sign-in dialog" }),
    );
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("labels fields and the modal, reports server errors, and clears the submitted password", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(anonymous))
        .mockResolvedValueOnce(
          response(
            {
              error: {
                code: "invalid_credentials",
                message: "Invalid username or password.",
              },
            },
            403,
          ),
        ),
    );
    const close = vi.fn();
    render(
      <SessionProvider>
        <LoginDialog open onOpenChange={close} />
      </SessionProvider>,
    );
    expect(
      screen.getByRole("dialog", { name: "Sign in to your workspace" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Sign in" }),
      ).not.toBeDisabled(),
    );
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "reviewer" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "test-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Invalid username or password.",
      ),
    );
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(close).not.toHaveBeenCalledWith(false);
    fireEvent.click(
      screen.getByRole("button", { name: "Close sign-in dialog" }),
    );
    expect(close).toHaveBeenCalledWith(false);
  });
});

describe("account registration and password rotation", () => {
  it("uses anonymous CSRF for registration, commits the returned session and keeps staff jobs unavailable", async () => {
    const registered = {
      ...authenticated,
      user: {
        id: 13,
        username: "new-reviewer",
        email: "reader@example.test",
        role: "user",
      },
      csrf_token: "registration-rotated-token",
    };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response(anonymous))
      .mockResolvedValueOnce(response(registered, 201));
    vi.stubGlobal("fetch", fetcher);
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("csrf")).toHaveTextContent("anonymous-token"),
    );
    fireEvent.click(screen.getByText("Test registration"));
    await waitFor(() =>
      expect(screen.getByTestId("csrf")).toHaveTextContent(
        "registration-rotated-token",
      ),
    );
    expect(fetcher.mock.calls[1][0]).toBe("/api/v1/session/register/");
    expect(fetcher.mock.calls[1][1].headers["X-CSRFToken"]).toBe(
      "anonymous-token",
    );
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({
      username: "new-reviewer",
      email: "reader@example.test",
      password: "strong-test-password",
      password_confirm: "strong-test-password",
    });
    expect(screen.getByTestId("role")).toHaveTextContent("user");
    expect(screen.getByTestId("jobs")).toHaveTextContent("false");
  });

  it("retains the authenticated session after changing a password and uses the rotated token for the next write", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response(authenticated))
      .mockResolvedValueOnce(
        response({ ...authenticated, csrf_token: "password-rotated-token" }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(response(anonymous));
    vi.stubGlobal("fetch", fetcher);
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("role")).toHaveTextContent("user"),
    );
    fireEvent.click(screen.getByText("Test password change"));
    await waitFor(() =>
      expect(screen.getByTestId("csrf")).toHaveTextContent(
        "password-rotated-token",
      ),
    );
    expect(fetcher.mock.calls[1][0]).toBe("/api/v1/account/password/");
    expect(fetcher.mock.calls[1][1].headers["X-CSRFToken"]).toBe(
      "login-rotated-token",
    );
    expect(screen.getByTestId("role")).toHaveTextContent("user");
    fireEvent.click(screen.getByText("Test logout"));
    await waitFor(() =>
      expect(screen.getByTestId("role")).toHaveTextContent("anonymous"),
    );
    expect(fetcher.mock.calls[2][1].headers["X-CSRFToken"]).toBe(
      "password-rotated-token",
    );
  });

  it("checks registration confirmation before a write and displays server field errors without keeping passwords", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response(anonymous))
      .mockResolvedValueOnce(
        response(
          {
            error: {
              code: "invalid_request",
              message: "Check the submitted fields.",
              details: { email: ["This email is already in use."] },
            },
          },
          400,
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    render(
      <SessionProvider>
        <LoginDialog open initialMode="register" onOpenChange={() => {}} />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Create account" }),
      ).not.toBeDisabled(),
    );
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "new-reviewer" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "reader@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "strong-test-password" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "different-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByText("Passwords do not match.")).toBeVisible();
    expect(fetcher).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "strong-test-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Email")).toHaveAttribute(
        "aria-invalid",
        "true",
      ),
    );
    expect(screen.getByText("This email is already in use.")).toBeVisible();
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(screen.getByLabelText("Confirm password")).toHaveValue("");
  });

  it("switches account tabs by keyboard and clears the password when switching modes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(anonymous)));
    render(
      <SessionProvider>
        <LoginDialog open onOpenChange={() => {}} />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Sign in" }),
      ).not.toBeDisabled(),
    );
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "temporary-secret" },
    });
    const tab = screen.getByRole("tab", { name: "Sign in" });
    tab.focus();
    fireEvent.keyDown(tab, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Sign up" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Sign up" })).toHaveFocus();
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(
      screen.getByRole("dialog", { name: "Create your IZ2 account" }),
    ).toBeVisible();
  });

  it("keeps an accepted auth result but never reopens a closed dialog or restores its secrets", async () => {
    let complete!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      complete = resolve;
    });
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response(anonymous))
      .mockReturnValueOnce(pending);
    vi.stubGlobal("fetch", fetcher);
    function DialogProbe() {
      const [open, setOpen] = useState(true);
      return (
        <>
          <Probe />
          <button onClick={() => setOpen(true)}>Reopen account</button>
          <LoginDialog open={open} onOpenChange={setOpen} />
        </>
      );
    }
    render(
      <SessionProvider>
        <DialogProbe />
      </SessionProvider>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Sign in" }),
      ).not.toBeDisabled(),
    );
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "reviewer" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "test-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Close sign-in dialog" }),
    );
    await act(async () => complete(response(authenticated)));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("role")).toHaveTextContent("user");
    fireEvent.click(screen.getByText("Reopen account"));
    expect(screen.getByLabelText("Username")).toHaveValue("");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });
});
