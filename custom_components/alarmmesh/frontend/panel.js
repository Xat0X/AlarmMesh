import { exercise, incidentDetail, careView } from "./family.js?v=family-beta16";
import { TEXT } from "./translations.js?v=heiman-linked-stop-1";
import { Drafts } from "./drafts.js?v=family-beta16";

// Safe DOM construction: names, labels and registry data are always text nodes.
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
};
const icon = (name) => {
  const node = el("ha-icon");
  node.setAttribute("icon", `mdi:${name}`);
  node.setAttribute("aria-hidden", "true");
  return node;
};
const button = (label, action, cls = "button") => {
  const node = el("button", label, cls);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
};

export class AlarmMeshPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.page = "overview";
    this.data = null;
    this.transport = "loading";
    this.generation = 0;
    this.detail = null;
    let storage;try{storage=globalThis.localStorage;}catch{storage=null;}this.drafts=new Drafts(storage);
    this.deviceFilters = {name:"", room:"", group:"", provider:"", status:"", maintenance:""};
    this.activityFilters = {source:"", group:"", kind:"", result:"", category:""};
    this.onDisconnected = () => { this.generation++; this.unsubscribe?.()?.catch?.(() => {}); this.unsubscribe = null; this.data = null; this.diagnostics = null; this.transport = "offline"; this.offlineDraft(); this.updateTestResult(); this.render(); };
    this.onReady = () => this.subscribe();
  }
  set hass(value) {
    const old = this._hass;
    this._hass = value;
    if(value.user?.id) this.drafts.switchUser(value.user.id);
    if(old?.user?.id && old.user.id!==value.user?.id) {this.clearDraftsForOldUser(old.user.id);this.closeDialog();}
    if (this.isConnected && (old?.connection !== value.connection || old?.user?.is_admin !== value.user?.is_admin || old?.user?.id !== value.user?.id)) this.bindConnection();
    if (old?.language !== value.language || old?.themes?.darkMode !== value.themes?.darkMode) this.render();
    if (!value.user?.is_admin) { this.generation++; this.data = null; this.closeDialog(); this.render(); }
  }
  set narrow(value) { this._narrow = value; }
  set panel(value) { this._panel = value; }
  get t() { return TEXT[this._hass?.language?.startsWith("nl") ? "nl" : "en"]; }
  connectedCallback() { const query=new URLSearchParams(window.location?.search || ""); this.linkedIncident=query.get("incident"); this.linkedSource=query.get("source"); if(this.linkedIncident) this.page="incidents"; else if(["incidents","maintenance"].includes(query.get("view"))) this.page=query.get("view"); if (this._hass) this.bindConnection(); this.render(); }
  disconnectedCallback() { this.unbindConnection(); this.closeDialog(); }
  unbindConnection() {
    this.generation++;
    this.unsubscribe?.()?.catch?.(() => {}); this.unsubscribe = null;
    this.connection?.removeEventListener("disconnected", this.onDisconnected);
    this.connection?.removeEventListener("ready", this.onReady);
    this.connection = null; this.catalog = null; this.catalogError = false; this.diagnostics = null;
    this.data = null;
  }
  bindConnection() {
    this.unbindConnection();
    this.connection = this._hass.connection;
    this.connection.addEventListener("disconnected", this.onDisconnected);
    this.connection.addEventListener("ready", this.onReady);
    this.subscribe();
  }
  async subscribe() {
    if (!this.isConnected || !this._hass?.user?.is_admin) return;
    const generation = ++this.generation;
    this.unsubscribe?.()?.catch?.(() => {}); this.unsubscribe = null;
    this.data = null; this.transport = "loading"; this.render();
    try {
      const unsubscribe = await this.connection.subscribeMessage((data) => {
        if (generation !== this.generation || !this.isConnected) return;
        this.data = data.available ? data : null;
        this.transport = data.available ? "ready" : "notLoaded";
        if (data.available && ["route","drill"].includes(this.detail?.kind) && data.result.smoke === "SMOKE_REPORTED") {
          this.linkedIncident=null; this.go("incidents");
        }
        if(data.available && this.linkedSource){const id=this.linkedSource;this.linkedSource=null;if(data.sources.some(s=>s.entity_id===id))this.openDialog({kind:"source",id});}
        if (!data.available) this.offlineDraft();
        else if (this.shadowRoot.querySelector(".offline-draft")) { this.shadowRoot.querySelector(".offline-draft").remove(); for (const b of this.shadowRoot.querySelectorAll('dialog button[type="submit"],dialog .confirm-execute,dialog .confirm-linking')) if (!b.dataset.started && !b.dataset.confirmLocked && !b.dataset.reopenRequired) b.disabled = false; }
        if (data.available && this.detail?.pendingRecovery?.interrupted) this.detail.showMemberships();
        this.updateTestResult();
        if(data.available && this.detail?.kind==="route" && this.detail.resumed)this.detail.resumed();
        if (data.available && this.detail?.kind === "edit") this.detail.refreshSounders?.();
        if (data.available && this.detail?.kind === "alarmsettings") this.detail.refresh?.();
        if (!data.available || this.page !== "catalog" || !this.shadowRoot.querySelector(".catalog-filters")) this.render();
        if (this.detail && !["edit", "delete", "settings", "maintenance", "test", "reminder", "copy", "route", "recovery", "alarmsettings", "phoneObservation", "care"].includes(this.detail.kind)) this.renderDialog();
      }, { type: "alarmmesh/subscribe" }, { resubscribe: false });
      if (generation !== this.generation || !this.isConnected) unsubscribe()?.catch?.(() => {});
      else this.unsubscribe = unsubscribe;
    } catch { if (generation === this.generation) { this.transport = "error"; this.render(); } }
  }
  async go(page) {
    this.closeDialog(); this.page = page; this.render();
    if (page === "diagnostics") this.loadDiagnostics();
    this.shadowRoot.querySelector(".shell")?.scrollIntoView?.({ block: "start", behavior: "instant" });
    if (page === "catalog" && !this.catalog && this._hass?.user?.is_admin) {
      const connection = this.connection;
      try {
        const data = await this._hass.callWS({ type: "alarmmesh/catalog" });
        if (this.isConnected && this.connection === connection && this._hass?.user?.is_admin && data?.entries) { this.catalog = data; this.render(); }
      } catch { this.catalogError = true; this.render(); }
    }
  }
  capabilityLabel(cap) {
    return this.t[cap.status === "linkable" && !cap.controls.some(c => c.safe_stop) ? "activation_only" : cap.status] || this.t.not_confirmed;
  }
  badge(result) {
    const state = result.smoke || result.status;
    const node = el("span", this.t[state] || this.t.unknown, `badge ${state === "SMOKE_REPORTED" ? "danger" : state === "NO_SMOKE_REPORTED" ? "clear" : "warning"}`);
    node.prepend(icon(state === "SMOKE_REPORTED" ? "fire" : state === "NO_SMOKE_REPORTED" ? "check-circle-outline" : "alert-circle-outline"));
    return node;
  }
  choose() {
    // HA's integration page owns the existing config/options flow and validation.
    window.history.pushState(null, "", "/config/integrations/integration/alarmmesh");
    window.dispatchEvent(new Event("location-changed"));
  }
  updateRecoverySmoke() {
    const dialog=this.shadowRoot.querySelector("dialog");
    if (!dialog) return;
    let warning=dialog.querySelector(".recovery-smoke");
    if(this.data?.result.smoke!=="SMOKE_REPORTED"){warning?.remove();return;}
    if(!warning){warning=el("p",undefined,"notice recovery-smoke");warning.setAttribute("role","alert");dialog.insertBefore(warning,dialog.children[1]);}
    warning.textContent=`${this.t.SMOKE_REPORTED}: ${this.data.sources.filter(s=>s.status==="SMOKE_REPORTED").map(s=>`${this.sourceName(s.entity_id)}${s.capability?.matter?.source_kind === "interconnect_smoke" ? ` · ${this.t.forwardedSmoke}` : ""}`).join(", ")}`;
  }
  render() {
    this.updateRecoverySmoke();
    if (!this.shadowRoot) return;
    this.shadowRoot.querySelector("dialog")?.classList.toggle("dark", Boolean(this._hass?.themes?.darkMode));
    const t = this.t;
    const sticky = this.shadowRoot.activeElement;
    const stickyKey = sticky?.dataset.sticky, selection = stickyKey ? [sticky.selectionStart, sticky.selectionEnd] : null;
    const link = el("link"); link.rel = "stylesheet"; link.href = "/alarmmesh-assets/panel.css?v=family-beta16";
    const shell = el("div", undefined, "shell");
    shell.classList.toggle("dark", Boolean(this._hass?.themes?.darkMode));
    const side = el("aside");
    const brand = el("div", undefined, "brand");
    const image = el("img"); image.src = "/alarmmesh-brand/icon.png"; image.alt = "";
    brand.append(image, el("strong", "AlarmMesh")); side.append(brand);
    const nav = el("nav"); nav.setAttribute("aria-label", "AlarmMesh");
    for (const [page, symbol] of [["overview", "view-dashboard-outline"], ["devices", "smoke-detector"], ["rooms", "floor-plan"], ["groups", "select-group"], ["settings", "cog-outline"]]) {
      const item = button(t[page], () => this.go(page), "nav-item"); item.prepend(icon(symbol));
      item.dataset.page = page;
      if (this.page === page) item.setAttribute("aria-current", "page");
      nav.append(item);
    }
    side.append(nav, el("small", t.noEvents, "side-note"));
    const workspace = el("div", undefined, "workspace");
    const header = el("header");
    const menu = button("☰", () => this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true })), "menu-button");
    menu.setAttribute("aria-label", "Home Assistant menu");
    header.append(menu, icon("home-outline"), el("span", this.page === "diagnostics" ? "AlarmMesh" : this.data?.title || "AlarmMesh"), el("span", "", "muted"));
    const main = el("main");
    main.append(el("h1", t[this.page]));
    if (this.page === "groups") main.append(el("p", t.groupIntro, "subtitle"));
    if (!this._hass?.user?.is_admin) main.append(el("p", t.restricted, "notice"));
    else if (!this.data) {
      const message = el("div", undefined, "notice"); message.setAttribute("role", "status");
      message.append(el("p", t[this.transport] || t.error));
      if (this.transport !== "loading") message.append(button(t.retry, () => this.subscribe()));
      main.append(message);
    } else {
      const data = this.data;
      if (this.page === "overview") this.renderOverview(main);
      if (this.page === "catalog") this.renderCatalog(main);
      if (this.page === "settings") this.renderSettings(main);
      if (this.page === "incidents") this.renderIncidents(main);
      if (this.page === "maintenance") this.renderMaintenance(main);
      if (this.page === "diagnostics") this.renderDiagnostics(main);
      if (this.page === "activity") this.renderActivity(main);
      if (this.page === "matterHelp") this.renderMatterHelp(main);
      if (this.page === "devices") {
        main.append(this.section(t.selected, button(t.choose, () => this.choose())));
        this.renderDevices(main);
      }
      if (this.page === "rooms") this.roomCards(main, data.rooms);
      if (this.page === "groups") {
        main.append(this.section(null, button(t.newGroup, () => this.openDialog({ kind: "edit", group: null }), "button primary")));
        if (!data.groups.length) main.append(el("p", t.noGroups, "notice"));
        const cards = el("div", undefined, "cards");
        for (const group of data.groups) {
          const card = button("", () => this.openDialog({ kind: "group", id: group.id }), "card room-card");
          card.append(icon("select-group"), el("h3", group.name), this.badge(group.result), el("p", t[group.result.availability]), el("p", this.detectorCount(group.members.length)));
          if (group.unselected.length) card.append(el("p", `${group.unselected.length} · ${t.stale}`, "warning-text"));
          card.append(el("p", `${t.linkTogether}: ${t[group.linking_status || "disabled"]}`),el("p",`${t.incidentActions}: ${t[group.actions?.enabled ? "enabled":"disabled"]}`));
          cards.append(card);
        }
        main.append(cards);
      }
      if (!data.sources.length && this.page !== "overview") main.append(el("p", t.empty, "notice"), button(t.choose, () => this.choose(), "button primary"));
    }
    main.append(el("footer", t.note)); workspace.append(header, main); shell.append(side, workspace);
    // Keep an open form separate: push updates never erase unsaved input or focus.
    const previous = this.shadowRoot.querySelector(".shell");
    if (previous) previous.replaceWith(shell);
    else this.shadowRoot.append(link, shell);
    if (stickyKey) { const field = [...shell.querySelectorAll('[data-sticky]')].find(n=>n.dataset.sticky === stickyKey); field?.focus({preventScroll:true}); if (field?.setSelectionRange && selection[0] != null) field.setSelectionRange(...selection); }
  }
  section(title, action) { const node = el("div", undefined, "section-head"); if (title) node.append(el("h2", title)); if (action) node.append(action); return node; }
  renderOverview(main) {
    const t = this.t, data = this.data, smoke = data.result.smoke;
    if (!data.sources.length) {
      const welcome = el("section", undefined, "notice welcome");
      welcome.append(icon("smoke-detector"), el("h2", t.firstDetector), el("p", t.firstDetectorNote), button(t.choose, () => this.choose(), "button primary"));
      main.append(welcome);
      return;
    }
    const hero = el("section", undefined, `hero ${smoke === "SMOKE_REPORTED" ? "alarm" : smoke === "INDETERMINATE" ? "uncertain" : ""}`);
    hero.setAttribute("role", "status");
    hero.append(icon(smoke === "SMOKE_REPORTED" ? "fire" : "smoke-detector"), el("h2", t[smoke] || t.unknown));
    hero.append(el("p", t[data.result.availability]));
    const active = data.sources.filter(s => s.status === "SMOKE_REPORTED");
    for (const source of active) hero.append(button(`${t.alarmFrom}: ${this.sourceName(source.entity_id)}${source.capability?.matter?.source_kind === "interconnect_smoke" ? ` · ${t.forwardedSmoke}` : ""}`, () => this.openDialog({ kind: "source", id: source.entity_id }), "alarm-source"));
    const attention = data.sources.filter(s => s.identity_changed || !["SMOKE_REPORTED", "NO_SMOKE_REPORTED"].includes(s.status));
    if (attention.length) {
      const missing = el("div", undefined, "hero-missing");
      missing.append(el("p", t.incompleteHelp));
      for (const source of attention) {
        const issue = el("section", undefined, "source-problem");
        issue.append(button(`${this.sourceName(source.entity_id)} · ${t[source.identity_changed ? "recovery_changed" : source.status] || t.UNKNOWN}`, () => this.openDialog({kind:"source", id:source.entity_id})));
        if (source.identity_changed || ["MISSING", "UNREACHABLE"].includes(source.status)) {
          if (source.status === "UNREACHABLE" && !source.identity_changed) issue.append(el("p", t.recovery_temporary));
          const temporary=source.status==='UNREACHABLE' && !source.identity_changed;
          const recover = button(temporary?t.checkConnection:t.recoverSource, () => this.openDialog({kind:temporary?'source':'recovery', id:source.entity_id}), "button source-recovery");
          recover.setAttribute("aria-label", `${temporary?t.checkConnection:t.recoverSource}: ${this.sourceName(source.entity_id)}`);
          issue.append(recover);
        }
        missing.append(issue);
      }
      hero.append(missing);
    }
    main.append(hero);
    this.renderDrafts(main);
    hero.append(button(t.viewIncidents, () => this.go("incidents"), "button incident-link"));
    hero.append(button(t.activity, () => this.go("activity")));
    hero.append(button(t.maintenance, () => this.go("maintenance"), "button maintenance-link"));
    hero.append(button(t.silentDrill,()=>this.openDialog({kind:"drill"})));
    hero.append(button(t.myAlarmSettings,()=>this.openDialog({kind:'alarmsettings'})));
    const stats = el("div", undefined, "stats");
    for (const [label, value, note] of [[t.sources, `${data.usable} / ${data.sources.length}`, data.usable === 1 ? t.usableSource : t.usable], [t.rooms, data.rooms.filter(r => r.id).length, "Home Assistant"], [t.groups, data.groups.length, t.organized]]) {
      const destination = label === t.sources ? "devices" : label === t.rooms ? "rooms" : "groups";
      const stat = button("", () => this.go(destination), "stat"); stat.setAttribute("aria-label", t[destination]); stat.append(el("span", label), el("strong", value), el("small", note)); stats.append(stat);
    }
    main.append(stats);
    const incident = data.incident;
    if (incident?.executor_state === "paused") main.append(el("p", t.execution_paused, "notice warning-text"));
    if (incident && (incident.active_sources.length || incident.targets.length)) {
      const section = el("section", undefined, "notice incident");
      section.setAttribute("aria-label", t.incident);
      section.append(el("h2", t.incident), el("p", t.commandNote));
      for (const id of incident.active_sources) section.append(el("p", `${t.rememberedSmoke}: ${data.sources.find(s => s.entity_id === id)?.name || id}`));
      for (const target of incident.targets) {
        const row = el("div", undefined, "execution-row");
        row.append(icon(["failed", "blocked", "stop_failed", "outcome_unknown"].includes(target.status) ? "alert-circle-outline" : "bullhorn-outline"), el("span", `${data.sources.find(s => s.entity_id === target.source)?.name || target.source} · ${t[target.status] || target.status}`));
        section.append(row);
      }
      main.append(section);
    }
    this.renderSetupGuide(main);

    const allRooms = button("→", () => this.go("rooms"));
    allRooms.setAttribute("aria-label", t.rooms);
    main.append(this.section(t.rooms, allRooms)); this.roomCards(main, data.rooms);
  }
  renderSetupGuide(parent) {
    const t = this.t, data = this.data;
    const guide = el("details", undefined, "setup-guide");
    guide.open = this.setupGuideOpen ?? false;
    guide.addEventListener("toggle", () => { this.setupGuideOpen = guide.open; });
    guide.append(el("summary", t.setupTitle), el("p", t.guidanceNote));
    const steps = el("ol", undefined, "setup-steps");
    const add = (title, note, label, action, key) => {
      const item = el("li"); item.dataset.step = key;
      const step = data.review?.steps.find(s => s.id === key);
      const state = step?.status || "unknown";
      const copy = el("div"); copy.append(el("h3", title), el("span", t['guide_' + state], `guide-state ${state}`), el("p", `${note}${step ? ` · ${t.savedCount}: ${step.count}` : ''}`));
      if (key === "groups") {
        for (const [id, label] of [["sounders", t.linkTogether], ["scripts", t.incidentActions]]) {
          const assessment = data.review?.steps.find(s => s.id === id);
          const status = assessment?.status || "unknown";
          const line = el("p", undefined, "group-setup-status"); line.dataset.step = id;
          line.append(el("span", label), el("span", t['guide_' + status], `guide-state ${status}`));
          copy.append(line);
        }
      }
      item.dataset.status = state;
      item.append(copy, button(label, action)); steps.append(item);
      if(key === "sources" && data.sources.some(s=>s.capability?.origin === "matter")) item.append(button(t.matterHelp,()=>this.go("matterHelp")));
      if (key === "notifications" && data.maintenance) {
        copy.append(el("p", `${t.maintenanceNotifications}: ${t[data.maintenance.settings.enabled ? "enabled" : "disabled"]}`));
        item.append(button(t.configureMaintenance, () => this.openDialog({kind: "maintenance"})));
      }
    };
    add(t.setupSources, data.sources.length ? `${data.sources.length} · ${t.selected}` : t.setupNoSources,
      t.choose, () => this.choose(), "sources");
    add(t.setupRooms, t.setupRoomsNote, t.rooms, () => this.go("rooms"), "rooms");
    add(t.setupGroups, t.groupSetupNote,
      t.groups, () => this.go("groups"), "groups");
    add(t.notifications, t.setupNotificationsNote, t.configureNotifications, () => this.openDialog({kind: "settings"}), "notifications");
    add(t.setupCheck, t.setupCheckNote, t.maintenance, () => this.go("maintenance"), "check");
    guide.append(steps); parent.append(guide);
  }
  issueAction(issue) {
    if (issue.purpose === "matter") return this.go("matterHelp");
    if (issue.purpose === "maintenance") return this.openDialog({kind:"maintenance"});
    if (issue.group) return this.openDialog({ kind: "edit", group: this.data.groups.find(g => g.id === issue.group) });
    if (issue.source && this.data.sources.some(s => s.entity_id === issue.source)) return this.openDialog({ kind: "source", id: issue.source });
    if (issue.code === "recipient_unavailable") return this.openDialog({ kind: "settings" });
    this.choose();
  }
  renderMaintenance(parent) {
    const t = this.t, data = this.data;
    const unavailable = data.sources.filter(source => source.identity_changed || ["MISSING", "UNREACHABLE", "UNKNOWN"].includes(source.status));
    for (const source of unavailable) {
      const issue = el("section", undefined, "notice maintenance-priority");
      const replacement = source.identity_changed || source.status === "MISSING";
      issue.append(el("h2", source.name), el("p", source.area_name || t.noRoom), el("p", t[source.identity_changed ? "recovery_changed" : source.status === "MISSING" ? "recovery_missing" : source.status === "UNREACHABLE" ? "recovery_temporary" : "UNKNOWN"]));
      issue.append(button(replacement ? t.recoverSource : t.inspectDetector, () => this.openDialog({kind:replacement ? "recovery" : "source", id:source.entity_id}), "button primary"));
      parent.append(issue);
    }
    parent.append(el("p",t.maintenanceSummary,"section-note"));
    const limits=el('details',undefined,'maintenance-limits');limits.append(el('summary',t.aboutInformation),el('p',t.maintenanceNote));parent.append(limits);
    if (data.maintenance) {
      const section = el("details", undefined, "notice maintenance-delivery");
      section.append(el("summary", t.maintenanceNotifications));
      section.append(el("h2", t.maintenanceNotifications), el("p", t[data.maintenance.settings.enabled ? "enabled" : "disabled"]), button(t.configureMaintenance, () => this.openDialog({kind: "maintenance"})));
      if (data.maintenance.error) section.append(el("p", t[data.maintenance.error] || t.error, "warning-text"));
      for (const issue of data.maintenance.issues) {
        const row = el("section", undefined, "maintenance-receipt");
        row.append(el("h3", `${issue.sources.map(id => data.sources.find(s => s.entity_id === id)?.name || id).join(", ")} · ${t['maintenance_' + issue.kind]}`), el("p", t[issue.reason] || t.guide_unknown));
        for (const [recipient, receipt] of Object.entries(issue.receipts)) for (const [phase, status] of Object.entries(receipt)) row.append(el("p", `${recipient.replace(/^mobile_app_/, "")} · ${t[phase === "problem" ? "maintenanceProblem" : "maintenanceRecoveryReceipt"]}: ${t['delivery_' + status] || t.guide_unknown}`));
        section.append(row);
      }
      section.append(el("small", t.maintenanceDeliveryNote)); parent.append(section);
    }
    const config = el("section", undefined, "notice configuration-issues");
    config.append(el("h2", t.configurationIssues));
    const issues = data.review?.issues;
    if (!issues) config.append(el("p", t.guide_unknown));
    else if (!issues.length) config.append(el("p", t.noConfigurationIssues));
    for (const issue of issues || []) {
      const name = data.sources.find(s => s.entity_id === issue.source)?.name || data.groups.find(g => g.id === issue.group)?.name || issue.target || issue.source || "AlarmMesh";
      const row = el("div", undefined, "check-item"); row.dataset.issue = issue.code;
      row.append(icon("information-outline"), el("span", `${name}: ${t[issue.code] || t.error}`), button(t.reviewAssignment, () => this.issueAction(issue)));
      config.append(row);
    }
    parent.append(config, this.section(t.deviceReports));
    for (const source of data.sources) {
      const card = el("section", undefined, "notice maintenance-device"); card.dataset.source = source.entity_id;
      card.append(el("h3", source.name), el("p", source.area_name || t.noRoom));
      const health = source.capability?.details?.maintenance;
      const table = el("dl");
      const field = (label, value, warn = false) => { table.append(el("dt", label), el("dd", value, warn ? "warning-text" : "")); };
      field(t.battery, health?.battery_percent == null ? t.guide_unknown : `${health.battery_percent}%`, health?.battery_percent != null && health.battery_percent <= 20);
      const low = health?.battery_low === true || health?.battery_percent != null && health.battery_percent <= 20;
      field(t.battery_low, low ? t.lowBatteryPresentation : health?.battery_low === false || health?.battery_percent != null ? t.noLowBatteryReport : t.guide_unknown, low);
      if (health && "end_of_service" in health) field(t.end_of_service, health.end_of_service == null ? t.guide_unknown : t[health.end_of_service ? "matter_expired" : "matter_not_expired"], health.end_of_service === true);
      field(t.fault, health?.fault == null ? t.guide_unknown : health.fault ? t.faultReported : t.noFaultReport, health?.fault === true);
      field(t.sourceAvailability, t[source.status] || t.guide_unknown);
      field(t.controlAvailability, source.capability ? t[source.capability.reason] || t.guide_unknown : t.guide_unknown);
      card.append(table,el("p",data.groups.filter(g=>g.members.includes(source.entity_id)).map(g=>g.name).join(", ")));
      if(source.identity_changed || source.status==="MISSING") card.append(el("p",t[source.identity_changed ? "recovery_changed":"recovery_missing"]),button(t.recoverSource,()=>this.openDialog({kind:"recovery",id:source.entity_id})));
      else if(source.status==="UNREACHABLE") card.append(el("p",t.recovery_temporary));
      const record = source.selftest?.record;
      card.append(el("p", record ? `${t.lastTest}: ${this.formatTime(record.started)} · ${t['test_' + record.status] || t.guide_unknown}` : `${t.lastTest}: ${t.noTestRequest}`));
      if (record) card.append(el("small", t.deviceResultNote));
      card.append(button(t.inspectDetector, () => this.openDialog({kind: "source", id: source.entity_id})));
      parent.append(card);
    }
    if (data.reminders) this.renderReminders(parent);
    if (!data.sources.length) parent.append(button(t.choose, () => this.choose()));
  }
  renderGroupChecks(parent, group) {
    const t = this.t, data = this.data;
    const section = el("section", undefined, "group-checks");
    section.setAttribute("aria-label", t.groupCheckTitle);
    section.append(el("h3", t.groupCheckTitle), el("p", t.groupCheckNote));
    const mode = el("p", `${t.linkTogether}: ${t[group.linking_status || "disabled"]}`, "configuration-mode");
    section.append(mode);
    const list = el("ul", undefined, "check-list");
    const add = (message, actionLabel, action, warning = false, key = "") => {
      const row = el("li", undefined, warning ? "check-item warning-text" : "check-item");
      if (key) row.dataset.check = key;
      row.append(icon(warning ? "alert-circle-outline" : "information-outline"), el("span", message));
      if (action) row.append(button(actionLabel, action));
      list.append(row);
    };
    const edit = () => this.openDialog({ kind: "edit", group });
    if (group.members.length < 2) add(t.checkFewMembers, t.edit, edit, false, "members");
    for (const id of group.unselected || []) add(`${t.stale}: ${id}`, t.choose, () => this.choose(), true, "unselected");
    const sources = data.sources.filter(s => group.members.includes(s.entity_id));
    for (const source of sources) {
      if (!["SMOKE_REPORTED", "NO_SMOKE_REPORTED"].includes(source.status))
        add(`${source.name}: ${t.checkSourceUnavailable}`, t.inspectDetector,
          () => this.openDialog({ kind: "source", id: source.entity_id }), true, "source");
      else if (source.status === "SMOKE_REPORTED")
        add(`${source.name}: ${t.checkSmokeActive}`, t.inspectDetector,
          () => this.openDialog({ kind: "source", id: source.entity_id }), true, "smoke");
    }
    const bindings = group.linking?.bindings || [];
    let unresolved = 0, activationOnly = 0;
    if (!bindings.length) add(t.checkNoTargets, t.edit, edit, false, "targets");
    for (const binding of bindings) {
      const source = data.sources.find(s => s.entity_id === binding.source);
      const cap = source?.capability;
      const control = cap?.controls?.find(c => c.source === binding.source && c.target === binding.target && c.profile === binding.profile && c.identity === binding.identity);
      const checked = group.binding_checks?.find(c => c.source === binding.source && c.target === binding.target);
      if (checked ? !checked.valid : !group.members.includes(binding.source) || !source || cap?.status !== "linkable" || !control) {
        unresolved++;
        const reason = checked ? t[checked.reason] || t.control_changed : cap && cap.status !== "linkable" ? (t[cap.reason] || t.control_changed) : t.control_changed;
        add(`${source?.name || binding.source}: ${reason}`, t.edit, edit, true, "binding");
      } else if (!control.safe_stop) activationOnly++;
    }
    if (activationOnly) add(`${activationOnly} · ${t.checkActivationOnly}`, null, null, false, "activation-only");
    if (group.linking_status === "review_needed" && !unresolved && !(group.unselected || []).length)
      add(t.checkBackendReview, t.edit, edit, true, "backend");
    if (bindings.length && !unresolved && !(group.unselected || []).length)
      add(t.checkMappingsCurrent, null, null, false, "current");
    if (!group.linking?.enabled) add(t.checkDisabled, null, null, false, "disabled");
    const outcomes = data.incident?.targets || [];
    for (const outcome of outcomes.filter(o => bindings.some(b => b.target === o.target))) {
      if (["failed", "blocked", "stop_failed", "outcome_unknown", "not_stopped"].includes(outcome.status)) {
        const source = data.sources.find(s => s.entity_id === outcome.source);
        add(`${source?.name || outcome.source}: ${t[outcome.status] || outcome.status}. ${t.checkFailureAdvice}`,
          source ? t.inspectDetector : null,
          source ? () => this.openDialog({ kind: "source", id: source.entity_id }) : null, true, "execution");
      }
    }
    section.append(list); parent.append(section);
  }
  sourceList(parent, sources) {
    const list = el("div", undefined, "source-list");
    for (const source of sources) {
      const row = button("", () => this.openDialog({ kind: "source", id: source.entity_id }), "source");
      const name = el("span", undefined, "source-name"); name.append(el("strong", source.name), el("small", [source.area_name || this.t.noRoom, source.manufacturer, source.model].filter(Boolean).join(" · ")));
      if (source.capability) name.append(el("small", `${this.providerLabel(source.capability)} · ${this.capabilityLabel(source.capability)}`));
      if (this.data.sources.filter(s => s.name === source.name && s.area_id === source.area_id).length > 1) name.append(el("small", source.entity_id, "source-identity"));
      const health = source.capability?.details?.maintenance;
      const percent = health?.battery_percent;
      const valid = !source.identity_changed && typeof percent === "number" && Number.isFinite(percent) && percent >= 0 && percent <= 100;
      const low = !source.identity_changed && (health?.battery_low === true || valid && percent <= 20);
      const battery = el("span", valid ? `${this.t.battery}: ${percent}%${low ? ` · ${this.t.lowBatteryShort}` : ''}` : low ? this.t.batteryLowShort : this.t.batteryUnknown, `source-battery${low ? ' warning-text' : ''}`);
      battery.prepend(icon(low ? "battery-alert-variant-outline" : valid ? "battery-outline" : "battery-unknown"));
      name.append(battery);
      row.append(icon("smoke-detector"), name, this.badge(source), icon("chevron-right"));
      const item = el("section", undefined, "source-entry");
      const route = button(this.t.alarmRoute, () => this.openDialog({kind:"route", id:source.entity_id}), "button source-route");
      route.setAttribute("aria-label", `${this.t.alarmRoute} · ${source.name}`);
      item.append(row, route);
      list.append(item);
    }
    parent.append(list);
  }
  roomCards(parent, rooms) {
    const cards = el("div", undefined, "cards");
    for (const room of rooms) {
      const card = button("", () => this.openDialog({ kind: "room", id: room.id }), "card room-card");
      card.append(icon("floor-plan"), this.badge(room.result), el("h3", room.name || this.t.noRoom), el("p", this.t[room.result.availability]), el("p", `${room.members.length} ${room.members.length === 1 ? this.t.detector : this.t.devices.toLowerCase()}`)); cards.append(card);
    }
    parent.append(cards);
  }
  openDialog(detail) {
    if (["drill","route"].includes(detail.kind) && !this.data) return;
    if (["drill","route"].includes(detail.kind) && this.data?.result.smoke==="SMOKE_REPORTED") {this.linkedIncident=null;this.go("incidents");return;}
    this.detail?.dispose?.();
    if (!this.detail) this.previousFocus = this.shadowRoot.activeElement;
    this.detail = detail;
    const draft=this.drafts.read(this._hass?.user?.id,this.data?.entry_id)[this.draftKey(detail)];
    if(draft) this.detail.pendingDraft=draft;
    this.renderDialog();
    const dialog = this.shadowRoot.querySelector("dialog");
    if (dialog) { dialog.querySelector("button")?.focus(); dialog.scrollTop = 0; }
  }
  closeDialog() {
    this.detail?.dispose?.();
    this.shadowRoot?.querySelector("dialog")?.remove(); this.detail = null;
    if (this.previousFocus?.isConnected) this.previousFocus.focus();
    else this.shadowRoot?.querySelector('[aria-current="page"]')?.focus();
  }
  renderDialog() {
    if (!this.detail || !this.data) return;
    const t = this.t, detail = this.detail;
    let dialog = this.shadowRoot.querySelector("dialog");
    const focusIndex = dialog ? [...dialog.querySelectorAll("button,input")].indexOf(this.shadowRoot.activeElement) : -1;
    const first = !dialog;
    if (first) { dialog = el("dialog"); this.shadowRoot.append(dialog); }
    else dialog.replaceChildren();
    dialog.classList.toggle("dark", Boolean(this._hass?.themes?.darkMode));
    dialog.setAttribute("aria-label", t.details);
    const close = button(t.close, () => this.closeDialog());
    dialog.append(close);
    if(detail.returnTo==='alarmsettings')dialog.append(button(t.backToAlarmSettings,()=>this.openDialog({kind:'alarmsettings'})));
    if(detail.pendingDraft) {
      const draft=detail.pendingDraft, valid=draft.signature===this.draftSignature();
      dialog.append(el("h2",t.draftFound),el("p",valid ? t.draftReview : t.draftChanged));
      if(valid) dialog.append(button(t.continueDraft,()=>{detail.restoredDraft=draft;delete detail.pendingDraft;this.renderDialog();}));
      dialog.append(button(t.discardDraft,()=>{this.clearDraft();delete detail.pendingDraft;this.renderDialog();}));
      if(first){dialog.showModal();close.focus();}return;
    }
    if(detail.restoredDraft) dialog.append(el("p",t.draftRestored,"notice"));
    if (detail.kind === "source") {
      const source = this.data.sources.find(s => s.entity_id === detail.id);
      if (!source) { this.closeDialog(); return; }
      dialog.append(el("h2", source.name), this.badge(source));
      careView(this,dialog,source);
      const props = el("dl");
      for (const [label, value] of [[t.state, source.ha_state || t.MISSING], [t.room, source.area_name || t.noRoom], [t.device, source.device_name], [t.manufacturer, source.manufacturer], [t.model, source.model]]) {
        props.append(el("dt", label), el("dd", value || t.unavailable));
      }
      dialog.append(el("p", source.area_name || t.noRoom), button(t.alarmRoute, () => this.openDialog({kind:"route", id:source.entity_id}), "button primary"));
      const recover = button(t.recoverSource, () => this.openDialog({kind:"recovery", id:source.entity_id}));
      if (source.identity_changed || source.status === "MISSING") dialog.append(el("p", t[source.identity_changed ? "recovery_changed" : "recovery_missing"], "notice"), recover);
      else if (source.status === "UNREACHABLE") dialog.append(el("p", t.recovery_temporary, "notice"));
      const technical = el("details", undefined, "advanced-options detector-technical");
      technical.append(el("summary", t.technicalDetails), props);
      if (!recover.isConnected) technical.append(recover);
      dialog.append(technical);
      if (!source.capability) { const technical = el("details"); technical.append(el("summary", t.requirements), el("p", `${t.entity}: ${source.entity_id}`)); dialog.append(technical); }
      if (source.capability) {
        const technicalStart = [...dialog.children];
        const cap = source.capability;
        dialog.append(el("h3", t.functions), el("p", `${this.providerLabel(cap)} / ${this.capabilityLabel(cap)}`));
        this.detectorDetails(dialog, source);
        if (cap.matter) this.matterDetails(dialog,source);
        if (cap.zwave) {
          dialog.append(el("p",t.zwave_observation_only,"notice"),el("p",t.zwaveSetup));
          const help=el("a",t.zwaveHelp);help.href=t.zwaveSetupUrl;help.target="_blank";help.rel="noopener noreferrer";dialog.append(help);
        }
        const limitations = el("details"); limitations.append(el("summary", t.requirements), el("p", t[cap.reason] || t.no_verified_profile), el("p", t.physicalNotTested, "muted"));
        limitations.append(el("p", `${t.entity}: ${source.entity_id}`));
        for (const control of cap.controls) limitations.append(el("p", `${t.proposedControl}: ${control.target}`));
        dialog.append(limitations);
        for (const child of [...dialog.children]) if (!technicalStart.includes(child)) technical.append(child);
      }
      if (source.selftest) {
        dialog.append(el("h3", t.selfTests), el("p", t[source.selftest.reason]));
        if (source.selftest.record) dialog.append(el("p", `${t.lastTest}: ${t['test_' + source.selftest.record.status]} · ${new Date(source.selftest.record.started).toLocaleString(this._hass.language)}`));
        if (source.selftest.available) {
          if (!source.selftest.control.has_explicit_result) dialog.append(el("p", t.selfTestNoResult));
          dialog.append(button(t.startSelfTest, () => this.openDialog({ kind: "test", actionKind: "selftest", target: source.entity_id, identity: source.selftest.control.identity, name: source.name }), "button destructive"));
        }
      }
      if (this.data.reminders) { const reminder = this.data.reminders.items.find(r=>r.source === source.entity_id); dialog.append(el("h3", t.reminders), el("p", reminder ? `${reminder.date} · ${t['reminder_' + reminder.status] || t.guide_unknown}` : t.reminderDisabled), button(t.configureReminder, ()=>this.openDialog({kind:"reminder", id:source.entity_id}))); }
      dialog.append(el("h3", t.membership));
      if (!source.groups.length) dialog.append(el("p", t.noGroups));
      for (const group of this.data.groups.filter(g => source.groups.includes(g.id))) dialog.append(button(group.name, () => this.openDialog({ kind: "group", id: group.id })));
      const info = button("Home Assistant", () => {
        this.closeDialog();
        this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: source.entity_id }, bubbles: true, composed: true }));
      });
      dialog.append(el("h3", t.explanation), el("p", t.reportNote), info);
    } else if (detail.kind === "room" || detail.kind === "group") {
      const collection = detail.kind === "room" ? this.data.rooms : this.data.groups;
      const group = collection.find(g => g.id === detail.id);
      if (!group) { this.closeDialog(); return; }
      dialog.append(el("h2", group.name || t.noRoom), this.badge(group.result), el("p", t[group.result.availability]));
      if (detail.kind === "group") {
        dialog.append(button(t.edit, () => this.openDialog({kind:"edit", group}), "button primary"), button(t.optionalActions, () => this.openDialog({kind:"edit", group, section:"actions"})));
        const checks = el("details", undefined, "advanced-options");
        checks.append(el("summary", t.groupCheckTitle));
        this.renderGroupChecks(checks, group);
        dialog.append(checks);
      }
      this.sourceList(dialog, this.data.sources.filter(s => group.members.includes(s.entity_id)));
      if (detail.kind === "group") {
        if (!group.members.length) dialog.append(el("p", t.emptyGroup));
        for (const member of group.unselected) dialog.append(el("p", `${member} · ${t.stale}`, "warning-text"));
        dialog.append(el("p", t.groupNote), button(t.copyGroup, ()=>this.openDialog({kind:"copy", id:group.id})), button(t.actionExample, () => this.openDialog({kind: "preview", id: group.id})), button(t.remove, () => this.openDialog({ kind: "delete", group }), "button destructive"));
      }
    } else if (detail.kind === "edit") this.groupForm(dialog, detail.group);
    else if (detail.kind === "settings") this.notificationForm(dialog);
    else if (detail.kind === "maintenance") this.maintenanceForm(dialog);
    else if(detail.kind==="drill") {
      dialog.append(el("h2",t.silentDrill),el("p",t.chooseDrillSource));
      if (!this.data.sources.length) dialog.append(el("p",t.noSources || t.NOT_CONFIGURED));
      const choices=el("div",undefined,"exercise-choices");
      for(const source of this.data.sources)choices.append(button(this.sourceName(source.entity_id),()=>this.openDialog({kind:"route",id:source.entity_id})));
      dialog.append(choices);
    }
    else if(detail.kind==="care"){const source=this.data.sources.find(s=>s.entity_id===detail.id);if(source)careView(this,dialog,source,true);}
    else if (detail.kind === "route") this.routeForm(dialog,detail);
    else if (detail.kind === "alarmsettings") this.alarmSettingsForm(dialog,detail);
    else if (detail.kind === "phoneObservation") this.phoneObservationForm(dialog,detail);
    else if (detail.kind === "recovery") this.recoveryForm(dialog,detail);
    else if (detail.kind === "preview") this.previewForm(dialog, detail);
    else if (detail.kind === "reminder") this.reminderForm(dialog, detail);
    else if (detail.kind === "copy") this.copyForm(dialog, detail);
    else if (detail.kind === "activity") this.activityDetail(dialog, detail.event);
    else if (detail.kind === "test") {
      dialog.append(el("h2", detail.actionKind === "selftest" ? t.startSelfTest : t.explicitTest));
      this.confirmRequest(dialog, detail);
      if(detail.actionKind==="selftest") dialog.append(button(t.refreshData,async()=>{const generation=this.generation;try{const fresh=await this._hass.callWS({type:"alarmmesh/current"});if(generation!==this.generation || this.detail!==detail)return;if(!fresh.available){this.closeDialog();return;}this.data=fresh;}catch{dialog.append(el("p",t.error));return;}const src=this.data?.sources.find(s=>s.entity_id===detail.target);if(!src?.selftest?.available){this.closeDialog();this.openDialog({kind:"source",id:detail.target});return;} this.openDialog({kind:"test",actionKind:"selftest",target:src.entity_id,name:src.name,identity:src.selftest.control.identity});}));
    }
    else if (detail.kind === "delete") {
      dialog.append(el("h2", t.confirmDelete), el("p", detail.group.name), el("p", t.deleteNote));
      detail.revision ??= this.data.revision;
      const error = el("p", "", "form-error"); error.setAttribute("role", "alert");
      dialog.append(error, button(t.cancel, () => this.closeDialog()), button(t.remove, async () => {
        await this.mutate({ operation: "delete", group_id: detail.group.id, revision: detail.revision }, error);
      }, "button destructive"));
    }
    this.updateRecoverySmoke();
    dialog.oncancel = () => this.closeDialog();
    if (first) { dialog.showModal(); close.focus(); }
    else if (focusIndex >= 0) ([...dialog.querySelectorAll("button,input")][focusIndex] || close).focus();
  }
  groupForm(dialog, group) {
    const original=group;group=this.detail.restoredDraft?.value || group;
    const t = this.t, revision = this.detail.restoredDraft?.revision ?? this.data.revision;
    dialog.append(el("h2", group ? t.edit : t.newGroup), el("p", t.simpleGroupNote));
    const form = el("form"); form.noValidate = true;
    const label = el("label", t.name); label.htmlFor = "group-name";
    const name = el("input"); name.id = "group-name"; name.name = "name"; name.value = group?.name || ""; name.maxLength = 64; name.required = true;
    const error = el("p", "", "form-error"); error.id = "group-error"; error.setAttribute("role", "alert"); name.setAttribute("aria-describedby", error.id);
    form.append(label, name, el("h3", t.members));
    const selected = new Set(group?.members || []);
    const choices = [...this.data.sources.map(s => ({ id: s.entity_id, name: s.name, note: s.area_name || t.noRoom })), ...(group?.unselected || []).map(id => ({ id, name: id, note: t.stale }))];
    const memberSearch = el("input"); memberSearch.type="search"; memberSearch.setAttribute("aria-label", t.searchMembers); memberSearch.placeholder=t.searchMembers;
    const memberCount = el("p", "", "member-count"); form.append(memberSearch, memberCount);
    for (const source of choices) {
      const row = el("label", undefined, "check");
      const check = el("input"); check.type = "checkbox"; check.name = "member"; check.value = source.id; check.checked = selected.has(source.id);
      const title = el("span"); title.append(el("strong", source.name), el("small", source.note)); row.append(check, title); form.append(row);
      row.dataset.memberSearch = `${source.name} ${source.note}`.toLocaleLowerCase();
    }
    if (group?.unselected.length) form.append(el("p", t.hiddenReferences, "muted"));
    const linkingSection = el("section", undefined, "linking-section");
    linkingSection.append(el("h3", t.linkTogether), el("p", t.linkIntro));
    const toggleLabel = el("label", undefined, "check");
    const toggle = el("input"); toggle.type = "checkbox"; toggle.name = "link-enabled"; toggle.checked = Boolean(group?.linking?.enabled);
    toggleLabel.append(toggle, el("span", t.enableLink)); linkingSection.append(toggleLabel);
    const bindings = [];
    const bindingSources = [...this.data.sources, ...(group?.linking?.bindings || []).filter(b => !this.data.sources.some(s => s.entity_id === b.source)).map(b => ({ entity_id: b.source, name: b.source }))];
    const availability = source => JSON.stringify([source.capability?.status, source.capability?.reason, source.capability?.controls]);
    for (const source of bindingSources) {
      const row = el("div", undefined, "binding-row");
      const oldBinding = group?.linking?.bindings.find(b => b.source === source.entity_id);
      const field = { source, row, availability: availability(source), readBinding: this.renderSounderChoice(row, source, oldBinding) };
      row.hidden = !selected.has(source.entity_id);
      for (const check of form.querySelectorAll('input[name="member"]')) if (check.value === source.entity_id) check.addEventListener("change", () => { row.hidden = !check.checked; });
      linkingSection.append(row); bindings.push(field);
    }
    this.detail.refreshSounders = () => {
      const confirmation = form.querySelector(".link-confirmation");
      for (const field of bindings) {
        const id = field.source.entity_id;
        const latest = this.data.sources.find(source => source.entity_id === id) || { entity_id: id };
        const signature = availability(latest);
        if (signature === field.availability) continue;
        const choice = field.readBinding();
        if (confirmation) {
          if (toggle.checked && choice && selectedMembers().includes(id)) {
            confirmation.dataset.stale = "true";
            confirmation.querySelector(".confirm-ack").checked = false;
            error.textContent = t.control_changed;
          }
          continue;
        }
        const fieldFocused = this.shadowRoot.activeElement === field.row.querySelector('[name="link-target"]');
        const detailsOpen = field.row.querySelector("details")?.open;
        field.row.replaceChildren();
        field.readBinding = this.renderSounderChoice(field.row, latest, choice);
        field.availability = signature;
        const details = field.row.querySelector("details");
        if (details && detailsOpen) details.open = true;
        if (fieldFocused) field.row.querySelector('[name="link-target"]')?.focus();
      }
    };
    const originSection = el("section", undefined, "linking-section");
    originSection.append(el("h3", t.incidentSources), el("p", t.incidentSourceNote));
    const originRows = [];
    for (const source of choices) {
      const row = el("label", undefined, "check");
      const check = el("input"); check.type = "checkbox"; check.name = "origin"; check.value = source.id; check.checked = !group?.origins || group.origins.includes(source.id);
      row.append(check, el("span", source.name)); row.hidden = !selected.has(source.id); originSection.append(row); originRows.push(check);
      for (const member of form.querySelectorAll('[name="member"]')) if (member.value === source.id) member.addEventListener("change", () => { row.hidden = !member.checked; });
    }
    const advanced = el("details", undefined, "advanced-options");
    advanced.open = Boolean(group?.linking?.enabled || group?.actions?.enabled || this.detail.section);
    const advancedSummary=el("summary",t.optionalActions);advanced.append(advancedSummary);
    const originsDetails=el('details',undefined,'group-option origins-option');originsDetails.append(el('summary',t.incidentSources),originSection);
    const linkingDetails=el('details',undefined,'group-option linking-option');linkingDetails.open=Boolean(group?.linking?.enabled);linkingDetails.append(el('summary',t.linkTogether),linkingSection);
    advanced.append(originsDetails,linkingDetails);
    form.append(advanced);
    const updateCounts = ()=> { memberCount.textContent=`${t.members}: ${[...form.querySelectorAll('[name="member"]')].filter(c=>c.checked).length}`; };
    form.addEventListener("change", updateCounts); updateCounts();
    memberSearch.addEventListener("input", ()=>{ for(const row of form.querySelectorAll('[data-member-search]')) row.hidden=!row.dataset.memberSearch.includes(memberSearch.value.toLocaleLowerCase()); });
    const scriptsDetails=el('details',undefined,'group-option scripts-option');scriptsDetails.open=Boolean(group?.actions?.enabled);scriptsDetails.append(el('summary',t.incidentActions));advanced.append(scriptsDetails);
    const actionFields = this.actionFields(scriptsDetails, group?.actions);
    const updateActionSummary=()=>{advancedSummary.textContent=`${t.optionalActions} · ${t.linkTogether}: ${t[toggle.checked?'enabled':'disabled']} · ${t.incidentActions}: ${t[actionFields().enabled?'enabled':'disabled']}`;};
    form.addEventListener('change',updateActionSummary);updateActionSummary();
    const selectedMembers = () => [...form.querySelectorAll('[name="member"]')].filter(c => c.checked).map(c => c.value);
    const selectedBindings = members => bindings.filter(b => members.includes(b.source.entity_id)).map(b => b.readBinding()).filter(Boolean);
    const readGroup = () => {
      const members = selectedMembers();
      return { name: name.value, members, origins: originRows.filter(c => c.checked && members.includes(c.value)).map(c => c.value),
        linking: { enabled: toggle.checked, bindings: selectedBindings(members) }, actions: actionFields(), unselected: group?.unselected || [] };
    };
    const changes=el("div");form.append(changes);const drawChanges=()=>{changes.replaceChildren();this.changeSummary(changes,"group",original || {},readGroup());};form.addEventListener("change",drawChanges);form.addEventListener("input",drawChanges);form.addEventListener("click",()=>queueMicrotask(drawChanges));drawChanges();
    const actions = el("div", undefined, "actions"); const save = el("button", t.save, "button primary"); save.type = "submit";
    actions.append(button(t.cancel, () => this.closeDialog()), save); form.append(error, actions);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (save.disabled) return;
      if (form.querySelector(".request-confirmation,.link-confirmation")) { error.textContent = t.finishConfirmation; return; }
      if (!name.value.trim() || name.value.trim().length > 64) { error.textContent = t.invalid_name; name.setAttribute("aria-invalid", "true"); name.focus(); return; }
      name.removeAttribute("aria-invalid");
      const members = selectedMembers();
      const mapped = selectedBindings(members);
      const payload = { operation: original ? "update" : "create", ...(original ? { group_id: original.id } : {}), revision, name: name.value.trim(), members };
      const origins = originRows.filter(c => c.checked && members.includes(c.value)).map(c => c.value);
      if (group?.origins || origins.length !== members.length) payload.origins = origins;
      const actionValue = actionFields();
      if (group?.actions || actionValue.enabled || actionValue.start.length || actionValue.recovery.length) payload.actions = actionValue;
      if (group?.linking || toggle.checked || mapped.length) payload.linking = { enabled: toggle.checked, bindings: mapped };
      if (!this.data) { error.textContent = t.offline; return; }
      if (toggle.checked || actionValue.enabled) {
        if (!origins.length) { error.textContent = t.invalid_origins; return; }
        if (actionValue.enabled && !actionValue.start.length && !actionValue.recovery.length) { error.textContent = t.invalid_actions; return; }
        if (toggle.checked && (members.length < 2 || !mapped.length || mapped.some(b => !b) || members.some(id => !this.data.sources.some(s => s.entity_id === id)))) { error.textContent = t.invalid_linking; return; }
        if (toggle.checked && mapped.some(binding => { const cap = this.data.sources.find(s => s.entity_id === binding.source)?.capability; return cap?.status !== "linkable" || !cap.controls.some(c => c.target === binding.target && c.identity === binding.identity); })) { error.textContent = t.control_changed; return; }
        const restore = this.lockControls(form);
        const confirmation = el("section", undefined, "link-confirmation");
        this.changeSummary(confirmation,"group",original || {},readGroup());
        confirmation.append(el("h3", toggle.checked ? t.confirmLink : t.confirmAutomation), el("p", t.commandNote));
        confirmation.append(el("p", `${t.incidentSources}: ${origins.map(id => { const s = this.data.sources.find(s => s.entity_id === id); return s ? `${s.name} (${s.area_name || t.noRoom})` : id; }).join(", ")}`));
        for (const destination of toggle.checked ? mapped : []) {
          const targetName = this.data.sources.find(s => s.entity_id === destination.source)?.name || destination.source;
          for (const source of this.data.sources.filter(s => origins.includes(s.entity_id) && s.entity_id !== destination.source)) confirmation.append(el("p", `${source.name} → ${targetName} (${destination.target})`));
          const control = this.data.sources.find(s => s.entity_id === destination.source)?.capability?.controls.find(c => c.target === destination.target && c.identity === destination.identity);
          confirmation.append(el("p", control?.safe_stop ? t.automation_stop_separate : t.no_safe_stop, "warning-text"));
        }
        if (actionValue.enabled) {
          confirmation.append(el("p", t.scriptConsequences));
          for (const phase of ["start", "recovery"]) for (const [index, action] of actionValue[phase].entries()) confirmation.append(el("p", `${t['phase_' + phase]} ${index + 1}: ${this.data.automation?.scripts.find(s => s.entity_id === action.entity_id)?.name || action.entity_id}`));
        }
        confirmation.append(el("p", t.physicalNotTested));
        const ackLabel = el("label", undefined, "check");
        const ack = el("input"); ack.type = "checkbox"; ack.className = "confirm-ack"; ackLabel.append(ack, el("span", t.acceptLink));
        const confirm = button(t.confirmEnable, async () => {
          if (confirmation.dataset.stale) { ack.checked = false; error.textContent = t.control_changed; return; }
          if(this.data?.revision!==revision){ack.checked=false;error.textContent=t.conflict;return;}
          if (!ack.checked) { error.textContent = t.linking_confirmation_required; ack.focus(); return; }
          if (!this.data) { error.textContent = t.offline; return; }
          confirm.disabled = true;
          await this.mutate({ ...payload, confirmed: true }, error);
          confirm.disabled = false;
        }, "button primary confirm-linking");
        confirmation.append(ackLabel, error, button(t.back, () => { confirmation.remove(); form.insertBefore(error, actions); error.textContent = ""; restore(); this.detail.refreshSounders(); }), confirm);
        form.append(confirmation); ack.focus(); return;
      }
      save.disabled = true;
      await this.mutate(payload, error);
      save.disabled = false;
    });
    this.trackDraft(form,revision,readGroup);
    dialog.append(form);
  }
  renderSounderChoice(row, source, oldBinding) {
    const t = this.t, cap = source.capability;
    const controls = cap?.controls || [];
    const currentBinding = controls.find(c => c.target === oldBinding?.target && c.identity === oldBinding?.identity && c.profile === oldBinding?.profile);
    const stale = oldBinding && !currentBinding;
    const canChoose = cap?.status === "linkable";
    const fieldId = `binding-${source.entity_id}`;
    const savedFields = c => ({ source: c.source, target: c.target, profile: c.profile, identity: c.identity });
    const name = this.sourceName(source.entity_id);
    let readBinding;
    if (controls.length <= 1) {
      const label = el("label", undefined, "check sound-choice");
      const check = el("input");
      check.type = "checkbox"; check.id = fieldId; check.name = "link-target";
      check.checked = Boolean(currentBinding);
      check.disabled = !controls.length || (!canChoose && !currentBinding);
      if (!canChoose && currentBinding) check.addEventListener("change", () => { check.disabled = !check.checked; });
      label.append(check, el("span", name));
      row.append(label);
      let kept = stale ? oldBinding : null;
      if (stale) {
        const warning = el("div", undefined, "stale-binding");
        const discard = () => { kept = null; warning.hidden = true; };
        warning.append(el("p", t.storedControlChanged), button(t.removeOldSounder, discard));
        row.append(warning);
        check.addEventListener("change", () => { if (check.checked) discard(); });
      }
      readBinding = () => check.checked && controls[0] ? savedFields(controls[0]) : kept;
    } else {
      // Replacing a stored identity (even at the same entity ID) requires
      // a distinct choice. Preserve the old binding until explicitly changed.
      const label = el("label", name);
      const select = el("select"); select.name = "link-target"; select.id = fieldId; label.htmlFor = fieldId;
      const empty = el("option", t.smokeOnlyRole); empty.value = ""; empty.selected = !oldBinding; select.append(empty);
      for (const control of controls) {
        const option = el("option", controls.length === 1 ? t.soundAlong : `${t.soundAlong} · ${control.target}`);
        option.value = control.target; option.disabled = !canChoose; option.selected = currentBinding === control; select.append(option);
      }
      if (stale) {
        const stored = el("option", t.storedControlChanged);
        stored.value = "stored"; stored.selected = true; select.append(stored);
      }
      row.append(label, select);
      readBinding = () => {
        if (select.value === "stored") return oldBinding;
        const choice = controls.find(c => c.target === select.value);
        return choice ? savedFields(choice) : null;
      };
    }
    const note = el("p", !canChoose ? (t[cap?.reason] || t.no_verified_profile)
      : controls.every(c => c.safe_stop) ? t.soundAutoStop : t.soundManualStop, "binding-help");
    note.id = `${fieldId}-help`;
    row.querySelector('[name="link-target"]').setAttribute("aria-describedby", note.id);
    row.append(note);
    if (cap) { const requirements = el("details"); requirements.append(el("summary", t.technicalDetails), el("p", t[cap.reason] || t.no_verified_profile), el("p", `${source.model || t.unknown} · ${source.entity_id}`)); for (const control of controls) requirements.append(el("p", control.target)); row.append(requirements); }
    else row.append(el("small", t.storedSourceMissing, "warning-text"));
    return readBinding;
  }
  detectorDetails(parent, source) {
    const t = this.t, details = source.capability.details || {};
    const table = el("dl", undefined, "diagnostics");
    const add = (label, value) => table.append(el("dt", label), el("dd", value));
    add(t.detectorType, t["kind_" + source.capability.kind] || t[source.capability.kind] || t.genericSmoke);
    add(t.sourceAvailability, source.ha_state === "on" || source.ha_state === "off" ? t.usableValue : t.unavailable);
    add(t.controlAvailability, source.capability.controls.length ? t.usableValue : t.unavailable);
    add(t.firmware, details.firmware || t.unavailable);
    if (!(details.values || []).length) add(t.additionalInfo, t.unavailable);
    for (const value of details.values || []) {
      const cell = el("dd", value.value === null ? t.unavailable : `${t[value.value] || value.value}${value.unit ? " " + value.unit : ""}`);
      if (value.changed_at) cell.append(el("small", `${t.valueChanged}: ${new Date(value.changed_at).toLocaleString(this._hass.language)}`));
      table.append(el("dt", (source.capability.origin === "matter" ? t["matter_function_" + value.key] : null) || t[value.key] || value.key), cell);
    }
    parent.append(table, el("small", t.contactUnknown, "muted"));
  }
  renderCatalog(parent) {
    const t = this.t;
    if (!this.catalog) { parent.append(el("p", this.catalogError ? t.error : t.loading, "notice")); return; }
    const catalog = this.catalog;
    parent.append(el("p", `${catalog.definitions} ${t.definitions} / ${catalog.website_rows} ${t.catalogModels} / ${catalog.checked}`, "muted"), el("p", t.catalogNote, "notice"));
    const filters = el("div", undefined, "catalog-filters");
    const search = el("input"); search.type = "search"; search.placeholder = t.searchCatalog; search.setAttribute("aria-label", t.searchCatalog); search.value = this.catalogSearch || "";
    const provider = el("select"); provider.setAttribute("aria-label", t.provider);
    for (const [value, label] of [["zigbee2mqtt", "Zigbee2MQTT"], ["zha", "ZHA"], ["matter", "Matter"], ["zwave_js", "Z-Wave JS"]]) { const option = el("option", label); option.value = value; provider.append(option); }
    [...provider.options].find(option => option.value === (this.catalogProvider || "zigbee2mqtt")).selected = true;
    const capability = el("select"); capability.setAttribute("aria-label", t.functions);
    for (const [value, label] of [["all", t.allModels], ["implemented", t.externalActivation], ["stop", t.automaticStop], ["detection", t.smokeSource], ["unconfirmed", t.not_confirmed]]) { const option = el("option", label); option.value = value; capability.append(option); }
    [...capability.options].find(option => option.value === (this.catalogCapability || "all")).selected = true;
    const results = el("div", undefined, "catalog-results");
    const count = el("p"); count.setAttribute("role", "status");
    const update = () => {
      this.catalogSearch = search.value; this.catalogProvider = provider.value; this.catalogCapability = capability.value;
      results.replaceChildren(); let shown = 0;
      search.disabled=capability.disabled=provider.value === "zwave_js";
      if(provider.value === "zwave_js") {
        count.textContent=t.zwaveGeneric;
        results.append(el("h3","Z-Wave JS"),el("p",t.zwaveSetup),el("p",t.zwave_observation_only,"notice"),el("p",t.physicalNotTested));
        return;
      }
      const entries = provider.value === "matter" ? (catalog.matter_entries || []) : catalog.entries;
      for (const entry of entries) {
        for (const variant of [{ vendor: entry.vendor, model: entry.model }, ...entry.aliases]) {
        const review = variant.providers?.[provider.value] || entry.providers[provider.value];
        const matches = capability.value === "all" || capability.value === "implemented" && review.activation === "implemented" || capability.value === "stop" && review.stop === "implemented" || capability.value === "detection" && review.detection !== "not_available" || capability.value === "unconfirmed" && [review.detection, review.activation].includes("unconfirmed");
        if (!matches) continue;
          if (!`${variant.vendor} ${variant.model} ${entry.model}`.toLocaleLowerCase().includes(search.value.toLocaleLowerCase().trim())) continue;
          shown++;
          const card = el("article", undefined, "card catalog-card");
          card.append(el("h3", `${variant.vendor} ${variant.model}`), el("p", `${t[provider.value]} / ${t["kind_" + entry.kind] || t[entry.kind] || entry.kind}`));
          if (variant.model !== entry.model) card.append(el("small", `${t.documentedVariant}: ${entry.vendor} ${entry.model}`, "muted"));
          const info = el("dl");
          for (const [label, value] of [[t.smokeSource, review.detection], [t.externalActivation, review.activation], [t.automaticStop, review.stop], [t.selfTestStatus, review.self_test]]) info.append(el("dt", label), el("dd", t[value] || value));
          const evidence = el("details"); evidence.append(el("summary", t.requirements), el("p", t.sourceReviewEnglish));
          for (const note of [...review.requirements, ...review.gaps]) evidence.append(el("p", note));
          evidence.append(el("p", `${t.additionalInfo}: ${review.information.join(", ") || t.unavailable}`));
          for (const url of review.sources) { const link = el("a", url.includes("zigbee2mqtt.io") ? "Zigbee2MQTT" : url.split("/").slice(-1)[0]); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; evidence.append(link); }
          card.append(info, evidence); results.append(card);
        }
      }
      count.textContent = `${shown} / ${provider.value === "matter" ? (catalog.matter_entries || []).length : catalog.website_rows} ${t.catalogModels}`;
    };
    search.addEventListener("input", update); provider.addEventListener("change", update); capability.addEventListener("change", update);
    filters.append(search, provider, capability); parent.append(filters, count, results); update();
  }
  offlineDraft() {
    if(this.detail?.kind==="route"){this.detail.suspend?.();this.shadowRoot.querySelector(".route-sections")?.replaceChildren();return;}
    if (this.detail?.pendingRecovery) this.detail.pendingRecovery.interrupted = true;
    if (!["edit", "settings", "maintenance", "reminder", "copy", "recovery", "phoneObservation","care"].includes(this.detail?.kind)) { this.closeDialog(); return; }
    const dialog = this.shadowRoot.querySelector("dialog");
    if (!dialog) return;
    if (!dialog.querySelector(".offline-draft")) dialog.prepend(el("p", this.t.offlineDraft, "notice offline-draft"));
    for (const b of dialog.querySelectorAll('button[type="submit"],.confirm-execute,.confirm-linking')) b.disabled = true;
  }
  renderSettings(parent) {
    const t=this.t,a=this.data.automation,d=this.data;
    if(!a){this.renderSetupGuide(parent);return;}
    parent.append(el('p',t.settingsIntro,'section-note'));
    parent.append(button(t.myAlarmSettings,()=>this.openDialog({kind:'alarmsettings'})));
    const grid=el('div',undefined,'settings-grid');
    const card=(key,title,summary,label,action,primary=false)=>{
      const box=el('section',undefined,'notice settings-task');box.dataset.setting=key;
      box.append(el('h2',title),el('p',summary,'setting-value'),button(label,action,primary?'button primary':'button'));grid.append(box);return box;
    };
    card('detectors',t.settingsDetectors,`${this.detectorCount(d.sources.length)} · ${t[d.result.availability]}`,t.choose,()=>this.choose(),!d.sources.length);
    const linked=d.groups.filter(g=>g.linking?.enabled).length;
    const groupCard=card('groups',t.settingsGroups,`${d.groups.length} ${t.groups.toLowerCase()} · ${linked} ${t.groupsSoundOn}`,t.manageGroups,()=>this.go('groups'));
    groupCard.append(el('p',t.groupSetupNote));
    const selected=a.settings.recipients.filter(r=>r.enabled).length;
    const phones=card('phones',t.settingsPhones,`${selected} ${t.phonesChosen} · ${t[a.settings.enabled?'automaticOn':'automaticOff']}`,t.configureNotifications,()=>this.openDialog({kind:'settings'}),Boolean(d.sources.length));
    if(a.settings.recipients.length){
      const details=el('details',undefined,'phone-settings-summary');details.append(el('summary',t.savedPhones));
      for(const r of a.settings.recipients){const name=a.recipients.find(p=>p.service===r.service)?.name || r.service.replace(/^mobile_app_/,'');
        details.append(el('h3',name),el('p',`${t[r.enabled?'recipientSelected':'recipientNotSelected']} · ${this.phoneSummary(r.profile)}`));
        const error=a.phone_plans?.[r.service]?.error || (a.missing_recipients.includes(r.service)?'recipient_unavailable':null);
        if(error)details.append(el('p',t[error] || t.invalid_phone_profile,'warning-text'));
      }
      details.append(el('p',t.phoneUnchecked));phones.append(details);
    }
    for(const row of (a.manual_results || []).filter(r=>r.kind==='notification').slice(0,3)){
      const last=el('details',undefined,'phone-latest');last.append(el('summary',`${t.lastPhoneTest}: ${row.target.replace(/^mobile_app_/,'')}`));this.notificationReceipt(last,row);phones.append(last);
    }
    this.phoneEvidenceList(phones);
    if(a.error)phones.append(el('p',t[a.error] || t.error,'warning-text'));
    const actions=d.groups.filter(g=>g.actions?.enabled).length;
    groupCard.append(el('p',`${actions} ${t.groupsActionsOn}`));
    const maintenance=card('maintenance',t.settingsMaintenance,t.maintenanceSetupShort,t.maintenance,()=>this.go('maintenance'));
    if(d.maintenance)maintenance.append(el('p',`${t.maintenanceNotifications}: ${t[d.maintenance.settings.enabled?'enabled':'disabled']}`));
    parent.append(grid);
    const help=el('details',undefined,'advanced-options settings-help');help.append(el('summary',t.installationAndHelp));this.renderSetupGuide(help);
    help.append(button(t.matterHelp,()=>this.go('matterHelp')),button(t.catalog,()=>this.go('catalog')),button(t.diagnostics,()=>this.go('diagnostics')));parent.append(help);
  }
  notificationForm(dialog) {
    const t = this.t, a = this.data.automation;
    if (!a) return;
    const cfg = this.detail.restoredDraft?.value || a.settings, revision = this.detail.restoredDraft?.revision ?? a.settings.revision, form = el("form");
    dialog.append(el("h2", a.profile_support ? t.phoneWizard : t.notifications), el("p", a.profile_support ? t.phoneWizardIntro : t.notificationNote));
    if(a.profile_support){const steps=el('ol',undefined,'phone-steps');for(const text of [t.phoneStepChoose,t.phoneStepSound,t.phoneStepSave])steps.append(el('li',text));dialog.append(steps);}
    const toggle = this.checkField(form, t.enableNotifications, cfg.enabled, "notifications-enabled");
    const recovery = this.checkField(form, t.recoveryNotification, cfg.recovery, "notifications-recovery");
    const stored = new Map(cfg.recipients.map(r => [r.service, r]));
    const choices = [...a.recipients, ...cfg.recipients.filter(r => !a.recipients.some(n => n.service === r.service)).map(r => ({ ...r, name: r.service, missing: true }))];
    const recipients = [], removed = new Set(), profiles = new Map();
    if (!choices.length) form.append(el("p", t.noRecipients, "notice"), el("p", t.phoneSetupHelp));
    for (const recipient of choices) {
      const row = el("section", undefined, "recipient-row");
      const input = this.checkField(row, `${recipient.name}${recipient.missing ? ' · ' + t.recipient_unavailable : ''}`, stored.get(recipient.service)?.enabled || false, "recipient");
      input.value = recipient.service; recipients.push(input);
      row.append(el("small", t[recipient.missing ? "phoneMissingHelp" : "phoneAvailable"]));
      const last=(a.manual_results || []).find(r=>r.kind==='notification' && r.target===recipient.service);
      if(last)row.append(el('p',`${t.lastPhoneTest}: ${this.formatTime(last.started)} · ${t['delivery_'+last.status] || t.guide_unknown}`));
      if (a.profile_support) {
        profiles.set(recipient.service,this.phoneFields(row,recipient,stored.get(recipient.service)?.profile,input));
        const problem=a.phone_plans?.[recipient.service]?.error;
        if(problem) row.append(el("p",t[problem] || t.invalid_phone_profile,"warning-text"));
      }
      const testHelp=el("p","","phone-test-help");testHelp.setAttribute("role","status");
      if (!recipient.missing) row.append(button(t.testNotification, () => {
        const saved=this.data?.automation?.settings.recipients.find(r=>r.service===recipient.service)?.profile;
        if(a.profile_support && JSON.stringify(profiles.get(recipient.service)?.())!==JSON.stringify(saved)) {testHelp.textContent=t.saveBeforeTest;return;}
        this.confirmRequest(form, { actionKind: "notification", target: recipient.service, name: recipient.name });
      }, "button"),testHelp);
      if (stored.has(recipient.service)) {const more=el('details',undefined,'phone-more');more.append(el('summary',t.morePhoneOptions),button(t.forgetRecipient, () => { removed.add(recipient.service); row.remove(); }, "button destructive"));row.append(more);}
      form.append(row);
    }
    if(a.profile_support)form.append(toggle.parentElement,recovery.parentElement);
    const preview = el("details"); preview.open = !a.profile_support; preview.append(el("summary", t.messagePreview), el("strong", a.preview.title), el("p", a.preview.message, "message-preview")); form.append(el("p", t.notificationTiming, "section-note"), preview);
    const error = el("p", "", "form-error"); error.setAttribute("role", "alert");
    const save = el("button", t.saveSettings, "button primary"); save.type = "submit";
    const read = () => ({enabled:toggle.checked,recovery:recovery.checked,recipients:recipients.filter(r=>!removed.has(r.value) && (r.checked || stored.has(r.value))).map(r=>{const profile=profiles.get(r.value)?.();return {service:r.value,enabled:r.checked,...(profile ? {profile}: {})};})});
    const changes=el("div");form.append(changes);const drawChanges=()=>{changes.replaceChildren();this.changeSummary(changes,"phones",a.settings,read());};form.addEventListener("change",drawChanges);form.addEventListener("input",drawChanges);form.addEventListener("click",()=>queueMicrotask(drawChanges));drawChanges();
    const detail = this.detail;
    let refreshSerial = 0;
    form.append(button(t.refreshRecipients, async () => {
      const serial = ++refreshSerial, generation = this.generation;
      const current = () => form.isConnected && this.detail === detail && generation === this.generation && serial === refreshSerial && !form.querySelector(".request-confirmation");
      try {
        const data=await this._hass.callWS({type:"alarmmesh/current"});
        if (!data.available || !current()) return;
        // Read at completion: edits made while the request was pending are newer.
        this.data=data; detail.restoredDraft={value:read(),revision}; this.renderDialog();
      } catch { if (current()) error.textContent=t.offline; }
    }), el("small",t.refreshRecipientsNote));
    form.append(error, save, button(t.cancel, () => this.closeDialog()));
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (form.querySelector(".request-confirmation")) { error.textContent = t.finishConfirmation; return; }
      if (!this.data) { error.textContent = t.offline; return; }
      const value = read();
      if (value.enabled && !value.recipients.some(r => r.enabled)) { error.textContent = t.invalid_notifications; return; }
      const send = async confirmed => {
        save.disabled = true;
        try { await this._hass.callWS({ type: "alarmmesh/settings", revision, notifications: value, confirmed }); this.clearDraft(); this.closeDialog(); }
        catch (e) {
          error.textContent = t[e.code] || t.saveResultUnknown; save.disabled = Boolean(save.dataset.confirmLocked);
          const pendingStatus=form.querySelector('.request-confirmation .request-status');if(pendingStatus)pendingStatus.textContent=t.saveResultUnknown;
          if(a.profile_support && !t[e.code]) {
            form.querySelector('.save-reconcile')?.remove();
            const status=el('section',undefined,'notice save-reconcile'),message=el('p',t.saveResultUnknown);
            const check=button(t.checkSavedPhones,async()=>{
              check.disabled=true;
              try {
                const current=await this._hass.callWS({type:'alarmmesh/current'});
                if(!status.isConnected)return;
                const saved=current.automation.settings;
                const canonical=v=>Array.isArray(v)?v.map(canonical):v && typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
                const same=JSON.stringify(canonical({enabled:saved.enabled,recovery:saved.recovery,recipients:saved.recipients}))===JSON.stringify(canonical(read()));
                message.textContent=t[same?'phonesSavedVerified':'phonesSavedDifferent'];
                const pendingStatus=form.querySelector('.request-confirmation .request-status');if(pendingStatus)pendingStatus.textContent='';
                error.textContent='';save.disabled=true;save.dataset.reopenRequired='true';
              } catch {message.textContent=t.saveResultUnknown;}
              finally {check.disabled=false;}
            });check.dataset.checkSavedPhones='';status.append(message,check);form.append(status);
            const edited=()=>{if(status.isConnected)message.textContent=t.phonesSaveEdited;};
            form.addEventListener('input',edited);form.addEventListener('change',edited);
          }
        }
      };
      if (!value.enabled && !value.recipients.some(r=>r.profile?.critical)) { await send(false); return; }
      this.confirmRequest(form, { changes:{kind:"phones",before:a.settings,after:value}, name: a.profile_support ? t.reviewPhones : t.confirmAutomation, confirmationOnly: true, note: `${a.profile_support ? t.saveIsQuiet : t.notificationNote}\n${value.recipients.filter(r => r.enabled).map(r => `${r.service.replace(/^mobile_app_/,"")}: ${this.phoneSummary(r.profile)}`).join('\n')}`, execute: () => send(true) });
    });
    this.trackDraft(form,revision,read);
    dialog.append(form);
  }
  phoneSummary(profile) {
    const t=this.t;if(!profile)return t.phoneOrdinary;
    const sound=t[this.data?.automation?.ios_sounds?.[profile.sound]] || profile.sound || t.sound_default;
    return `${t['phone_'+profile.platform] || t.guide_unknown} · ${t[profile.critical ? 'phoneCritical':'phoneOrdinary']}${profile.platform==='ios' ? ` · ${sound}${profile.critical ? ` · ${Number((profile.volume*100).toPrecision(12))}%` : ''}`:''}`;
  }
  changeRows(kind, before, after) {
    if(!this.data)return [];
    const t=this.t, rows=[],same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
    const add=(label,a,b)=>{if(!same(a,b))rows.push(`${t[b===false || b===null || (Array.isArray(b)&&!b.length)?'changeRemoved':a===null?'changeAdded':'changeChanged']}: ${label}`);};
    if(kind==='phones'){
      add(t.enableNotifications,Boolean(before.enabled),Boolean(after.enabled));add(t.recoveryNotification,Boolean(before.recovery),Boolean(after.recovery));
      const a=new Map((before.recipients||[]).map(r=>[r.service,r])),b=new Map((after.recipients||[]).map(r=>[r.service,r]));
      for(const key of new Set([...a.keys(),...b.keys()])){const old=a.get(key),next=b.get(key),name=this.data.automation?.recipients.find(r=>r.service===key)?.name || key.replace(/^mobile_app_/,'');if(!same(old,next))rows.push(`${t[!next || !next.enabled?'changeRemoved':!old?'changeAdded':'changeChanged']}: ${name}${next?' · '+this.phoneSummary(next.profile):''}`);}
    }else{
      add(t.name,before.name??null,after.name);for(const [key,label] of [['members',t.members],['origins',t.incidentSources]]){const a=before[key] || (key==='origins'?before.members:[]) || [],b=after[key] || (key==='origins'?after.members:[]) || [];for(const id of new Set([...a,...b]))if(a.includes(id)!==b.includes(id))rows.push(`${t[b.includes(id)?'changeAdded':'changeRemoved']}: ${label} · ${this.sourceName(id)}`);}
      add(t.linkTogether,Boolean(before.linking?.enabled),Boolean(after.linking?.enabled));
      const a=new Map((before.linking?.bindings||[]).map(r=>[r.target,r])),b=new Map((after.linking?.bindings||[]).map(r=>[r.target,r]));for(const key of new Set([...a.keys(),...b.keys()])){const old=a.get(key),next=b.get(key);if(!same(old,next))rows.push(`${t[!next?'changeRemoved':!old?'changeAdded':'changeChanged']}: ${this.sourceName((next||old).source)}`);}
      add(t.incidentActions,Boolean(before.actions?.enabled),Boolean(after.actions?.enabled));for(const phase of ['start','recovery'])if(!same(before.actions?.[phase]||[],after.actions?.[phase]||[]))rows.push(`${t.changeChanged}: ${t.incidentActions} · ${t['phase_'+phase]} · ${(after.actions?.[phase]||[]).map((r,i)=>`${i+1}. ${this.data.automation?.scripts.find(s=>s.entity_id===r.entity_id)?.name || r.entity_id}`).join(', ') || t.disabled}`);
    }return rows;
  }
  changeSummary(parent, kind, before, after) {
    const box=el('section',undefined,'change-summary');box.append(el('h3',this.t.changeSummary));const rows=this.changeRows(kind,before,after);if(!rows.length)box.append(el('p',this.t.nothingToSave));else{const list=el('ul');for(const row of rows)list.append(el('li',row));box.append(list);}parent.append(box);return box;
  }
  phoneEvidenceList(parent, target=null) {
    const t=this.t,evidence=this.data.phone_evidence;if(!evidence)return;
    const box=el('details',undefined,'phone-user-evidence');box.append(el('summary',t.phoneUserTests),el('p',t.phoneObservationLimit));
    if(evidence.error)box.append(el('p',t[evidence.error] || t.error));
    const rows=evidence.requests.filter(r=>!target || r.target===target);
    if(!rows.length)box.append(el('p',t.noUserTest));
    for(const row of rows){const item=el('section');item.append(el('h4',this.data.automation?.recipients.find(r=>r.service===row.target)?.name || row.target.replace(/^mobile_app_/,'')),el('p',`${this.formatTime(row.started)} · ${this.phoneSummary(row.profile)}`),el('p',t['delivery_'+row.status] || t.guide_unknown));
      if(!row.current)item.append(el('p',`${t.pastProfile}: ${t[row.reason] || t.guide_unknown}`));
      for(const observation of row.observations){item.append(el('p',`${t[observation.simulation?'simulationObservation':'userObservation']}: ${this.formatTime(observation.at)}`),el('p',`${t.testReceived}: ${t[observation.received===null?'notChecked':observation.received?'answerYes':'answerNo']} · ${t.testHeard}: ${t[observation.heard===null?'notChecked':observation.heard?'answerYes':'answerNo']}`));}
      if(row.attempted && row.status!=='sending' && !evidence.error)item.append(button(t.recordObservation,()=>this.openDialog({kind:'phoneObservation',id:row.request_id})));
      box.append(item);
    }parent.append(box);
  }
  phoneObservationForm(parent, detail) {
    const t=this.t,evidence=this.data.phone_evidence,row=evidence?.requests.find(r=>r.request_id===detail.id);
    parent.append(el('h2',t.recordObservation));if(!row){parent.append(el('p',t.phone_request_missing));return;}
    parent.append(el('p',`${this.data.automation?.recipients.find(r=>r.service===row.target)?.name || row.target.replace(/^mobile_app_/,'')} · ${this.formatTime(row.started)}`),el('p',this.phoneSummary(row.profile)),el('p',t.phoneObservationLimit));
    if(!row.current)parent.append(el('p',t.pastProfile));
    const form=el('form'),fields={};const last=row.observations.at(-1);
    for(const [key,label] of [['received',t.testReceived],['heard',t.testHeard]]){const wrapper=el('label',label),select=el('select');select.name=key;for(const [value,text] of [['unknown',t.notChecked],['yes',t.answerYes],['no',t.answerNo]]){const o=el('option',text);o.value=value;o.selected=value===(last?.[key]===true?'yes':last?.[key]===false?'no':'unknown');select.append(o);}wrapper.append(select);form.append(wrapper);fields[key]=select;}
    const simulation=this.checkField(form,t.simulationObservation,last?.simulation || false,'simulation-observation');
    const read=()=>({received:fields.received.value==='unknown'?null:fields.received.value==='yes',heard:fields.heard.value==='unknown'?null:fields.heard.value==='yes',simulation:simulation.checked});
    const status=el('p','', 'observation-status');status.setAttribute('role','status');const save=el('button',t.saveObservation,'button primary');save.type='submit';let busy=false;
    const check=button(t.checkSavedPhones,async()=>{check.disabled=true;try{const fresh=await this._hass.callWS({type:'alarmmesh/current'});if(!form.isConnected)return;const current=fresh.phone_evidence.requests.find(r=>r.request_id===row.request_id)?.observations.at(-1);const same=current && Object.entries(read()).every(([k,v])=>current[k]===v);status.textContent=t[same?'observationSaved':'observationDifferent'];save.disabled=true;save.dataset.reopenRequired='true';}catch{status.textContent=t.saveResultUnknown;}finally{check.disabled=false;}});
    form.addEventListener('change',()=>{status.textContent=t.phonesSaveEdited;});
    form.addEventListener('submit',async event=>{event.preventDefault();if(busy || save.dataset.reopenRequired)return;if(!this.data){status.textContent=t.offline;return;}busy=true;save.disabled=true;const value=read();try{await this._hass.callWS({type:'alarmmesh/phone_observation',request_id:row.request_id,revision:evidence.revision,...value});if(!form.isConnected)return;status.textContent=t[Object.entries(read()).every(([k,v])=>value[k]===v)?'observationSaved':'observationDifferent'];save.dataset.reopenRequired='true';}catch(e){status.textContent=t[e.code] || t.saveResultUnknown;save.dataset.reopenRequired='true';}finally{busy=false;}});
    form.append(status,save,button(t.cancel,()=>this.closeDialog()),check);parent.append(form);
  }
  phoneFields(parent,recipient,saved,chosen) {
    const t=this.t,meta=this.data.automation.phone_metadata?.[recipient.service];
    let changed=false,identity=saved?.identity || meta?.identity || '',origin=saved?.origin || meta?.origin || 'user';
    const box=el("details",undefined,"phone-profile");box.open=chosen.checked;
    const summary=el("summary",t.phoneOptions);box.append(summary);
    const field=(label,name,choices,value)=>{const l=el("label",label),s=el("select");s.name=name;
      for(const [id,text] of choices){const o=el("option",text);o.value=id;o.selected=id===value;s.append(o);}l.append(s);box.append(l);return s;};
    const platform=field(t.phonePlatform,"phone-platform",[["unknown",t.phone_unknown],["ios",t.phone_ios],["android",t.phone_android]],saved?.platform || meta?.platform || "unknown");
    box.append(el('small',t[origin==='metadata' ? 'platformFromHA':'platformFromUser']));
    const critical=this.checkField(box,t.phoneCritical,"critical" in (saved || {}) ? saved.critical : false,"phone-critical");
    const ios=el("section",undefined,"phone-ios"),help=el("details",undefined,"phone-help");
    const soundLabel=el("label",t.phoneSound),sound=el("select");sound.name="phone-sound";
    for(const [id,key] of Object.entries(this.data.automation.ios_sounds || {default:'sound_default'})){const o=el("option",t[key] || id);o.value=id;o.selected=saved?.sound_source!=='imported' && id===(saved?.sound || 'default');sound.append(o);}
    const custom=el("option",t.sound_imported);custom.value="imported";custom.selected=saved?.sound_source==='imported';sound.append(custom);soundLabel.append(sound);
    const nameLabel=el("label",t.importedFilename),name=el("input");name.name="phone-sound-file";name.maxLength=100;name.value=saved?.sound_source==='imported' ? saved.sound : '';nameLabel.append(name);
    const volumeLabel=el("label",t.phoneVolume),volume=el("input");volume.type="number";volume.name="phone-volume";volume.min="0";volume.max="100";volume.step="any";volume.value=String(Number(((saved?.volume ?? 1)*100).toPrecision(12)));volumeLabel.append(volume);
    ios.append(soundLabel,nameLabel,volumeLabel,el("small",t.soundAvailability));box.append(ios,help,el("p",t.phoneUnchecked,"phone-evidence"));
    const read=()=>{if(!changed && !saved)return undefined;const p={version:1,platform:platform.value,origin,identity,critical:critical.checked};if(p.platform==='ios')Object.assign(p,{sound:sound.value==='imported' ? name.value : sound.value,sound_source:sound.value==='imported' ? 'imported':'bundled',volume:Number.parseFloat(volume.value)/100});return p;};
    const draw=()=>{ios.hidden=platform.value!=='ios';nameLabel.hidden=sound.value!=='imported';volumeLabel.hidden=!critical.checked;critical.disabled=platform.value==='unknown';
      help.replaceChildren(el("summary",t.whyNoSound),el("p",t['phoneHelp_'+platform.value]));
      if(meta?.identity_scope==='session')help.append(el("p",t.phoneSessionIdentity));
      if(sound.value==='imported' && platform.value==='ios')help.append(el("p",t.importSoundHelp));
      help.append(el("p",t.phoneNoProof));summary.textContent=this.phoneSummary(read() || {platform:platform.value,critical:false});};
    box.addEventListener('input',()=>{changed=true;draw();});box.addEventListener('change',()=>{changed=true;draw();});
    platform.addEventListener('change',()=>{changed=true;origin='user';identity=meta?.identity || identity;critical.checked=false;draw();});
    chosen.addEventListener('change',()=>{box.open=chosen.checked;});
    if(saved && meta && saved.identity!==meta.identity)box.append(button(t.reviewPhoneIdentity,()=>{changed=true;identity=meta.identity;origin='user';critical.checked=false;draw();}));
    draw();parent.append(box);return read;
  }
  maintenanceForm(dialog) {
    const t = this.t, m = this.data.maintenance, a = this.data.automation;
    if (!m || !a) return;
    const cfg = this.detail.restoredDraft?.value || m.settings, revision = this.detail.restoredDraft?.revision ?? m.settings.revision, form = el("form");
    dialog.append(el("h2", t.maintenanceNotifications), el("p", t.maintenanceDeliveryNote));
    const enabled = this.checkField(form, t.enableMaintenance, cfg.enabled, "maintenance-enabled"), fields = {};
    for (const kind of ["battery", "fault", "unavailable", "recovery"]) fields[kind] = this.checkField(form, t['maintenance_' + kind], cfg[kind], 'maintenance-' + kind);
    const label = el("label", t.maintenanceDelay); label.htmlFor = "maintenance-delay";
    const delay = el("select"); delay.id = "maintenance-delay"; delay.name = "maintenance-delay";
    for (const minutes of [5,15,30,60]) { const option = el("option", `${minutes} ${t.minutes}`); option.value = String(minutes); option.selected = cfg.delay === minutes; delay.append(option); }
    form.append(label, delay, el("p", t.maintenanceDelayNote), el("h3", t.maintenanceRecipients));
    const stored = new Map(cfg.recipients.map(r => [r.service, r])), removed = new Set(), inputs = [];
    const choices = [...a.recipients, ...cfg.recipients.filter(r => !a.recipients.some(n => n.service === r.service)).map(r => ({...r, name:r.service, missing:true}))];
    if (!choices.length) form.append(el("p", t.noRecipients));
    for (const recipient of choices) {
      const row = el("div", undefined, "recipient-row");
      const input = this.checkField(row, `${recipient.name}${recipient.missing ? ' · ' + t.recipient_unavailable : ''}`, stored.get(recipient.service)?.enabled, "maintenance-recipient");
      input.value = recipient.service; inputs.push(input);
      if (stored.has(recipient.service)) {const more=el('details',undefined,'phone-more');more.append(el('summary',t.morePhoneOptions),button(t.forgetRecipient, () => { removed.add(recipient.service); row.remove(); }, "button destructive"));row.append(more);}
      form.append(row);
    }
    const error = el("p", "", "form-error"); error.setAttribute("role", "alert");
    const save = el("button", t.saveSettings, "button primary"); save.type = "submit";
    form.append(error, save, button(t.cancel, () => this.closeDialog()));
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (form.querySelector(".request-confirmation")) { error.textContent = t.finishConfirmation; return; }
      if (!this.data) { error.textContent = t.offline; return; }
      const settings = {enabled:enabled.checked, delay:Number(delay.value), recipients:inputs.filter(r => !removed.has(r.value) && (r.checked || stored.has(r.value))).map(r=>({service:r.value,enabled:r.checked})), ...Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.checked]))};
      if (settings.enabled && (!settings.recipients.some(r=>r.enabled) || !["battery","fault","unavailable"].some(k=>settings[k]))) { error.textContent = t.invalid_maintenance; return; }
      const send = async confirmed => {
        save.disabled = true;
        try { await this._hass.callWS({type:"alarmmesh/maintenance_settings",revision,settings,confirmed}); this.clearDraft(); this.closeDialog(); }
        catch (e) { error.textContent = t[e.code] || t.error; save.disabled = Boolean(save.dataset.confirmLocked); }
      };
      if (!settings.enabled) { await send(false); return; }
      this.confirmRequest(form, {name:t.maintenanceNotifications, confirmationOnly:true, note:`${t.maintenanceDeliveryNote}\n${["battery","fault","unavailable"].filter(k=>settings[k]).map(k=>t['maintenance_'+k]).join(', ')}\n${settings.delay} ${t.minutes}\n${t.maintenance_recovery}: ${t[settings.recovery ? 'enabled' : 'disabled']}\n${settings.recipients.filter(r=>r.enabled).map(r=>r.service).join(', ')}`, execute:()=>send(true)});
    });
    this.trackDraft(form,revision,()=>({enabled:enabled.checked,delay:Number(delay.value),recipients:inputs.filter(r=>!removed.has(r.value) && (r.checked || stored.has(r.value))).map(r=>({service:r.value,enabled:r.checked})),...Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.checked]))}));
    dialog.append(form);
  }
  previewForm(dialog, detail) {
    const t = this.t, group = this.data.groups.find(g=>g.id===detail.id);
    if (!group) { dialog.append(el("p", t.not_found)); return; }
    dialog.append(el("h2", t.actionExample), el("p", t.exampleNoOutput, "notice"), el("p", t.previewNote));
    if (!group.members.length) { dialog.append(el("p", t.emptyGroup)); return; }
    const label = el("label", t.previewSource); label.htmlFor = "preview-source";
    const select = el("select"); select.id = "preview-source";
    for (const id of group.members) { const option=el("option",this.data.sources.find(s=>s.entity_id===id)?.name || id); option.value=id; option.selected=id===(detail.source || group.members[0]); select.append(option); }
    const output=el("div",undefined,"preview-output"); output.setAttribute("role","status");
    const load = async () => {
      const source=select.value; detail.source=source; output.replaceChildren(el("p",t.loading));
      try {
        const result=await this._hass.callWS({type:"alarmmesh/preview",group_id:group.id,source});
        if (!output.isConnected || this.detail!==detail || detail.source!==source || !this.data) return;
        if (result.revision !== this.data.revision || result.readonly !== true) { output.replaceChildren(el("p",t.previewStale)); return; }
        output.replaceChildren(el("h3", t.groups));
        if (result.paused) output.append(el("p",t.execution_paused,"notice"));
        for (const row of result.groups) output.append(el("p",`${this.data.groups.find(g=>g.id===row.id)?.name || t.groups}: ${t[row.can_start ? 'preview_can_start' : 'preview_origin_blocked']}`));
        output.append(el("h3", t.linkTogether), el("p",t[result.linking_enabled ? 'enabled':'disabled']));
        if (!result.targets.length) output.append(el("p",t.checkNoTargets));
        for (const row of result.targets) output.append(el("p",`${this.data.sources.find(s=>s.entity_id===row.source)?.name || row.source}: ${t[row.reason] || t.guide_unknown}`),el("small",t[row.eligible !== true ? 'preview_stop_unassessed' : row.safe_stop ? 'automation_stop_separate' : 'no_safe_stop']));
        output.append(el("h3",t.notifications),el("p",t[result.notifications_enabled ? 'enabled':'disabled']));
        for (const row of result.phones) output.append(el("p",`${row.target.replace(/^mobile_app_/, '')}: ${t[row.reason] || t.guide_unknown}`));
        output.append(el("h3",t.incidentActions),el("p",t[result.actions_enabled ? 'enabled':'disabled']));
        for (const row of result.scripts) output.append(el("p",`${t['phase_'+row.phase]} ${row.order} · ${row.name}: ${t[row.reason] || t.guide_unknown}`));
        output.append(el("h3",t.maintenanceRecovery),el("p",t.previewRecovery),el("p",result.recovery_sources.map(id=>this.data.sources.find(s=>s.entity_id===id)?.name || id).join(', ')),el("p",`${t.recoveryNotification}: ${t[result.notification_recovery ? 'enabled':'disabled']}`),el("p",t.physicalNotTested));
      } catch(e) { if(output.isConnected) output.replaceChildren(el("p",t[e.code] || t.error)); }
    };
    select.addEventListener("change",load); dialog.append(label,select,button(t.alarmRoute,()=>this.openDialog({kind:"route",id:select.value})),output); load();
  }

  phoneRouteCards(parent, phones) {
    const t=this.t;
    parent.append(el("p",t.globalPhones,"muted"));
    const active=el("div",undefined,"phone-route-active");
    const others=el("details",undefined,"phone-route-others");
    const unused=phones.filter(p=>!p.selected);
    others.append(el("summary",`${t.otherPhones} (${unused.length})`));
    for(const phone of phones) {
      const card=el("section",undefined,"phone-route-card");
      const raw=this.data.automation?.recipients.find(r=>r.service===phone.target)?.name || phone.target.replace(/^mobile_app_/,"");
      const title=el("div",undefined,"phone-route-title");title.append(icon("cellphone"),el("h4",raw.replaceAll('_',' ')));
      const state=!phone.selected ? 'phoneNotChosenShort' : !phone.available ? 'phoneUnavailableShort' : !phone.enabled ? 'phoneAutoOffShort' : phone.eligible ? 'phoneReadyShort' : 'phoneBlockedShort';
      title.append(el("span",t[state],`phone-route-status ${phone.selected && !phone.eligible ? 'warning-text' : ''}`));card.append(title);
      if(phone.selected) {
        if(phone.profile)card.append(el("p",this.phoneSummary(phone.profile),"phone-route-profile"));
        if(!phone.eligible)card.append(el("p",t[phone.reason] || t.guide_unknown));
        card.append(el("small",t.phoneDeliveryUnconfirmed));
      }
      const details=el("details",undefined,"phone-route-details");details.append(el("summary",t.technicalDetails),el("small",phone.target),el("p",`${t[phone.available?'phoneServiceFound':'phoneUnavailableShort']} · ${t[phone.enabled?'automaticOn':'automaticOff']}`));card.append(details);
      (phone.selected ? active : others).append(card);
    }
    if(!phones.some(p=>p.selected))active.append(el("p",t.noPhonesChosen));
    parent.append(active);
    if(unused.length)parent.append(others);
  }
  routeForm(parent, detail) {
    const t = this.t;
    const routeDetails=el("details",undefined,"drill-route-details");
    routeDetails.append(el("summary",this._hass.language?.startsWith("nl") ? "Bekijk de route-instellingen" : "View route settings"));
    const output = el("div", undefined, "route-sections");
    let serial = 0;
    // A group revision alone does not cover receiver settings, source loss or changed control identities.
    const routeContext = data => JSON.stringify([
      data.entry_id, data.revision, data.matter_revision, data.groups, data.sources,
      data.incident, data.selftest, data.automation?.settings, data.automation?.notification_routes,
      data.automation?.recipients, data.automation?.scripts, data.automation?.episodes, data.automation?.error
    ]);
    let context = routeContext(this.data);
    const load = async () => {
      if (!this.data) return;
      const request = ++serial;
      const connectionGeneration = this.generation;
      output.replaceChildren(el("p", t.loading));
      try {
        const result = await this._hass.callWS({type:"alarmmesh/route", source:detail.id});
        if (request !== serial || connectionGeneration !== this.generation || !output.isConnected || !this.data) return;
        if (result.revision !== this.data.revision || !result.readonly) {
          output.replaceChildren(el("p", t.previewStale));
          return;
        }
        detail.dispose?.();parent.querySelector(".exercise")?.remove();
        exercise(this,parent,detail,result);
        output.replaceChildren(el("h3", t.linkTogether));
        if (!result.targets.length) output.append(el("p", t.checkNoTargets));
        for (const target of result.targets) {
          const card = el("section", undefined, "route-target");
          card.append(el("h4", this.sourceName(target.source)), el("p", t[target.eligible ? "routeOnce" : "routeBlocked"]));
          for (const via of target.via) {
            const group = this.data.groups.find(g => g.id === via.group);
            card.append(el("p", `${group?.name || t.groups} · ${t[via.reason] || t.guide_unknown}`));
          }
          output.append(card);
        }
        output.append(el("h3", t.notifications));
        this.phoneRouteCards(output, result.phones);
        if (result.notification_preview) { const preview=el("details"); preview.append(el("summary",t.messagePreview),el("strong",result.notification_preview.title),el("p",result.notification_preview.message,"message-preview"),el("small",t.phoneDeliveryUnconfirmed));output.append(preview); }
        output.append(button(t.configureNotifications, () => this.openDialog({kind:"settings"})));
        for (const assessment of result.groups) {
          const group = this.data.groups.find(g => g.id === assessment.group);
          const card = el("section", undefined, "route-target");
          card.append(el("h3", group?.name || t.groups));
          for (const script of assessment.scripts) card.append(el("p", `${t["phase_" + script.phase]} ${script.order} · ${script.name} · ${t[script.reason] || t.guide_unknown}`));
          if (!assessment.scripts.length) card.append(el("p", t.noGroupScripts));
          if (group) card.append(button(t.optionalActions, () => this.openDialog({kind:"edit", group, section:"actions"})));
          output.append(card);
        }
        output.append(el("p", t.previewRecovery), el("p", t.routeScripts), el("small", t.physicalNotTested));
      } catch (error) {
        if (request === serial && output.isConnected) output.replaceChildren(el("p", t[error.code] || t.error));
      }
    };
    detail.suspend = () => {
      ++serial;
      detail.pauseExercise?.();
      if (!detail.pauseExercise) routeDetails.open = true;
      routeDetails.querySelector("button").disabled = !this.data;
      output.replaceChildren(el("p", t.previewStale));
    };
    detail.resumed = () => {
      const next = routeContext(this.data);
      routeDetails.querySelector("button").disabled = false;
      if (next !== context) {
        context = next;
        detail.suspend();
      } else {
        detail.resumeExercise?.();
      }
    };
    routeDetails.append(button(t.refreshData, load), output);parent.append(routeDetails);
    load();
  }
  alarmSettingsForm(parent, detail) {
    const t=this.t;parent.append(el('h2',t.myAlarmSettings),el('p',t.alarmSettingsNote));
    const output=el('div',undefined,'alarm-settings-list');let serial=0;
    const navigate=(next)=>this.openDialog({...next,returnTo:'alarmsettings'});
    const load=async()=>{const id=++serial;output.setAttribute('aria-busy','true');
      try{const result=await this._hass.callWS({type:'alarmmesh/alarm_settings'});if(id!==serial || !output.isConnected || !this.data)return;
        if(!result.readonly || result.revision!==this.data.revision)throw {code:'previewStale'};
        const opened=new Set([...output.querySelectorAll('details[open]')].map(n=>n.dataset.source));output.replaceChildren();
        if(!result.rows.length)output.append(el('p',t.empty),button(t.choose,()=>this.choose()));
        for(const row of result.rows){const source=this.data.sources.find(s=>s.entity_id===row.source);if(!source)continue;
          const card=el('details',undefined,'alarm-setting-card');card.dataset.source=row.source;card.open=opened.has(row.source);
          card.append(el('summary',this.sourceName(row.source)),this.badge({status:row.status}));
          if(!['NO_SMOKE_REPORTED','SMOKE_REPORTED'].includes(row.status))card.append(el('p',t[row.status==='UNREACHABLE'?'recovery_temporary':row.status==='MISSING'?'recovery_missing':'UNKNOWN']),button(t.inspectDetector,()=>navigate({kind:'source',id:row.source})));
          card.append(el('h3',t.groups));for(const g of row.groups){const group=this.data.groups.find(x=>x.id===g.id);if(group)card.append(button(group.name,()=>navigate({kind:'group',id:g.id})));}if(!row.groups.length)card.append(el('p',t.noGroups));
          card.append(el('h3',t.linkTogether));if(!row.targets.length)card.append(el('p',t.noConfiguredTargets));
          for(const target of row.targets){const section=el('section');section.append(el('h4',this.sourceName(target.source)),el('p',t[target.eligible?'routeReady':'routeBlocked']));if(target.via.length>1)section.append(el('small',t.sharedTarget));
            for(const via of target.via){const group=this.data.groups.find(g=>g.id===via.group);section.append(el('p',`${group?.name || t.groups}: ${t[via.reason] || t.guide_unknown}`));if(group)section.append(button(t.reviewAssignment,()=>navigate({kind:'edit',group,section:'actions'})));}card.append(section);}
          card.append(el('h3',t.notifications));this.phoneRouteCards(card,row.phones);
          card.append(button(t.configureNotifications,()=>navigate({kind:'settings'})),el('h3',t.incidentActions));
          let scripts=0;for(const g of row.groups)for(const action of g.scripts){scripts++;card.append(el('p',`${this.data.groups.find(x=>x.id===g.id)?.name || t.groups} · ${t['phase_'+action.phase]} ${action.order}: ${action.name}`),el('p',t[action.reason] || t.guide_unknown));const group=this.data.groups.find(x=>x.id===g.id);if(group)card.append(button(t.reviewAssignment,()=>navigate({kind:'edit',group,section:'actions'})));}
          if(!scripts)card.append(el('p',t.noGroupScripts));output.append(card);
        }
      }catch(e){if(id===serial && output.isConnected)output.replaceChildren(el('p',t[e.code] || t.error));}finally{if(id===serial)output.removeAttribute('aria-busy');}};
    detail.refresh=load;parent.append(button(t.refreshData,load),output);load();
  }
  recoveryForm(parent,detail) {
    const t = this.t;
    parent.append(el("h2", t.recoverSource), el("p", this.sourceName(detail.id)));
    const steps = el("ol", undefined, "recovery-steps");
    for (const step of t.recoveryPreparation) steps.append(el("li", step));
    parent.append(steps);
    parent.append(button(t.choose,()=>this.choose()),button(t.notifications,()=>this.go("settings")),button(t.groups,()=>this.go("groups")));
    const output=el("div");parent.append(output);
    detail.showMemberships = () => {
      const attempt = detail.pendingRecovery;
      if (!attempt || !this.data) return;
      delete detail.pendingRecovery;
      const summary = el("section", undefined, "notice recovery-summary");
      summary.setAttribute("role", "status");
      summary.append(el("h3", t.recoveryCurrent), el("p", t.recoveryLostReply));
      for (const item of attempt.groups) {
        const group = this.data.groups.find(g => g.id === item.id);
        const members = group?.members || [];
        const names = [detail.id, attempt.target].filter(id => members.includes(id)).map(id => this.sourceName(id));
        const state = group ? names.join(", ") || t.recoveryNeither : t.recoveryGroupGone;
        summary.append(el("p", (group?.name || item.name) + " · " + state));
      }
      output.replaceChildren(summary);
    };
    const load=async()=>{output.replaceChildren(el("p",t.loading));try{const plan=await this._hass.callWS({type:"alarmmesh/recovery",source:detail.id});if(!output.isConnected || !this.data)return;output.replaceChildren(el("p",plan.selected ? t.recoveryOldSelected:t.recoveryOldRemoved));
      if(plan.blocked || plan.outputs_enabled){output.append(el("p",t[plan.blocked ? "recovery_busy":"recovery_disable"]));return;}
      const form=el("form"),select=el("select");select.setAttribute("aria-label",t.recoveryCandidate);for(const c of plan.candidates){const o=el("option",this.sourceName(c.entity_id));o.value=c.entity_id;select.append(o);}form.append(el("label",t.recoveryCandidate),select);const checks=[];
      for(const id of plan.groups){const c=this.checkField(form,this.data.groups.find(g=>g.id===id)?.name || id,false,"recovery-group");c.value=id;checks.push(c);}
      const error=el("p", "","form-error");form.append(el("p",t.recoveryAuthority),error);const save=el("button",t.recoveryReview,"button primary");save.type="submit";save.disabled=!plan.candidates.length || !plan.groups.length;form.append(save);
      form.addEventListener("submit",event=>{event.preventDefault();if(form.querySelector('.request-confirmation'))return;const target=select.value,groups=checks.filter(c=>c.checked).map(c=>c.value);if(!groups.length){error.textContent=t.invalid_members;return;}this.confirmRequest(form,{name:t.recoverSource,confirmationOnly:true,note:`${t.changeChanged}: ${this.sourceName(detail.id)} → ${this.sourceName(target)}\n${groups.map(id=>this.data.groups.find(g=>g.id===id)?.name || id).join(', ')}\n${t.recoveryAuthority}`,execute:async()=>{
        const attempt = {target, groups: groups.map(id => ({id, name: this.data.groups.find(g => g.id === id)?.name || id}))};
        detail.pendingRecovery = attempt;
        try{await this._hass.callWS({type:"alarmmesh/recovery",source:detail.id,target,groups,token:plan.token,confirmed:true});if(detail.pendingRecovery !== attempt || attempt.interrupted)return;delete detail.pendingRecovery;output.replaceChildren(el("p",t.recoverySaved),button(t.groups,()=>this.go("groups")),button(t.choose,()=>this.choose()));} catch(e) {
          if (detail.pendingRecovery !== attempt || attempt.interrupted) return;
          error.textContent=t[e?.code] || t.error;
          if (e?.code && t[e.code]) delete detail.pendingRecovery;
          else attempt.interrupted = true;
        }
      }});});output.append(form);
    }catch(e){if(output.isConnected)output.replaceChildren(el("p",t[e.code] || t.error));}};
    parent.append(button(t.refreshData,async()=>{
      if (!detail.pendingRecovery) return load();
      if (!detail.pendingRecovery.interrupted || !this.data) return;
      const generation = this.generation;
      const attempt = detail.pendingRecovery;
      try {
        const fresh = await this._hass.callWS({type:"alarmmesh/current"});
        if (!fresh.available || this.detail !== detail || generation !== this.generation || detail.pendingRecovery !== attempt) return;
        this.data = fresh;
        detail.showMemberships();
      } catch { if (output.isConnected) output.append(el("p",t.error)); }
    }));load();
  }
  async loadDiagnostics() {
    if (!this.data || !this._hass.user?.is_admin) return;
    this.diagnostics=null; this.diagnosticError=false;
    const connection=this.connection, generation=this.generation;
    try { const report=await this._hass.callWS({type:"alarmmesh/diagnostics"}); if(this.isConnected && this.connection===connection && generation===this.generation && this.data && this._hass.user?.is_admin) this.diagnostics=report; }
    catch { this.diagnosticError=true; }
    if(this.page==="diagnostics") this.render();
  }
  renderDiagnostics(parent) {
    const t=this.t, report=this.diagnostics;
    parent.append(el("p",t.diagnosticNote,"notice"),button(t.refreshReport,()=>this.loadDiagnostics()));
    if(!report) { parent.append(el("p",this.diagnosticError ? t.error : t.loading)); return; }
    const table=el("dl");
    for(const [key,value] of Object.entries(report.versions || {})) table.append(el("dt",key==="alarmmesh" ? "AlarmMesh" : "Home Assistant"),el("dd",value));
    for(const [key,value] of Object.entries(report.counts || {})) table.append(el("dt",t['count_'+key] || t.guide_unknown),el("dd",String(value)));
    table.append(el("dt",t.sources),el("dd",t[report.result.availability] || t.guide_unknown)); parent.append(table);
    for(const source of report.sources || []) parent.append(el("p",`${source.alias} · ${t[source.provider] || t.guide_unknown} · ${source.model === "unknown" ? t.guide_unknown : source.model} · ${t[source.assessment] || t.guide_unknown}`));
    for(const problem of report.problems || []) { const row=el("section",undefined,"notice"); row.append(el("h3",problem.source || problem.group || "AlarmMesh"),el("p",t[problem.reason] || t.guide_unknown),el("p",t['diagnose_'+problem.setting] || t.diagnosticConsequence),button(t.reviewAssignment,()=>problem.setting==="maintenance" ? this.go("maintenance") : problem.setting==="groups" ? this.go("groups") : problem.setting==="notifications" ? this.go("settings") : this.choose())); parent.append(row); }
    for(const recipient of report.recipients || []) if(!recipient.available) parent.append(el("p",`${recipient.alias}: ${t.recipient_unavailable}`));
    for(const error of report.recorded_errors || []) parent.append(el("p",`${error.target}: ${t['delivery_'+error.status] || t[error.status] || t.guide_unknown}`));
    const label=el("label",t.reportPreview); label.htmlFor="support-report";
    const area=el("textarea"); area.id="support-report"; area.readOnly=true; area.value=JSON.stringify(report,null,2); area.rows=16;
    const status=el("p", ""); status.setAttribute("role","status");
    parent.append(label,area,button(t.copyReport,async()=>{ try { await navigator.clipboard.writeText(area.value); status.textContent=t.reportCopied; } catch { area.focus(); area.select?.(); status.textContent=t.copyManually; } }),status);
  }
  checkField(parent, text, checked, name) {
    const label = el("label", undefined, "check"), input = el("input");
    input.type = "checkbox"; input.checked = Boolean(checked); input.name = name;
    label.append(input, el("span", text)); parent.append(label); return input;
  }
  lockControls(parent) {
    const controls = [...parent.querySelectorAll("input,select,button")].map(node => [node, node.disabled]);
    for (const [node] of controls) { node.dataset.confirmLocked = "true"; node.disabled = true; }
    return () => {
      for (const [node, disabled] of controls) { delete node.dataset.confirmLocked; node.disabled = disabled || Boolean(node.dataset.reopenRequired); }
      if (!this.data) this.offlineDraft();
    };
  }
  confirmRequest(parent, detail) {
    const t = this.t;
    if(detail.actionKind==='notification' && this.data?.automation?.profile_support && !detail.phonePlan) {
      const previous=parent.querySelector('.request-confirmation');previous?.restore?.();previous?.remove();
      const restore=this.lockControls(parent),pending=el('section',undefined,'notice request-confirmation');pending.restore=restore;
      const status=el('p',t.loading);pending.append(status,button(t.cancel,()=>{pending.remove();restore();}));parent.append(pending);
      const generation=this.generation;
      if(typeof globalThis.crypto?.getRandomValues!=='function'){status.textContent=t.request_random_unavailable;return;}
      const request=Array.from(globalThis.crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
      this._hass.callWS({type:'alarmmesh/notification_preview',target:detail.target,request_id:request}).then(plan=>{
        if(!pending.isConnected || generation!==this.generation || !this.data)return;
        if(plan.context!==this.data.automation.confirmations[detail.target]) {status.textContent=t.notification_confirmation_stale;return;}
        pending.remove();restore();this.confirmRequest(parent,{...detail,phonePlan:plan});
      }).catch(e=>{if(pending.isConnected)status.textContent=t[e.code] || t.offline;});return;
    }
    const previous = parent.querySelector(".request-confirmation"); previous?.restore?.(); previous?.remove();
    const restore = this.lockControls(parent);
    const box = el("section", undefined, "notice request-confirmation");
    box.restore = restore;
    if (detail.actionKind === "notification") {
      box.dataset.notificationTarget = detail.target;
      box.dataset.notificationToken = detail.phonePlan?.context || this.data?.automation?.confirmations?.[detail.target] || "";
      detail.identity = detail.phonePlan?.confirmation || box.dataset.notificationToken;
    }
    if(detail.changes)this.changeSummary(box,detail.changes.kind,detail.changes.before,detail.changes.after);
    const summaryRevision=detail.changes?.kind==='phones' ? this.data?.automation?.settings.revision : this.data?.revision;
    const summaryStale=()=>detail.changes && summaryRevision!==(detail.changes.kind==='phones' ? this.data?.automation?.settings.revision : this.data?.revision);
    box.append(el("h3", detail.name || t.explicitTest), el("p", detail.note || (detail.actionKind === "selftest" ? t.selfTestWarning : detail.actionKind === "script" ? t.scriptConsequences : t.notifyTestWarning)));
    const ack = this.checkField(box, t.confirmExactTarget, false, "confirm-request");
    const error = el("p", "", "form-error"); error.setAttribute("role", "alert");
    const status = el("p", "", "request-status"); status.setAttribute("role", "status");
    const execute = button(detail.confirmationOnly ? t.confirmRequest : detail.actionKind==='notification' ? t.sendPhoneTest : detail.actionKind==='selftest' ? t.startSelfTest : t.runScriptTest, async () => {
      if (execute.disabled || execute.dataset.started) return;
      if(summaryStale()){ack.checked=false;error.textContent=t.conflict;return;}
      if (detail.actionKind === "notification" && (!detail.identity || box.dataset.notificationToken !== this.data?.automation?.confirmations?.[detail.target])) {
        ack.checked = false; status.textContent = t.notification_confirmation_stale; return;
      }
      if (!ack.checked) { error.textContent = t.test_confirmation_required; ack.focus(); return; }
      if (!this.data) { error.textContent = t.offline; return; }
      error.textContent = "";
      execute.disabled = true;
      execute.dataset.started = "true";
      status.textContent = t.delivery_sending;
      if (detail.execute) { await detail.execute(); return; }
      try {
        if (typeof globalThis.crypto?.getRandomValues !== "function") throw Object.assign(new Error("Secure random values unavailable"), { code: "request_random_unavailable" });
        // getRandomValues also works on local HTTP; randomUUID requires a secure context.
        const request = detail.phonePlan?.request_id || Array.from(globalThis.crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
        if (detail.actionKind === "selftest") box.dataset.selftestRequest = request;
        if (detail.actionKind === "notification") box.dataset.deliveryRequest = request;
        const result = await this._hass.callWS({ type: "alarmmesh/test", kind: detail.actionKind, target: detail.target, identity: detail.identity || "", confirmed: true, request_id: request });
        status.textContent = t[(detail.actionKind === "selftest" ? "test_" : "delivery_") + result.status] || t.error;
        this.updateTestResult();
      } catch (e) {
        if (detail.actionKind === "notification") status.textContent = t[e.code] || t.delivery_outcome_unknown;
        else error.textContent = t[e.code] || t.error;
      }
    }, "button destructive confirm-execute");
    box.append(status, error, button(t.cancel, () => { box.remove(); restore(); if (parent.tagName === "DIALOG" && this.detail?.kind === "test") this.closeDialog(); }), execute); parent.append(box); ack.focus();
    if (detail.actionKind === "notification" && this.data?.automation?.test_preview) {
      const preview = detail.phonePlan?.message || this.data.automation.test_preview;
      box.insertBefore(el("p", `${preview.title}\n${preview.message}`, "message-preview"), ack.parentElement);
      if(detail.phonePlan)box.insertBefore(el('p',`${this.phoneSummary(detail.phonePlan.profile)}. ${detail.phonePlan.profile?.critical ? t.criticalTestWarning : t.phoneUnchecked}`,'notice'),ack.parentElement);
      box.append(el("small", t.phoneDeliveryUnconfirmed), button(t.refreshConfirmation, () => this.confirmRequest(parent, {...detail,phonePlan:null})));
    }
  }
  updateTestResult() {
    for (const box of this.shadowRoot.querySelectorAll("[data-notification-target]")) {
      const status = box.querySelector(".request-status");
      if (box.dataset.deliveryRequest) {
        const receipt = this.data?.automation?.manual_results?.find(row => row.request_id === box.dataset.deliveryRequest);
        if (receipt) status.textContent = this.t['delivery_' + receipt.status] + (receipt.error ? ` · ${this.t[receipt.error] || this.t.deliveryAdvice}` : "");
        else if (!this.data) status.textContent = this.t.delivery_outcome_unknown;
      } else if (this.data?.automation?.confirmations?.[box.dataset.notificationTarget] !== box.dataset.notificationToken) {
        box.querySelector('[name="confirm-request"]').checked = false;
        status.textContent = this.t.notification_confirmation_stale;
      }
    }
    const result = this.data?.selftest;
    for (const box of this.shadowRoot.querySelectorAll("[data-selftest-request]")) {
      if (result?.request_id === box.dataset.selftestRequest) box.querySelector(".request-status").textContent = this.t["test_" + result.status] || this.t.error;
    }
  }
  actionFields(parent, saved) {
    const t = this.t, section = el("section", undefined, "linking-section action-config");
    section.append(el("h3", t.incidentActions), el("p", t.scriptConsequences));
    const enabled = this.checkField(section, t.enableActions, saved?.enabled, "actions-enabled");
    const lists = {};
    for (const phase of ["start", "recovery"]) {
      const items = (saved?.[phase] || []).map(b => ({ ...b }));
      const area = el("div"); area.dataset.phase = phase;
      section.append(el("h3", t['phase_' + phase]), area);
      const draw = focusIndex => {
        area.replaceChildren();
        for (const [index, binding] of items.entries()) {
          const row = el("div", undefined, "action-row"), select = el("select"); select.setAttribute("aria-label", `${t['phase_' + phase]} ${index + 1}`);
          const empty = el("option", t.chooseScript); empty.value = ""; select.append(empty);
          const current = this.data?.automation?.scripts.find(s => s.entity_id === binding.entity_id && s.identity === binding.identity);
          for (const script of this.data?.automation?.scripts || []) { const option = el("option", script.name); option.value = script.entity_id; option.selected = script === current; select.append(option); }
          if (binding.entity_id && !current) { const name = this.data?.automation?.scripts.find(s => s.entity_id === binding.entity_id)?.name || binding.entity_id; const option = el("option", `${name} · ${t.script_changed}`); option.value = `stored:${binding.entity_id}`; option.selected = true; select.append(option); }
          select.addEventListener("change", () => { const script = this.data?.automation?.scripts.find(s => s.entity_id === select.value); if (script) items[index] = { entity_id: script.entity_id, identity: script.identity }; else if (!select.value) items[index] = { entity_id: "", identity: "" }; draw(index); });
          const test = button(t.testScript, () => { const b = items[index]; const script = this.data?.automation?.scripts.find(s => s.entity_id === b?.entity_id && s.identity === b.identity); if (script) this.confirmRequest(section, { actionKind: "script", target: b.entity_id, identity: b.identity, name: script.name }); });
          test.disabled = !current;
          const up = button(t.moveUp, () => { [items[index - 1], items[index]] = [items[index], items[index - 1]]; draw(index - 1); }); up.disabled = index === 0;
          const down = button(t.moveDown, () => { [items[index + 1], items[index]] = [items[index], items[index + 1]]; draw(index + 1); }); down.disabled = index === items.length - 1;
          for (const [node, title] of [[up, t.moveUp], [down, t.moveDown], [test, t.testScript]]) node.setAttribute("aria-label", `${title}: ${current?.name || binding.entity_id || t.chooseScript}, ${t['phase_' + phase]} ${index + 1}`);
          row.append(el("span", `${index + 1}.`), select,
            up, down,
            button(t.removeAction, () => { items.splice(index, 1); draw(Math.min(index, items.length - 1)); }),
            test);
          if (binding.entity_id && !current) row.append(el("small", t.script_changed, "warning-text"));
          area.append(row);
        }
        if (focusIndex !== undefined) { if (items.length) area.querySelectorAll("select")[focusIndex]?.focus(); else add.focus(); }
      };
      const add = button(t.addScript, () => { if (items.length < 20) { items.push({ entity_id: "", identity: "" }); draw(items.length - 1); } }); section.append(add);
      lists[phase] = items; draw();
    }
    parent.append(section);
    return () => ({ enabled: enabled.checked, start: lists.start.map(b => ({ ...b })), recovery: lists.recovery.map(b => ({ ...b })) });
  }
  renderIncidents(parent) {
    if(this.linkedIncident){incidentDetail(this,parent,this.linkedIncident);return;}
    parent.append(button(this.t.activity,()=>this.go("activity")));
    const t = this.t, data = this.data;
    const current=el('section',undefined,'notice incident-now');current.append(el('h2',t.currentSituation),this.badge(data.result),el('p',t[data.result.availability]));parent.append(current);
    const explanation=el('details',undefined,'incident-explanation');explanation.append(el('summary',t.howToReadIncidents),el('p',t.incidentNote));parent.append(explanation);
    const timeline=el('details',undefined,'incident-timeline');timeline.append(el('summary',t.incidentTimeline),el('p',t.incidentTimelineNote));
    const events=[...(data.activity?.events || [])].filter(r=>r.category==='alarm');const list=el('ol');
    for(const event of events){const item=el('li');item.append(el('time',this.formatTime(event.observed_at)),el('p',`${t['activity_'+event.kind] || t.guide_unknown}: ${this.activityResult(event)}`));if(event.source)item.append(el('p',this.sourceName(event.source)));if(event.target)item.append(el('p',data.automation?.recipients.find(r=>r.service===event.target)?.name || data.automation?.scripts.find(r=>r.entity_id===event.target)?.name || event.target.replace(/^mobile_app_/,'')));const technical=el('details');technical.append(el('summary',t.technicalDetails),el('p',event.correlation || t.guide_unknown));item.append(technical);list.append(item);}
    if(!events.length)timeline.append(el('p',t.noFilterResults));if(data.activity?.incomplete)timeline.append(el('p',t.activityIncomplete));timeline.append(list);parent.append(timeline);
    this.sourceList(parent, data.sources.filter(s => s.status === "SMOKE_REPORTED"));
    const active = data.incident?.active_sources || [];
    const pending = active.filter(id => data.sources.find(s => s.entity_id === id)?.status !== "SMOKE_REPORTED");
    if (pending.length) parent.append(el("p", `${t.incidentPending}: ${pending.map(id => data.sources.find(s => s.entity_id === id)?.name || id).join(", ")}`, "notice"));
    const groups = data.groups.filter(g => (g.origins || g.members).some(id => active.includes(id)));
    if (groups.length) { const section=el("section",undefined,"notice"); section.append(el("h2",t.groups)); for (const group of groups) section.append(button(group.name,()=>this.openDialog({kind:"group",id:group.id}))); parent.append(section); }
    for (const target of data.incident?.targets || []) {
      const row = el("section", undefined, "notice sounder-receipt");
      row.append(el("h3", data.sources.find(s => s.entity_id === target.source)?.name || target.source), el("p", t[target.status] || t.guide_unknown));
      if (target.origins?.length) row.append(el("p", `${t.recordedOrigins}: ${target.origins.map(id => this.sourceName(id)).join(", ")}`));
      row.append(el("small", t.commandNote)); parent.append(row);
    }
    const episodes = data.automation?.episodes || [];
    if (!episodes.length && !(data.incident?.active_sources || []).length) parent.append(el("p", t.noIncidents));
    for (const episode of episodes) {
      const card = el("section", undefined, "notice incident-episode"); card.dataset.incident = episode.id;
      const group = data.groups.find(g => g.id === episode.group_id);
      card.append(el("h2", group?.name || t.notifications),el("p",t[episode.phase==='recovery'?'incidentClosed':'incidentStillOpen'],"episode-phase"));
      const flow = el("ol", undefined, "incident-flow");
      flow.append(el("li", `${t.incidentStarted}: ${this.formatTime(episode.started)}`));
      flow.append(el("li", `${t.recordedOrigins}: ${episode.origins.map(id => this.sourceName(id)).join(", ")}`));
      if (episode.phase !== "recovery") {
        const waiting = (episode.relevant || episode.origins).filter(id => data.sources.find(s => s.entity_id === id)?.status !== "NO_SMOKE_REPORTED");
        flow.append(el("li", waiting.length ? `${t.incidentPending}: ${waiting.map(id => this.sourceName(id)).join(", ")}` : t.recoveryNotRecorded));
      }
      card.append(flow);
      for (const receipt of Object.values(episode.receipts)) {
        const row = el("div", undefined, "execution-row");
        const name = data.automation?.scripts.find(s => s.entity_id === receipt.target)?.name || receipt.target.replace(/^mobile_app_/, "");
        row.append(icon(["failed", "blocked", "outcome_unknown"].includes(receipt.status) ? "alert-circle-outline" : receipt.status === "accepted" ? "email-check-outline" : "progress-clock"), el("span", `${t[receipt.kind === "script" ? "scriptRequest" : "phoneRequest"]} · ${name}: ${t['delivery_' + receipt.status] || t.guide_unknown} · ${t['phase_' + receipt.phase]}`));
        if (["failed", "blocked", "outcome_unknown"].includes(receipt.status)) row.append(el("small", receipt.kind === "script" ? t.script_changed : t.deliveryAdvice));
        card.append(row);
      }
      if (episode.phase === "recovery") flow.append(el("li", `${t.recoveryRecorded}: ${this.formatTime(episode.updated)}`));
      card.append(el("small", t.incidentEvidenceLimit, "muted"));
      parent.append(card);
    }
    for (const row of data.automation?.manual_results || []) this.notificationReceipt(parent,row);
    this.phoneEvidenceList(parent);
    if (data.selftest) parent.append(el("section", undefined, "notice selftest-result"));
    const self = parent.querySelector(".selftest-result");
    if (self) self.append(el("h2", t.selfTests), el("p", `${data.sources.find(s => s.entity_id === data.selftest.source)?.name || data.selftest.source}: ${t['test_' + data.selftest.status]}`), el("p", t.deviceResultNote));
  }
  sourceName(id) {
    const source = this.data.sources.find(s => s.entity_id === id);
    if (!source) return id;
    const duplicate = this.data.sources.some(other => other.entity_id !== id && other.name === source.name && other.area_id === source.area_id);
    return `${source.name} · ${source.area_name || this.t.noRoom}${duplicate ? ` · ${id}` : ""}`;
  }
  notificationReceipt(parent,row) {
    const t=this.t,card=el("section",undefined,"notice");
    card.append(el("strong",`${t.explicitTest} · ${row.target.replace(/^mobile_app_/,"")}`),el("p",t['delivery_'+row.status] || t.guide_unknown),el("small",this.formatTime(row.started)));
    if(row.kind==="notification") {
      if(row.alarm_profile)card.append(el('p',this.phoneSummary(row.alarm_profile)));
      card.append(el("p",t.phoneDeliveryUnconfirmed));
      const saved=this.data.phone_evidence?.requests.find(r=>r.request_id===row.request_id);
      if(saved?.attempted && saved.status!=='sending')card.append(button(t.recordObservation,()=>this.openDialog({kind:'phoneObservation',id:row.request_id})));
      if(["failed","blocked","outcome_unknown"].includes(row.status)) card.append(el("p",t[row.error] || t.deliveryAdvice),button(t.configureNotifications,()=>this.openDialog({kind:"settings"})));
    }
    const details=el("details");details.append(el("summary",t.requestContext),el("p",row.request_id || t.guide_unknown));card.append(details);parent.append(card);
  }
  draftKey(detail=this.detail) {return detail ? detail.kind+":"+(detail.id || detail.group?.id || "new") : "";}
  draftSignature() {const d=this.data;if(!d)return "";return JSON.stringify([d.sources.map(s=>[s.entity_id,s.reminder_identity || null,s.capability?.matter?.fingerprint || null,s.capability?.controls?.map(c=>[c.target,c.identity]) || [],s.selftest?.control?.identity || null]),(d.automation?.scripts || []).map(s=>[s.entity_id,s.identity]),(d.automation?.recipients || []).map(r=>r.service).sort()]);}
  clearDraftsForOldUser(id) {this.drafts.clearUser(id);}
  clearDraft() {this.drafts.remove(this._hass?.user?.id,this.data?.entry_id,this.draftKey());}
  trackDraft(form,revision,read) {
    const user=this._hass?.user?.id,entry=this.data?.entry_id,detail=this.detail,signature=this.draftSignature(),target=detail.id || detail.group?.id || "new";
    const capture=event=>{if(!form.isConnected || !user || event.target?.closest?.('.request-confirmation,.link-confirmation'))return;try{this.drafts.put(user,entry,detail.kind,target,revision,signature,read());}catch{this.drafts.error=true;}};
    form.addEventListener("input",capture);form.addEventListener("change",capture);
    form.addEventListener("click",event=>{if(event.target?.closest?.('.request-confirmation,.link-confirmation'))return;setTimeout(()=>capture(event),0);});
  }
  renderDrafts(parent) {
    const entries=Object.entries(this.drafts.read(this._hass?.user?.id,this.data?.entry_id));
    if(!entries.length)return;const t=this.t,box=el("section",undefined,"notice draft-list");box.append(el("h2",t.draftFound),el("p",t.draftReview));
    for(const [key,draft] of entries) {
      const label=t[draft.kind==="edit" ? "groups" : draft.kind==="reminder" ? "reminders" : draft.kind==="maintenance" ? "maintenanceNotifications" : "notifications"];
      const group=this.data.groups.find(g=>g.id===draft.target);
      if(draft.kind==="edit" && draft.target!=="new" && !group) box.append(el("p",t.draftChanged));
      else box.append(button(`${t.continueDraft}: ${label}`,()=>{const detail={kind:draft.kind};if(draft.kind==="edit")detail.group=group || null;if(draft.kind==="reminder")detail.id=draft.target;this.openDialog(detail);}));
      box.append(button(t.discardDraft,()=>{this.drafts.remove(this._hass?.user?.id,this.data?.entry_id,key);this.render();}));
    }parent.append(box);
  }
  providerLabel(cap) {
    if(cap.origin!=="matter") return this.t[cap.origin] || this.t.unknown_origin;
    return `${this.t.matter} · ${this.t['transport_'+(cap.matter?.transport || 'unknown')]}`;
  }
  matterDetails(parent,source) {
    const t=this.t, info=source.capability.matter;
    parent.append(el("p",t['matter_kind_'+info.source_kind] || t.matter_origin_unknown));
    const table=el("dl",undefined,"matter-functions");
    for(const row of info.functions || []) {table.append(el("dt",t['matter_function_'+row.key] || t[row.key] || row.key),el("dd",t[row.reason] || t.guide_unknown));}
    parent.append(table);
    if(info.identity_changed && info.fingerprint) parent.append(button(t.reviewMatterIdentity,()=>{
      const current=this.data; if(!current)return;
      const groups=current.groups.filter(g=>g.members.includes(source.entity_id));
      this.confirmRequest(parent,{name:source.name,confirmationOnly:true,note:`${t.matterIdentityNote}\n${source.name} · ${source.model || t.guide_unknown}\n${groups.map(g=>`${g.name}: ${t[g.linking?.enabled ? 'enabled':'disabled']}`).join('\n')}`,execute:async()=>{
        if(!this.data)return;const status=el("p", "");parent.append(status);
        try{await this._hass.callWS({type:"alarmmesh/matter_review",source:source.entity_id,identity:info.fingerprint,revision:current.matter_revision,confirmed:true});this.closeDialog();}catch(e){status.textContent=t[e.code] || t.error;}
      }});
    }));
    parent.append(button(t.matterHelp,()=>this.go("matterHelp")));
  }
  renderMatterHelp(parent) {
    const t=this.t;parent.append(el("p",t.matterHelpIntro,"notice"));
    const steps=el("ol",undefined,"incident-flow");for(let i=1;i<=6;i++) steps.append(el("li",t['matterStep'+i]));parent.append(steps,el("p",t.matterTransportNote),el("p",t.matterRouteLimits));
    for(const [url,label] of [[t.matterSetupUrl,t.matterSetupLink],[t.threadSetupUrl,t.threadSetupLink]]) {const link=el("a",label);link.href=url;link.target="_blank";link.rel="noopener noreferrer";parent.append(link,el("br"));}
    parent.append(button(t.choose,()=>this.choose()),button(t.groups,()=>this.go("groups")),button(t.catalog,()=>this.go("catalog")));
    if(this.data.matter_error) parent.append(el("p",t[this.data.matter_error] || t.error,"notice warning-text"));
  }
  filterField(parent, label, key, value, choices, change) {
    const wrapper=el("label",label), field=el(choices ? "select" : "input");
    field.dataset.sticky=key; field.name=key;
    if(choices) for(const [id,name] of [["",this.t.allFilters],...choices]) { const option=el("option",name); option.value=id; option.selected=id===value; field.append(option); }
    else { field.type="search"; field.value=value; }
    field.addEventListener(choices ? "change" : "input",()=>change(field.value)); wrapper.append(field); parent.append(wrapper); return field;
  }
  renderDevices(parent) {
    const t=this.t, data=this.data, f=this.deviceFilters;
    const status=el("section",undefined,"notice filter-alarm"); status.append(this.badge(data.result),el("p",t[data.result.availability])); parent.append(status);
    if(!data.sources.length) return;
    const bar=el("div",undefined,"filter-bar device-filters"), results=el("section",undefined,"filtered-devices");
    const draw=()=> { results.replaceChildren(); const rows=data.sources.filter(s=>{
      const h=s.capability?.details?.maintenance, attention=h?.end_of_service===true || h?.fault===true || h?.battery_low===true || h?.battery_percent!=null && h.battery_percent<=20;
      return (!f.name || s.name.toLocaleLowerCase().includes(f.name.toLocaleLowerCase())) && (!f.room || (s.area_id || "none")===f.room) && (!f.group || s.groups.includes(f.group)) && (!f.provider || (s.capability?.origin === "zigbee2mqtt" ? "mqtt" : s.capability?.origin || "unknown_origin")===f.provider) && (!f.status || (f.status==="unusable" ? ["UNREACHABLE","MISSING"].includes(s.status) : s.status===f.status)) && (!f.maintenance || (f.maintenance==="attention" ? attention : h?.fault==null && h?.battery_low==null && h?.battery_percent==null));
    }); if(!rows.length) results.append(el("p",t.noFilterResults,"notice")); else this.sourceList(results,rows); };
    const field=(label,key,choices)=>this.filterField(bar,label,`device-${key}`,f[key],choices,value=>{ f[key]=value; draw(); });
    field(t.findDetector,"name"); field(t.room,"room",data.rooms.map(r=>[r.id || "none",r.name || t.noRoom])); field(t.groups,"group",data.groups.map(g=>[g.id,g.name])); field(t.provider,"provider",[["mqtt",t.zigbee2mqtt],["zha",t.zha],["matter",t.matter],["zwave_js",t.zwave_js],["unknown_origin",t.unknown_origin]]);
    field(t.state,"status",[["SMOKE_REPORTED",t.SMOKE_REPORTED],["unusable",t.unavailable],["UNKNOWN",t.UNKNOWN]]); field(t.maintenance,"maintenance",[["attention",t.attention],["unknown",t.missingInformation]]);
    const filters = el("details", undefined, "more-filters");
    filters.open = Object.entries(f).some(([key, value]) => key !== "name" && value);
    filters.append(el("summary", t.moreFilters));
    for (const field of [...bar.children].slice(1)) filters.append(field);
    filters.append(button(t.clearFilters, () => { for (const key of Object.keys(f)) f[key] = ""; this.render(); }));
    bar.append(filters); parent.append(bar,results); draw();
  }
  renderActivity(parent) {
    const t=this.t, history=this.data.activity, f=this.activityFilters;
    parent.append(el("p",t.activitySummary,"section-note"));const limits=el('details',undefined,'activity-limits');limits.append(el('summary',t.aboutInformation),el('p',t.activityLimit));parent.append(limits);
    if(!history) {parent.append(el("p",t.guide_unknown));return;}
    if(history.incomplete) parent.append(el("p",t.activityIncomplete,"notice warning-text"));
    if(!history.events.length) {parent.append(el("p",t.activityEmpty,"notice"));return;}
    const bar=el("div",undefined,"filter-bar activity-filters"), list=el("div",undefined,"activity-list");
    const draw=()=>{list.replaceChildren();const rows=history.events.filter(r=>(!f.source || r.source===f.source) && (!f.group || r.groups.includes(f.group)) && (!f.kind || r.kind===f.kind) && (!f.result || r.result===f.result) && (!f.category || r.category===f.category)); if(!rows.length) list.append(el("p",t.noFilterResults)); for(const row of rows) { const item=button("",()=>this.openDialog({kind:"activity",event:row}),"button activity-row"); item.append(el("strong",`${t['activity_'+row.kind] || row.kind} · ${this.activityResult(row)}`),el("span",row.source ? this.sourceName(row.source) : row.groups.map(id=>this.data.groups.find(g=>g.id===id)?.name || id).join(", ")),el("small",`${t.observedAt}: ${this.formatTime(row.observed_at)}`)); list.append(item); }};
    const unique=key=>[...new Set(history.events.flatMap(r=>key==="group" ? r.groups : r[key]).filter(Boolean))];
    const field=(label,key,choices)=>this.filterField(bar,label,`activity-${key}`,f[key],choices,value=>{f[key]=value;draw();});
    field(t.detector,"source",unique("source").map(id=>[id,this.sourceName(id)])); field(t.groups,"group",unique("group").map(id=>[id,this.data.groups.find(g=>g.id===id)?.name || id])); field(t.activityKind,"kind",unique("kind").map(id=>[id,t['activity_'+id] || id])); field(t.activityResultLabel,"result",unique("result").map(id=>[id,this.activityResult({kind:"",result:id})])); field(t.activityCategory,"category",unique("category").map(id=>[id,t['category_'+id]]));
    bar.append(button(t.clearFilters,()=>{for(const key of Object.keys(f)) f[key]="";this.render();}));
    const filters = el("details", undefined, "more-filters");
    filters.open = Object.values(f).some(Boolean);
    filters.append(el("summary", t.moreFilters), bar);
    parent.append(filters, list); draw();
  }
  activityResult(row) { const t=this.t; return t['activity_result_'+row.result] || (row.kind==="selftest" ? t['test_'+row.result] : t['delivery_'+row.result]) || t['test_'+row.result] || t[row.result] || t.guide_unknown; }
  activityDetail(parent,row) {
    const t=this.t; parent.append(el("h2",t['activity_'+row.kind] || t.activity),el("p",this.activityResult(row)));
    const props=el("dl"); for(const [label,value] of [[t.observedAt,this.formatTime(row.observed_at)],[t.detector,row.source ? this.sourceName(row.source) : t.guide_unknown],[t.groups,row.groups.map(id=>this.data.groups.find(g=>g.id===id)?.name || id).join(", ") || t.noGroups],[t.target,row.target || t.guide_unknown],[t.requestContext,row.correlation || t.guide_unknown]]) props.append(el("dt",label),el("dd",value)); parent.append(props,el("p",t.activityLimit));
    if(this.data.sources.some(s=>s.entity_id===row.source)) parent.append(button(t.inspectDetector,()=>this.openDialog({kind:"source",id:row.source})));
    for(const group of this.data.groups.filter(g=>row.groups.includes(g.id))) parent.append(button(group.name,()=>this.openDialog({kind:"group",id:group.id})));
    if(row.category==="alarm") parent.append(button(t.viewIncidents,()=>this.go("incidents")));
    if(row.kind==="phone_observation")this.phoneEvidenceList(parent,row.target);
    if(row.kind==="notification") parent.append(el("p",row.category==="configuration" ? t.explicitTest : t.phoneRequest),el("p",t.phoneDeliveryUnconfirmed),button(t.configureNotifications,()=>this.openDialog({kind:"settings"})));
  }
  renderReminders(parent) {
    const t=this.t, data=this.data.reminders, section=el("section",undefined,"notice reminder-list"); section.append(el("h2",t.reminders),el("p",t.reminderNote));
    if(data.error) section.append(el("p",t[data.error] || t.error,"warning-text"));
    if(!data.items.length) section.append(el("p",t.reminderEmpty));
    for(const item of data.items) {const row=el("section");row.append(el("h3",this.sourceName(item.source)),el("p",`${t[item.enabled ? 'enabled':'disabled']} · ${item.date} · ${t['reminder_'+item.status] || t.guide_unknown}`));if(item.attention) row.append(el("p",t[item.attention],"warning-text"));row.append(button(t.configureReminder,()=>this.openDialog({kind:"reminder",id:item.source})));section.append(row);}
    for(const source of this.data.sources.filter(s=>!data.items.some(r=>r.source===s.entity_id))) section.append(button(`${t.configureReminder}: ${source.name}`,()=>this.openDialog({kind:"reminder",id:source.entity_id})));
    parent.append(section);
  }
  reminderForm(parent,detail) {
    const t=this.t, source=this.data.sources.find(s=>s.entity_id===detail.id), serverSaved=this.data.reminders.items.find(i=>i.source===detail.id), saved=detail.restoredDraft?.value || serverSaved, revision=detail.restoredDraft?.revision ?? this.data.reminders.revision;
    parent.append(el("h2",t.reminders),el("p",source?.name || detail.id),el("p",t.reminderNote));
    const form=el("form");form.noValidate=true;const enabled=this.checkField(form,t.enableReminder,saved?.enabled,"reminder-enabled");
    const label=el("label",t.nextReminder), when=el("input");when.type="date";when.name="reminder-date";const parts=new Intl.DateTimeFormat('en-CA',{timeZone:this.data.reminders.time_zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const part=key=>parts.find(p=>p.type===key)?.value;when.value=saved?.date || `${part('year')}-${part('month')}-${part('day')}`;label.append(when);form.append(label,el("p",`${t.reminderTime}: ${this.data.reminders.time_zone}`));
    const intervalLabel=el("label",t.repeatPreference), interval=el("select"); interval.name="reminder-interval";for(const days of [0,30,90,180,365]) {const o=el("option",days ? `${days} ${t.days}` : t.noRepeat);o.value=String(days);o.selected=days===(saved?.interval || 0);interval.append(o);} intervalLabel.append(interval);form.append(intervalLabel);
    const receiverLabel=el("label",t.recipient), receiver=el("select");receiver.name="reminder-recipient";const choices=this.data.automation?.recipients || [];const empty=el("option",t.chooseRecipient);empty.value="";empty.selected=!saved;receiver.append(empty);for(const row of choices) {const o=el("option",row.name || row.service);o.value=row.service;o.selected=row.service===saved?.recipient;receiver.append(o);}if(saved && !choices.some(r=>r.service===saved.recipient)){const o=el("option",`${saved.recipient} · ${t.recipient_unavailable}`);o.value=saved.recipient;o.selected=true;receiver.append(o);}receiverLabel.append(receiver);form.append(receiverLabel);
    const error=el("p","","form-error");error.setAttribute("role","alert");form.append(error);
    const request=(operation,value)=>{if(!this.data){error.textContent=t.offline;return;}this.confirmRequest(form,{name:t.reminders,confirmationOnly:true,note:`${source?.name || detail.id}\n${operation === 'handle' ? t.handleReminder : operation==='snooze' ? t.snoozeReminder : operation==='delete' ? t.removeReminder : t.saveReminder}\n${operation === "save" ? value.date : operation === "snooze" ? value.date : serverSaved?.date} · ${operation === "save" ? value.recipient : serverSaved?.recipient}\n${t.enableReminder}: ${t[(operation === "save" ? value.enabled : serverSaved?.enabled) ? "enabled" : "disabled"]}\n${t.repeatPreference}: ${(operation === "save" ? value.interval : serverSaved?.interval) ? `${operation === "save" ? value.interval : serverSaved?.interval} ${t.days}` : t.noRepeat}\n${t.reminderNote}`,execute:async()=>{if(!this.data){error.textContent=t.offline;return;}try{await this._hass.callWS({type:"alarmmesh/reminder",operation,source:detail.id,revision,value,confirmed:true});this.clearDraft();this.closeDialog();}catch(e){error.textContent=t[e.code] || t.error;}}});};
    const save=el("button",t.saveReminder,"button primary");save.type="submit";form.append(button(t.cancel,()=>this.closeDialog()),save);form.addEventListener("submit",event=>{event.preventDefault();if(form.querySelector('.request-confirmation')) return;if(!source?.reminder_identity || !when.value || !receiver.value){error.textContent=t.invalid_reminder;return;}request("save",{identity:source.reminder_identity,enabled:enabled.checked,date:when.value,interval:Number(interval.value),recipient:receiver.value});});
    if(serverSaved) form.append(button(t.snoozeReminder,()=>request("snooze",{date:when.value})),button(t.handleReminder,()=>request("handle",{})),button(t.removeReminder,()=>request("delete",{}),"button destructive")); this.trackDraft(form,revision,()=>({identity:source?.reminder_identity || saved?.identity,enabled:enabled.checked,date:when.value,interval:Number(interval.value),recipient:receiver.value})); parent.append(form);
  }
  copyForm(parent,detail) {
    const t=this.t, group=this.data.groups.find(g=>g.id===detail.id);if(!group) {parent.append(el("p",t.not_found));return;}
    const revision=this.data.revision, form=el("form");form.noValidate=true;parent.append(el("h2",t.copyGroup),el("p",t.copyGroupNote));
    const label=el("label",t.name), name=el("input");name.name="copy-name";name.value=`${group.name} ${t.copySuffix}`.slice(0,64);name.maxLength=64;label.append(name);form.append(label);
    const members=[], origins=[];for(const source of this.data.sources.filter(s=>group.members.includes(s.entity_id))) {const member=this.checkField(form,source.name,true,"copy-member");member.value=source.entity_id;members.push(member);if((group.origins || group.members).includes(source.entity_id)){const origin=this.checkField(form,`${t.smokeSource}: ${source.name}`,true,"copy-origin");origin.value=source.entity_id;origins.push(origin);}}
    if(group.unselected?.length) form.append(el("p",t.copyOmitted));
    const error=el("p","","form-error");error.setAttribute("role","alert");const submit=el("button",t.reviewCopy,"button primary");submit.type="submit";form.append(error,button(t.cancel,()=>this.closeDialog()),submit);
    form.addEventListener("submit",event=>{event.preventDefault();if(form.querySelector('.request-confirmation'))return;if(!this.data){error.textContent=t.offline;return;}const chosen=members.filter(c=>c.checked).map(c=>c.value), selectedOrigins=origins.filter(c=>c.checked && chosen.includes(c.value)).map(c=>c.value);if(!name.value.trim()){error.textContent=t.invalid_name;return;}const payload={type:"alarmmesh/group_copy",group_id:group.id,revision,name:name.value.trim(),members:chosen,origins:selectedOrigins,confirmed:true};this.confirmRequest(form,{name:t.copyGroup,confirmationOnly:true,note:`${payload.name}\n${t.members}: ${chosen.map(id=>this.sourceName(id)).join(', ')}\n${t.incidentSources}: ${selectedOrigins.map(id=>this.sourceName(id)).join(', ')}\n${t.copyGroupNote}`,execute:async()=>{if(!this.data){error.textContent=t.offline;return;}try{await this._hass.callWS(payload);this.closeDialog();}catch(e){error.textContent=t[e.code] || t.error;}}});});parent.append(form);
  }
  detectorCount(count) { return `${count} ${count === 1 ? this.t.detector : this.t.detectors}`; }
  formatTime(value) {
    const date = new Date(value);
    return value && Number.isFinite(date.getTime()) ? date.toLocaleString(this._hass.language) : this.t.guide_unknown;
  }
  async mutate(payload, error) {
    try {
      await this._hass.callWS({ type: "alarmmesh/group", ...payload });
      this.clearDraft();
      this.closeDialog();
    } catch (err) { error.textContent = this.t[err.code] || this.t.error; }
  }
}
if (!customElements.get("alarmmesh-panel")) customElements.define("alarmmesh-panel", AlarmMeshPanel);
