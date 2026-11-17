"use strict";

const byId = (id) => document.getElementById(id);
const views = [...document.querySelectorAll(".view")];
const menus = [...document.querySelectorAll("[data-view]")];
const resultNodes = [...document.querySelectorAll("#route li")];
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const domainInput = byId("domain");
const searchForm = byId("resolve-form");
const searchButton = byId("resolve-button");
const settingsForm = byId("settings-form");
const settings = settingsForm.elements;
const policyForm = byId("policy-form");
const notice = byId("notice");
const formatNumber = new Intl.NumberFormat("en-US");
const statuses = {
  OK: ["Answered", "good"],
  AD_BLOCK: ["Ad block", "warn"],
  SANCTION: ["Sanction rule", "warn"],
  CACHE: ["Cache", "good"],
  UPSTREAM: ["Upstream", "flow"],
  NOT_FOUND: ["Not found", "warn"],
  SERVER_ERROR: ["Server error", "error"],
  INVALID_INPUT: ["Invalid input", "error"],
  NONE: ["No source", ""],
};
const descriptions = {
  AD_BLOCK: "Matched the ad block list and returned the sinkhole address.",
  SANCTION: "Matched the sanction list and returned the configured proxy address.",
  CACHE: "Answered from the local cache without another upstream request.",
  UPSTREAM: "Answered by the configured upstream server.",
  NOT_FOUND: "The upstream server returned no A record for this domain.",
  SERVER_ERROR: "The upstream returned an error or did not respond in time.",
  INVALID_INPUT: "Enter a domain name using letters, digits, dots or hyphens.",
};
let snapshot;
let currentView;
let activity = [];
let stateVersion = 0;
let historyVersion = 0;
let actionInProgress = false;
let noticeTimer;
let cacheEntries = [];

async function api(path, data) {
  const options = data === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
  const reply = await fetch("/api/" + path, options);
  const body = await reply.json();
  if (!reply.ok) throw new Error(body.error || "The request failed.");
  return body;
}

function message(text, isError = false, persistent = false) {
  clearTimeout(noticeTimer);
  notice.hidden = !text;
  notice.toggleAttribute("data-error", isError);
  byId("notice-icon").setAttribute("href", isError ? "#i-alert" : "#i-check");
  byId("notice-message").textContent = text;
  if (text && !persistent) noticeTimer = setTimeout(() => { notice.hidden = true; }, 4800);
}

function statusChip(value, chip = document.createElement("span")) {
  const [label, tone] = statuses[value] || [value, ""];
  chip.className = "chip";
  chip.textContent = label;
  chip.dataset.tone = tone;
  return chip;
}

function tableRows(id, entries, columnCount, empty, valuesFor) {
  const body = document.createDocumentFragment();
  if (!entries.length) {
    const row = document.createElement("tr");
    const cell = row.insertCell();
    cell.colSpan = columnCount;
    cell.className = "empty-cell";
    cell.textContent = empty;
    body.append(row);
  }
  for (const entry of entries) {
    const row = document.createElement("tr");
    for (const value of valuesFor(entry)) {
      const cell = row.insertCell();
      if (value instanceof HTMLElement) cell.append(value);
      else cell.textContent = value;
    }
    body.append(row);
  }
  byId(id).replaceChildren(body);
}

function domainLink(domain) {
  if (!domain || domain === "-") return "—";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "domain-link";
  button.dataset.lookup = domain;
  button.title = "Use this domain in the resolver";
  button.textContent = domain;
  return button;
}

function recentDomain(row) {
  const cell = document.createElement("span");
  const time = document.createElement("small");
  time.className = "mobile-time";
  time.textContent = row.time.split(" ").at(-1);
  cell.append(domainLink(row.domain), time);
  return cell;
}

function renderCache(entries) {
  const currentRows = byId("cache-rows").rows;
  const sameEntries = entries.length === cacheEntries.length && entries.every((entry, index) =>
    entry.domain === cacheEntries[index].domain && entry.ip === cacheEntries[index].ip);
  if (sameEntries && currentRows.length) {
    entries.forEach((entry, index) => {
      currentRows[index].cells[2].textContent = entry.ttl + " s";
    });
  } else {
    tableRows("cache-rows", entries, 3, "The cache is empty.", (row) => [
      domainLink(row.domain), row.ip, row.ttl + " s",
    ]);
  }
  cacheEntries = entries;
}

