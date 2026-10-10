import { translate as t, useI18n, LanguageSwitch } from "./i18n";
import { BrandMark } from "./components/BrandMark";
import { lazy, Suspense, useEffect, useState, type FormEvent } from "react";
import {
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { motion } from "motion/react";
import {
  DashboardIcon,
  CubeIcon,
  LayersIcon,
  PersonIcon,
  FileTextIcon,
  MagnifyingGlassIcon,
  ArrowTopRightIcon,
  ArrowRightIcon,
  Cross2Icon,
  HamburgerMenuIcon,
  LightningBoltIcon,
  LockClosedIcon,
  InfoCircledIcon,
} from "@radix-ui/react-icons";
import { LoginDialog, useSession } from "./components/Session";
import { useMotionPreferences } from "./components/MotionPreferences";
import { PageState } from "./components/ui";
import { FocusFrame } from "./components/motion/FocusFrame";
import { GlitchText } from "./components/motion/GlitchText";
import Particles from "./components/effects/Particles";
import WorkspaceFooter from "./components/WorkspaceFooter";
import Home from "./pages/Home";
const Companies = lazy(() =>
  import("./pages/Companies").then((m) => ({ default: m.Companies })),
);
const CompanyDetail = lazy(() =>
  import("./pages/CompanyDetail").then((m) => ({ default: m.CompanyDetail })),
);
const People = lazy(() =>
  import("./pages/People").then((m) => ({ default: m.People })),
);
const PersonDetail = lazy(() =>
  import("./pages/PersonDetail").then((m) => ({ default: m.PersonDetail })),
);
const Contracts = lazy(() =>
  import("./pages/Contracts").then((m) => ({ default: m.Contracts })),
);
const Clusters = lazy(() =>
  import("./pages/Clusters").then((m) => ({ default: m.Clusters })),
);
const ClusterDetail = lazy(() =>
  import("./pages/ClusterDetail").then((m) => ({ default: m.ClusterDetail })),
);
const About = lazy(() => import("./pages/About"));
const Profile = lazy(() => import("./pages/Profile"));
const navigation = [
  { path: "/", name: "Overview", icon: DashboardIcon },
  { path: "/clusters", name: "Relationship groups", icon: LayersIcon },
  { path: "/companies", name: "Companies", icon: CubeIcon },
  { path: "/people", name: "People", icon: PersonIcon },
  { path: "/contracts", name: "Contracts", icon: FileTextIcon },
  { path: "/about", name: "About Us", icon: InfoCircledIcon },
];
function Brand() {
  useI18n();
  return (
    <Link to="/" className="brand" aria-label={t("IZ2 overview")}>
      <span className="brand-symbol">
        <BrandMark />
      </span>
      <GlitchText text={t("IZ2")} className="brand-wordmark" period={18} />
      <span className="brand-caption">{t("INTELLIGENCE")}</span>
    </Link>
  );
}
function SideNav({ close }: { close?: () => void }) {
  useI18n();
  const { enabled } = useMotionPreferences();
  const [hoverPath, setHoverPath] = useState<string | null>(null);
  const [focusedPath, setFocusedPath] = useState<string | null>(null);
  const focusPath = hoverPath ?? focusedPath;
  const scope = close ? "mobile-navigation" : "navigation";
  return (
    <>
      <div className="sidebar-brand">
        <Brand />
      </div>
      <div className="nav-label">
        {t("WORKSPACE")}{" "}
        <span>01 / {String(navigation.length).padStart(2, "0")}</span>
      </div>
      <nav className="primary-nav" aria-label={t("Main navigation")}>
        {navigation.map(({ path, name, icon: Icon }, i) => (
          <NavLink
            key={path}
            to={path}
            end={path === "/"}
            onClick={close}
            onPointerEnter={(event) => {
              if (event.pointerType !== "touch") setHoverPath(path);
            }}
            onPointerLeave={() => setHoverPath(null)}
            onFocus={() => setFocusedPath(path)}
            onBlur={() => setFocusedPath(null)}
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    className="nav-active-surface"
                    layoutId={
                      close ? "mobile-navigation-active" : "navigation-active"
                    }
                    transition={{
                      duration: enabled ? 0.28 : 0,
                      ease: "easeOut",
                    }}
                    aria-hidden="true"
                  />
                )}
                {(focusPath === path || (focusPath === null && isActive)) && (
                  <FocusFrame scope={scope} />
                )}
                <Icon aria-hidden="true" />
                <span className="nav-name">{t(name)}</span>
                <small>0{i + 1}</small>
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-note">
          <span className="note-symbol">
            <LockClosedIcon aria-hidden="true" />
          </span>
          <p>
            {t("Evidence first.")}
            <br />
            <span>{t("Every connection has a source.")}</span>
          </p>
        </div>
        <a
          href="/api/v1/docs/"
          target="_blank"
          rel="noreferrer"
          className="sidebar-external"
        >
          <FileTextIcon aria-hidden="true" /> {t("API documentation")}{" "}
          <ArrowTopRightIcon aria-hidden="true" />
        </a>
        <div className="sidebar-version">
          <span>{t("IZ2 WORKSPACE")}</span>
          <span>{t("V1.0")}</span>
        </div>
      </div>
    </>
  );
}
function Layout() {
  const { language } = useI18n();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [mobile, setMobile] = useState(false);
  const [login, setLogin] = useState(false);
  const [accountMode, setAccountMode] = useState<"login" | "register">("login");
  const { session, user, loading } = useSession();
  const { enabled, toggle, reduced } = useMotionPreferences();
  useEffect(() => {
    setMobile(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);
  useEffect(() => {
    const title =
      navigation.find((item) =>
        item.path === "/" ? pathname === "/" : pathname.startsWith(item.path),
      )?.name ?? (pathname === "/profile" ? "Profile" : "Workspace");
    document.title = t(title) + " · IZ2";
  }, [pathname, language]);
  function submit(event: FormEvent) {
    event.preventDefault();
    navigate(
      "/companies" +
        (search.trim() ? "?search=" + encodeURIComponent(search.trim()) : ""),
    );
    setSearch("");
  }
  return (
    <div className="app-shell">
      <Particles />
      <a href="#main-content" className="skip-link">
        {t("Skip to content")}
      </a>
      <aside className="sidebar">
        <SideNav />
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="mobile-brand">
            <Brand />
          </div>
          <Dialog.Root open={mobile} onOpenChange={setMobile}>
            <Dialog.Trigger
              className="icon-button mobile-menu"
              aria-label={t("Open navigation")}
            >
              <HamburgerMenuIcon />
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="nav-overlay" />
              <Dialog.Content className="mobile-drawer">
                <Dialog.Title className="sr-only">
                  {t("Workspace navigation")}
                </Dialog.Title>
                <Dialog.Description className="sr-only">
                  {t("Explore companies, relationships, people and contracts.")}
                </Dialog.Description>
                <Dialog.Close
                  className="drawer-close icon-button"
                  aria-label={t("Close navigation")}
                >
                  <Cross2Icon />
                </Dialog.Close>
                <SideNav close={() => setMobile(false)} />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
          <div className="topbar-location">
            {t("Workspace")} <span>/</span>{" "}
            <strong>
              {t(
                navigation.find((item) =>
                  item.path === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.path),
                )?.name ?? (pathname === "/profile" ? "Profile" : "Overview"),
              )}
            </strong>
          </div>
          <form className="global-search" role="search" onSubmit={submit}>
            <MagnifyingGlassIcon aria-hidden="true" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              maxLength={100}
              placeholder={t("Search company or BIN")}
              aria-label={t("Search companies")}
            />
          </form>
          <div className="topbar-actions">
            <LanguageSwitch />
            <span
              className={"connection-status " + (session ? "connected" : "")}
            >
              <i />
              {t(
                session
                  ? "API connected"
                  : loading
                    ? "Connecting"
                    : "API unavailable",
              )}
            </span>
            <button
              type="button"
              className={
                "icon-button motion-toggle " + (enabled ? "is-on" : "")
              }
              onClick={toggle}
              aria-label={t(
                enabled
                  ? "Pause decorative animations"
                  : "Enable decorative animations",
              )}
              aria-pressed={enabled}
              disabled={reduced}
              title={t(
                reduced
                  ? "Reduced motion follows your device settings"
                  : enabled
                    ? "Pause animations"
                    : "Enable animations",
              )}
            >
              <LightningBoltIcon aria-hidden="true" />
            </button>
            {user.role === "anonymous" ? (
              <>
                <button
                  className="button account-button"
                  disabled={loading}
                  onClick={() => {
                    setAccountMode("login");
                    setLogin(true);
                  }}
                >
                  <PersonIcon aria-hidden="true" />
                  <span>{t("Sign in")}</span>
                </button>
                <button
                  className="button button-primary account-signup"
                  disabled={loading}
                  onClick={() => {
                    setAccountMode("register");
                    setLogin(true);
                  }}
                >
                  {t("Sign up")}
                </button>
              </>
            ) : (
              <Link
                className="button account-button account-profile-link"
                to="/profile"
                aria-label={t("Open profile for {username}", {
                  username: user.username ?? "",
                })}
              >
                <PersonIcon aria-hidden="true" />
                <span>{user.username}</span>
              </Link>
            )}
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          <Suspense fallback={<PageState loading />}>
            <Outlet />
          </Suspense>
        </main>
        <WorkspaceFooter />
      </div>
      <LoginDialog
        open={login}
        onOpenChange={setLogin}
        initialMode={accountMode}
      />
    </div>
  );
}
function NotFound() {
  useI18n();
  return (
    <div className="not-found">
      <span className="eyebrow">{t("404 / UNCHARTED TERRITORY")}</span>
      <h1>{t("This page is outside the network.")}</h1>
      <p className="muted">
        {t("Return to the workspace to continue exploring saved evidence.")}
      </p>
      <Link className="button button-primary" to="/">
        {t("Back to overview")} <ArrowRightIcon />
      </Link>
    </div>
  );
}
export default function App() {
  useI18n();
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="companies" element={<Companies />} />
        <Route path="companies/:id" element={<CompanyDetail />} />
        <Route path="people" element={<People />} />
        <Route path="people/:id" element={<PersonDetail />} />
        <Route path="contracts" element={<Contracts />} />
        <Route path="about" element={<About />} />
        <Route path="profile" element={<Profile />} />
        <Route path="clusters" element={<Clusters />} />
        <Route path="clusters/:uuid" element={<ClusterDetail />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
