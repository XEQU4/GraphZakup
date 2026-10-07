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
  return (
    <Link to="/" className="brand" aria-label="IZ2 overview">
      <span className="brand-symbol">
        <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <path
            d="M8 8H13V32H8Z M18 8H33V13L24 27H33V32H18V27L27 13H18Z"
            fill="currentColor"
          />
          <path
            d="M3 3H12M3 3V12M37 28V37H28"
            stroke="#4b84ff"
            strokeWidth="2"
          />
        </svg>
      </span>
      <GlitchText text="IZ2" className="brand-wordmark" />
      <span className="brand-caption">INTELLIGENCE</span>
    </Link>
  );
}
function SideNav({ close }: { close?: () => void }) {
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
        WORKSPACE <span>01 / {String(navigation.length).padStart(2, "0")}</span>
      </div>
      <nav className="primary-nav" aria-label="Main navigation">
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
                <span className="nav-name">{name}</span>
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
            Evidence first.
            <br />
            <span>Every connection has a source.</span>
          </p>
        </div>
        <a
          href="/api/v1/docs/"
          target="_blank"
          rel="noreferrer"
          className="sidebar-external"
        >
          <FileTextIcon aria-hidden="true" /> API documentation{" "}
          <ArrowTopRightIcon aria-hidden="true" />
        </a>
        <div className="sidebar-version">
          <span>IZ2 WORKSPACE</span>
          <span>V1.0</span>
        </div>
      </div>
    </>
  );
}
function Layout() {
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
    const title =
      navigation.find((item) =>
        item.path === "/" ? pathname === "/" : pathname.startsWith(item.path),
      )?.name ?? (pathname === "/profile" ? "Profile" : "Workspace");
    document.title = title + " · IZ2";
  }, [pathname]);
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
        Skip to content
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
              aria-label="Open navigation"
            >
              <HamburgerMenuIcon />
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="nav-overlay" />
              <Dialog.Content className="mobile-drawer">
                <Dialog.Title className="sr-only">
                  Workspace navigation
                </Dialog.Title>
                <Dialog.Description className="sr-only">
                  Explore companies, relationships, people and contracts.
                </Dialog.Description>
                <Dialog.Close
                  className="drawer-close icon-button"
                  aria-label="Close navigation"
                >
                  <Cross2Icon />
                </Dialog.Close>
                <SideNav close={() => setMobile(false)} />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
          <div className="topbar-location">
            Workspace <span>/</span>{" "}
            <strong>
              {navigation.find((item) =>
                item.path === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.path),
              )?.name ?? (pathname === "/profile" ? "Profile" : "Overview")}
            </strong>
          </div>
          <form className="global-search" role="search" onSubmit={submit}>
            <MagnifyingGlassIcon aria-hidden="true" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              maxLength={100}
              placeholder="Search company or BIN"
              aria-label="Search companies"
            />
          </form>
          <div className="topbar-actions">
            <span
              className={"connection-status " + (session ? "connected" : "")}
            >
              <i />
              {session
                ? "API connected"
                : loading
                  ? "Connecting"
                  : "API unavailable"}
            </span>
            <button
              type="button"
              className={
                "icon-button motion-toggle " + (enabled ? "is-on" : "")
              }
              onClick={toggle}
              aria-label={
                enabled
                  ? "Pause decorative animations"
                  : "Enable decorative animations"
              }
              aria-pressed={enabled}
              disabled={reduced}
              title={
                reduced
                  ? "Reduced motion follows your device settings"
                  : enabled
                    ? "Pause animations"
                    : "Enable animations"
              }
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
                  <span>Sign in</span>
                </button>
                <button
                  className="button button-primary account-signup"
                  disabled={loading}
                  onClick={() => {
                    setAccountMode("register");
                    setLogin(true);
                  }}
                >
                  Sign up
                </button>
              </>
            ) : (
              <Link
                className="button account-button account-profile-link"
                to="/profile"
                aria-label={"Open profile for " + user.username}
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
  return (
    <div className="not-found">
      <span className="eyebrow">404 / UNCHARTED TERRITORY</span>
      <h1>This page is outside the network.</h1>
      <p className="muted">
        Return to the workspace to continue exploring saved evidence.
      </p>
      <Link className="button button-primary" to="/">
        Back to overview <ArrowRightIcon />
      </Link>
    </div>
  );
}
export default function App() {
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
