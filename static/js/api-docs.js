/* IZ2 navigation around the bundled Swagger UI; never sends API requests. */
(() => {
  "use strict";
  const root = document.getElementById("swagger-ui");
  const toc = document.getElementById("api-docs-toc");
  const status = document.querySelector(".api-docs-status");
  if (!root || !toc || !status) return;

  // Use Swagger's resource-filter hook without replacing its native bootstrap.
  // https://github.com/swagger-api/swagger-ui/blob/main/docs/customization/plug-points.md#fnopsfilter
  const initializeSwagger = () => {
    if (typeof ui === "undefined" || !ui.fn) return;
    ui.fn.opsFilter = (taggedOps, phrase) => {
      const query = String(phrase).trim().toLowerCase();
      return taggedOps.filter((operations, tag) =>
        [String(tag), labels[tag] || ""].some((label) =>
          label.toLowerCase().includes(query),
        ),
      );
    };
    scheduleRefresh();
  };

  const motionButton = document.querySelector(".api-docs-motion");
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let motionAllowed = true;
  try {
    motionAllowed = localStorage.getItem("iz2.motion-enabled.v1") !== "false";
  } catch {}
  const applyMotion = () => {
    const enabled = motionAllowed && !motionQuery.matches;
    document.documentElement.dataset.apiMotion = enabled ? "on" : "off";
    if (motionButton) {
      motionButton.textContent = enabled ? "Motion on" : "Motion off";
      motionButton.setAttribute("aria-pressed", String(enabled));
      motionButton.disabled = motionQuery.matches;
      motionButton.title = motionQuery.matches
        ? "Reduced motion is enabled on your device"
        : "Toggle interface animations";
    }
  };
  motionButton?.addEventListener("click", () => {
    motionAllowed = !motionAllowed;
    try {
      localStorage.setItem("iz2.motion-enabled.v1", String(motionAllowed));
    } catch {}
    applyMotion();
  });
  motionQuery.addEventListener("change", applyMotion);
  window.addEventListener("storage", (event) => {
    if (event.key === "iz2.motion-enabled.v1") {
      motionAllowed = event.newValue !== "false";
      applyMotion();
    }
  });
  applyMotion();

  const labels = {
    account: "Account",
    clusters: "Relationship groups",
    Companies: "Companies",
    Contracts: "Contracts",
    Jobs: "Background jobs",
    overview: "Overview",
    People: "People & roles",
    session: "Sessions",
    snapshots: "Saved snapshots",
  };
  let headings = [];
  let active = null;
  let frame = null;
  let signature = null;
  let selectedTag = null;
  let filterValue = "";
  const links = new Map();

  const setActive = (id) => {
    if (id === active) return;
    active = id;
    for (const [key, link] of links) {
      if (key === id) {
        link.dataset.active = "true";
        link.setAttribute("aria-current", "location");
      } else {
        delete link.dataset.active;
        link.removeAttribute("aria-current");
      }
    }
  };

  const updateActive = () => {
    let current = headings[0];
    for (const heading of headings) {
      if (heading.getBoundingClientRect().top <= 150) current = heading;
      else break;
    }
    setActive(current?.id ?? null);
  };

  const openSection = (heading) => {
    heading = document.getElementById(heading.id) || heading;
    selectedTag = heading.dataset.tag;
    if (heading.dataset.isOpen !== "true") {
      const button = heading.querySelector("button");
      if (button) button.click();
      else heading.click();
    }
    requestAnimationFrame(() => {
      const target =
        root.querySelector('[id="' + CSS.escape(heading.id) + '"]') || heading;
      target.scrollIntoView({ block: "start" });
      const button = target.querySelector("button");
      if (button) button.focus({ preventScroll: true });
      setActive(target.id);
    });
  };

  const refresh = () => {
    frame = null;
    headings = [...root.querySelectorAll(".opblock-tag[id]")];
    const filter = root.querySelector(".filter-container input");
    if (filter) {
      filter.setAttribute("aria-label", "Filter API resources");
      filter.setAttribute("placeholder", "Filter resources by name…");
    }
    if (headings.length) {
      status.dataset.state = "ready";
      status.textContent = "Reference ready";
    } else if (root.querySelector(".errors-wrapper")) {
      status.dataset.state = "error";
      status.textContent = "Reference unavailable";
    } else {
      status.textContent =
        status.dataset.state === "ready"
          ? "Reference ready"
          : "Loading reference…";
    }

    const nextFilterValue = filter?.value ?? "";
    if (nextFilterValue !== filterValue) {
      filterValue = nextFilterValue;
      selectedTag = null;
    }
    const nextSignature = headings.map((heading) => heading.id).join("|");
    if (nextSignature !== signature) {
      signature = nextSignature;
      links.clear();
      toc.replaceChildren();
      for (const heading of headings) {
        const tag = heading.dataset.tag || heading.textContent.trim();
        const link = document.createElement("a");
        link.className = "api-docs-toc-link";
        link.href = "#" + encodeURIComponent(heading.id);
        const label = document.createElement("span");
        label.textContent = labels[tag] || tag;
        const marker = document.createElement("span");
        marker.className = "api-docs-toc-marker";
        marker.textContent = "↗";
        marker.setAttribute("aria-hidden", "true");
        link.append(label, marker);
        link.addEventListener("click", (event) => {
          event.preventDefault();
          openSection(heading);
        });
        toc.append(link);
        links.set(heading.id, link);
      }
      if (!headings.length) {
        const message = document.createElement("p");
        message.className = "api-docs-loading";
        message.textContent = filterValue
          ? "No matching resources."
          : "Reference sections will appear here.";
        toc.append(message);
      }
      active = null;
    }
    if (selectedTag) {
      const selected = headings.find(
        (heading) => heading.dataset.tag === selectedTag,
      );
      if (selected) setActive(selected.id);
    } else {
      updateActive();
    }
  };

  const scheduleRefresh = () => {
    if (frame === null) frame = requestAnimationFrame(refresh);
  };
  const observer = new MutationObserver(scheduleRefresh);
  observer.observe(root, { childList: true, subtree: true });
  window.addEventListener(
    "scroll",
    () => {
      selectedTag = null;
      scheduleRefresh();
    },
    { passive: true },
  );
  window.addEventListener("resize", scheduleRefresh, { passive: true });
  window.addEventListener(
    "pagehide",
    () => {
      observer.disconnect();
      if (frame !== null) cancelAnimationFrame(frame);
    },
    { once: true },
  );
  scheduleRefresh();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeSwagger, {
      once: true,
    });
  } else {
    initializeSwagger();
  }
})();