function renderState(data) {
  snapshot = data;
  const config = data.settings;
  const stats = data.stats;
  const simulator = data.simulator;
  const endpoint = config.upstream_ip + ":" + config.upstream_port;
  byId("upstream-address").textContent = endpoint;
  byId("connection-detail").textContent = simulator.running ? "Local simulator running"
    : simulator.available ? "Local simulator stopped" : "Configured UDP endpoint";
  byId("mode-label").textContent = config.real_dns_enabled ? "Real DNS" : "Simulated UDP";
  byId("mode-pill").toggleAttribute("data-offline", simulator.available && !simulator.running);
  byId("mode-pill").title = endpoint;

  const examples = config.real_dns_enabled ? ["example.com", "iana.org", "cloudflare.com"]
    : ["normal.example.net", "ads.example.com", "service.example.org"];
  byId("examples").querySelectorAll("button").forEach((button, index) => {
    button.dataset.domain = examples[index];
    button.textContent = examples[index];
  });

  byId("stat-total").textContent = formatNumber.format(stats.total);
  byId("stat-total-note").textContent = formatNumber.format(stats.upstream) + " sent upstream";
  byId("stat-cache").textContent = formatNumber.format(stats.cache);
  const entries = data.cache.length;
  const entryCount = formatNumber.format(entries) + (entries === 1 ? " active entry" : " active entries");
  byId("stat-cache-note").textContent = config.cache_enabled ? entryCount : "Cache disabled";
  byId("stat-policies").textContent = formatNumber.format(stats.ad_block + stats.sanction);
  byId("stat-policy-note").textContent = formatNumber.format(stats.ad_block) + " blocked · "
    + formatNumber.format(stats.sanction) + " redirected";
  byId("stat-errors").textContent = formatNumber.format(stats.errors);

  const capacity = config.cache_max_entries === null ? "Unlimited capacity" :
    "Capacity: " + formatNumber.format(config.cache_max_entries);
  byId("cache-caption").textContent = config.cache_enabled ? entryCount + " · " + capacity + " · FIFO" : "DNS cache is disabled.";
  byId("clear-cache").disabled = !entries;
  renderCache(data.cache);

  byId("simulator-caption").textContent = simulator.available
    ? simulator.running ? endpoint + " · " + formatNumber.format(simulator.requests) + " UDP requests"
      : endpoint + " · stopped"
    : "Available in simulated UDP mode with a loopback address.";
  byId("simulator-toggle").disabled = !simulator.available;
  byId("simulator-toggle").textContent = simulator.running ? "Stop simulator" : "Start simulator";
  if (byId("settings-fields").disabled) fillSettings();
}

function fillSettings() {
  for (const [name, value] of Object.entries(snapshot.settings)) {
    const input = settings.namedItem(name);
    if (input.type === "checkbox") input.checked = value;
    else input.value = value === null ? "" : String(value);
  }
  byId("settings-fields").disabled = false;
}

function renderResult(result) {
  const status = statuses[result.status];
  statusChip(result.status, byId("result-status"));
  statusChip(result.source, byId("result-source")).hidden = result.source === "NONE";
  byId("result-domain").textContent = result.domain || "(empty domain)";
  byId("result-ip").textContent = result.ip || "—";
  byId("copy-ip").hidden = !result.ip;
  byId("result-ttl").textContent = result.ttl === null ? "—" : result.ttl + " s";
  byId("result-ms").textContent = result.elapsed_ms.toFixed(2) + " ms";
  const description = descriptions[result.status === "OK" ? result.source : result.status];
  byId("result-message").textContent = description;
  byId("lookup-announcement").textContent = [result.domain, status[0], result.ip, description].filter(Boolean).join(". ");
  const index = resultNodes.findIndex((node) => node.dataset.source === result.source);
  byId("route").dataset.step = index + 1;
  byId("route").dataset.tone = status[1];
  resultNodes.forEach((node, i) => {
    node.classList.toggle("checked", i < index);
    node.classList.toggle("selected", i === index);
    node.querySelector(".route-state").textContent = i === index
      ? (result.source !== "UPSTREAM" ? "MATCH" : result.status === "OK" ? "ANSWERED" : status[0])
      : "";
  });
  byId("result-details").hidden = false;
}

