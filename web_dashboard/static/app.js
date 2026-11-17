"use strict";

const byId = (id) => document.getElementById(id);
const views = [...document.querySelectorAll(".view")];
const menus = [...document.querySelectorAll("[data-view]")];
const resultNodes = [...document.querySelectorAll("#route li")];
const domainInput = byId("domain");
const settings = byId("settings-form").elements;
const policyForm = byId("policy-form");
const notice = byId("notice");
const number = new Intl.NumberFormat("en-US");
const descriptions = {
  AD_BLOCK: "Matched the ad block list and returned the sinkhole address.",
  SANCTION: "Matched the sanction list and returned the configured proxy address.",
  CACHE: "Answered from the local cache without another upstream request.",
  UPSTREAM: "Contacted the configured upstream server.",
  NOT_FOUND: "The upstream server returned no A record for this domain.",
  SERVER_ERROR: "The upstream returned an error or did not respond in time.",
  INVALID_INPUT: "Enter a domain name using letters, digits, dots or hyphens.",
};
let snapshot;
let currentView = "overview";
let actionCount = 0;
let stateVersion = 0;
let noticeTimer;

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
  notice.textContent = text;
  notice.toggleAttribute("data-error", isError);
  notice.hidden = !text;
  if (text && !persistent) noticeTimer = setTimeout(() => { notice.hidden = true; }, 4800);
}

function statusChip(value) {
  const span = document.createElement("span");
  span.className = "chip";
  span.textContent = value;
  span.dataset.tone = value === "OK" || value === "CACHE" ? "good"
    : value === "SERVER_ERROR" || value === "INVALID_INPUT" ? "error"
    : value === "AD_BLOCK" || value === "NOT_FOUND" ? "warn" : "flow";
  return span;
}

function tableRows(id, entries, columnCount, empty, valuesFor) {
  const tbody = byId(id);
  tbody.replaceChildren();
  if (!entries.length) {
    const cell = tbody.insertRow().insertCell();
    cell.colSpan = columnCount;
    cell.className = "empty-cell";
    cell.textContent = empty;
    return;
  }
  for (const entry of entries) {
    const row = tbody.insertRow();
    for (const value of valuesFor(entry)) {
      const cell = row.insertCell();
      if (value instanceof HTMLElement) cell.append(value);
      else cell.textContent = value;
    }
  }
}

function renderState(data) {
  snapshot = data;
  const config = data.settings;
  const stats = data.stats;
  const simulator = data.simulator;
  const endpoint = config.upstream_ip + ":" + config.upstream_port;
  const mode = config.real_dns_enabled ? "Real DNS" : "Simulated UDP";
  const modePill = byId("mode-pill");
  byId("mode-label").textContent = mode;
  modePill.toggleAttribute("data-offline", simulator.available && !simulator.running);
  modePill.title = endpoint;
  const examples = byId("examples");
  if (config.real_dns_enabled) {
    examples.firstElementChild.textContent = "Try";
    const names = ["example.com", "iana.org", "cloudflare.com"];
    examples.querySelectorAll("button").forEach((button, i) => {
      button.dataset.domain = names[i];
      button.textContent = names[i];
    });
  } else {
    const names = ["normal.example.net", "ads.example.com", "service.example.org"];
    examples.querySelectorAll("button").forEach((button, i) => {
      button.dataset.domain = names[i];
      button.textContent = names[i];
    });
  }
  byId("stat-total").textContent = number.format(stats.total);
  byId("stat-total-note").textContent = number.format(stats.upstream) + " sent upstream";
  byId("stat-cache").textContent = number.format(stats.cache);
  const entries = data.cache.length;
  byId("stat-cache-note").textContent = config.cache_enabled
    ? entries + (entries === 1 ? " active entry" : " active entries") : "Cache disabled";
  byId("stat-policies").textContent = number.format(stats.ad_block + stats.sanction);
  byId("stat-policy-note").textContent = stats.ad_block + (stats.ad_block === 1 ? " ad block" : " ad blocks")
    + " · " + stats.sanction + (stats.sanction === 1 ? " sanction" : " sanctions");
  byId("stat-errors").textContent = number.format(stats.errors);

  const capacity = config.cache_max_entries === null ? "unlimited FIFO capacity" : config.cache_max_entries + " FIFO capacity";
  byId("cache-caption").textContent = config.cache_enabled ? data.cache.length + " entries · " + capacity : "DNS cache is disabled.";
  byId("clear-cache").disabled = !data.cache.length;
  tableRows("cache-rows", data.cache, 3, "The cache is empty.", (row) => [row.domain, row.ip, row.ttl + " s"]);

  byId("simulator-caption").textContent = simulator.available
    ? simulator.running ? endpoint + " · " + simulator.requests + " UDP requests" : endpoint + " · stopped"
    : "Available in simulated UDP mode with a loopback address.";
  byId("simulator-toggle").disabled = !simulator.available;
  byId("simulator-toggle").textContent = simulator.running ? "Stop simulator" : "Start simulator";
}

function fillSettings() {
  if (!snapshot) return;
  for (const [name, value] of Object.entries(snapshot.settings)) {
    const input = settings.namedItem(name);
    if (input.type === "checkbox") input.checked = value;
    else input.value = value === null ? "" : String(value);
  }
}

