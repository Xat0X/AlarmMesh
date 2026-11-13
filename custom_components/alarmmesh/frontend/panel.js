import { TEXT } from "./translations.js?v=20261113-copy";

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
    this.connection = null;
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
        this.render();
        if (this.detail && this.detail.kind !== "edit" && this.detail.kind !== "delete") this.renderDialog();
      }, { type: "alarmmesh/subscribe" }, { resubscribe: false });
      if (generation !== this.generation || !this.isConnected) unsubscribe()?.catch?.(() => {});
      else this.unsubscribe = unsubscribe;
    } catch { if (generation === this.generation) { this.transport = "error"; this.render(); } }
  }
  go(page) { this.closeDialog(); this.page = page; this.render(); }
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
    const link = el("link"); link.rel = "stylesheet"; link.href = "/alarmmesh-assets/panel.css?v=20261113-copy";
    const shell = el("div", undefined, "shell");
    shell.classList.toggle("dark", Boolean(this._hass?.themes?.darkMode));
    const side = el("aside");
    const brand = el("div", undefined, "brand");
    const image = el("img"); image.src = "/alarmmesh-brand/icon.png"; image.alt = "";
    brand.append(image, el("strong", "AlarmMesh")); side.append(brand);
    const nav = el("nav"); nav.setAttribute("aria-label", "AlarmMesh");
    for (const [page, symbol] of [["overview", "view-dashboard-outline"], ["devices", "smoke-detector"], ["rooms", "floor-plan"], ["groups", "select-group"]]) {
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
      const name = el("span", undefined, "source-name"); name.append(el("strong", source.name), el("small", [source.area_name || this.t.noRoom, source.model].filter(Boolean).join(" · ")));
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
  openDialog(detail) { if (!this.detail) this.previousFocus = this.shadowRoot.activeElement; this.detail = detail; this.renderDialog(); }
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
      for (const [label, value] of [[t.state, source.ha_state || t.MISSING], [t.entity, source.entity_id], [t.room, source.area_name || t.noRoom], [t.device, source.device_name], [t.manufacturer, source.manufacturer], [t.model, source.model]]) {
        props.append(el("dt", label), el("dd", value || t.unavailable));
      }
      dialog.append(props, el("h3", t.membership));
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
    const actions = el("div", undefined, "actions"); const save = el("button", t.save, "button primary"); save.type = "submit";
    actions.append(button(t.cancel, () => this.closeDialog()), save); form.append(error, actions);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!name.value.trim() || name.value.trim().length > 64) { error.textContent = t.invalid_name; name.setAttribute("aria-invalid", "true"); name.focus(); return; }
      name.removeAttribute("aria-invalid");
      const members = [...form.querySelectorAll('input[name="member"]')].filter(c => c.checked).map(c => c.value);
      save.disabled = true;
      await this.mutate({ operation: group ? "update" : "create", ...(group ? { group_id: group.id } : {}), revision, name: name.value.trim(), members }, error);
      save.disabled = false;
    });
    dialog.append(form);
  }
  async mutate(payload, error) {
    try {
      await this._hass.callWS({ type: "alarmmesh/group", ...payload });
      this.closeDialog();
    } catch (err) { error.textContent = this.t[err.code] || this.t.error; }
  }
}
if (!customElements.get("alarmmesh-panel")) customElements.define("alarmmesh-panel", AlarmMeshPanel);
