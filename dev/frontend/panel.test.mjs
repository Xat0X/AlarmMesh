import test from "node:test";
import assert from "node:assert/strict";
import { parseHTML } from "linkedom";
import { readFile } from "node:fs/promises";

const { window } = parseHTML("<!doctype html><html><body></body></html>");
for (const key of ["window", "document", "HTMLElement", "customElements", "Event", "CustomEvent"]) globalThis[key] = window[key];
// Linkedom has DOM, not a layout engine or native modal behavior. Those checks
// belong to the separate real-browser acceptance, never inferred from this shim.
HTMLElement.prototype.showModal = function () { this.setAttribute("open", ""); };
await import("../../custom_components/alarmmesh/frontend/panel.js");

const source = { entity_id: "binary_sensor.simulation_a", name: "Detector A", area_id: null, area_name: null, status: "NO_SMOKE_REPORTED", ha_state: "off", groups: [], model: null };
const normal = () => ({ available: true, title: "Simulation only", entry_id: "test-entry", revision: 0, result: { smoke: "NO_SMOKE_REPORTED", availability: "COMPLETE" }, usable: 1, sources: [{ ...source }], rooms: [{ id: null, name: null, members: [source.entity_id], result: { smoke: "NO_SMOKE_REPORTED", availability: "COMPLETE" } }], groups: [] });
const tick = () => new Promise(resolve => setImmediate(resolve));
function setup(language = "en") {
  const listeners = new Map();
  const transport = { callbacks: [], stopped: 0,
    addEventListener(type, callback) { listeners.set(type, callback); },
    removeEventListener(type, callback) { if (listeners.get(type) === callback) listeners.delete(type); },
    async subscribeMessage(callback, message) { assert.equal(message.type, "alarmmesh/subscribe"); this.callbacks.push(callback); return () => { this.stopped++; }; },
    event(type) { listeners.get(type)?.(); },
  };
  const calls = [];
  const panel = document.createElement("alarmmesh-panel");
  panel.hass = { language, user: { is_admin: true }, themes: { darkMode: false }, connection: transport, async callWS(command) { calls.push(command); return { revision: 1 }; } };
  document.body.append(panel);
  transport.callbacks.at(-1)(normal());
  return { panel, transport, calls, root: panel.shadowRoot, listeners };
}

test("four screens use pushed data, safe long labels and existing HA metadata", async () => {
  const { panel, root, transport } = setup();
  const data = normal(); data.sources[0].name = '<img src=x onerror="bad()">' + " Long".repeat(60);
  transport.callbacks.at(-1)(data);
  for (const page of ["devices", "rooms", "groups", "overview"]) {
    root.querySelector(`[data-page="${page}"]`).click();
    assert.equal(root.querySelector('[aria-current="page"]').dataset.page, page);
  }
  assert.equal(root.querySelector(".section-head button").getAttribute("aria-label"), "Rooms");
  panel.go("devices");
  assert.ok([...root.childNodes].map(n => n.textContent).join("").includes(data.sources[0].name));
  assert.equal(root.querySelectorAll(".source img").length, 0);
  assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("No area"));
  assert.ok(![...root.childNodes].map(n => n.textContent).join("").includes("Heiman"));
  panel.remove(); await tick();
});

test("detail shows actual source state and closes without writing", () => {
  const { panel, root, calls } = setup("nl");
  panel.go("devices"); root.querySelector(".source").click();
  assert.ok(root.querySelector("dialog").textContent.includes(source.entity_id));
  assert.ok(root.querySelector("dialog").textContent.includes("off"));
  assert.ok(root.querySelector("dialog").textContent.includes("Geen ruimte"));
  root.querySelector("dialog > button").click();
  assert.equal(root.querySelector("dialog"), null); assert.deepEqual(calls, []);
  panel.remove();
});

test("push preserves backend smoke priority and an unsaved group form", () => {
  const { panel, root, transport } = setup();
  panel.openDialog({ kind: "edit", group: null });
  const input = root.querySelector("#group-name"); input.value = "Unsaved";
  const dialog = root.querySelector("dialog");
  const data = normal(); data.result = { smoke: "SMOKE_REPORTED", availability: "INCOMPLETE" }; data.sources[0].status = "SMOKE_REPORTED";
  transport.callbacks.at(-1)(data);
  assert.ok(root.querySelector(".hero.alarm").textContent.includes("Smoke reported"));
  assert.ok(root.querySelector(".hero").textContent.includes("Source information incomplete"));
  assert.equal(root.querySelector("dialog"), dialog);
  assert.equal(input.value, "Unsaved");
  panel.remove();
});