function renderHistory() {
  const query = byId("activity-filter").value.trim().toLowerCase();
  const matches = activity.filter((row) => [row.domain, row.source, row.status,
    statuses[row.source]?.[0], statuses[row.status]?.[0],
  ].some((field) => field?.toLowerCase().includes(query)));
  const total = activity.length;
  byId("activity-count").textContent = query ? matches.length + " of " + total + " entries"
    : total + (total === 1 ? " entry" : " entries");
  tableRows("activity-rows", matches, 6, query ? "No entries match the filter." : "The activity log is empty.", (row) =>
    [row.time, domainLink(row.domain), statusChip(row.source), statusChip(row.status), row.ip, row.ttl]);
}

async function updateActivity() {
  const version = ++historyVersion;
  const rows = await api("activity");
  if (version !== historyVersion) return;
  activity = rows;
  tableRows("overview-activity", activity.slice(0, 5), 4, "Your queries will appear here.", (row) =>
    [recentDomain(row), statusChip(row.source), statusChip(row.status), row.time.split(" ").at(-1)]);
  renderHistory();
}

async function updatePolicies() {
  const data = await api("policies");
  const ads = byId("ads");
  const sanctions = byId("sanctions");
  ads.value = data.ads;
  sanctions.value = data.sanctions;
  ads.disabled = false;
  sanctions.disabled = false;
  byId("save-policies").disabled = false;
  policyForm.dataset.loaded = "true";
}

async function updateState() {
  const version = ++stateVersion;
  const data = await api("state");
  if (stateVersion === version && !actionInProgress) renderState(data);
}

async function openView(id, focusHeading) {
  currentView = id;
  for (const view of views) view.hidden = view.id !== id;
  for (const item of menus) {
    if (item.dataset.view === id) {
      item.setAttribute("aria-current", "page");
      byId("current-view").textContent = item.textContent.trim();
    } else item.removeAttribute("aria-current");
  }
  const heading = byId(id).querySelector("h1");
  if (focusHeading) {
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  try {
    if (!snapshot || id === "cache") await updateState();
    if (id === "policies" && !policyForm.dataset.loaded) await updatePolicies();
    if (id === "overview" || id === "activity") await updateActivity();
  } catch (error) {
    message(error.message, true);
  }
}

function viewFromLocation() {
  const id = location.hash.slice(1);
  return views.some((view) => view.id === id) ? id : "overview";
}

function focusResolver() {
  if (currentView !== "overview") {
    history.pushState(null, "", "#overview");
    void openView("overview", false);
  }
  domainInput.focus();
}

async function action(path, data, sourceButton, confirmation) {
  actionInProgress = true;
  stateVersion++;
  sourceButton.disabled = true;
  try {
    const body = await api(path, data);
    if (confirmation) message(
      [confirmation, ...body.warnings].join("\n"),
      Boolean(body.warnings.length),
      Boolean(body.warnings.length),
    );
    return body;
  } catch (error) {
    message(error.message, true);
    return null;
  } finally {
    sourceButton.disabled = false;
    actionInProgress = false;
  }
}

window.addEventListener("hashchange", () => openView(viewFromLocation(), true));
byId("activity-filter").addEventListener("input", renderHistory);

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (actionInProgress) return;
  const hero = searchForm.closest(".hero");
  const response = byId("response-panel");
  const route = byId("route").closest(".panel");
  const wasEmpty = byId("response-empty").hidden === false;
  hero.classList.add("is-querying");
  route.setAttribute("aria-busy", "true");
  byId("resolve-label").textContent = "Resolving…";
  byId("lookup-announcement").textContent = "Resolving domain.";
  byId("response-empty").hidden = true;
  byId("result-details").hidden = true;
  byId("result-loading").hidden = false;
  const result = await action("resolve", { domain: domainInput.value }, searchButton);
  byId("resolve-label").textContent = "Resolve";
  byId("result-loading").hidden = true;
  hero.classList.remove("is-querying");
  route.removeAttribute("aria-busy");
  if (result) {
    renderState(result);
    renderResult(result.result);
    if (currentView === "overview" && response.getBoundingClientRect().top > window.innerHeight - 90) {
      response.scrollIntoView({ block: "start", behavior: reducedMotion.matches ? "instant" : "smooth" });
    }
    try { await updateActivity(); } catch (error) { message(error.message, true); }
  } else {
    byId("response-empty").hidden = !wasEmpty;
    byId("result-details").hidden = wasEmpty;
    byId("lookup-announcement").textContent = "The lookup could not be completed.";
  }
});

