import { translate as t, useI18n } from "../i18n";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Cross2Icon,
  LockClosedIcon,
  ArrowRightIcon,
  CheckIcon,
  LayersIcon,
  PersonIcon,
} from "@radix-ui/react-icons";
import { ApiError, apiFetch, getJson } from "../lib/api";
import type {
  AccountRegistration,
  Capabilities,
  Session,
  SessionUser,
} from "../lib/types";
import {
  accountErrors,
  translateAccountMessage,
  type FieldErrors,
} from "../lib/accountForms";
import "./AccountDialog.css";
import { useDecorationActive } from "./motion/useDecorationActive";

const anonymousUser: SessionUser = {
  id: null,
  username: null,
  role: "anonymous",
};
const anonymousCapabilities: Capabilities = {
  can_save_views: false,
  can_start_jobs: false,
};

interface SessionContextValue {
  session: Session | null;
  user: SessionUser;
  capabilities: Capabilities;
  csrfToken: string | null;
  loading: boolean;
  error: ApiError | null;
  refresh: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  register: (details: AccountRegistration) => Promise<void>;
  changePassword: (details: {
    current_password: string;
    new_password: string;
    new_password_confirm: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  useI18n();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const sessionRef = useRef<Session | null>(null);
  const sequence = useRef(0);
  const mounted = useRef(true);
  const bootstrapAbort = useRef<AbortController | null>(null);

  const commit = useCallback((value: Session, request: number) => {
    if (mounted.current && request === sequence.current) {
      sessionRef.current = value;
      setSession(value);
      setError(null);
    }
  }, []);

  const failure = useCallback((value: unknown, request: number) => {
    if (mounted.current && request === sequence.current) {
      setError(
        value instanceof ApiError
          ? value
          : new ApiError("Session could not be updated."),
      );
    }
  }, []);

  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    bootstrapAbort.current?.abort();
    const abort = new AbortController();
    bootstrapAbort.current = abort;
    setLoading(true);
    try {
      commit(await getJson<Session>("session/", abort.signal), request);
    } catch (value) {
      failure(value, request);
      throw value;
    } finally {
      if (bootstrapAbort.current === abort) bootstrapAbort.current = null;
      if (mounted.current && request === sequence.current) setLoading(false);
    }
  }, [commit, failure]);

  useEffect(() => {
    mounted.current = true;
    void refresh().catch(() => undefined);
    return () => {
      mounted.current = false;
      sequence.current++;
      bootstrapAbort.current?.abort();
    };
  }, [refresh]);

  const login = useCallback(
    async (username: string, password: string) => {
      const request = ++sequence.current;
      // A discarded bootstrap also sets a cookie: abort it before rotating login CSRF.
      bootstrapAbort.current?.abort();
      bootstrapAbort.current = null;
      setLoading(true);
      setError(null);
      try {
        // An anonymous login also requires CSRF; bootstrap without retaining credentials.
        const current =
          sessionRef.current ?? (await getJson<Session>("session/"));
        const result = await apiFetch<Session>("session/login/", {
          method: "POST",
          body: { username, password },
          csrfToken: current.csrf_token,
        });
        commit(result, request);
      } catch (value) {
        failure(value, request);
        throw value;
      } finally {
        if (mounted.current && request === sequence.current) setLoading(false);
      }
    },
    [commit, failure],
  );

  const logout = useCallback(async () => {
    const request = ++sequence.current;
    bootstrapAbort.current?.abort();
    bootstrapAbort.current = null;
    setLoading(true);
    setError(null);
    try {
      const current = sessionRef.current;
      if (!current || current.user.role === "anonymous") return;
      await apiFetch<void>("session/logout/", {
        method: "POST",
        csrfToken: current.csrf_token,
      });
      // Logout rotates CSRF. Clear local authority before retrieving the new anonymous token.
      if (mounted.current && request === sequence.current) {
        sessionRef.current = null;
        setSession(null);
      }
      commit(await getJson<Session>("session/"), request);
    } catch (value) {
      failure(value, request);
      throw value;
    } finally {
      if (mounted.current && request === sequence.current) setLoading(false);
    }
  }, [commit, failure]);

  const register = useCallback(
    async (details: AccountRegistration) => {
      const request = ++sequence.current;
      bootstrapAbort.current?.abort();
      bootstrapAbort.current = null;
      setLoading(true);
      setError(null);
      try {
        const current =
          sessionRef.current ?? (await getJson<Session>("session/"));
        const result = await apiFetch<Session>("session/register/", {
          method: "POST",
          body: details,
          csrfToken: current.csrf_token,
        });
        commit(result, request);
      } catch (value) {
        failure(value, request);
        throw value;
      } finally {
        if (mounted.current && request === sequence.current) setLoading(false);
      }
    },
    [commit, failure],
  );

