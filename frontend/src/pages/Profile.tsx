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
} from "@radix-ui/react-icons";
import { useSession } from "../components/Session";
import { BorderGlow } from "../components/design/BorderGlow";
import { TechHeading } from "../components/motion/TechHeading";
import { PageState, Pagination } from "../components/ui";
import { accountErrors, type FieldErrors } from "../lib/accountForms";
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
  const [page, setPage] = useState(1);
  const views = useApi<Paginated<AccountSavedView>>(
    queryPath("account/views/", { page, page_size: 6 }),
  );
  return (
    <section
      className="profile-saved-views"
      aria-labelledby="profile-saved-title"
    >
      <div className="profile-saved-heading">
        <div>
          <span className="eyebrow">SAVED TO YOUR ACCOUNT</span>
          <h2 id="profile-saved-title">Your graph views</h2>
          <p>
            Reopen the last view you saved for each group, including node
            positions, zoom, selection and filters.
          </p>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={views.reload}
          disabled={views.loading}
          aria-label="Refresh saved graph views"
        >
          <ReloadIcon aria-hidden="true" /> Refresh
        </button>
      </div>
      <PageState
        loading={views.loading && !views.data}
        error={views.error}
        onRetry={views.reload}
      />
      {views.data &&
        !views.error &&
        (views.data.count === 0 ? (
          <div className="profile-views-empty">
            <span className="profile-panel-icon">
              <BookmarkIcon aria-hidden="true" />
            </span>
            <div>
              <h3>No graph views saved yet.</h3>
              <p>
                Open a relationship group, arrange or pin nodes, choose filters,
                then click <strong>Save view</strong>. Return here to reopen it
                on any browser or device where you sign in.
              </p>
              <Link className="button button-primary" to="/clusters">
                Explore relationship groups{" "}
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
                      <LayersIcon aria-hidden="true" /> Graph v
                      {view.saved_snapshot_version}
                    </span>
                    {!view.cluster_is_active ? (
                      <span className="profile-view-status">
                        Archived group
                      </span>
                    ) : view.current_snapshot_version !== null &&
                      view.current_snapshot_version !==
                        view.saved_snapshot_version ? (
                      <span className="profile-view-status">
                        Newer graph available
                      </span>
                    ) : null}
                  </div>
                  <h3>{view.cluster_name}</h3>
                  <p>Saved {formatDateTime(view.updated_at)}</p>
                  <div className="profile-view-actions">
                    <Link
                      className="button button-secondary"
                      to={
                        "/clusters/" +
                        view.cluster_uuid +
                        "?version=" +
                        view.saved_snapshot_version
                      }
                    >
                      Open saved view <ArrowRightIcon aria-hidden="true" />
                    </Link>
                    {view.current_snapshot_version !== null &&
                      view.current_snapshot_version !==
                        view.saved_snapshot_version && (
                        <Link
                          className="profile-current-graph"
                          to={"/clusters/" + view.cluster_uuid}
                        >
                          Open current graph{" "}
                          <ArrowRightIcon aria-hidden="true" />
                        </Link>
                      )}
                  </div>
                </BorderGlow>
              ))}
            </div>
            <div className="profile-view-pagination">
              <span>
                {formatCount(views.data.count)} saved{" "}
                {views.data.count === 1 ? "view" : "views"}
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
        <span className="eyebrow">PERSONAL WORKSPACE</span>
        <TechHeading as="h1" text="Your account starts here." />
        <p>
          Sign in or create an account to keep graph positions, selected nodes
          and relationship filters across browsers and devices. Guest views stay
          only in this browser.
        </p>
        <Link to="/" className="button button-secondary">
          Back to overview <ArrowRightIcon aria-hidden="true" />
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
        {passwordFields[name]}
      </span>
    ) : null;

  return (
    <div className="profile-page">
      <div className="profile-heading">
        <div>
          <span className="eyebrow">PERSONAL WORKSPACE</span>
          <TechHeading as="h1" text="Your saved workspace." />
          <p>
            Save a graph view once. Reopen its positions, selected node and
            filters on another browser or device.
          </p>
        </div>
        <span className="profile-account-label">
          <PersonIcon aria-hidden="true" />{" "}
          {account.role === "staff" ? "Staff account" : "Personal account"}
        </span>
      </div>
      <div className="profile-overview">
        <span className="profile-current-name">{user.username}</span>
        <span>
          <CheckCircledIcon aria-hidden="true" /> Signed in
        </span>
        <span>Joined {formatDate(account.date_joined)}</span>
        <Link to="/clusters">
          <LayersIcon aria-hidden="true" /> Explore saved groups{" "}
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
              <h2>Account details</h2>
              <p>A name for your workspace. An email for your account.</p>
            </div>
          </div>
          <form
            className="profile-form"
            onSubmit={saveUsername}
            aria-busy={pending === "username"}
          >
            <label className="profile-field" htmlFor="profile-username">
              <span>Username</span>
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
                {nameFields.username}
              </span>
            )}
            <label className="profile-field" htmlFor="profile-email">
              <span>
                Email <LockClosedIcon aria-hidden="true" />
              </span>
              <input
                id="profile-email"
                value={account.email}
                type={account.email ? "email" : "text"}
                placeholder="No email recorded for this account"
                readOnly
                aria-describedby="profile-email-note"
              />
            </label>
            <span id="profile-email-note" className="profile-helper">
              Your email is read-only. Only your username can be updated here.
            </span>
            {nameError && (
              <p className="form-error" role="alert">
                {nameError}
              </p>
            )}
            {nameSaved && (
              <p className="profile-success" role="status">
                <CheckCircledIcon aria-hidden="true" /> Your username has been
                saved.
              </p>
            )}
            <button
              className="button button-primary"
              type="submit"
              disabled={busy || username.trim() === account.username}
            >
              {pending === "username" ? "Saving…" : "Save username"}
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
              <h2>Password</h2>
              <p>Choose a strong password that you use only here.</p>
            </div>
          </div>
          <form
            className="profile-form"
            onSubmit={savePassword}
            aria-busy={pending === "password"}
          >
            <label className="profile-field" htmlFor="profile-current-password">
              <span>Current password</span>
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
              <span>New password</span>
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
              At least 8 characters. Avoid common passwords and personal
              details.
            </span>
            <label className="profile-field" htmlFor="profile-confirm-password">
              <span>Confirm new password</span>
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
                {passwordError}
              </p>
            )}
            {passwordSaved && (
              <p className="profile-success" role="status">
                <CheckCircledIcon aria-hidden="true" /> Password changed. You
                are still signed in here.
              </p>
            )}
            <button
              className="button button-secondary"
              type="submit"
              disabled={busy}
            >
              {pending === "password" ? "Updating…" : "Change password"}
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
            <h2>Leave this workspace</h2>
            <p>
              Sign out when you have finished. Your saved views stay with your
              account.
            </p>
          </div>
        </div>
        <button
          className="button button-secondary"
          type="button"
          disabled={busy}
          onClick={() => void signOut()}
        >
          {pending === "logout" ? "Signing out…" : "Sign out"}
          <ExitIcon aria-hidden="true" />
        </button>
        {logoutError && (
          <p className="form-error" role="alert">
            {logoutError}
          </p>
        )}
      </div>
    </div>
  );
}
export default Profile;
