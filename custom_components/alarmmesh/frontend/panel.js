import { TEXT } from "./translations.js?v=20261117-recovery-1";
import { Drafts } from "./drafts.js?v=20261116-matter-1";

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
    this.onDisconnected = () => { this.generation++; this.unsubscribe?.()?.catch?.(() => {}); this.unsubscribe = null; this.data = null; this.diagnostics = null; this.transport = "offline"; this.offlineDraft(); this.render(); };
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
  connectedCallback() { const query=new URLSearchParams(window.location?.search || ""); if(query.has("incident")) this.page="incidents"; else if(["incidents","maintenance"].includes(query.get("view"))) this.page=query.get("view"); if (this._hass) this.bindConnection(); this.render(); }
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
        if (!data.available) this.offlineDraft();
        else if (this.shadowRoot.querySelector(".offline-draft")) { this.shadowRoot.querySelector(".offline-draft").remove(); for (const b of this.shadowRoot.querySelectorAll('dialog button[type="submit"],dialog .confirm-execute,dialog .confirm-linking')) if (!b.dataset.started && !b.dataset.confirmLocked) b.disabled = false; }
        if (data.available && this.detail?.pendingRecovery?.interrupted) this.detail.showMemberships();
        this.updateTestResult();
        if (!data.available || this.page !== "catalog" || !this.shadowRoot.querySelector(".catalog-filters")) this.render();
        if (this.detail && !["edit", "delete", "settings", "maintenance", "test", "reminder", "copy", "route", "recovery"].includes(this.detail.kind)) this.renderDialog();
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
    if(!dialog || this.detail?.kind!=="recovery")return;
    let warning=dialog.querySelector(".recovery-smoke");
    if(this.data?.result.smoke!=="SMOKE_REPORTED"){warning?.remove();return;}
    if(!warning){warning=el("p",undefined,"notice recovery-smoke");warning.setAttribute("role","alert");dialog.insertBefore(warning,dialog.children[1]);}
    warning.textContent=`${this.t.SMOKE_REPORTED}: ${this.data.sources.filter(s=>s.status==="SMOKE_REPORTED").map(s=>s.name).join(", ")}`;
  }
  render() {
    this.updateRecoverySmoke();
    if (!this.shadowRoot) return;
    this.shadowRoot.querySelector("dialog")?.classList.toggle("dark", Boolean(this._hass?.themes?.darkMode));
    const t = this.t;
    const sticky = this.shadowRoot.activeElement;
    const stickyKey = sticky?.dataset.sticky, selection = stickyKey ? [sticky.selectionStart, sticky.selectionEnd] : null;
    const link = el("link"); link.rel = "stylesheet"; link.href = "/alarmmesh-assets/panel.css?v=20261117-recovery-1";
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
    header.append(menu, icon("home-outline"), el("span", this.page === "diagnostics" ? "AlarmMesh" : this.data?.title || "AlarmMesh"), el("span", ` / ${t[this.page]}`, "muted"));
    const main = el("main");
    main.append(el("div", "ALARMMESH", "eyebrow"), el("h1", this.page === "overview" ? t.title : t[this.page]), el("p", this.page === "groups" ? t.groupIntro : t.subtitle, "subtitle"));
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
          card.append(el("p", `${t.linkTogether}: ${t[group.linking_status || "disabled"]}`));
          cards.append(card);
        }
        main.append(cards);
      }
      if (!data.sources.length) main.append(el("p", t.empty, "notice"), button(t.choose, () => this.choose(), "button primary"));
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
    const hero = el("section", undefined, `hero ${smoke === "SMOKE_REPORTED" ? "alarm" : smoke === "INDETERMINATE" ? "uncertain" : ""}`);
    hero.setAttribute("role", "status");
    hero.append(icon(smoke === "SMOKE_REPORTED" ? "fire" : "smoke-detector"), el("h2", t[smoke] || t.unknown));
    hero.append(el("p", t[data.result.availability]));
    const active = data.sources.filter(s => s.status === "SMOKE_REPORTED");
    for (const source of active) hero.append(button(`${t.alarmFrom}: ${source.name} · ${source.area_name || t.noRoom}`, () => this.openDialog({ kind: "source", id: source.entity_id }), "alarm-source"));
    main.append(hero);
    this.renderDrafts(main);
    hero.append(button(t.viewIncidents, () => this.go("incidents"), "button incident-link"));
    hero.append(button(t.activity, () => this.go("activity")));
    const stats = el("div", undefined, "stats");
    for (const [label, value, note] of [[t.sources, `${data.usable} / ${data.sources.length}`, data.usable === 1 ? t.usableSource : t.usable], [t.rooms, data.rooms.filter(r => r.id).length, "Home Assistant"], [t.groups, data.groups.length, t.organized]]) {
      const stat = el("div", undefined, "stat"); stat.append(el("span", label), el("strong", value), el("small", note)); stats.append(stat);
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
    const attention = data.sources.filter(s => !["SMOKE_REPORTED", "NO_SMOKE_REPORTED"].includes(s.status));
    if (attention.length) { main.append(this.section(t.attention)); this.sourceList(main, attention); }
    this.renderSetupGuide(main);
    main.append(button(t.maintenance, () => this.go("maintenance"), "button maintenance-link"));
    main.append(button(t.matterHelp,()=>this.go("matterHelp")));
    const allRooms = button("→", () => this.go("rooms"));
    allRooms.setAttribute("aria-label", t.rooms);
    main.append(this.section(t.rooms, allRooms)); this.roomCards(main, data.rooms);
  }
  renderSetupGuide(parent) {
    const t = this.t, data = this.data;
    const guide = el("details", undefined, "setup-guide");
    guide.open = this.setupGuideOpen ?? (!data.sources.length || !data.groups.length);
    guide.addEventListener("toggle", () => { this.setupGuideOpen = guide.open; });
    guide.append(el("summary", t.setupTitle), el("p", t.guidanceNote));
    const steps = el("ol", undefined, "setup-steps");
    const add = (title, note, label, action, key) => {
      const item = el("li"); item.dataset.step = key;
      const step = data.review?.steps.find(s => s.id === key);
      const state = step?.status || "unknown";
      const copy = el("div"); copy.append(el("h3", title), el("span", t['guide_' + state], `guide-state ${state}`), el("p", `${note}${step ? ` · ${t.savedCount}: ${step.count}` : ''}`));
      item.dataset.status = state;
      item.append(copy, button(label, action)); steps.append(item);
      if(key === "sources") item.append(button(t.matterHelp,()=>this.go("matterHelp")));
      if (key === "notifications" && data.maintenance) {
        copy.append(el("p", `${t.maintenanceNotifications}: ${t[data.maintenance.settings.enabled ? "enabled" : "disabled"]}`));
        item.append(button(t.configureMaintenance, () => this.openDialog({kind: "maintenance"})));
      }
    };
    add(t.setupSources, data.sources.length ? `${data.sources.length} · ${t.selected}` : t.setupNoSources,
      t.choose, () => this.choose(), "sources");
    add(t.setupRooms, t.setupRoomsNote, t.rooms, () => this.go("rooms"), "rooms");
    add(t.setupGroups, data.groups.length ? `${data.groups.length} · ${t.groups}` : t.setupNoGroups,
      t.groups, () => this.go("groups"), "groups");
    add(t.setupSounders, t.setupSoundersNote, t.inspectGroups, () => this.go("groups"), "sounders");
    add(t.notifications, t.setupNotificationsNote, t.configureNotifications, () => this.openDialog({kind: "settings"}), "notifications");
    add(t.incidentActions, t.actionsLocation, t.groups, () => this.go("groups"), "scripts");
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
    parent.append(el("p", t.maintenanceNote, "notice"));
    if (data.reminders) this.renderReminders(parent);
    if (data.maintenance) {
      const section = el("section", undefined, "notice maintenance-delivery");
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
      row.append(icon("smoke-detector"), name, this.badge(source), icon("chevron-right")); list.append(row);
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
    if (!this.detail) this.previousFocus = this.shadowRoot.activeElement;
    this.detail = detail;
    const draft=this.drafts.read(this._hass?.user?.id,this.data?.entry_id)[this.draftKey(detail)];
    if(draft) this.detail.pendingDraft=draft;
    this.renderDialog();
    const dialog = this.shadowRoot.querySelector("dialog");
    if (dialog) { dialog.querySelector("button")?.focus(); dialog.scrollTop = 0; }
  }
  closeDialog() {
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
      const props = el("dl");
      for (const [label, value] of [[t.state, source.ha_state || t.MISSING], [t.room, source.area_name || t.noRoom], [t.device, source.device_name], [t.manufacturer, source.manufacturer], [t.model, source.model]]) {
        props.append(el("dt", label), el("dd", value || t.unavailable));
      }
      dialog.append(props,button(t.alarmRoute,()=>this.openDialog({kind:"route",id:source.entity_id})),button(t.recoverSource,()=>this.openDialog({kind:"recovery",id:source.entity_id})));
      if (!source.capability) { const technical = el("details"); technical.append(el("summary", t.requirements), el("p", `${t.entity}: ${source.entity_id}`)); dialog.append(technical); }
      if (source.capability) {
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
      }
      if (source.selftest) {
        dialog.append(el("h3", t.selfTests), el("p", t[source.selftest.reason]));
        if (source.selftest.record) dialog.append(el("p", `${t.lastTest}: ${t['test_' + source.selftest.record.status]} · ${new Date(source.selftest.record.started).toLocaleString(this._hass.language)}`));
        if (source.selftest.available) {
          if (!source.selftest.control.has_explicit_result) dialog.append(el("p", t.selfTestNoResult));
          dialog.append(button(t.startSelfTest, () => this.openDialog({ kind: "test", actionKind: "selftest", target: source.entity_id, identity: source.selftest.control.identity, name: source.name }), "button destructive"));
        }
      }
      dialog.append(el("h3", t.membership));
      if (this.data.reminders) { const reminder = this.data.reminders.items.find(r=>r.source === source.entity_id); dialog.append(el("h3", t.reminders), el("p", reminder ? `${reminder.date} · ${t['reminder_' + reminder.status] || t.guide_unknown}` : t.reminderDisabled), button(t.configureReminder, ()=>this.openDialog({kind:"reminder", id:source.entity_id}))); }
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
      if (detail.kind === "group") this.renderGroupChecks(dialog, group);
      this.sourceList(dialog, this.data.sources.filter(s => group.members.includes(s.entity_id)));
      if (detail.kind === "group") {
        if (!group.members.length) dialog.append(el("p", t.emptyGroup));
        for (const member of group.unselected) dialog.append(el("p", `${member} · ${t.stale}`, "warning-text"));
        dialog.append(el("p", t.groupNote), button(t.copyGroup, ()=>this.openDialog({kind:"copy", id:group.id})), button(t.actionExample, () => this.openDialog({kind: "preview", id: group.id})), button(t.edit, () => this.openDialog({ kind: "edit", group })), button(t.remove, () => this.openDialog({ kind: "delete", group }), "button destructive"));
      }
    } else if (detail.kind === "edit") this.groupForm(dialog, detail.group);
    else if (detail.kind === "settings") this.notificationForm(dialog);
    else if (detail.kind === "maintenance") this.maintenanceForm(dialog);
    else if (detail.kind === "route") this.routeForm(dialog,detail);
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
    dialog.append(el("h2", group ? t.edit : t.newGroup), el("p", t.groupNote));
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
    for (const source of bindingSources) {
      const cap = source.capability;
      const row = el("div", undefined, "binding-row");
      const targetLabel = el("label", `${source.name} · ${source.area_name || t.noRoom}`);
      const select = el("select"); select.id = `binding-${source.entity_id}`; select.name = "link-target"; targetLabel.htmlFor = select.id;
      const empty = el("option", t.detection_only); empty.value = ""; select.append(empty);
      const controls = cap?.controls || [];
      const oldBinding = group?.linking?.bindings.find(b => b.source === source.entity_id);
      empty.selected = !oldBinding;
      const currentBinding = controls.find(c => c.target === oldBinding?.target && c.identity === oldBinding?.identity);
      for (const control of controls) {
        const option = el("option", `${source.name} · ${t[control.profile] || t.activation_only}`); option.value = control.target; option.disabled = cap.status !== "linkable"; option.selected = currentBinding?.target === control.target; select.append(option);
      }
      if (oldBinding && !controls.some(c => c.target === oldBinding.target && c.identity === oldBinding.identity)) {
        const stale = el("option", t.storedControlChanged); stale.value = `stored:${oldBinding.target}`; stale.selected = true; select.append(stale);
      }
      row.append(targetLabel, select, el("small", cap ? `${this.providerLabel(cap)} / ${this.capabilityLabel(cap)}` : t.no_verified_profile));
      if (cap) { row.append(el("small", t[cap.reason] || t.no_verified_profile)); const requirements = el("details"); requirements.append(el("summary", t.technicalDetails), el("p", `${source.model || t.unknown} · ${source.entity_id}`)); for (const control of controls) requirements.append(el("p", control.target)); row.append(requirements); }
      else row.append(el("small", t.storedSourceMissing, "warning-text"));
      row.hidden = !selected.has(source.entity_id);
      for (const check of form.querySelectorAll('input[name="member"]')) if (check.value === source.entity_id) check.addEventListener("change", () => { row.hidden = !check.checked; });
      linkingSection.append(row); bindings.push({ source, select, controls, oldBinding });
    }
    const originSection = el("section", undefined, "linking-section");
    originSection.append(el("h3", t.incidentSources), el("p", t.incidentSourceNote));
    const originRows = [];
    for (const source of choices) {
      const row = el("label", undefined, "check");
      const check = el("input"); check.type = "checkbox"; check.name = "origin"; check.value = source.id; check.checked = !group?.origins || group.origins.includes(source.id);
      row.append(check, el("span", source.name)); row.hidden = !selected.has(source.id); originSection.append(row); originRows.push(check);
      for (const member of form.querySelectorAll('[name="member"]')) if (member.value === source.id) member.addEventListener("change", () => { row.hidden = !member.checked; });
    }
    form.append(originSection, linkingSection);
    const updateCounts = ()=> { memberCount.textContent=`${t.members}: ${[...form.querySelectorAll('[name="member"]')].filter(c=>c.checked).length} · ${t.incidentSources}: ${originRows.filter(c=>c.checked && [...form.querySelectorAll('[name="member"]')].some(m=>m.value===c.value && m.checked)).length}`; };
    form.addEventListener("change", updateCounts); updateCounts();
    memberSearch.addEventListener("input", ()=>{ for(const row of form.querySelectorAll('[data-member-search]')) row.hidden=!row.dataset.memberSearch.includes(memberSearch.value.toLocaleLowerCase()); });
    const actionFields = this.actionFields(form, group?.actions);
    const actions = el("div", undefined, "actions"); const save = el("button", t.save, "button primary"); save.type = "submit";
    actions.append(button(t.cancel, () => this.closeDialog()), save); form.append(error, actions);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (form.querySelector(".request-confirmation,.link-confirmation")) { error.textContent = t.finishConfirmation; return; }
      if (!name.value.trim() || name.value.trim().length > 64) { error.textContent = t.invalid_name; name.setAttribute("aria-invalid", "true"); name.focus(); return; }
      name.removeAttribute("aria-invalid");
      const members = [...form.querySelectorAll('input[name="member"]')].filter(c => c.checked).map(c => c.value);
      const mapped = bindings.filter(b => members.includes(b.source.entity_id) && b.select.value).map(b => {
        if (b.select.value.startsWith("stored:")) return b.oldBinding;
        const control = b.controls.find(c => c.target === b.select.value);
        return control ? { source: control.source, target: control.target, profile: control.profile, identity: control.identity } : b.oldBinding;
      });
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
        confirmation.append(el("h3", toggle.checked ? t.confirmLink : t.confirmAutomation), el("p", t.commandNote));
        confirmation.append(el("p", `${t.incidentSources}: ${origins.map(id => { const s = this.data.sources.find(s => s.entity_id === id); return s ? `${s.name} (${s.area_name || t.noRoom})` : id; }).join(", ")}`));
        for (const destination of toggle.checked ? mapped : []) {
          const targetName = this.data.sources.find(s => s.entity_id === destination.source)?.name || destination.source;
          for (const source of this.data.sources.filter(s => origins.includes(s.entity_id) && s.entity_id !== destination.source)) confirmation.append(el("p", `${source.name} → ${targetName} (${destination.target})`));
          const control = bindings.flatMap(b => b.controls).find(c => c.target === destination.target);
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
          if (!ack.checked) { error.textContent = t.linking_confirmation_required; ack.focus(); return; }
          if (!this.data) { error.textContent = t.offline; return; }
          confirm.disabled = true;
          await this.mutate({ ...payload, confirmed: true }, error);
          confirm.disabled = false;
        }, "button primary confirm-linking");
        confirmation.append(ackLabel, error, button(t.back, () => { confirmation.remove(); form.insertBefore(error, actions); error.textContent = ""; restore(); }), confirm);
        form.append(confirmation); ack.focus(); return;
      }
      save.disabled = true;
      await this.mutate(payload, error);
      save.disabled = false;
    });
    this.trackDraft(form,revision,()=>({name:name.value,members:[...form.querySelectorAll('[name="member"]')].filter(c=>c.checked).map(c=>c.value),origins:originRows.filter(c=>c.checked && [...form.querySelectorAll('[name="member"]')].some(m=>m.value===c.value && m.checked)).map(c=>c.value),linking:{enabled:toggle.checked,bindings:bindings.filter(b=>[...form.querySelectorAll('[name="member"]')].some(m=>m.checked && m.value===b.source.entity_id) && b.select.value).map(b=>{const c=b.controls.find(c=>c.target===b.select.value);return c ? {source:c.source,target:c.target,profile:c.profile,identity:c.identity} : b.oldBinding;}).filter(Boolean)},actions:actionFields(),unselected:group?.unselected || []}));
    dialog.append(form);
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
    if (this.detail?.pendingRecovery) this.detail.pendingRecovery.interrupted = true;
    if (!["edit", "settings", "maintenance", "reminder", "copy", "recovery"].includes(this.detail?.kind)) { this.closeDialog(); return; }
    const dialog = this.shadowRoot.querySelector("dialog");
    if (!dialog) return;
    if (!dialog.querySelector(".offline-draft")) dialog.prepend(el("p", this.t.offlineDraft, "notice offline-draft"));
    for (const b of dialog.querySelectorAll('button[type="submit"],.confirm-execute,.confirm-linking')) b.disabled = true;
  }
  renderSettings(parent) {
    const t = this.t, automation = this.data.automation;
    parent.append(button(t.matterHelp,()=>this.go("matterHelp")),button(t.catalog, () => this.go("catalog")), button(t.viewIncidents, () => this.go("incidents")), button(t.maintenance, () => this.go("maintenance")), button(t.diagnostics, () => this.go("diagnostics")));
    this.renderSetupGuide(parent);
    if (!automation) return;
    const section = el("section", undefined, "notice");
    section.append(el("h2", t.notifications), el("p", `${t.notifications}: ${t[automation.settings.enabled ? "enabled" : "disabled"]}`), el("p", t.notificationNote));
    for (const recipient of automation.settings.recipients) section.append(el("p", `${recipient.service.replace(/^mobile_app_/, "")}: ${t[recipient.enabled ? "enabled" : "disabled"]}${automation.missing_recipients.includes(recipient.service) ? ' · ' + t.recipient_unavailable : ''}`));
    section.append(button(t.configureNotifications, () => this.openDialog({ kind: "settings" }), "button primary"));
    if (automation.error) section.append(el("p", t[automation.error] || t.error, "warning-text"));
    parent.append(section, el("p", t.actionsLocation, "notice"));
    if (this.data.maintenance) parent.append(button(t.configureMaintenance, () => this.openDialog({kind: "maintenance"})));
  }
  notificationForm(dialog) {
    const t = this.t, a = this.data.automation;
    if (!a) return;
    const cfg = this.detail.restoredDraft?.value || a.settings, revision = this.detail.restoredDraft?.revision ?? a.settings.revision, form = el("form");
    dialog.append(el("h2", t.notifications), el("p", t.notificationNote));
    const toggle = this.checkField(form, t.enableNotifications, cfg.enabled, "notifications-enabled");
    const recovery = this.checkField(form, t.recoveryNotification, cfg.recovery, "notifications-recovery");
    const stored = new Map(cfg.recipients.map(r => [r.service, r]));
    const choices = [...a.recipients, ...cfg.recipients.filter(r => !a.recipients.some(n => n.service === r.service)).map(r => ({ ...r, name: r.service, missing: true }))];
    const recipients = [], removed = new Set();
    if (!choices.length) form.append(el("p", t.noRecipients, "notice"));
    for (const recipient of choices) {
      const row = el("section", undefined, "recipient-row");
      const input = this.checkField(row, `${recipient.name}${recipient.missing ? ' · ' + t.recipient_unavailable : ''}`, stored.get(recipient.service)?.enabled || false, "recipient");
      input.value = recipient.service; recipients.push(input);
      if (!recipient.missing) row.append(button(t.testNotification, () => this.confirmRequest(form, { actionKind: "notification", target: recipient.service, name: recipient.name }), "button"));
      if (stored.has(recipient.service)) row.append(button(t.forgetRecipient, () => { removed.add(recipient.service); row.remove(); }, "button destructive"));
      form.append(row);
    }
    const preview = el("details"); preview.append(el("summary", t.messagePreview), el("strong", a.preview.title), el("p", a.preview.message, "message-preview")); form.append(preview);
    const error = el("p", "", "form-error"); error.setAttribute("role", "alert");
    const save = el("button", t.saveSettings, "button primary"); save.type = "submit";
    form.append(error, save, button(t.cancel, () => this.closeDialog()));
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (form.querySelector(".request-confirmation")) { error.textContent = t.finishConfirmation; return; }
      if (!this.data) { error.textContent = t.offline; return; }
      const value = { enabled: toggle.checked, recovery: recovery.checked, recipients: recipients.filter(r => !removed.has(r.value) && (r.checked || stored.has(r.value))).map(r => ({ service: r.value, enabled: r.checked })) };
      if (value.enabled && !value.recipients.some(r => r.enabled)) { error.textContent = t.invalid_notifications; return; }
      const send = async confirmed => {
        save.disabled = true;
        try { await this._hass.callWS({ type: "alarmmesh/settings", revision, notifications: value, confirmed }); this.clearDraft(); this.closeDialog(); }
        catch (e) { error.textContent = t[e.code] || t.error; save.disabled = Boolean(save.dataset.confirmLocked); }
      };
      if (!value.enabled) { await send(false); return; }
      this.confirmRequest(form, { name: t.confirmAutomation, confirmationOnly: true, note: `${t.notificationNote}\n${value.recipients.filter(r => r.enabled).map(r => r.service).join(', ')}`, execute: () => send(true) });
    });
    this.trackDraft(form,revision,()=>({enabled:toggle.checked,recovery:recovery.checked,recipients:recipients.filter(r=>!removed.has(r.value) && (r.checked || stored.has(r.value))).map(r=>({service:r.value,enabled:r.checked}))}));
    dialog.append(form);
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
      if (stored.has(recipient.service)) row.append(button(t.forgetRecipient, () => { removed.add(recipient.service); row.remove(); }, "button destructive"));
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

  routeForm(parent,detail) {
    const t=this.t, source=this.data.sources.find(s=>s.entity_id===detail.id);
    parent.append(el("h2",t.alarmRoute),el("p",source ? `${source.name} · ${source.area_name || t.noRoom}` : detail.id),el("p",t.exampleNoOutput,"notice"));
    const output=el("div");let serial=0;
    const load=async()=>{const n=++serial;output.replaceChildren(el("p",t.loading));try{const r=await this._hass.callWS({type:"alarmmesh/route",source:detail.id});if(n!==serial || !output.isConnected || !this.data)return;if(r.revision!==this.data.revision || !r.readonly){output.replaceChildren(el("p",t.previewStale));return;}
      output.replaceChildren(el("h3",t.linkTogether));if(!r.targets.length)output.append(el("p",t.checkNoTargets));
      for(const row of r.targets){output.append(el("h3",this.sourceName(row.source)),el("p",t[row.eligible ? "routeOnce":"routeBlocked"]));for(const via of row.via)output.append(el("p",`${this.data.groups.find(g=>g.id===via.group)?.name || t.groups}: ${t[via.reason] || t.guide_unknown}`));}
      output.append(el("h3",t.notifications));for(const row of r.phones)output.append(el("p",`${row.target}: ${t[row.reason] || t.guide_unknown}`));if(!r.phones.length)output.append(el("p",t.noRecipients));
      for(const g of r.groups){output.append(el("h3",this.data.groups.find(x=>x.id===g.group)?.name || t.groups));for(const row of g.scripts)output.append(el("p",`${t['phase_'+row.phase]} ${row.order} · ${row.name}: ${t[row.reason] || t.guide_unknown}`));}
      output.append(el("p",t.previewRecovery),el("p",t.routeScripts),el("p",t.physicalNotTested));
    }catch(e){if(output.isConnected)output.replaceChildren(el("p",t[e.code] || t.error));}};
    parent.append(button(t.refreshData,load),output);load();
  }
  recoveryForm(parent,detail) {
    const t=this.t;parent.append(el("h2",t.recoverSource),el("p",this.sourceName(detail.id)),el("p",t.recoverySteps,"notice"));
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
      const form=el("form"),select=el("select");select.setAttribute("aria-label",t.recoveryCandidate);for(const c of plan.candidates){const o=el("option",`${c.name} · ${c.area_name || t.noRoom}`);o.value=c.entity_id;select.append(o);}form.append(el("label",t.recoveryCandidate),select);const checks=[];
      for(const id of plan.groups){const c=this.checkField(form,this.data.groups.find(g=>g.id===id)?.name || id,false,"recovery-group");c.value=id;checks.push(c);}
      const error=el("p", "","form-error");form.append(el("p",t.recoveryAuthority),error);const save=el("button",t.recoveryReview,"button primary");save.type="submit";save.disabled=!plan.candidates.length || !plan.groups.length;form.append(save);
      form.addEventListener("submit",event=>{event.preventDefault();if(form.querySelector('.request-confirmation'))return;const target=select.value,groups=checks.filter(c=>c.checked).map(c=>c.value);if(!groups.length){error.textContent=t.invalid_members;return;}this.confirmRequest(form,{name:t.recoverSource,confirmationOnly:true,note:`${this.sourceName(detail.id)} → ${this.sourceName(target)}\n${groups.map(id=>this.data.groups.find(g=>g.id===id)?.name || id).join(', ')}\n${t.recoveryAuthority}`,execute:async()=>{
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
      for (const [node, disabled] of controls) { delete node.dataset.confirmLocked; node.disabled = disabled; }
      if (!this.data) this.offlineDraft();
    };
  }
  confirmRequest(parent, detail) {
    const t = this.t;
    const previous = parent.querySelector(".request-confirmation"); previous?.restore?.(); previous?.remove();
    const restore = this.lockControls(parent);
    const box = el("section", undefined, "notice request-confirmation");
    box.restore = restore;
    box.append(el("h3", detail.name || t.explicitTest), el("p", detail.note || (detail.actionKind === "selftest" ? t.selfTestWarning : detail.actionKind === "script" ? t.scriptConsequences : t.notifyTestWarning)));
    const ack = this.checkField(box, t.confirmExactTarget, false, "confirm-request");
    const error = el("p", "", "form-error"); error.setAttribute("role", "alert");
    const status = el("p", "", "request-status"); status.setAttribute("role", "status");
    const execute = button(t.confirmRequest, async () => {
      if (!ack.checked) { error.textContent = t.test_confirmation_required; ack.focus(); return; }
      if (!this.data) { error.textContent = t.offline; return; }
      error.textContent = "";
      execute.disabled = true;
      execute.dataset.started = "true";
      if (detail.execute) { await detail.execute(); return; }
      try {
        if (typeof globalThis.crypto?.getRandomValues !== "function") throw Object.assign(new Error("Secure random values unavailable"), { code: "request_random_unavailable" });
        // getRandomValues also works on local HTTP; randomUUID requires a secure context.
        const request = Array.from(globalThis.crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
        if (detail.actionKind === "selftest") box.dataset.selftestRequest = request;
        const result = await this._hass.callWS({ type: "alarmmesh/test", kind: detail.actionKind, target: detail.target, identity: detail.identity || "", confirmed: true, request_id: request });
        status.textContent = t[(detail.actionKind === "selftest" ? "test_" : "delivery_") + result.status] || t.error;
        this.updateTestResult();
      } catch (e) { error.textContent = t[e.code] || t.error; }
    }, "button destructive confirm-execute");
    box.append(status, error, button(t.cancel, () => { box.remove(); restore(); if (parent.tagName === "DIALOG" && this.detail?.kind === "test") this.closeDialog(); }), execute); parent.append(box); ack.focus();
  }
  updateTestResult() {
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
    parent.append(button(this.t.activity,()=>this.go("activity")));
    const t = this.t, data = this.data;
    parent.append(el("p", t.incidentNote, "notice"));
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
      card.append(el("h2", group?.name || t.notifications));
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
    for (const row of data.automation?.manual_results || []) parent.append(el("p", `${t.explicitTest} · ${row.target}: ${t['delivery_' + row.status]}`));
    if (data.selftest) parent.append(el("section", undefined, "notice selftest-result"));
    const self = parent.querySelector(".selftest-result");
    if (self) self.append(el("h2", t.selfTests), el("p", `${data.sources.find(s => s.entity_id === data.selftest.source)?.name || data.selftest.source}: ${t['test_' + data.selftest.status]}`), el("p", t.deviceResultNote));
  }
  sourceName(id) {
    const source = this.data.sources.find(s => s.entity_id === id);
    return source ? `${source.name} · ${source.area_name || this.t.noRoom}` : id;
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
    bar.append(button(t.clearFilters,()=>{for(const key of Object.keys(f)) f[key]=""; this.render();})); parent.append(bar,results); draw();
  }
  renderActivity(parent) {
    const t=this.t, history=this.data.activity, f=this.activityFilters;
    parent.append(el("p",t.activityLimit,"notice"));
    if(!history) {parent.append(el("p",t.guide_unknown));return;}
    if(history.incomplete) parent.append(el("p",t.activityIncomplete,"notice warning-text"));
    if(!history.events.length) {parent.append(el("p",t.activityEmpty,"notice"));return;}
    const bar=el("div",undefined,"filter-bar activity-filters"), list=el("div",undefined,"activity-list");
    const draw=()=>{list.replaceChildren();const rows=history.events.filter(r=>(!f.source || r.source===f.source) && (!f.group || r.groups.includes(f.group)) && (!f.kind || r.kind===f.kind) && (!f.result || r.result===f.result) && (!f.category || r.category===f.category)); if(!rows.length) list.append(el("p",t.noFilterResults)); for(const row of rows) { const item=button("",()=>this.openDialog({kind:"activity",event:row}),"button activity-row"); item.append(el("strong",`${t['activity_'+row.kind] || row.kind} · ${this.activityResult(row)}`),el("span",row.source ? this.sourceName(row.source) : row.groups.map(id=>this.data.groups.find(g=>g.id===id)?.name || id).join(", ")),el("small",`${t.observedAt}: ${this.formatTime(row.observed_at)}`)); list.append(item); }};
    const unique=key=>[...new Set(history.events.flatMap(r=>key==="group" ? r.groups : r[key]).filter(Boolean))];
    const field=(label,key,choices)=>this.filterField(bar,label,`activity-${key}`,f[key],choices,value=>{f[key]=value;draw();});
    field(t.detector,"source",unique("source").map(id=>[id,this.sourceName(id)])); field(t.groups,"group",unique("group").map(id=>[id,this.data.groups.find(g=>g.id===id)?.name || id])); field(t.activityKind,"kind",unique("kind").map(id=>[id,t['activity_'+id] || id])); field(t.activityResultLabel,"result",unique("result").map(id=>[id,this.activityResult({kind:"",result:id})])); field(t.activityCategory,"category",unique("category").map(id=>[id,t['category_'+id]]));
    bar.append(button(t.clearFilters,()=>{for(const key of Object.keys(f)) f[key]="";this.render();})); parent.append(bar,list); draw();
  }
  activityResult(row) { const t=this.t; return t['activity_result_'+row.result] || (row.kind==="selftest" ? t['test_'+row.result] : t['delivery_'+row.result]) || t['test_'+row.result] || t[row.result] || t.guide_unknown; }
  activityDetail(parent,row) {
    const t=this.t; parent.append(el("h2",t['activity_'+row.kind] || t.activity),el("p",this.activityResult(row)));
    const props=el("dl"); for(const [label,value] of [[t.observedAt,this.formatTime(row.observed_at)],[t.detector,row.source ? this.sourceName(row.source) : t.guide_unknown],[t.groups,row.groups.map(id=>this.data.groups.find(g=>g.id===id)?.name || id).join(", ") || t.noGroups],[t.target,row.target || t.guide_unknown],[t.requestContext,row.correlation || t.guide_unknown]]) props.append(el("dt",label),el("dd",value)); parent.append(props,el("p",t.activityLimit));
    if(this.data.sources.some(s=>s.entity_id===row.source)) parent.append(button(t.inspectDetector,()=>this.openDialog({kind:"source",id:row.source})));
    for(const group of this.data.groups.filter(g=>row.groups.includes(g.id))) parent.append(button(group.name,()=>this.openDialog({kind:"group",id:group.id})));
    if(row.category==="alarm") parent.append(button(t.viewIncidents,()=>this.go("incidents")));
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
