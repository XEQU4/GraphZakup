/* IZ2 navigation around the bundled Swagger UI; never sends API requests. */
(() => {
  "use strict";
  const root = document.getElementById("swagger-ui");
  const toc = document.getElementById("api-docs-toc");
  const status = document.querySelector(".api-docs-status");
  if (!root || !toc || !status) return;

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
  let signature = "";
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
    if (filter && !filter.hasAttribute("aria-label")) {
      filter.setAttribute("aria-label", "Filter API resources");
      filter.setAttribute("placeholder", "Filter resources by name…");
    }
    if (headings.length) {
      status.dataset.state = "ready";
      status.textContent = "Reference ready";
    } else if (root.querySelector(".errors-wrapper")) {
      status.dataset.state = "error";
      status.textContent = "Reference unavailable";
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
  refresh();
})();