test("HA entity information receives the source after releasing our modal", () => {
  const { panel, root } = setup();
  panel.go("devices"); root.querySelector(".source").click();
  let observed = false;
  panel.addEventListener("hass-more-info", event => {
    assert.equal(root.querySelector("dialog"), null);
    assert.equal(event.detail.entityId, source.entity_id);
    observed = true;
  });
  [...root.querySelectorAll("dialog button")].find(node => node.textContent === "Home Assistant").click();
  assert.equal(observed, true); panel.remove();
});

test("empty, unloaded and disconnected data never retain an old current status", async () => {
  const { panel, root, transport, listeners } = setup();
  const data = normal(); data.sources = []; data.rooms = []; data.result = { smoke: "INDETERMINATE", availability: "NOT_CONFIGURED" }; data.usable = 0;
  transport.callbacks.at(-1)(data);
  assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("Choose existing smoke detectors"));
  transport.event("disconnected"); assert.equal(panel.data, null);
  assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("Connection lost"));
  const old = transport.callbacks.at(-1); old(normal()); assert.equal(panel.data, null);
  transport.event("ready"); await tick();
  transport.callbacks.at(-1)({ available: false });
  assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("not loaded"));
  panel.remove(); assert.equal(listeners.size, 0);
});

test("group form validates, trims and sends revision with selected memberships", async () => {
  const { panel, root, calls } = setup();
  panel.openDialog({ kind: "edit", group: null });
  const form = root.querySelector("form");
  const input = form.querySelector("#group-name"); input.value = "   ";
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.equal(calls.length, 0); assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("1–64"));
  input.value = "  My group  "; form.querySelector('[name="member"]').checked = true;
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.deepEqual(calls[0], { type: "alarmmesh/group", operation: "create", revision: 0, name: "My group", members: [source.entity_id] });
  assert.equal(root.querySelector("dialog"), null); panel.remove();
});

test("stale editor conflicts remain visible without replacing saved browser inputs", async () => {
  const { panel, root } = setup();
  panel._hass.callWS = async () => { throw { code: "conflict" }; };
  panel.openDialog({ kind: "edit", group: null });
  root.querySelector("#group-name").value = "Keep my draft";
  root.querySelector("form").dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.ok(root.querySelector("dialog").textContent.includes("Another browser"));
  assert.equal(root.querySelector("#group-name").value, "Keep my draft");
  panel.remove();
});

test("delete has a separate confirmation and cancellation makes no write", () => {
  const { panel, root, calls } = setup();
  panel.openDialog({ kind: "delete", group: { id: "a".repeat(32), name: "Home" } });
  assert.ok(root.querySelector("dialog").textContent.includes("Delete this group?"));
  panel.closeDialog(); assert.deepEqual(calls, []); panel.remove();
});

test("a lost save acknowledgement does not claim the server made no change", async () => {
  const { panel, root } = setup();
  panel._hass.callWS = async () => { throw { code: "unknown_error" }; };
  panel.openDialog({ kind: "edit", group: null });
  root.querySelector("#group-name").value = "Unconfirmed save";
  root.querySelector("form").dispatchEvent(new Event("submit", { cancelable: true }));
  await tick();
  assert.ok(root.querySelector("#group-error").textContent.includes("could not be confirmed"));
  assert.ok(!root.querySelector("#group-error").textContent.includes("not replaced"));
  assert.equal(root.querySelector("#group-name").value, "Unconfirmed save");
  panel.remove();
});

test("language, theme and unauthorized session react to HA context", () => {
  const { panel, root } = setup();
  panel.hass = { ...panel._hass, language: "nl", themes: { darkMode: true } };
  assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("Alles in beeld")); assert.ok(root.querySelector(".shell.dark"));
  panel.hass = { ...panel._hass, user: { is_admin: false } };
  assert.equal(panel.data, null); assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("beheerders"));
  panel.remove();
});

