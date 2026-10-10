import { translate as t, useI18n } from "../i18n";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRightIcon,
  CheckCircledIcon,
  ExitIcon,
  LayersIcon,
  LockClosedIcon,
  Pencil1Icon,
  PersonIcon,
  ReloadIcon,
  BookmarkIcon,
  Cross2Icon,
} from "@radix-ui/react-icons";
import { useSession } from "../components/Session";
import { BorderGlow } from "../components/design/BorderGlow";
import { TechHeading } from "../components/motion/TechHeading";
import { PageState, Pagination } from "../components/ui";
import {
  accountErrors,
  translateAccountMessage,
  type FieldErrors,
} from "../lib/accountForms";
import {
  apiFetch,
  formatCount,
  formatDate,
  formatDateTime,
  queryPath,
  useApi,
} from "../lib/api";
import type { AccountProfile, AccountSavedView, Paginated } from "../lib/types";
import "./Profile.css";

function SavedGraphViews() {
  useI18n();
  const { csrfToken, user } = useSession();
  const [page, setPage] = useState(1);
  const [removing, setRemoving] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const pending = useRef<AbortController | null>(null);
  useEffect(
    () => () => {
      pending.current?.abort();
    },
    [user.id],
  );
  const views = useApi<Paginated<AccountSavedView>>(
    queryPath("account/views/", { page, page_size: 6 }),
  );
  async function remove(view: AccountSavedView) {
    if (pending.current) return;
    const abort = new AbortController();
    pending.current = abort;
    setRemoving(view.cluster_uuid);
    setNotice("");
    try {
      await apiFetch("clusters/" + view.cluster_uuid + "/view/", {
        method: "DELETE",
        csrfToken,
        signal: abort.signal,
        body: { revision: view.revision },
      });
      if (abort.signal.aborted) return;
      setNotice(
        "Saved view removed. The group is still available in Relationship groups.",
      );
      if (page > 1 && views.data?.results.length === 1) setPage(page - 1);
      else views.reload();
    } catch (error) {
      if (!abort.signal.aborted)
        setNotice(
          error instanceof Error
            ? error.message + " Refresh saved views before trying again."
            : "Could not remove this view. Refresh and try again.",
        );
    } finally {
      if (pending.current === abort) pending.current = null;
      if (!abort.signal.aborted) setRemoving(null);
    }
  }
  return (
    <section
      className="profile-saved-views"
      aria-labelledby="profile-saved-title"
    >
      <div className="profile-saved-heading">
        <div>
          <span className="eyebrow">{t("SAVED TO YOUR ACCOUNT")}</span>
          <h2 id="profile-saved-title">{t("Your graph views")}</h2>
          <p>
            {t(
              "Reopen the last view you saved for each group, including node positions, zoom, selection and filters.",
            )}
          </p>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={views.reload}
          disabled={views.loading}
          aria-label={t("Refresh saved graph views")}
        >
          <ReloadIcon aria-hidden="true" /> {t("Refresh")}
        </button>
      </div>
      <PageState
        loading={views.loading && !views.data}
        error={views.error}
        onRetry={views.reload}
      />
      {notice && (
        <p role="status" className="profile-view-notice">
          {translateAccountMessage(notice)}
        </p>
      )}
      {views.data &&
        !views.error &&
        (views.data.count === 0 ? (
          <div className="profile-views-empty">
            <span className="profile-panel-icon">
              <BookmarkIcon aria-hidden="true" />
            </span>
            <div>
              <h3>{t("No graph views saved yet.")}</h3>
              <p>
                {t(
                  "Open a relationship group, arrange or pin nodes, choose filters, then click",
                )}{" "}
                <strong>{t("Save view")}</strong>
                {t(
                  ". Return here to reopen it on any browser or device where you sign in.",
                )}
              </p>
              <Link className="button button-primary" to="/clusters">
                {t("Explore relationship groups")}{" "}
                <ArrowRightIcon aria-hidden="true" />
              </Link>
            </div>
          </div>
        ) : (
          <>
            <div className="profile-view-list">
              {views.data.results.map((view) => (
                <BorderGlow
                  as="article"
                  key={view.cluster_uuid}
                  className="profile-view-card"
                  borderRadius={17}
                  fillOpacity={0.08}
                >
                  <div className="profile-view-label">
                    <span>
                      <LayersIcon aria-hidden="true" /> {t("Graph v")}
                      {view.saved_snapshot_version}
                    </span>
                    {!view.cluster_is_active ? (
                      <span className="profile-view-status">
                        {t("Archived group")}
                      </span>
                    ) : view.current_snapshot_version !== null &&
                      view.current_snapshot_version !==
                        view.saved_snapshot_version ? (
                      <span className="profile-view-status">
                        {t("Newer graph available")}
                      </span>
                    ) : null}
                  </div>
                  <h3>{view.cluster_name}</h3>
                  <p>
                    {t("Saved")} {formatDateTime(view.updated_at)}
                  </p>
                  <div className="profile-view-actions">
                    <button
                      type="button"
                      className="button button-quiet"
                      disabled={removing !== null || views.loading}
                      aria-label={t("Remove saved view for {name}", {
                        name: view.cluster_name,
                      })}
                      onClick={() => void remove(view)}
                    >
                      <Cross2Icon aria-hidden="true" />
                      {removing === view.cluster_uuid
                        ? t("Removing…")
                        : t("Remove")}
                    </button>
                    <Link
                      className="button button-secondary"
                      to={
                        "/clusters/" +
                        view.cluster_uuid +
                        "?version=" +
                        view.saved_snapshot_version
                      }
                    >
                      {t("Open saved view")}{" "}
                      <ArrowRightIcon aria-hidden="true" />
                    </Link>
                    {view.current_snapshot_version !== null &&
                      view.current_snapshot_version !==
                        view.saved_snapshot_version && (
                        <Link
                          className="profile-current-graph"
                          to={"/clusters/" + view.cluster_uuid}
                        >
                          {t("Open current graph")}{" "}
                          <ArrowRightIcon aria-hidden="true" />
                        </Link>
                      )}
                  </div>
                </BorderGlow>
              ))}
            </div>
            <div className="profile-view-pagination">
              <span>
                {t(
                  views.data.count === 1
                    ? "{count} saved view"
                    : "{count} saved views",
                  { count: formatCount(views.data.count) },
                )}
              </span>
              {views.data.count > 6 && (
                <Pagination
                  page={page}
                  total={views.data.count}
                  pageSize={6}
                  onPage={setPage}
                />
              )}
            </div>
          </>
        ))}
    </section>
  );
}