function renderResult(result) {
  byId("response-empty").hidden = true;
  const detail = byId("result-details");
  detail.hidden = true;
  const status = statusChip(result.status);
  status.id = "result-status";
  byId("result-status").replaceWith(status);
  byId("result-domain").textContent = result.domain || "(empty)";
  byId("result-ip").textContent = result.ip || "—";
  byId("result-ttl").textContent = result.ttl === null ? "—" : result.ttl + " s";
  byId("result-ms").textContent = result.elapsed_ms.toFixed(2) + " ms";
  byId("result-message").textContent = "Source " + result.source + " · " +
    descriptions[result.status === "OK" ? result.source : result.status];
  const index = resultNodes.findIndex((node) => node.dataset.source === result.source);
  resultNodes.forEach((node, i) => {
    node.classList.toggle("checked", i < index);
    node.classList.toggle("selected", i === index);
  });
  detail.hidden = false;
}

async function updateActivity() {
  const rows = await api("activity");
  tableRows("overview-activity", rows.slice(0, 5), 4, "Your queries will appear here.", (row) =>
    [row.domain, statusChip(row.source), statusChip(row.status), row.time.split(" ").at(-1)]);
  tableRows("activity-rows", rows, 6, "The activity log is empty.", (row) =>
    [row.time, row.domain, statusChip(row.source), statusChip(row.status), row.ip, row.ttl]);
}

async function updatePolicies() {
  const data = await api("policies");
  byId("ads").value = data.ads;
  byId("sanctions").value = data.sanctions;
}

async function updateState() {
  const version = ++stateVersion;
  const data = await api("state");
  if (stateVersion === version) renderState(data);
}

async function openView(id, focusHeading = true) {
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
    heading.focus();
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  try {
    if (!snapshot || id === "cache") await updateState();
    if (id === "settings") fillSettings();
    if (id === "policies" && !policyForm.dataset.loaded) {
      await updatePolicies();
      policyForm.dataset.loaded = "true";
    }
    if (id === "overview" || id === "activity") await updateActivity();
  } catch (error) {
    message(error.message, true);
  }
}

async function action(path, data, sourceButton, confirmation) {
  actionCount++;
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
    actionCount--;
  }
}

menus.forEach((button) => button.addEventListener("click", () => openView(button.dataset.view)));
document.querySelectorAll("[data-open]").forEach((button) =>
  button.addEventListener("click", () => openView(button.dataset.open)));

const searchForm = byId("resolve-form");
const searchButton = byId("resolve-button");
searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (searchButton.disabled) return;
  searchForm.closest(".hero").classList.add("is-querying");
  const label = searchButton.firstChild;
  const original = label.textContent;
  label.textContent = "Resolving… ";
  const result = await action("resolve", { domain: domainInput.value }, searchButton);
  label.textContent = original;
  searchForm.closest(".hero").classList.remove("is-querying");
  if (result) {
    renderState(result);
    renderResult(result.result);
    try { await updateActivity(); } catch (error) { message(error.message, true); }
  }
});

byId("examples").addEventListener("click", (event) => {
  const chip = event.target.closest("button[data-domain]");
  if (!chip || searchButton.disabled) return;
  domainInput.value = chip.dataset.domain;
  searchForm.requestSubmit();
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target.closest?.("input, textarea, select, [contenteditable]")) return;
  event.preventDefault();
  if (currentView !== "overview") openView("overview", false);
  domainInput.focus();
});

byId("refresh").addEventListener("click", async () => {
  try {
    await updateState();
    if (currentView === "activity" || currentView === "overview") await updateActivity();
    message("Dashboard refreshed.");
  } catch (error) { message(error.message, true); }
});

byId("clear-cache").addEventListener("click", async (event) => {
  const data = await action("cache/clear", {}, event.currentTarget, "Cache cleared.");
  if (data) renderState(data);
});

byId("reload-policies").addEventListener("click", async (event) => {
  const data = await action("policies/reload", {}, event.currentTarget, "Policy lists reloaded.");
  if (!data) return;
  renderState(data);
  try { await updatePolicies(); } catch (error) { message(error.message, true); }
});

policyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = await action("policies", {
    ads: byId("ads").value,
    sanctions: byId("sanctions").value,
  }, event.submitter, "Policy lists saved and reloaded.");
  if (data) renderState(data);
});

byId("use-default-upstream").addEventListener("click", () => {
  const real = settings.namedItem("real_dns_enabled").value === "true";
  settings.namedItem("upstream_ip").value = real ? "1.1.1.1" : "127.0.0.1";
  settings.namedItem("upstream_port").value = real ? "53" : "5354";
});

byId("settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
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
  }, event.submitter, "Settings saved and cache cleared.");
  if (data) {
    renderState(data);
    fillSettings();
  }
});

byId("simulator-toggle").addEventListener("click", async (event) => {
  const running = !snapshot.simulator.running;
  const data = await action("simulator", { running }, event.currentTarget,
    running ? "Local simulator started." : "Local simulator stopped.");
  if (data) renderState(data);
});

async function initialize() {
  try {
    await Promise.all([updateState(), updateActivity()]);
    if (snapshot?.warnings.length) message(snapshot.warnings.join("\n"), true, true);
  } catch (error) {
    byId("mode-label").textContent = "Connection failed";
    byId("mode-pill").setAttribute("data-offline", "");
    message(error.message, true, true);
  }
}

setInterval(() => {
  if (currentView === "cache" && !actionCount && document.visibilityState === "visible") {
    updateState().catch((error) => message(error.message, true));
  }
}, 1000);

initialize();