test("every product label has Dutch and English text; no remote runtime imports", async () => {
  const { TEXT } = await import("../../custom_components/alarmmesh/frontend/translations.js");
  assert.deepEqual(Object.keys(TEXT.en).sort(), Object.keys(TEXT.nl).sort());
  for (const locale of Object.values(TEXT)) assert.ok(!/[A-Za-z]\?[A-Za-z]|\uFFFD/.test(Object.values(locale).join(" ")), "Translation contains a broken character");
  const js = await readFile(new URL("../../custom_components/alarmmesh/frontend/panel.js", import.meta.url), "utf8");
  assert.ok(!/innerHTML|window\.openai|Tweak|https?:\/\//.test(js));
});

function linkedData() {
  const data = normal();
  const other = { ...source, entity_id: "binary_sensor.simulation_b", name: "Detector B", capability: { origin: "zha", status: "linkable", reason: "no_safe_stop", controls: [{ source: "binary_sensor.simulation_b", target: "siren.simulation_b", profile: "smszb_zha", identity: "a".repeat(64), safe_stop: false }] } };
  data.sources.push(other);
  data.sources[0].capability = { origin: "mqtt", status: "not_confirmed", reason: "control_missing", controls: [] };
  return data;
}

test("linked sounding is off by default and requires an exact preview plus acknowledgement", async () => {
  const { panel, root, calls, transport } = setup();
  transport.callbacks.at(-1)(linkedData());
  panel.openDialog({ kind: "edit", group: null });
  const form = root.querySelector("form");
  root.querySelector("#group-name").value = "Mixed group";
  assert.equal(Boolean(form.querySelector('[name="link-enabled"]').checked), false);
  for (const input of form.querySelectorAll('[name="member"]')) input.checked = true;
  form.querySelector('[name="link-enabled"]').checked = true;
  const select = [...form.querySelectorAll("select")][1];
  select.querySelector('option[value="siren.simulation_b"]').selected = true;
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.deepEqual(calls, []);
  assert.ok(root.querySelector(".link-confirmation").textContent.includes("Detector A → Detector B"));
  assert.ok(root.querySelector(".link-confirmation").textContent.includes("safe automatic stopping is not proven"));
  root.querySelector(".confirm-linking").click(); await tick();
  assert.deepEqual(calls, []);
  root.querySelector(".confirm-ack").checked = true;
  root.querySelector(".confirm-linking").click(); await tick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].confirmed, true);
  assert.deepEqual(calls[0].linking, { enabled: true, bindings: [{ source: "binary_sensor.simulation_b", target: "siren.simulation_b", profile: "smszb_zha", identity: "a".repeat(64) }] });
  panel.remove();
});

test("missing sounder cannot enable; cancelled confirmation writes nothing", async () => {
  const { panel, root, calls, transport } = setup("nl");
  transport.callbacks.at(-1)(linkedData());
  panel.openDialog({ kind: "edit", group: null });
  root.querySelector("#group-name").value = "Niet opslaan";
  for (const input of root.querySelectorAll('[name="member"]')) input.checked = true;
  root.querySelector('[name="link-enabled"]').checked = true;
  root.querySelector("form").dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.ok(root.querySelector("#group-error").textContent.includes("minstens twee"));
  assert.deepEqual(calls, []);
  panel.closeDialog(); assert.deepEqual(calls, []); panel.remove();
});

test("incident UI distinguishes smoke, failed requests and physical uncertainty", () => {
  const { panel, root, transport } = setup();
  const data = linkedData();
  data.result = { smoke: "SMOKE_REPORTED", availability: "INCOMPLETE" };
  data.incident = { active_sources: [source.entity_id], targets: [{ source: "binary_sensor.simulation_b", target: "siren.simulation_b", status: "failed" }] };
  transport.callbacks.at(-1)(data);
  assert.ok(root.querySelector(".hero.alarm").textContent.includes("Smoke reported"));
  assert.ok(root.querySelector(".incident").textContent.includes("Activation request failed"));
  assert.ok(root.querySelector(".incident").textContent.includes("not that sound was heard"));
  transport.event("disconnected");
  assert.equal(root.querySelector(".incident"), null);
  panel.remove();
});

test("opening another dialog starts at its heading instead of the old scroll position", () => {
  const { panel, root, transport } = setup();
  transport.callbacks.at(-1)(linkedData());
  panel.openDialog({ kind: "source", id: source.entity_id });
  root.querySelector("dialog").scrollTop = 800;
  panel.openDialog({ kind: "edit", group: null });
  assert.equal(root.querySelector("dialog").scrollTop, 0);
  panel.remove();
});


test("target assignments only show current group members, retaining unsaved choices", () => {
  const { panel, root, transport, calls } = setup();
  transport.callbacks.at(-1)(linkedData());
  panel.openDialog({ kind: "edit", group: null });
  const rows = [...root.querySelectorAll(".binding-row")];
  assert.ok(rows.every(row => row.hidden));
  const members = [...root.querySelectorAll('[name="member"]')];
  members[1].checked = true; members[1].dispatchEvent(new Event("change"));
  assert.equal(rows.filter(row => !row.hidden).length, 1);
  const target = rows[1].querySelector("select"); target.querySelector('option[value="siren.simulation_b"]').selected = true;
  members[1].checked = false; members[1].dispatchEvent(new Event("change"));
  members[1].checked = true; members[1].dispatchEvent(new Event("change"));
  assert.equal(target.value, "siren.simulation_b");
  transport.callbacks.at(-1)(linkedData());
  assert.equal(root.querySelectorAll(".binding-row")[1].querySelector("select").value, "siren.simulation_b");
  assert.deepEqual(calls, []); panel.remove();
});

