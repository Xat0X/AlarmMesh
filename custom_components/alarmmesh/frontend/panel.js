import { TEXT } from "./translations.js?v=20261114-broadcast-1";

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
    this.onDisconnected = () => { this.generation++; this.unsubscribe?.()?.catch?.(() => {}); this.unsubscribe = null; this.data = null; this.transport = "offline"; this.closeDialog(); this.render(); };
    this.onReady = () => this.subscribe();
  }
  set hass(value) {
    const old = this._hass;
    this._hass = value;
    if (this.isConnected && (old?.connection !== value.connection || old?.user?.is_admin !== value.user?.is_admin)) this.bindConnection();
    if (old?.language !== value.language || old?.themes?.darkMode !== value.themes?.darkMode) this.render();
    if (!value.user?.is_admin) { this.generation++; this.data = null; this.closeDialog(); this.render(); }
  }
  set narrow(value) { this._narrow = value; }
  set panel(value) { this._panel = value; }
  get t() { return TEXT[this._hass?.language?.startsWith("nl") ? "nl" : "en"]; }
  connectedCallback() { if (this._hass) this.bindConnection(); this.render(); }
  disconnectedCallback() { this.unbindConnection(); this.closeDialog(); }
  unbindConnection() {
    this.generation++;
    this.unsubscribe?.()?.catch?.(() => {}); this.unsubscribe = null;
    this.connection?.removeEventListener("disconnected", this.onDisconnected);
    this.connection?.removeEventListener("ready", this.onReady);
    this.connection = null; this.catalog = null; this.catalogError = false;
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
        if (!data.available) this.closeDialog();
        if (!data.available || this.page !== "catalog" || !this.shadowRoot.querySelector(".catalog-filters")) this.render();
        if (this.detail && this.detail.kind !== "edit" && this.detail.kind !== "delete") this.renderDialog();
      }, { type: "alarmmesh/subscribe" }, { resubscribe: false });
      if (generation !== this.generation || !this.isConnected) unsubscribe()?.catch?.(() => {});
      else this.unsubscribe = unsubscribe;
    } catch { if (generation === this.generation) { this.transport = "error"; this.render(); } }
  }
  async go(page) {
    this.closeDialog(); this.page = page; this.render();
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
  render() {
    if (!this.shadowRoot) return;
    const t = this.t;
    const link = el("link"); link.rel = "stylesheet"; link.href = "/alarmmesh-assets/panel.css?v=20261114-broadcast-1";
    const shell = el("div", undefined, "shell");
    shell.classList.toggle("dark", Boolean(this._hass?.themes?.darkMode));
    const side = el("aside");
    const brand = el("div", undefined, "brand");
    const image = el("img"); image.src = "/alarmmesh-brand/icon.png"; image.alt = "";
    brand.append(image, el("strong", "AlarmMesh")); side.append(brand);
    const nav = el("nav"); nav.setAttribute("aria-label", "AlarmMesh");
    for (const [page, symbol] of [["overview", "view-dashboard-outline"], ["devices", "smoke-detector"], ["rooms", "floor-plan"], ["groups", "select-group"], ["catalog", "book-search-outline"]]) {
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
    header.append(menu, icon("home-outline"), el("span", this.data?.title || "AlarmMesh"), el("span", ` / ${t[this.page]}`, "muted"));
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
      if (this.page === "devices") {
        main.append(this.section(t.selected, button(t.choose, () => this.choose())));
        this.sourceList(main, data.sources);
      }
      if (this.page === "rooms") this.roomCards(main, data.rooms);
      if (this.page === "groups") {
        main.append(this.section(null, button(t.newGroup, () => this.openDialog({ kind: "edit", group: null }), "button primary")));
        if (!data.groups.length) main.append(el("p", t.noGroups, "notice"));
        const cards = el("div", undefined, "cards");
        for (const group of data.groups) {
          const card = button("", () => this.openDialog({ kind: "group", id: group.id }), "card room-card");
          card.append(icon("select-group"), el("h3", group.name), this.badge(group.result), el("p", t[group.result.availability]), el("p", `${group.members.length} ${group.members.length === 1 ? t.detector : t.devices.toLowerCase()}`));
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
    const stats = el("div", undefined, "stats");
    for (const [label, value, note] of [[t.sources, `${data.usable} / ${data.sources.length}`, t.usable], [t.rooms, data.rooms.filter(r => r.id).length, "Home Assistant"], [t.groups, data.groups.length, t.organized]]) {
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
    const allRooms = button("→", () => this.go("rooms"));
    allRooms.setAttribute("aria-label", t.rooms);
    main.append(this.section(t.rooms, allRooms)); this.roomCards(main, data.rooms);
  }
  sourceList(parent, sources) {
    const list = el("div", undefined, "source-list");
    for (const source of sources) {
      const row = button("", () => this.openDialog({ kind: "source", id: source.entity_id }), "source");
      const name = el("span", undefined, "source-name"); name.append(el("strong", source.name), el("small", [source.area_name || this.t.noRoom, source.manufacturer, source.model].filter(Boolean).join(" · ")));
      if (source.capability) name.append(el("small", `${this.t[source.capability.origin]} · ${this.capabilityLabel(source.capability)}`));
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
    this.detail = detail; this.renderDialog();
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
    dialog.setAttribute("aria-label", t.details);
    const close = button(t.close, () => this.closeDialog());
    dialog.append(close);
    if (detail.kind === "source") {
      const source = this.data.sources.find(s => s.entity_id === detail.id);
      if (!source) { this.closeDialog(); return; }
      dialog.append(el("h2", source.name), this.badge(source));
      const props = el("dl");
      for (const [label, value] of [[t.state, source.ha_state || t.MISSING], [t.room, source.area_name || t.noRoom], [t.device, source.device_name], [t.manufacturer, source.manufacturer], [t.model, source.model]]) {
        props.append(el("dt", label), el("dd", value || t.unavailable));
      }
      dialog.append(props);
      if (!source.capability) { const technical = el("details"); technical.append(el("summary", t.requirements), el("p", `${t.entity}: ${source.entity_id}`)); dialog.append(technical); }
      if (source.capability) {
        const cap = source.capability;
        dialog.append(el("h3", t.functions), el("p", `${t[cap.origin]} / ${this.capabilityLabel(cap)}`));
        this.detectorDetails(dialog, source);
        const limitations = el("details"); limitations.append(el("summary", t.requirements), el("p", t[cap.reason] || t.no_verified_profile), el("p", t.physicalNotTested, "muted"));
        limitations.append(el("p", `${t.entity}: ${source.entity_id}`));
        for (const control of cap.controls) limitations.append(el("p", `${t.proposedControl}: ${control.target}`));
        dialog.append(limitations);
      }
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
      this.sourceList(dialog, this.data.sources.filter(s => group.members.includes(s.entity_id)));
      if (detail.kind === "group") {
        if (!group.members.length) dialog.append(el("p", t.emptyGroup));
        for (const member of group.unselected) dialog.append(el("p", `${member} · ${t.stale}`, "warning-text"));
        dialog.append(el("p", t.groupNote), button(t.edit, () => this.openDialog({ kind: "edit", group })), button(t.remove, () => this.openDialog({ kind: "delete", group }), "button destructive"));
        dialog.append(el("p", `${t.linkTogether}: ${t[group.linking_status || "disabled"]}`));
      }
    } else if (detail.kind === "edit") this.groupForm(dialog, detail.group);
    else if (detail.kind === "delete") {
      dialog.append(el("h2", t.confirmDelete), el("p", detail.group.name), el("p", t.deleteNote));
      detail.revision ??= this.data.revision;
      const error = el("p", "", "form-error"); error.setAttribute("role", "alert");
      dialog.append(error, button(t.cancel, () => this.closeDialog()), button(t.remove, async () => {
        await this.mutate({ operation: "delete", group_id: detail.group.id, revision: detail.revision }, error);
      }, "button destructive"));
    }
    dialog.oncancel = () => this.closeDialog();
    if (first) { dialog.showModal(); close.focus(); }
    else if (focusIndex >= 0) ([...dialog.querySelectorAll("button,input")][focusIndex] || close).focus();
  }
  groupForm(dialog, group) {
    const t = this.t, revision = this.data.revision;
    dialog.append(el("h2", group ? t.edit : t.newGroup), el("p", t.groupNote));
    const form = el("form"); form.noValidate = true;
    const label = el("label", t.name); label.htmlFor = "group-name";
    const name = el("input"); name.id = "group-name"; name.name = "name"; name.value = group?.name || ""; name.maxLength = 64; name.required = true;
    const error = el("p", "", "form-error"); error.id = "group-error"; error.setAttribute("role", "alert"); name.setAttribute("aria-describedby", error.id);
    form.append(label, name, el("h3", t.members));
    const selected = new Set(group?.members || []);
    const choices = [...this.data.sources.map(s => ({ id: s.entity_id, name: s.name, note: s.area_name || t.noRoom })), ...(group?.unselected || []).map(id => ({ id, name: id, note: t.stale }))];
    for (const source of choices) {
      const row = el("label", undefined, "check");
      const check = el("input"); check.type = "checkbox"; check.name = "member"; check.value = source.id; check.checked = selected.has(source.id);
      const title = el("span"); title.append(el("strong", source.name), el("small", source.note)); row.append(check, title); form.append(row);
    }
    if (group?.unselected.length) form.append(el("p", t.hiddenReferences, "muted"));
    const linkingSection = el("section", undefined, "linking-section");
    linkingSection.append(el("h3", t.linkTogether), el("p", t.linkIntro));
    const toggleLabel = el("label", undefined, "check");
    const toggle = el("input"); toggle.type = "checkbox"; toggle.name = "link-enabled"; toggle.checked = Boolean(group?.linking?.enabled);
    toggleLabel.append(toggle, el("span", t.enableLink)); linkingSection.append(toggleLabel);
    const bindings = [];
    for (const source of this.data.sources) {
      const cap = source.capability;
      const row = el("div", undefined, "binding-row");
      const targetLabel = el("label", `${source.name} · ${t.smokeSource}`);
      const select = el("select"); select.id = `binding-${source.entity_id}`; select.name = "link-target"; targetLabel.htmlFor = select.id;
      const empty = el("option", t.detection_only); empty.value = ""; select.append(empty);
      const controls = cap?.controls || [];
      const oldBinding = group?.linking?.bindings.find(b => b.source === source.entity_id);
      empty.selected = !oldBinding;
      for (const control of controls) {
        const option = el("option", `${control.target} · ${t[control.profile] || t.activation_only}`); option.value = control.target; option.disabled = cap.status !== "linkable"; option.selected = oldBinding?.target === control.target; select.append(option);
      }
      if (oldBinding && !controls.some(c => c.target === oldBinding.target && c.identity === oldBinding.identity)) {
        const stale = el("option", `${oldBinding.target} · ${t.control_changed}`); stale.value = oldBinding.target; stale.selected = true; select.append(stale);
      }
      row.append(targetLabel, select, el("small", cap ? `${t[cap.origin]} / ${this.capabilityLabel(cap)}` : t.no_verified_profile));
      if (cap) { const requirements = el("details"); requirements.append(el("summary", t.requirements), el("p", t[cap.reason] || t.no_verified_profile)); row.append(requirements); }
      row.hidden = !selected.has(source.entity_id);
      for (const check of form.querySelectorAll('input[name="member"]')) if (check.value === source.entity_id) check.addEventListener("change", () => { row.hidden = !check.checked; });
      linkingSection.append(row); bindings.push({ source, select, controls, oldBinding });
    }
    form.append(linkingSection);
    const actions = el("div", undefined, "actions"); const save = el("button", t.save, "button primary"); save.type = "submit";
    actions.append(button(t.cancel, () => this.closeDialog()), save); form.append(error, actions);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!name.value.trim() || name.value.trim().length > 64) { error.textContent = t.invalid_name; name.setAttribute("aria-invalid", "true"); name.focus(); return; }
      name.removeAttribute("aria-invalid");
      const members = [...form.querySelectorAll('input[name="member"]')].filter(c => c.checked).map(c => c.value);
      const mapped = bindings.filter(b => members.includes(b.source.entity_id) && b.select.value).map(b => {
        const control = b.controls.find(c => c.target === b.select.value);
        return control ? { source: control.source, target: control.target, profile: control.profile, identity: control.identity } : b.oldBinding;
      });
      const payload = { operation: group ? "update" : "create", ...(group ? { group_id: group.id } : {}), revision, name: name.value.trim(), members };
      if (group?.linking || toggle.checked || mapped.length) payload.linking = { enabled: toggle.checked, bindings: mapped };
      if (toggle.checked) {
        if (members.length < 2 || !mapped.length || mapped.some(b => !b) || members.some(id => !this.data.sources.some(s => s.entity_id === id))) { error.textContent = t.invalid_linking; return; }
        if (mapped.some(binding => { const cap = this.data.sources.find(s => s.entity_id === binding.source)?.capability; return cap?.status !== "linkable" || !cap.controls.some(c => c.target === binding.target && c.identity === binding.identity); })) { error.textContent = t.control_changed; return; }
        const frozen = [...form.querySelectorAll("input,select")]; frozen.forEach(node => { node.disabled = true; }); save.disabled = true;
        const confirmation = el("section", undefined, "link-confirmation");
        confirmation.append(el("h3", t.confirmLink), el("p", t.commandNote));
        for (const destination of mapped) {
          const targetName = this.data.sources.find(s => s.entity_id === destination.source)?.name || destination.source;
          for (const source of this.data.sources.filter(s => members.includes(s.entity_id) && s.entity_id !== destination.source)) confirmation.append(el("p", `${source.name} → ${targetName} (${destination.target})`));
          const control = bindings.flatMap(b => b.controls).find(c => c.target === destination.target);
          confirmation.append(el("p", control?.safe_stop ? t.automation_stop_separate : t.no_safe_stop, "warning-text"));
        }
        confirmation.append(el("p", t.physicalNotTested));
        const ackLabel = el("label", undefined, "check");
        const ack = el("input"); ack.type = "checkbox"; ack.className = "confirm-ack"; ackLabel.append(ack, el("span", t.acceptLink));
        const confirm = button(t.confirmEnable, async () => {
          if (!ack.checked) { error.textContent = t.linking_confirmation_required; ack.focus(); return; }
          confirm.disabled = true;
          await this.mutate({ ...payload, confirmed: true }, error);
          confirm.disabled = false;
        }, "button primary confirm-linking");
        confirmation.append(ackLabel, error, button(t.back, () => { confirmation.remove(); form.insertBefore(error, actions); error.textContent = ""; frozen.forEach(node => { node.disabled = false; }); save.disabled = false; }), confirm);
        form.append(confirmation); ack.focus(); return;
      }
      save.disabled = true;
      await this.mutate(payload, error);
      save.disabled = false;
    });
    dialog.append(form);
  }
  detectorDetails(parent, source) {
    const t = this.t, details = source.capability.details || {};
    const table = el("dl", undefined, "diagnostics");
    const add = (label, value) => table.append(el("dt", label), el("dd", value));
    add(t.detectorType, source.capability.kind ? t[source.capability.kind === "smoke" ? "kind_smoke" : source.capability.kind] : t.genericSmoke);
    add(t.sourceAvailability, source.ha_state === "on" || source.ha_state === "off" ? t.usableValue : t.unavailable);
    add(t.controlAvailability, source.capability.controls.length ? t.usableValue : t.unavailable);
    add(t.firmware, details.firmware || t.unavailable);
    if (!(details.values || []).length) add(t.additionalInfo, t.unavailable);
    for (const value of details.values || []) {
      const cell = el("dd", value.value === null ? t.unavailable : `${t[value.value] || value.value}${value.unit ? " " + value.unit : ""}`);
      if (value.changed_at) cell.append(el("small", `${t.valueChanged}: ${new Date(value.changed_at).toLocaleString(this._hass.language)}`));
      table.append(el("dt", t[value.key] || value.key), cell);
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
    for (const [value, label] of [["zigbee2mqtt", "Zigbee2MQTT"], ["zha", "ZHA"]]) { const option = el("option", label); option.value = value; provider.append(option); }
    [...provider.options].find(option => option.value === (this.catalogProvider || "zigbee2mqtt")).selected = true;
    const capability = el("select"); capability.setAttribute("aria-label", t.functions);
    for (const [value, label] of [["all", t.allModels], ["implemented", t.externalActivation], ["stop", t.automaticStop], ["detection", t.smokeSource], ["unconfirmed", t.not_confirmed]]) { const option = el("option", label); option.value = value; capability.append(option); }
    [...capability.options].find(option => option.value === (this.catalogCapability || "all")).selected = true;
    const results = el("div", undefined, "catalog-results");
    const count = el("p"); count.setAttribute("role", "status");
    const update = () => {
      this.catalogSearch = search.value; this.catalogProvider = provider.value; this.catalogCapability = capability.value;
      results.replaceChildren(); let shown = 0;
      for (const entry of catalog.entries) {
        for (const variant of [{ vendor: entry.vendor, model: entry.model }, ...entry.aliases]) {
        const review = variant.providers?.[provider.value] || entry.providers[provider.value];
        const matches = capability.value === "all" || capability.value === "implemented" && review.activation === "implemented" || capability.value === "stop" && review.stop === "implemented" || capability.value === "detection" && review.detection !== "not_available" || capability.value === "unconfirmed" && [review.detection, review.activation].includes("unconfirmed");
        if (!matches) continue;
          if (!`${variant.vendor} ${variant.model} ${entry.model}`.toLocaleLowerCase().includes(search.value.toLocaleLowerCase().trim())) continue;
          shown++;
          const card = el("article", undefined, "card catalog-card");
          card.append(el("h3", `${variant.vendor} ${variant.model}`), el("p", `${t[provider.value]} / ${t[entry.kind === "smoke" ? "kind_smoke" : entry.kind] || entry.kind}`));
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
      count.textContent = `${shown} / ${catalog.website_rows} ${t.catalogModels}`;
    };
    search.addEventListener("input", update); provider.addEventListener("change", update); capability.addEventListener("change", update);
    filters.append(search, provider, capability); parent.append(filters, count, results); update();
  }
  async mutate(payload, error) {
    try {
      await this._hass.callWS({ type: "alarmmesh/group", ...payload });
      this.closeDialog();
    } catch (err) { error.textContent = this.t[err.code] || this.t.error; }
  }
}
if (!customElements.get("alarmmesh-panel")) customElements.define("alarmmesh-panel", AlarmMeshPanel);