export function Profile() {
  useI18n();
  const { user, loading, csrfToken, refresh, changePassword, logout } =
    useSession();
  const profile = useApi<AccountProfile>(
    user.role === "anonymous" ? null : "account/profile/",
  );
  const [username, setUsername] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState<
    "username" | "password" | "logout" | null
  >(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [nameFields, setNameFields] = useState<FieldErrors>({});
  const [passwordFields, setPasswordFields] = useState<FieldErrors>({});
  const [nameSaved, setNameSaved] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const version = useRef(0);
  const busy = loading || pending !== null;

  useEffect(() => {
    if (profile.data) setUsername(profile.data.username);
  }, [profile.data?.username]);
  useEffect(
    () => () => {
      version.current++;
    },
    [],
  );

  async function saveUsername(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const request = ++version.current;
    setPending("username");
    setNameError(null);
    setNameFields({});
    setNameSaved(false);
    try {
      await apiFetch<AccountProfile>("account/profile/", {
        method: "PATCH",
        csrfToken,
        body: { username: username.trim() },
      });
      await refresh();
      if (request === version.current) {
        profile.reload();
        setNameSaved(true);
      }
    } catch (value) {
      if (request === version.current) {
        const result = accountErrors(
          value,
          "Your username could not be saved.",
        );
        setNameError(result.message);
        setNameFields(result.fields);
      }
    } finally {
      if (request === version.current) setPending(null);
    }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setPasswordError(null);
    setPasswordFields({});
    setPasswordSaved(false);
    if (newPassword !== confirmation) {
      setPasswordFields({ new_password_confirm: "Passwords do not match." });
      setPasswordError("Check the highlighted field.");
      return;
    }
    const request = ++version.current;
    setPending("password");
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: confirmation,
      });
      if (request === version.current) setPasswordSaved(true);
    } catch (value) {
      if (request === version.current) {
        const result = accountErrors(
          value,
          "Your password could not be changed.",
        );
        setPasswordError(result.message);
        setPasswordFields(result.fields);
      }
    } finally {
      if (request === version.current) {
        setCurrentPassword("");
        setNewPassword("");
        setConfirmation("");
        setPending(null);
      }
    }
  }

  async function signOut() {
    if (busy) return;
    const request = ++version.current;
    setPending("logout");
    setLogoutError(null);
    try {
      await logout();
    } catch (value) {
      if (request === version.current)
        setLogoutError(
          value instanceof Error
            ? value.message
            : "Sign out failed. Try again.",
        );
    } finally {
      if (request === version.current) setPending(null);
    }
  }

  if (loading && !profile.data) return <PageState loading />;
  if (user.role === "anonymous")
    return (
      <div className="profile-page profile-signed-out">
        <span className="eyebrow">{t("PERSONAL WORKSPACE")}</span>
        <TechHeading as="h1" text={t("Your account starts here.")} />
        <p>
          {t(
            "Sign in or create an account to keep graph positions, selected nodes and relationship filters across browsers and devices. Guest views stay only in this browser.",
          )}
        </p>
        <Link to="/" className="button button-secondary">
          {t("Back to overview")} <ArrowRightIcon aria-hidden="true" />
        </Link>
      </div>
    );
  if (!profile.data)
    return (
      <PageState
        loading={profile.loading}
        error={profile.error}
        onRetry={profile.reload}
      />
    );
  const account = profile.data;
  const passwordErrorNote = (name: string) =>
    passwordFields[name] ? (
      <span className="account-field-error" id={"profile-" + name + "-error"}>
        {translateAccountMessage(passwordFields[name])}
      </span>
    ) : null;

  return (
    <div className="profile-page">
      <div className="profile-heading">
        <div>
          <span className="eyebrow">{t("PERSONAL WORKSPACE")}</span>
          <TechHeading as="h1" text={t("Your saved workspace.")} />
          <p>
            {t(
              "Save a graph view once. Reopen its positions, selected node and filters on another browser or device.",
            )}
          </p>
        </div>
        <span className="profile-account-label">
          <PersonIcon aria-hidden="true" />{" "}
          {account.role === "staff"
            ? t("Staff account")
            : t("Personal account")}
        </span>
      </div>
      <div className="profile-overview">
        <span className="profile-current-name">{user.username}</span>
        <span>
          <CheckCircledIcon aria-hidden="true" /> {t("Signed in")}
        </span>
        <span>
          {t("Joined")} {formatDate(account.date_joined)}
        </span>
        <Link to="/clusters">
          <LayersIcon aria-hidden="true" /> {t("Explore saved groups")}{" "}
          <ArrowRightIcon aria-hidden="true" />
        </Link>
      </div>
      <SavedGraphViews />
      <div className="profile-grid">
        <BorderGlow
          as="section"
          className="profile-panel"
          borderRadius={22}
          fillOpacity={0.08}
        >
          <div className="profile-panel-heading">
            <span className="profile-panel-icon">
              <Pencil1Icon aria-hidden="true" />
            </span>
            <div>
              <h2>{t("Account details")}</h2>
              <p>
                {t("A name for your workspace. An email for your account.")}
              </p>
            </div>
          </div>
          <form
            className="profile-form"
            onSubmit={saveUsername}
            aria-busy={pending === "username"}
          >
            <label className="profile-field" htmlFor="profile-username">
              <span>{t("Username")}</span>
              <input
                id="profile-username"
                name="username"
                value={username}
                onChange={(event) => {
                  setUsername(event.target.value);
                  setNameSaved(false);
                }}
                maxLength={150}
                autoComplete="username"
                required
                disabled={busy}
                aria-invalid={Boolean(nameFields.username)}
                aria-describedby={
                  nameFields.username ? "profile-username-error" : undefined
                }
              />
            </label>
            {nameFields.username && (
              <span className="account-field-error" id="profile-username-error">
                {translateAccountMessage(nameFields.username)}
              </span>
            )}
            <label className="profile-field" htmlFor="profile-email">
              <span>
                {t("Email")} <LockClosedIcon aria-hidden="true" />
              </span>
              <input
                id="profile-email"
                value={account.email}
                type={account.email ? "email" : "text"}
                placeholder={t("No email recorded for this account")}
                readOnly
                aria-describedby="profile-email-note"
              />
            </label>
            <span id="profile-email-note" className="profile-helper">
              {t(
                "Your email is read-only. Only your username can be updated here.",
              )}
            </span>
            {nameError && (
              <p className="form-error" role="alert">
                {translateAccountMessage(nameError)}
              </p>
            )}
            {nameSaved && (
              <p className="profile-success" role="status">
                <CheckCircledIcon aria-hidden="true" />{" "}
                {t("Your username has been saved.")}
              </p>
            )}
            <button
              className="button button-primary"
              type="submit"
              disabled={busy || username.trim() === account.username}
            >
              {pending === "username" ? t("Saving…") : t("Save username")}
              <ArrowRightIcon aria-hidden="true" />
            </button>
          </form>
        </BorderGlow>
        <BorderGlow
          as="section"
          className="profile-panel"
          borderRadius={22}
          fillOpacity={0.08}
        >
          <div className="profile-panel-heading">
            <span className="profile-panel-icon">
              <LockClosedIcon aria-hidden="true" />
            </span>
            <div>
              <h2>{t("Password")}</h2>
              <p>{t("Choose a strong password that you use only here.")}</p>
            </div>
          </div>
          <form
            className="profile-form"
            onSubmit={savePassword}
            aria-busy={pending === "password"}
          >
            <label className="profile-field" htmlFor="profile-current-password">
              <span>{t("Current password")}</span>
              <input
                id="profile-current-password"
                name="current_password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(event) => {
                  setCurrentPassword(event.target.value);
                  setPasswordSaved(false);
                }}
                required
                maxLength={128}
                disabled={busy}
                aria-invalid={Boolean(passwordFields.current_password)}
                aria-describedby={
                  passwordFields.current_password
                    ? "profile-current_password-error"
                    : undefined
                }
              />
            </label>
            {passwordErrorNote("current_password")}
            <label className="profile-field" htmlFor="profile-new-password">
              <span>{t("New password")}</span>
              <input
                id="profile-new-password"
                name="new_password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => {
                  setNewPassword(event.target.value);
                  setPasswordSaved(false);
                }}
                required
                minLength={8}
                maxLength={128}
                disabled={busy}
                aria-invalid={Boolean(passwordFields.new_password)}
                aria-describedby={
                  passwordFields.new_password
                    ? "profile-new_password-error"
                    : "profile-password-note"
                }
              />
            </label>
            {passwordErrorNote("new_password")}
            <span id="profile-password-note" className="profile-helper">
              {t(
                "At least 8 characters. Avoid common passwords and personal details.",
              )}
            </span>
            <label className="profile-field" htmlFor="profile-confirm-password">
              <span>{t("Confirm new password")}</span>
              <input
                id="profile-confirm-password"
                name="new_password_confirm"
                type="password"
                autoComplete="new-password"
                value={confirmation}
                onChange={(event) => {
                  setConfirmation(event.target.value);
                  setPasswordSaved(false);
                }}
                required
                minLength={8}
                maxLength={128}
                disabled={busy}
                aria-invalid={Boolean(passwordFields.new_password_confirm)}
                aria-describedby={
                  passwordFields.new_password_confirm
                    ? "profile-new_password_confirm-error"
                    : undefined
                }
              />
            </label>
            {passwordErrorNote("new_password_confirm")}
            {passwordError && (
              <p className="form-error" role="alert">
                {translateAccountMessage(passwordError)}
              </p>
            )}
            {passwordSaved && (
              <p className="profile-success" role="status">
                <CheckCircledIcon aria-hidden="true" />{" "}
                {t("Password changed. You are still signed in here.")}
              </p>
            )}
            <button
              className="button button-secondary"
              type="submit"
              disabled={busy}
            >
              {pending === "password" ? t("Updating…") : t("Change password")}
              <ArrowRightIcon aria-hidden="true" />
            </button>
          </form>
        </BorderGlow>
      </div>
      <div className="profile-session">
        <div>
          <span className="profile-panel-icon">
            <ExitIcon aria-hidden="true" />
          </span>
          <div>
            <h2>{t("Leave this workspace")}</h2>
            <p>
              {t(
                "Sign out when you have finished. Your saved views stay with your account.",
              )}
            </p>
          </div>
        </div>
        <button
          className="button button-secondary"
          type="button"
          disabled={busy}
          onClick={() => void signOut()}
        >
          {pending === "logout" ? t("Signing out…") : t("Sign out")}
          <ExitIcon aria-hidden="true" />
        </button>
        {logoutError && (
          <p className="form-error" role="alert">
            {translateAccountMessage(logoutError)}
          </p>
        )}
      </div>
    </div>
  );
}
export default Profile;