  const changePassword = useCallback(
    async (details: {
      current_password: string;
      new_password: string;
      new_password_confirm: string;
    }) => {
      const request = ++sequence.current;
      bootstrapAbort.current?.abort();
      bootstrapAbort.current = null;
      setLoading(true);
      setError(null);
      try {
        const result = await apiFetch<Session>("account/password/", {
          method: "POST",
          body: details,
          csrfToken: sessionRef.current?.csrf_token,
        });
        commit(result, request);
      } catch (value) {
        failure(value, request);
        throw value;
      } finally {
        if (mounted.current && request === sequence.current) setLoading(false);
      }
    },
    [commit, failure],
  );

  return (
    <SessionContext.Provider
      value={{
        session,
        user: session?.user ?? anonymousUser,
        capabilities: session?.capabilities ?? anonymousCapabilities,
        csrfToken: session?.csrf_token ?? null,
        loading,
        error,
        refresh,
        login,
        register,
        changePassword,
        logout,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context)
    throw new Error("useSession must be used within SessionProvider.");
  return context;
}

function AccountStory() {
  useI18n();
  const { ref, active } = useDecorationActive<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className="account-story"
      aria-hidden="true"
      data-active={active}
    >
      <span className="account-story-label">{t("YOUR IZ2 WORKSPACE")}</span>
      <div className="account-orbit">
        <span />
        <span />
        <span />
        <LayersIcon />
      </div>
      <h2>{t("Your view, saved.")}</h2>
      <p>
        {t(
          "Keep your graph layout in your account and reopen it on another browser or device.",
        )}
      </p>
      <span className="account-story-note">
        <CheckIcon /> {t("Node positions and zoom")}
      </span>
      <span className="account-story-note">
        <CheckIcon /> {t("Selected nodes and relationship filters")}
      </span>
    </div>
  );
}

export type AccountMode = "login" | "register";

export function LoginDialog({
  open,
  onOpenChange,
  initialMode = "login",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialMode?: AccountMode;
}) {
  useI18n();
  const { login, register, loading } = useSession();
  const [mode, setMode] = useState<AccountMode>(initialMode);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<FieldErrors>({});
  const [pending, setPending] = useState(false);
  const usernameInput = useRef<HTMLInputElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const queuedFocus = useRef(false);
  const generation = useRef(0);
  const busy = pending || loading;
  const registering = mode === "register";

  useEffect(() => {
    generation.current++;
    setMode(initialMode);
    setPassword("");
    setConfirmation("");
    setFields({});
    setError(null);
    setPending(false);
    if (!open) {
      setUsername("");
      setEmail("");
    }
    return () => {
      generation.current++;
    };
  }, [open, initialMode]);

  useEffect(() => {
    if (!open) queuedFocus.current = false;
    if (open && !busy && queuedFocus.current && usernameInput.current) {
      usernameInput.current.focus();
      queuedFocus.current = false;
    }
  }, [open, busy]);

  function switchMode(next: AccountMode) {
    if (busy || mode === next) return;
    setMode(next);
    setPassword("");
    setConfirmation("");
    setError(null);
    setFields({});
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setFields({});
    if (registering && password !== confirmation) {
      setFields({ password_confirm: "Passwords do not match." });
      setError("Check the highlighted field.");
      return;
    }
    const request = ++generation.current;
    setPending(true);
    try {
      if (registering) {
        await register({
          username: username.trim(),
          email: email.trim(),
          password,
          password_confirm: confirmation,
        });
      } else {
        await login(username.trim(), password);
      }
      if (request === generation.current) onOpenChange(false);
    } catch (value) {
      if (request === generation.current) {
        const result = accountErrors(
          value,
          registering
            ? "Could not create your account. Try again."
            : "Could not sign in. Try again.",
        );
        setError(result.message);
        setFields(result.fields);
      }
    } finally {
      if (request === generation.current) {
        setPassword("");
        setConfirmation("");
        setPending(false);
      }
    }
  }

  const fieldError = (name: string) =>
    fields[name] ? (
      <span className="account-field-error" id={"account-" + name + "-error"}>
        {translateAccountMessage(fields[name])}
      </span>
    ) : null;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="login-overlay account-overlay" />
        <Dialog.Content
          className="login-dialog account-dialog"
          onOpenAutoFocus={(event) => {
            returnFocus.current =
              document.activeElement instanceof HTMLElement
                ? document.activeElement
                : null;
            event.preventDefault();
            queuedFocus.current = true;
            if (usernameInput.current && !usernameInput.current.disabled) {
              usernameInput.current.focus();
              queuedFocus.current = false;
            }
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (returnFocus.current?.isConnected) returnFocus.current.focus();
          }}
        >
          <AccountStory />
          <div className="account-dialog-body">
            <div className="dialog-header">
              <span className="dialog-mark">
                <LockClosedIcon aria-hidden="true" />
              </span>
              <Dialog.Close
                className="icon-button"
                aria-label={
                  registering
                    ? t("Close sign-up dialog")
                    : t("Close sign-in dialog")
                }
              >
                <Cross2Icon aria-hidden="true" />
              </Dialog.Close>
            </div>
            <div
              className="account-tabs"
              role="tablist"
              aria-label={t("Account access")}
            >
              {(["login", "register"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  role="tab"
                  id={"account-tab-" + tab}
                  aria-selected={mode === tab}
                  aria-controls="account-form-panel"
                  tabIndex={mode === tab ? 0 : -1}
                  disabled={busy}
                  onClick={() => switchMode(tab)}
                  onKeyDown={(event) => {
                    if (
                      ["ArrowLeft", "ArrowRight", "Home", "End"].includes(
                        event.key,
                      )
                    ) {
                      event.preventDefault();
                      const next =
                        event.key === "Home"
                          ? "login"
                          : event.key === "End"
                            ? "register"
                            : mode === "login"
                              ? "register"
                              : "login";
                      switchMode(next);
                      document.getElementById("account-tab-" + next)?.focus();
                    }
                  }}
                >
                  {tab === "login" ? t("Sign in") : t("Sign up")}
                </button>
              ))}
            </div>
            <Dialog.Title>
              {registering
                ? t("Create your IZ2 account")
                : t("Sign in to your workspace")}
            </Dialog.Title>
            <Dialog.Description>
              {registering
                ? t(
                    "Save graph layouts to your account and reopen them on another browser or device.",
                  )
                : t(
                    "Restore your saved node positions, selection and relationship filters across browsers and devices.",
                  )}
            </Dialog.Description>
            <div
              id="account-form-panel"
              role="tabpanel"
              aria-labelledby={"account-tab-" + mode}
            >
              <form
                className="login-form account-form"
                onSubmit={submit}
                aria-busy={busy}
              >
                <label className="field" htmlFor="account-username">
                  {t("Username")}
                </label>
                <input
                  id="account-username"
                  ref={usernameInput}
                  name="username"
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  maxLength={150}
                  required
                  disabled={busy}
                  aria-invalid={Boolean(fields.username)}
                  aria-describedby={
                    fields.username ? "account-username-error" : undefined
                  }
                  placeholder={t("Your username")}
                />
                {fieldError("username")}
                {registering && (
                  <>
                    <label className="field" htmlFor="account-email">
                      {t("Email")}
                    </label>
                    <input
                      id="account-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      maxLength={254}
                      required
                      disabled={busy}
                      aria-invalid={Boolean(fields.email)}
                      aria-describedby={
                        fields.email
                          ? "account-email-error"
                          : "account-email-note"
                      }
                      placeholder={t("you@example.com")}
                    />
                    <span
                      className="account-field-note"
                      id="account-email-note"
                    >
                      {t(
                        "Your email stays private and cannot be changed here.",
                      )}
                    </span>
                    {fieldError("email")}
                  </>
                )}
                <label className="field" htmlFor="account-password">
                  {t("Password")}
                </label>
                <input
                  id="account-password"
                  name="password"
                  type="password"
                  autoComplete={
                    registering ? "new-password" : "current-password"
                  }
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={registering ? 8 : undefined}
                  maxLength={128}
                  required
                  disabled={busy}
                  aria-invalid={Boolean(fields.password)}
                  aria-describedby={
                    fields.password
                      ? "account-password-error"
                      : registering
                        ? "account-password-note"
                        : undefined
                  }
                  placeholder={
                    registering
                      ? t("Choose a strong password")
                      : t("Enter your password")
                  }
                />
                {registering && (
                  <span
                    id="account-password-note"
                    className="account-field-note"
                  >
                    {t(
                      "Use at least 8 characters. Avoid common passwords and personal details.",
                    )}
                  </span>
                )}
                {fieldError("password")}
                {registering && (
                  <>
                    <label className="field" htmlFor="account-password-confirm">
                      {t("Confirm password")}
                    </label>
                    <input
                      id="account-password-confirm"
                      name="password_confirm"
                      type="password"
                      autoComplete="new-password"
                      value={confirmation}
                      onChange={(event) => setConfirmation(event.target.value)}
                      minLength={8}
                      maxLength={128}
                      required
                      disabled={busy}
                      aria-invalid={Boolean(fields.password_confirm)}
                      aria-describedby={
                        fields.password_confirm
                          ? "account-password_confirm-error"
                          : undefined
                      }
                      placeholder={t("Enter your password again")}
                    />
                    {fieldError("password_confirm")}
                  </>
                )}
                {error && (
                  <p className="form-error" role="alert">
                    {translateAccountMessage(error)}
                  </p>
                )}
                <button
                  className="button button-primary"
                  type="submit"
                  disabled={busy}
                >
                  {busy
                    ? t("Connecting…")
                    : registering
                      ? t("Create account")
                      : t("Sign in")}
                  <ArrowRightIcon aria-hidden="true" />
                </button>
              </form>
            </div>
            <p className="dialog-footnote">
              <PersonIcon aria-hidden="true" />{" "}
              {registering
                ? t(
                    "Creating an account signs you in automatically. Guest views stay only in this browser.",
                  )
                : t(
                    "Without an account, saved graph views stay only in this browser. Sign up to keep them with your account.",
                  )}
            </p>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