test("cached diagnostics distinguish changed values from contact and keep limitations folded", () => {
  const { panel, root, transport, calls } = setup("nl");
  const data = linkedData();
  data.sources[0].capability.details = { firmware: null, values: [{ key: "battery", value: 72, unit: "%", changed_at: "2026-11-14T10:00:00Z" }], recent_contact: null };
  transport.callbacks.at(-1)(data); panel.openDialog({ kind: "source", id: source.entity_id });
  assert.ok(root.querySelector(".diagnostics").textContent.includes("72 %"));
  assert.ok(root.querySelector(".diagnostics").textContent.includes("Waarde gewijzigd"));
  assert.ok(root.querySelector("dialog").textContent.includes("geen laatste radiocontact"));
  assert.equal(root.querySelector("dialog details").hasAttribute("open"), false);
  assert.deepEqual(calls, []); panel.remove();
});

test("catalog is searched locally with provider-specific assessments and safe text", async () => {
  const { panel, root, calls } = setup();
  const review = { detection: "conditional", activation: "unconfirmed", stop: "not_authorized", self_test: "not_available", information: [], requirements: [], gaps: [], sources: ["https://www.zigbee2mqtt.io/devices/example.html"] };
  panel.catalog = { definitions: 1, website_rows: 2, checked: "2026-11-14", entries: [{ model: "Original", vendor: "Example", kind: "smoke", aliases: [{ model: "<img src=x>", vendor: "Variant" }], providers: { zha: review, zigbee2mqtt: { ...review, detection: "documented", activation: "implemented" } } }] };
  await panel.go("catalog");
  assert.equal(root.querySelectorAll(".catalog-card").length, 2);
  const search = root.querySelector('[type="search"]'); search.value = "variant"; search.dispatchEvent(new Event("input"));
  assert.equal(root.querySelectorAll(".catalog-card").length, 1);
  assert.equal(root.querySelectorAll(".catalog-card img").length, 0);
  const provider = root.querySelector('select[aria-label="Provider"]'); provider.querySelector('option[value="zha"]').selected = true; provider.dispatchEvent(new Event("change"));
  assert.ok(root.querySelector(".catalog-card").textContent.includes("Not yet confirmed"));
  assert.deepEqual(calls, []); panel.remove();
});


test("Z2M white-label evidence does not advertise implemented ZHA alias control", async () => {
  const { panel, root, calls } = setup();
  const base = { detection: "conditional", activation: "implemented", stop: "not_authorized", self_test: "conditional_read_only", information: [], requirements: [], gaps: [], sources: [] };
  panel.catalogProvider = "zha"; panel.catalogCapability = "implemented";
  panel.catalog = { definitions: 1, website_rows: 2, checked: "2026-11-14", entries: [{ model: "Canonical", vendor: "Example", kind: "smoke", aliases: [{ model: "Marketing alias", vendor: "Variant", providers: { zha: { ...base, activation: "unconfirmed" } } }], providers: { zha: base, zigbee2mqtt: base } }] };
  await panel.go("catalog");
  assert.equal(root.querySelectorAll(".catalog-card").length, 1);
  assert.ok(!root.querySelector(".catalog-card").textContent.includes("Marketing alias"));
  const filter = root.querySelector('select[aria-label="Functions and information"]');
  filter.querySelector('option[value="all"]').selected = true; filter.dispatchEvent(new Event("change"));
  assert.equal(root.querySelectorAll(".catalog-card").length, 2);
  assert.ok(root.querySelectorAll(".catalog-card")[1].textContent.includes("Not yet confirmed"));
  assert.deepEqual(calls, []); panel.remove();
});


test("Bosch broadcast prerequisite is explained in both languages without writes", () => {
  for (const language of ["en", "nl"]) {
    const { panel, root, transport, calls } = setup(language);
    const data = normal();
    data.sources[0].capability = { origin: "zigbee2mqtt", status: "setting_needed", reason: "bosch_broadcast_must_be_off", controls: [], details: { values: [], firmware: null } };
    transport.callbacks.at(-1)(data);
    panel.go("devices"); root.querySelector(".source").click();
    const text = root.querySelector("dialog").textContent;
    assert.ok(text.includes("broadcast_alarms"));
    assert.ok(text.includes(language === "nl" ? "buiten je gekozen doelen" : "outside your selected targets"));
    assert.deepEqual(calls, []); panel.remove();
  }
});