byId("examples").addEventListener("click", (event) => {
  const chip = event.target.closest("button[data-domain]");
  if (!chip || actionInProgress) return;
  domainInput.value = chip.dataset.domain;
  searchForm.requestSubmit();
});

document.querySelector(".content").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-lookup]");
  if (!button || actionInProgress) return;
  domainInput.value = button.dataset.lookup;
  focusResolver();
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target.closest?.("input, textarea, select, [contenteditable]")) return;
  event.preventDefault();
  focusResolver();
});

byId("copy-ip").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(byId("result-ip").textContent);
    message("IPv4 address copied.");
  } catch {
    message("Could not copy. Select the address to copy it manually.", true);
  }
});
byId("dismiss-notice").addEventListener("click", () => message(""));

byId("refresh").addEventListener("click", async (event) => {
  if (actionInProgress) return;
  const button = event.currentTarget;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  try {
    await updateState();
    if (currentView === "activity" || currentView === "overview") await updateActivity();
    const warnings = snapshot?.warnings || [];
    message(warnings.length ? warnings.join("\n") : "Dashboard refreshed.", Boolean(warnings.length), Boolean(warnings.length));
  } catch (error) {
    message(error.message, true);
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
});

byId("clear-cache").addEventListener("click", async (event) => {
  if (actionInProgress) return;
  const data = await action("cache/clear", {}, event.currentTarget, "Cache cleared.");
  if (data) renderState(data);
});

byId("reload-policies").addEventListener("click", async (event) => {
  if (actionInProgress) return;
  const data = await action("policies/reload", {}, event.currentTarget, "Policy lists reloaded.");
  if (!data) return;
  renderState(data);
  try { await updatePolicies(); } catch (error) { message(error.message, true); }
});

policyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (actionInProgress || !policyForm.dataset.loaded) return;
  const data = await action("policies", {
    ads: byId("ads").value,
    sanctions: byId("sanctions").value,
  }, byId("save-policies"), "Policy lists saved and reloaded.");
  if (data) renderState(data);
});

byId("use-default-upstream").addEventListener("click", () => {
  const real = settings.namedItem("real_dns_enabled").value === "true";
  settings.namedItem("upstream_ip").value = real ? "1.1.1.1" : "127.0.0.1";
  settings.namedItem("upstream_port").value = real ? "53" : "5354";
});

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (actionInProgress || !snapshot) return;
  const read = (name) => settings.namedItem(name).value;
  const data = await action("settings", {
    upstream_ip: read("upstream_ip"),
    upstream_port: Number(read("upstream_port")),
    upstream_timeout_sec: Number(read("upstream_timeout_sec")),
    sinkhole_ip: read("sinkhole_ip"),
    proxy_ip: read("proxy_ip"),
    local_ttl: Number(read("local_ttl")),
    cache_enabled: settings.namedItem("cache_enabled").checked,
    cache_max_entries: read("cache_max_entries") ? Number(read("cache_max_entries")) : null,
    real_dns_enabled: read("real_dns_enabled") === "true",
  }, settingsForm.querySelector('button[type="submit"]'), "Settings saved and cache cleared.");
  if (data) {
    renderState(data);
    fillSettings();
  }
});

byId("simulator-toggle").addEventListener("click", async (event) => {
  if (actionInProgress || !snapshot) return;
  const running = !snapshot.simulator.running;
  const data = await action("simulator", { running }, event.currentTarget,
    running ? "Local simulator started." : "Local simulator stopped.");
  if (data) renderState(data);
});

async function initialize() {
  await openView(viewFromLocation(), false);
  if (snapshot?.warnings.length) message(snapshot.warnings.join("\n"), true, true);
  if (!snapshot) {
    byId("mode-label").textContent = "Connection failed";
    byId("mode-pill").setAttribute("data-offline", "");
  }
}

setInterval(() => {
  if (currentView === "cache" && !actionInProgress && document.visibilityState === "visible") {
    updateState().catch((error) => message(error.message, true));
  }
}, 1000);

initialize();
