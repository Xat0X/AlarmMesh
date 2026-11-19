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
  assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("Choose a smoke detector already available in Home Assistant"));
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
  assert.ok([...root.childNodes].map(n => n.textContent).join("").includes("Overzicht")); assert.ok(root.querySelector(".shell.dark"));
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
  const options = form.querySelectorAll('input[name="link-target"]');
  assert.equal(options[0].disabled, true);
  assert.ok(options[0].closest(".binding-row").querySelector(".binding-help").textContent.includes("missing or disabled"));
  assert.equal(options[1].type, "checkbox");
  assert.equal(options[1].checked, false);
  options[1].checked = true;
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

test("a changed device at the same target needs explicit replacement", async () => {
  const { panel, root, transport, calls } = setup();
  const data = linkedData(), control = data.sources[1].capability.controls[0];
  const old = { source: control.source, target: control.target, profile: control.profile, identity: "b".repeat(64) };
  const group = { id: "g", name: "Floor", members: data.sources.map(s => s.entity_id), unselected: [], linking: { enabled: false, bindings: [old] } };
  data.groups = [group]; transport.callbacks.at(-1)(data); panel.openDialog({ kind: "edit", group });
  const form = root.querySelector("form"), field = form.querySelectorAll('input[name="link-target"]')[1];
  assert.ok(!field.checked && !field.disabled);
  assert.ok(form.querySelector(".stale-binding button"));
  form.querySelector('[name="link-enabled"]').checked = true;
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.equal(root.querySelector(".link-confirmation"), null);
  assert.deepEqual(calls, []);
  field.checked = true; field.dispatchEvent(new Event("change"));
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  form.querySelector(".confirm-ack").checked = true; form.querySelector(".confirm-linking").click(); await tick();
  assert.equal(calls[0].linking.bindings[0].identity, control.identity);
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
  const target = rows[1].querySelector('input[name="link-target"]'); target.checked = true;
  members[1].checked = false; members[1].dispatchEvent(new Event("change"));
  members[1].checked = true; members[1].dispatchEvent(new Event("change"));
  assert.equal(target.checked, true);
  transport.callbacks.at(-1)(linkedData());
  assert.equal(root.querySelectorAll(".binding-row")[1].querySelector('input[name="link-target"]').checked, true);
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
  const provider = root.querySelector('select[aria-label="Connected through"]'); provider.querySelector('option[value="zha"]').selected = true; provider.dispatchEvent(new Event("change"));
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


function guidedGroupData() {
  const data = linkedData();
  const control = data.sources[1].capability.controls[0];
  data.groups = [{ id: "guide-group", name: "Upstairs", members: data.sources.map(s => s.entity_id), unselected: [], result: data.result,
    linking_status: "disabled", linking: { enabled: false, bindings: [{ source: control.source, target: control.target, profile: control.profile, identity: control.identity }] } }];
  return data;
}

test("setup guide handles empty sources and only navigates to existing configuration", () => {
  const { panel, root, transport, calls } = setup();
  const data = normal(); data.sources = []; data.groups = []; data.rooms = []; data.usable = 0;
  transport.callbacks.at(-1)(data);
  assert.equal(root.querySelectorAll(".welcome .primary").length, 1);
  assert.equal(root.querySelector(".setup-guide"), null);
  panel.go("settings");
  assert.equal(root.querySelector(".setup-guide").open, false);
  assert.equal(root.querySelectorAll(".setup-steps li").length, 5);
  assert.ok(root.querySelector('[data-step="sources"]').textContent.includes("existing Home Assistant"));
  root.querySelector('[data-step="groups"] button').click();
  assert.equal(panel.page, "groups"); assert.deepEqual(calls, []); panel.remove();
});

test("group check explains off and activation-only without offering a sounder action", () => {
  const { panel, root, transport, calls } = setup("nl");
  transport.callbacks.at(-1)(guidedGroupData());
  panel.openDialog({ kind: "group", id: "guide-group" });
  const check = root.querySelector(".group-checks");
  assert.ok(check.textContent.includes("Configuratiecontrole"));
  assert.ok(check.querySelector('[data-check="disabled"]').textContent.includes("geen apparaat dat al klinkt"));
  assert.ok(check.querySelector('[data-check="activation-only"]').textContent.includes("geen automatische stop"));
  assert.ok(check.querySelector('[data-check="current"]').textContent.includes("Dit bevestigt niet"));
  assert.equal(check.querySelectorAll("input,select,.confirm-linking").length, 0);
  assert.deepEqual(calls, []); panel.remove();
});

test("group checks explain stale binding and live prerequisite recovery without a write", () => {
  const { panel, root, transport, calls } = setup();
  const data = guidedGroupData();
  data.groups[0].linking.enabled = true; data.groups[0].linking_status = "review_needed";
  data.sources[1].capability.status = "setting_needed";
  data.sources[1].capability.reason = "bosch_broadcast_must_be_off";
  transport.callbacks.at(-1)(data); panel.openDialog({ kind: "group", id: "guide-group" });
  assert.ok(root.querySelector('[data-check="binding"]').textContent.includes("broadcast_alarms"));
  assert.equal(root.querySelector('[data-check="current"]'), null);
  const recovered = guidedGroupData(); recovered.groups[0].linking.enabled = true; recovered.groups[0].linking_status = "enabled";
  transport.callbacks.at(-1)(recovered);
  assert.equal(root.querySelector('[data-check="binding"]'), null);
  assert.ok(root.querySelector('[data-check="current"]'));
  assert.deepEqual(calls, []); panel.remove();
});

test("changed mapping identity is never described as current", () => {
  const { panel, root, transport, calls } = setup(); const data = guidedGroupData();
  data.groups[0].linking_status = "review_needed";
  data.groups[0].linking.bindings[0].identity = "b".repeat(64);
  transport.callbacks.at(-1)(data); panel.openDialog({ kind: "group", id: "guide-group" });
  assert.ok(root.querySelector('[data-check="binding"]').textContent.includes("detector's control changed"));
  assert.equal(root.querySelector('[data-check="current"]'), null);
  root.querySelector('[data-check="binding"] button').click();
  assert.ok(root.querySelector("#group-name")); assert.deepEqual(calls, []); panel.remove();
});

test("organizer-only groups and missing selections get actionable explanations", () => {
  const { panel, root, transport, calls } = setup("nl"); const data = guidedGroupData();
  data.groups[0].linking.bindings = []; data.groups[0].members = [source.entity_id, "binary_sensor.removed"];
  data.groups[0].unselected = ["binary_sensor.removed"];
  data.sources[0].status = "UNREACHABLE";
  transport.callbacks.at(-1)(data); panel.openDialog({ kind: "group", id: "guide-group" });
  assert.ok(root.querySelector('[data-check="targets"]').textContent.includes("geen melders ingesteld"));
  assert.ok(root.querySelector('[data-check="unselected"]'));
  assert.ok(root.querySelector('[data-check="source"]'));
  root.querySelector('[data-check="source"] button').click();
  assert.ok(root.querySelector("dialog").textContent.includes("Detector A"));
  assert.deepEqual(calls, []); panel.remove();
});

test("group check keeps active smoke and request failure distinct and closes on disconnect", () => {
  const { panel, root, transport, calls } = setup(); const data = guidedGroupData();
  data.sources[0].status = "SMOKE_REPORTED";
  data.incident = { active_sources: [source.entity_id], targets: [{ source: data.sources[1].entity_id, target: data.groups[0].linking.bindings[0].target, status: "failed" }] };
  transport.callbacks.at(-1)(data); panel.openDialog({ kind: "group", id: "guide-group" });
  assert.ok(root.querySelector('[data-check="smoke"]').textContent.includes("currently reported"));
  assert.ok(root.querySelector('[data-check="execution"]').textContent.includes("does not automatically retry"));
  assert.deepEqual(calls, []); transport.event("disconnected");
  assert.equal(root.querySelector(".group-checks"), null); assert.equal(root.querySelector(".setup-guide"), null); panel.remove();
});

function featureData() {
  const data = linkedData();
  data.automation = { confirmations: {mobile_app_simulated_phone: "a".repeat(64)}, settings: { revision: 0, enabled: false, recovery: false, recipients: [] }, recipients: [{ service: "mobile_app_simulated_phone", name: "SIMULATED phone" }], scripts: [{ entity_id: "script.simulated_start", identity: "c".repeat(64), name: "SIMULATED action" }], missing_recipients: [], episodes: [], manual_results: [], preview: { title: "AlarmMesh preview", message: "Example source and room" } };
  data.sources[0].selftest = { available: true, reason: "selftest_supported", control: { source: source.entity_id, identity: "d".repeat(64) }, record: null };
  data.sources[1].selftest = { available: false, reason: "selftest_unsupported", control: null, record: null };
  return data;
}

test("notification settings require exact-recipient acknowledgement and preserve draft on pushes", async () => {
  const { panel, root, calls, transport } = setup("nl");
  transport.callbacks.at(-1)(featureData());
  await panel.go("settings"); panel.openDialog({ kind: "settings" });
  const form = root.querySelector("dialog form");
  form.querySelector('[name="notifications-enabled"]').checked = true;
  form.querySelector('[name="recipient"]').checked = true;
  const update = featureData(); update.automation.settings.revision = 9;
  transport.callbacks.at(-1)(update);
  assert.equal(root.querySelector("dialog form"), form);
  assert.equal(form.querySelector('[name="recipient"]').checked, true);
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.deepEqual(calls, []);
  root.querySelector(".confirm-execute").click(); await tick();
  assert.deepEqual(calls, []);
  root.querySelector('[name="confirm-request"]').checked = true;
  root.querySelector(".confirm-execute").click(); await tick();
  assert.deepEqual(calls[0], { type: "alarmmesh/settings", revision: 0, notifications: { enabled: true, recovery: false, recipients: [{ service: "mobile_app_simulated_phone", enabled: true }] }, confirmed: true });
  panel.remove();
});

test("empty notification selection and cancelling an explicit test make no request", async () => {
  const { panel, root, calls, transport } = setup(); transport.callbacks.at(-1)(featureData());
  panel.openDialog({ kind: "settings" });
  const form = root.querySelector("dialog form"); form.querySelector('[name="notifications-enabled"]').checked = true;
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.ok(form.textContent.includes("at least one")); assert.deepEqual(calls, []);
  [...form.querySelectorAll("button")].find(b => b.textContent === "Prepare test notification").click();
  assert.ok(form.querySelector(".request-confirmation").textContent.includes("SIMULATED phone"));
  [...form.querySelectorAll(".request-confirmation button")].find(b => b.textContent === "Cancel").click();
  assert.equal(form.querySelector(".request-confirmation"), null); assert.deepEqual(calls, []); panel.remove();
});

test("explicit notification test names only the chosen server target and is not replayed", async () => {
  const { panel, root, calls, transport } = setup(); transport.callbacks.at(-1)(featureData());
  panel._hass.callWS = async payload => { calls.push(payload); return { status: "accepted" }; };
  panel.openDialog({ kind: "test", actionKind: "notification", target: "mobile_app_simulated_phone", name: "SIMULATED phone" });
  root.querySelector('[name="confirm-request"]').checked = true;
  const execute = root.querySelector(".confirm-execute"); execute.click(); await tick();
  assert.equal(calls.length, 1); assert.equal(calls[0].kind, "notification"); assert.equal(calls[0].target, "mobile_app_simulated_phone");
  assert.equal(calls[0].confirmed, true); assert.match(calls[0].request_id, /^[a-f0-9]{32}$/);
  transport.callbacks.at(-1)(featureData());
  assert.equal(execute.disabled, true); assert.equal(calls.length, 1);
  assert.ok(root.querySelector("dialog").textContent.includes("physical result unconfirmed")); panel.remove();
});

test("group origin subset and ordered script actions share the existing explicit preview", async () => {
  const { panel, root, calls, transport } = setup(); transport.callbacks.at(-1)(featureData());
  panel.openDialog({ kind: "edit", group: null });
  const form = root.querySelector("dialog form"); form.querySelector("#group-name").value = "Simulation";
  for (const member of form.querySelectorAll('[name="member"]')) member.checked = true;
  form.querySelectorAll('[name="origin"]')[1].checked = false;
  form.querySelector('[name="actions-enabled"]').checked = true;
  [...form.querySelectorAll(".action-config button")].find(b => b.textContent === "Add script").click();
  const select = form.querySelector('[data-phase="start"] select'); select.querySelector('option[value="script.simulated_start"]').selected = true; select.dispatchEvent(new Event("change"));
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.deepEqual(calls, []); assert.ok(form.querySelector(".link-confirmation").textContent.includes("SIMULATED action"));
  assert.ok(form.querySelector(".link-confirmation").textContent.includes("Review it first. AlarmMesh does not confirm"));
  form.querySelector(".confirm-ack").checked = true; form.querySelector(".confirm-linking").click(); await tick();
  assert.deepEqual(calls[0].origins, [source.entity_id]);
  assert.deepEqual(calls[0].actions, { enabled: true, start: [{ entity_id: "script.simulated_start", identity: "c".repeat(64) }], recovery: [] });
  assert.equal(calls[0].confirmed, true); panel.remove();
});

test("offline configuration draft survives without displaying cached current smoke", async () => {
  const { panel, root, transport } = setup(); transport.callbacks.at(-1)(featureData());
  panel.openDialog({ kind: "edit", group: null }); const form = root.querySelector("dialog form");
  form.querySelector("#group-name").value = "Keep this draft";
  transport.event("disconnected");
  assert.equal(panel.data, null); assert.equal(root.querySelector(".hero"), null);
  assert.equal(root.querySelector("dialog form"), form); assert.ok(root.querySelector(".offline-draft"));
  assert.equal(form.querySelector('button[type="submit"]').disabled, true);
  transport.event("ready"); await tick(); transport.callbacks.at(-1)(featureData());
  assert.equal(root.querySelector("dialog form"), form); assert.equal(form.querySelector("#group-name").value, "Keep this draft");
  assert.equal(form.querySelector('button[type="submit"]').disabled, false); panel.remove();
});

test("self-test is offered only with its own reviewed control and exact target confirmation", async () => {
  const { panel, root, transport, calls } = setup(); const data = featureData(); transport.callbacks.at(-1)(data);
  panel.openDialog({ kind: "source", id: data.sources[1].entity_id });
  assert.ok(root.querySelector("dialog").textContent.includes("not a self-test"));
  assert.ok(![...root.querySelectorAll("dialog button")].some(b => b.textContent === "Request self-test"));
  panel.openDialog({ kind: "source", id: data.sources[0].entity_id });
  [...root.querySelectorAll("dialog button")].find(b => b.textContent === "Request self-test").click();
  assert.deepEqual(calls, []); assert.ok(root.querySelector("dialog").textContent.includes("Sound may occur"));
  assert.ok(root.querySelector("dialog").textContent.includes(data.sources[0].name));
  root.querySelector('[name="confirm-request"]').checked = true; root.querySelector(".confirm-execute").click(); await tick();
  assert.equal(calls[0].kind, "selftest"); assert.equal(calls[0].target, data.sources[0].entity_id); assert.equal(calls[0].identity, "d".repeat(64)); panel.remove();
});

test("incident details distinguish current smoke, delivery failures and explicit device result", async () => {
  const { panel, root, transport } = setup("nl"); const data = featureData();
  data.sources[0].status = "SMOKE_REPORTED"; data.sources[0].ha_state = "on";
  data.automation.episodes = [{ group_id: "notifications", id: "e".repeat(32), started: "2026-11-14T12:00:00Z", phase: "start", origins: [source.entity_id], receipts: { phone: { target: "mobile_app_simulated_phone", kind: "notification", phase: "start", status: "failed" } } }];
  data.selftest = { source: source.entity_id, status: "outcome_unknown" };
  transport.callbacks.at(-1)(data); await panel.go("incidents");
  const text = root.querySelector("main").textContent;
  assert.ok(text.includes("Rook gemeld")); assert.ok(text.includes("Aanvraag mislukt")); assert.ok(text.includes("geen geslaagde test"));
  assert.ok(text.includes("Bovenaan staat de huidige rookstatus")); panel.remove();
});

test("stored changed sounder identity is retained until explicitly reselected", async () => {
  const { panel, root, transport, calls } = setup(); const data = guidedGroupData();
  data.groups[0].linking.bindings[0].identity = "b".repeat(64);
  transport.callbacks.at(-1)(data); panel.openDialog({ kind: "edit", group: data.groups[0] });
  root.querySelector("dialog form").dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.equal(calls[0].linking.bindings[0].identity, "b".repeat(64));
  panel.remove();
});

test("an unselected stored sounder is not silently deleted by an organizer edit", async () => {
  const { panel, root, transport, calls } = setup(); const data = guidedGroupData();
  const targetSource = data.sources[1].entity_id, old = structuredClone(data.groups[0].linking.bindings);
  data.sources = data.sources.slice(0, 1); data.groups[0].unselected = [targetSource];
  transport.callbacks.at(-1)(data); panel.openDialog({ kind: "edit", group: data.groups[0] });
  root.querySelector("#group-name").value = "Keep stale choices";
  root.querySelector("dialog form").dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.deepEqual(calls[0].linking.bindings, old); panel.remove();
});

test("notification confirmation freezes its exact selection until cancelled", async () => {
  const { panel, root, transport, calls } = setup(); transport.callbacks.at(-1)(featureData());
  panel.openDialog({ kind: "settings" }); const form = root.querySelector("dialog form");
  form.querySelector('[name="notifications-enabled"]').checked = true;
  const recipient = form.querySelector('[name="recipient"]'); recipient.checked = true;
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  assert.equal(recipient.disabled, true);
  const cancel = [...form.querySelectorAll(".request-confirmation button")].find(b => b.textContent === "Cancel");
  cancel.click(); assert.equal(recipient.disabled, false); assert.equal(recipient.checked, true);
  assert.deepEqual(calls, []); panel.remove();
});

test("group confirmation locks script editing and cannot dispatch while disconnected", async () => {
  const { panel, root, transport, calls } = setup(); const data = featureData();
  transport.callbacks.at(-1)(data); panel.openDialog({ kind: "edit", group: null });
  const form = root.querySelector("dialog form"); form.querySelector("#group-name").value = "Preview";
  for (const member of form.querySelectorAll('[name="member"]')) member.checked = true;
  form.querySelector('[name="link-enabled"]').checked = true;
  const target = form.querySelectorAll('[name="link-target"]')[1]; target.checked = true;
  form.dispatchEvent(new Event("submit", { cancelable: true })); await tick();
  const add = [...form.querySelectorAll(".action-config button")].find(b => b.textContent === "Add script");
  assert.equal(add.disabled, true);
  form.querySelector(".confirm-ack").checked = true;
  transport.event("disconnected");
  const confirm = form.querySelector(".confirm-linking"); assert.equal(confirm.disabled, true);
  confirm.dispatchEvent(new Event("click")); await tick(); assert.deepEqual(calls, []);
  transport.event("ready"); await tick(); transport.callbacks.at(-1)(data);
  assert.equal(add.disabled, true); assert.equal(form.querySelector('button[type="submit"]').disabled, true);
  assert.equal(confirm.disabled, false);
  [...form.querySelectorAll(".link-confirmation button")].find(b => b.textContent === "Back").click();
  assert.equal(add.disabled, false); panel.remove();
});

test("changed script identity is visible and cannot be tested as the stored script", () => {
  const { panel, root, transport, calls } = setup(); const data = featureData();
  const group = { ...guidedGroupData().groups[0], actions: { enabled: false, start: [{entity_id: "script.simulated_start", identity: "a".repeat(64)}], recovery: [] } };
  transport.callbacks.at(-1)(data); panel.openDialog({kind: "edit", group});
  const row = root.querySelector(".action-row"), select = row.querySelector("select");
  assert.ok(select.selectedOptions?.[0]?.textContent.includes("changed") || [...select.options].find(o => o.selected)?.textContent.includes("changed"));
  assert.equal([...row.querySelectorAll("button")].find(b => b.textContent === "Test this script").disabled, true);
  assert.deepEqual(calls, []); panel.remove();
});

test("self-test confirmation follows only its own request's live result", async () => {
  const { panel, root, transport } = setup(); transport.callbacks.at(-1)(featureData()); let request;
  panel._hass.callWS = async payload => { request = payload.request_id; return { status: "request_sent" }; };
  panel.openDialog({kind: "test", actionKind: "selftest", target: source.entity_id, name: "SIMULATED A", identity: "d".repeat(64)});
  root.querySelector('[name="confirm-request"]').checked = true; root.querySelector(".confirm-execute").click(); await tick();
  const update = featureData(); update.selftest = { request_id: request, status: "test_active", source: source.entity_id };
  transport.callbacks.at(-1)(update);
  assert.ok(root.querySelector(".request-confirmation").textContent.includes("test is active"));
  update.selftest.status = "device_success"; transport.callbacks.at(-1)(update);
  assert.ok(root.querySelector(".request-confirmation").textContent.includes("explicitly reports success"));
  update.selftest = { ...update.selftest, request_id: "f".repeat(32), status: "failed" }; transport.callbacks.at(-1)(update);
  assert.ok(root.querySelector(".request-confirmation").textContent.includes("explicitly reports success")); panel.remove();
});

test("scripts can move both ways and the reviewed configuration names its origins", async () => {
  const { panel, root, transport, calls } = setup(); const data = featureData();
  data.automation.scripts.push({entity_id: "script.simulated_second", identity: "e".repeat(64), name: "SIMULATED second"});
  transport.callbacks.at(-1)(data); panel.openDialog({kind: "edit", group: null});
  const form = root.querySelector("dialog form"); form.querySelector("#group-name").value = "Ordered scripts";
  form.querySelector('[name="member"]').checked = true; form.querySelector('[name="actions-enabled"]').checked = true;
  for (const id of ["script.simulated_start", "script.simulated_second"]) {
    [...form.querySelectorAll(".action-config button")].find(b => b.textContent === "Add script").click();
    const select = [...form.querySelectorAll('[data-phase="start"] select')].at(-1);
    select.querySelector(`option[value="${id}"]`).selected = true; select.dispatchEvent(new Event("change"));
  }
  const first = form.querySelector(".action-row");
  assert.equal([...first.querySelectorAll("button")].find(b => b.textContent === "Move up").disabled, true);
  [...first.querySelectorAll("button")].find(b => b.textContent === "Move down").click();
  const rows = form.querySelectorAll(".action-row");
  assert.equal(rows[0].querySelector("select").value, "script.simulated_second");
  assert.equal(rows[1].querySelector("select").value, "script.simulated_start");
  form.dispatchEvent(new Event("submit", {cancelable: true})); await tick();
  assert.ok(form.querySelector(".link-confirmation").textContent.includes("Detector A"));
  form.querySelector(".confirm-ack").checked = true; form.querySelector(".confirm-linking").click(); await tick();
  assert.deepEqual(calls[0].actions.start.map(s => s.entity_id), ["script.simulated_second", "script.simulated_start"]);
  panel.remove();
});

test("default dialog warning and danger colors meet normal-text contrast in each theme", async () => {
  const css = await readFile(new URL("../../custom_components/alarmmesh/frontend/panel.css", import.meta.url), "utf8");
  const lum = hex => hex.match(/../g).map(c => parseInt(c,16)/255).map(c => c <= .04045 ? c/12.92 : ((c+.055)/1.055)**2.4).reduce((s,c,i) => s+c*[.2126,.7152,.0722][i],0);
  for (const [selector,background] of [["dialog", "ffffff"],["dialog.dark", "172736"]]) {
    const rule = [...css.matchAll(/(dialog(?:\.dark)?)\{([^}]+)\}/g)].filter(m => m[1] === selector).at(-1)[2];
    for (const key of ["warn","alarm"]) {
      const color = rule.match(new RegExp(`--${key}:#([a-f0-9]{6})`))[1];
      const [low,high] = [lum(color),lum(background)].sort((a,b) => a-b);
      assert.ok((high+.05)/(low+.05) >= 4.5, `${selector} ${key} normal-text contrast`);
    }
    const {panel,root}=setup(); panel.hass={...panel._hass,themes:{darkMode:selector.includes("dark")}};
    panel.openDialog({kind:"settings"}); assert.equal(root.querySelector("dialog").classList.contains("dark"),selector.includes("dark")); panel.remove();
  }
});

test("link-only incident details name groups and distinguish uncleared unknown origins", () => {
  const {panel,root,transport}=setup(); const data=guidedGroupData();
  data.groups[0].linking.enabled=true;
  data.sources[0].status="UNREACHABLE"; data.sources[0].ha_state="unavailable";
  data.incident={active_sources:[source.entity_id],targets:[]};
  transport.callbacks.at(-1)(data); panel.go("incidents");
  assert.ok(root.querySelector("main").textContent.includes("Upstairs"));
  assert.ok(root.querySelector("main").textContent.includes("explicit no-smoke"));
  assert.ok(root.querySelector("main").textContent.includes("Detector A"));
  assert.equal(root.querySelector("main .badge.danger"),null);
  panel.remove();
});


test("confirming after an unchecked attempt clears the obsolete validation warning", async () => {
  const { panel, root, calls, transport } = setup();
  transport.callbacks.at(-1)(featureData());
  panel._hass.callWS = async payload => { calls.push(payload); return { status: "accepted" }; };
  panel.openDialog({ kind: "test", actionKind: "script", target: "script.simulated_start", identity: "a".repeat(64), name: "SIMULATED start" });
  const box = root.querySelector(".request-confirmation"), execute = box.querySelector(".confirm-execute");
  execute.click(); await tick();
  assert.ok(box.querySelector(".form-error").textContent.length > 0);
  assert.equal(calls.length, 0);
  box.querySelector('[name="confirm-request"]').checked = true;
  execute.click(); await tick();
  assert.equal(calls.length, 1);
  assert.equal(box.querySelector(".form-error").textContent, "");
  assert.ok(box.querySelector(".request-status").textContent.includes("accepted"));
  assert.equal(execute.disabled, true);
  panel.remove();
});

test("five task steps retain all server assessments, allow skipping and never enable anything", async () => {
  const { panel, root, transport, calls } = setup("nl");
  const data = featureData();
  data.review = { steps: [
    ["sources", "configured"], ["rooms", "needs_attention"], ["groups", "configured"],
    ["sounders", "not_supported"], ["notifications", "disabled"], ["scripts", "disabled"], ["check", "needs_attention"]
  ].map(([id, status]) => ({id, status, count: 0})), issues: [] };
  transport.callbacks.at(-1)(data);
  assert.equal(root.querySelectorAll(".setup-steps li").length, 5);
  assert.ok(root.querySelector('[data-step="notifications"]').textContent.includes("Uit · optioneel"));
  assert.ok(root.querySelector('[data-step="sounders"]').textContent.includes("Niet ondersteund"));
  root.querySelector('[data-step="rooms"] button').click(); assert.equal(panel.page, "rooms");
  await panel.go("overview"); assert.equal(root.querySelector('[data-step="sources"]').dataset.status, "configured");
  root.querySelector('[data-step="notifications"] button').click();
  assert.ok(root.querySelector('dialog [name="notifications-enabled"]'));
  assert.deepEqual(calls, []); panel.remove();
});

test("maintenance keeps absent evidence unknown and a low-battery warning separate from smoke", async () => {
  const {panel,root,transport,calls}=setup(); const data=featureData();
  data.sources[0].capability.details={maintenance:{battery_percent:19,battery_low:false,fault:true}};
  data.sources[1].capability.details={maintenance:{battery_percent:null,battery_low:null,fault:null}};
  data.review={steps:[],issues:[{code:"control_missing",source:data.sources[1].entity_id,group:"simulated-group"}]};
  transport.callbacks.at(-1)(data); await panel.go("maintenance");
  const cards=root.querySelectorAll(".maintenance-device");
  assert.ok(cards[0].textContent.includes("19%")); assert.ok(cards[0].textContent.includes("20% display threshold"));
  assert.ok(cards[0].textContent.includes("Problem reported by device"));
  assert.ok(cards[1].textContent.includes("Unknown")); assert.ok(!cards[1].textContent.includes("No problem reported"));
  assert.ok(root.querySelector('[data-issue="control_missing"]'));
  assert.deepEqual(panel.data.result,data.result); assert.deepEqual(calls,[]);
  await panel.go("overview"); assert.ok(root.querySelector(".hero").textContent.includes("No smoke reported"));
  panel.remove();
});

test("missing recipient stays visible until explicit removal, cancelling preserves it", async () => {
  const {panel,root,transport,calls}=setup(); const data=featureData();
  data.automation.settings.recipients=[{service:"mobile_app_simulated_gone",enabled:false}];
  data.automation.missing_recipients=["mobile_app_simulated_gone"];
  transport.callbacks.at(-1)(data); panel.openDialog({kind:"settings"});
  const missing=[...root.querySelectorAll(".recipient-row")].find(r=>r.textContent.includes("simulated_gone"));
  assert.ok(missing.textContent.includes("Phone not found")); assert.equal(missing.querySelectorAll("button").length,1);
  missing.querySelector("button").click(); panel.closeDialog(); assert.deepEqual(calls,[]);
  panel.openDialog({kind:"settings"}); assert.ok(root.querySelector('input[value="mobile_app_simulated_gone"]'));
  [...root.querySelectorAll(".recipient-row")].find(r=>r.textContent.includes("simulated_gone")).querySelector("button").click();
  root.querySelector("form").dispatchEvent(new Event("submit",{cancelable:true})); await tick();
  assert.deepEqual(calls[0].notifications.recipients,[]); panel.remove();
});

test("incident summary records only known times and separates pending clearance and device-test outcome", async () => {
  const {panel,root,transport}=setup(); const data=featureData();
  data.sources[0].status="UNREACHABLE";
  data.incident={active_sources:[source.entity_id],targets:[{source:data.sources[1].entity_id,status:"failed",origins:[source.entity_id]}]};
  data.automation.episodes=[{id:"episode",group_id:"notifications",phase:"start",started:"2026-11-15T08:00:00Z",origins:[source.entity_id],relevant:[source.entity_id],receipts:{p:{kind:"notification",target:"mobile_app_simulated_phone",phase:"start",status:"accepted"}}}];
  data.selftest={source:data.sources[1].entity_id,status:"outcome_unknown"};
  transport.callbacks.at(-1)(data); await panel.go("incidents");
  const flow=root.querySelector(".incident-flow"); assert.ok(flow.textContent.includes("explicit no-smoke"));
  assert.ok(!flow.textContent.includes("No smoke reported at"));
  assert.ok(root.querySelector(".incident-episode").textContent.includes("physical result unconfirmed"));
  assert.ok(root.querySelector(".selftest-result").textContent.includes("not a pass"));
  const recovered=structuredClone(data); recovered.automation.episodes[0].phase="recovery"; recovered.automation.episodes[0].updated="2026-11-15T08:05:00Z";
  transport.callbacks.at(-1)(recovered); assert.ok(root.querySelector(".incident-flow").textContent.includes("No smoke reported at"));
  panel.remove();
});

test("maintenance and guide do not expose cached data after loss of admin authorization", async () => {
  const {panel,root,transport,calls}=setup(); transport.callbacks.at(-1)(featureData());
  await panel.go("maintenance"); assert.ok(root.querySelector(".maintenance-device"));
  panel.hass={...panel._hass,user:{is_admin:false}};
  assert.equal(root.querySelector(".maintenance-device"),null); assert.equal(root.querySelector(".setup-guide"),null);
  assert.deepEqual(calls,[]); panel.remove();
});

test("page navigation returns to the panel start while live updates preserve reading position", async () => {
  const original = HTMLElement.prototype.scrollIntoView;
  const scrolled = [];
  HTMLElement.prototype.scrollIntoView = function (options) { scrolled.push({ node: this, options }); };
  let panel;
  try {
    const view = setup("nl"); panel = view.panel;
    await panel.go("maintenance");
    assert.equal(scrolled.length, 1);
    assert.equal(scrolled[0].node.classList.contains("shell"), true);
    assert.equal(scrolled[0].options.block, "start");
    view.transport.callbacks.at(-1)(normal());
    assert.equal(scrolled.length, 1, "a pushed state must not reset the reading position");
    await panel.go("overview");
    assert.equal(scrolled.length, 2);
  } finally {
    panel?.remove();
    if (original) HTMLElement.prototype.scrollIntoView = original;
    else delete HTMLElement.prototype.scrollIntoView;
  }
});


test("HTTP-compatible self-test confirmation uses secure random bytes without randomUUID", async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  const realCrypto = globalThis.crypto;
  let randomCalls = 0;
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: {
    getRandomValues(bytes) { randomCalls++; return realCrypto.getRandomValues(bytes); },
  } });
  let panel;
  try {
    const view = setup(); panel = view.panel;
    view.transport.callbacks.at(-1)(featureData());
    panel.openDialog({ kind: "test", actionKind: "selftest", target: source.entity_id, identity: "d".repeat(64), name: "HTTP SIMULATED self-test" });
    view.root.querySelector(".confirm-execute").click(); await tick();
    assert.equal(view.calls.length, 0, "explicit confirmation is still required");
    view.root.querySelector('[name="confirm-request"]').checked = true;
    view.root.querySelector(".confirm-execute").click(); await tick();
    assert.equal(view.calls.length, 1, "one mock request must reach HA even without randomUUID");
    assert.equal(randomCalls, 1);
    assert.match(view.calls[0].request_id, /^[a-f0-9]{32}$/);
    assert.equal(view.calls[0].target, source.entity_id);
    assert.equal(view.calls[0].identity, "d".repeat(64));
    assert.equal(view.root.querySelector(".form-error").textContent, "");
    assert.equal(view.root.querySelector(".confirm-execute").disabled, true);
    const text = view.root.querySelector("dialog").textContent;
    assert.equal(text.split("Sound may occur").length - 1, 1, "show the warning once");
  } finally {
    panel?.remove();
    Object.defineProperty(globalThis, "crypto", descriptor);
  }
});

test("missing secure randomness blocks dispatch with an actionable message", async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: {} });
  let panel;
  try {
    const view = setup("nl"); panel = view.panel;
    view.transport.callbacks.at(-1)(featureData());
    panel.openDialog({ kind: "test", actionKind: "selftest", target: source.entity_id, identity: "d".repeat(64), name: "SIMULATED" });
    view.root.querySelector('[name="confirm-request"]').checked = true;
    view.root.querySelector(".confirm-execute").click(); await tick();
    assert.equal(view.calls.length, 0);
    assert.match(view.root.querySelector(".form-error").textContent, /browser.*aanvraagnummer/i);
  } finally {
    panel?.remove();
    Object.defineProperty(globalThis, "crypto", descriptor);
  }
});
function maintenanceData() {
  const data = featureData(); data.groups = guidedGroupData().groups;
  data.maintenance = {settings:{revision:0,enabled:false,recovery:false,recipients:[],battery:true,fault:true,unavailable:true,delay:15},issues:[],missing_recipients:[],error:null,paused:false};
  return data;
}

test("maintenance settings are opt-in, exact-confirmed and preserve draft through reconnect", async () => {
  const {panel,root,transport,calls}=setup("nl"); const data=maintenanceData(); transport.callbacks.at(-1)(data);
  panel.openDialog({kind:"maintenance"}); const form=root.querySelector("dialog form");
  assert.equal(form.querySelector('[name="maintenance-enabled"]').checked,false);
  assert.equal(form.querySelector('[name="maintenance-delay"]').value,"15");
  form.querySelector('[name="maintenance-enabled"]').checked=true;
  form.querySelector('[name="maintenance-recipient"]').checked=true;
  form.querySelector('[name="maintenance-delay"] option[value="5"]').selected=true;
  transport.event("disconnected"); assert.equal(root.querySelector("dialog form"),form);
  assert.equal(form.querySelector('[type="submit"]').disabled,true);
  transport.event("ready"); await tick(); transport.callbacks.at(-1)(data);
  assert.equal(form.querySelector('[name="maintenance-delay"]').value,"5");
  form.dispatchEvent(new Event("submit",{cancelable:true})); await tick();
  assert.deepEqual(calls,[]); assert.ok(root.querySelector(".request-confirmation").textContent.includes("mobile_app_simulated_phone"));
  assert.equal(form.querySelector('[name="maintenance-delay"]').disabled,true);
  root.querySelector('[name="confirm-request"]').checked=true; root.querySelector(".confirm-execute").click(); await tick();
  assert.equal(calls[0].type,"alarmmesh/maintenance_settings"); assert.equal(calls[0].settings.delay,5); assert.equal(calls[0].confirmed,true);
  assert.equal(calls[0].settings.recovery,false); panel.remove();
});

test("maintenance cancel does not change stored choices or send a test request", async () => {
  const {panel,root,transport,calls}=setup(); const data=maintenanceData(); transport.callbacks.at(-1)(data);
  panel.openDialog({kind:"maintenance"}); root.querySelector('[name="maintenance-enabled"]').checked=true;
  [...root.querySelectorAll("dialog button")].find(b=>b.textContent==="Cancel").click();
  assert.deepEqual(calls,[]); assert.equal(data.maintenance.settings.enabled,false); panel.remove();
});

test("group action example only reads and never creates executable confirmations", async () => {
  const {panel,root,transport,calls}=setup(); const data=maintenanceData(); transport.callbacks.at(-1)(data);
  panel._hass.callWS=async command=>{calls.push(command);return {readonly:true,revision:data.revision,groups:[{id:data.groups[0].id,can_start:true}],targets:[{source:data.sources[1].entity_id,reason:"control_missing",safe_stop:false}],phones:[],scripts:[],linking_enabled:true,notifications_enabled:false,actions_enabled:false,recovery_sources:[source.entity_id],notification_recovery:false};};
  panel.openDialog({kind:"preview",id:data.groups[0].id}); await tick();
  assert.ok(root.querySelector("dialog").textContent.includes("Example — no commands are sent."));
  assert.ok(root.querySelector("dialog").textContent.includes("missing or disabled"));
  assert.equal(root.querySelectorAll("dialog form,.confirm-execute,.confirm-linking").length,0);
  assert.deepEqual(calls.map(c=>c.type),["alarmmesh/preview"]);
  transport.event("disconnected"); assert.equal(root.querySelector("dialog"),null); panel.remove();
});

test("diagnostic preview and copy use server aliases without private header or live names", async () => {
  const {panel,root,transport,calls}=setup(); const data=maintenanceData(); data.title="PRIVATE_LOCATION"; data.sources[0].name="PRIVATE_DETECTOR";
  const report={schema:1,versions:{alarmmesh:"0.1.0-beta.5",home_assistant:"2026.11.1"},counts:{sources:2,groups:1,valid_assignments:0,invalid_assignments:1},result:{availability:"INCOMPLETE"},sources:[{alias:"Detector 1",provider:"zha",model:"unknown",assessment:"not_confirmed"}],problems:[{source:"Detector 1",reason:"control_missing",setting:"groups"}],recipients:[],recorded_errors:[],physical_confirmed:false};
  panel._hass.callWS=async command=>{calls.push(command);return report;};
  transport.callbacks.at(-1)(data); await panel.go("diagnostics"); await tick();
  assert.ok(![...root.childNodes].map(n=>n.textContent).join("").includes("PRIVATE_")); assert.ok(root.querySelector("textarea").value.includes("Detector 1"));
  const descriptor=Object.getOwnPropertyDescriptor(globalThis,"navigator"); const copied=[];
  Object.defineProperty(globalThis,"navigator",{configurable:true,value:{clipboard:{async writeText(value){copied.push(value);}}}});
  try { [...root.querySelectorAll("main button")].find(b=>b.textContent==="Copy this report").click(); await tick(); assert.deepEqual(copied,[JSON.stringify(report,null,2)]); }
  finally { if(descriptor) Object.defineProperty(globalThis,"navigator",descriptor); else delete globalThis.navigator; }
  transport.event("disconnected"); assert.equal(root.querySelector("textarea"),null); assert.deepEqual(calls.map(c=>c.type),["alarmmesh/diagnostics"]); panel.remove();
});


test("a blocked preview target does not become an activation-only capability claim", async () => {
  for (const language of ["en", "nl"]) {
    const { panel, root, transport, calls } = setup(language);
    try {
      const data = maintenanceData(); transport.callbacks.at(-1)(data);
      panel._hass.callWS = async command => {
        calls.push(command);
        return { readonly: true, revision: data.revision, groups: [], targets: [{ source: source.entity_id, reason: "disabled", eligible: false, safe_stop: false }], phones: [], scripts: [], recovery_sources: [source.entity_id] };
      };
      panel.openDialog({ kind: "preview", id: data.groups[0].id }); await tick();
      const text = root.querySelector("dialog").textContent;
      assert.ok(!text.includes(panel.t.no_safe_stop), "blocked does not establish activation-only support");
      assert.equal(typeof panel.t.preview_stop_unassessed, "string");
      assert.ok(text.includes(panel.t.preview_stop_unassessed));
      assert.deepEqual(calls.map(c => c.type), ["alarmmesh/preview"]);
      assert.equal(root.querySelectorAll(".confirm-execute,.confirm-linking").length, 0);
    } finally { panel.remove(); }
  }
});

test("maintenance recovery receipts are labelled as requests, not future conditions", () => {
  for (const [language, expected] of [["nl", "Herstelaanvraag"], ["en", "Recovery request"]]) {
    const { panel, root, transport } = setup(language);
    try {
      const data = maintenanceData();
      data.maintenance.issues = [{ sources: [source.entity_id], kind: "battery", active: false, reason: "maintenance_current", receipts: { mobile_app_simulated_phone_a: { problem: "accepted", recovery: "accepted" } } }];
      transport.callbacks.at(-1)(data); panel.go("maintenance");
      const text = root.querySelector("main").textContent;
      assert.ok(text.includes(expected + ":"));
      assert.ok(!text.includes(panel.t.maintenanceRecovery + ":"));
    } finally { panel.remove(); }
  }
});

test("combined detector filters retain global smoke and survive pushes", () => {
  const {panel,root,transport}=setup(); const data=normal();
  data.sources[0]={...data.sources[0],name:"Very long simulated detector ".repeat(12),area_id:"room-a",groups:["g"],capability:{origin:"mqtt",status:"detection_only",controls:[],details:{maintenance:{battery_percent:10,fault:false}}}};
  data.sources.push({...source,entity_id:"binary_sensor.simulation_b",name:"Other",status:"SMOKE_REPORTED",capability:{origin:"zha",status:"detection_only",controls:[]}});
  data.result={smoke:"SMOKE_REPORTED",availability:"COMPLETE"}; data.groups=[{id:"g",name:"SIMULATION group"}]; transport.callbacks.at(-1)(data); panel.go("devices");
  const search=root.querySelector('[name="device-name"]');search.value="Very long";search.dispatchEvent(new Event("input"));
  const provider=root.querySelector('[name="device-provider"]');provider.querySelector('[value="mqtt"]').selected=true;provider.dispatchEvent(new Event("change"));
  assert.equal(root.querySelectorAll('.filtered-devices .source').length,1);assert.ok(root.querySelector('.filter-alarm').textContent.includes('Smoke reported'));
  transport.callbacks.at(-1)(data);assert.equal(root.querySelector('[name="device-name"]').value,'Very long');
  const next=root.querySelector('[name="device-name"]');next.value='No match';next.dispatchEvent(new Event('input'));assert.ok(root.querySelector('.filtered-devices').textContent.includes('No results'));
  assert.ok(root.querySelector('.filter-alarm').textContent.includes('Smoke reported'));panel.remove();
});

test("activity empty state, filters and detail are read-only and retained",()=>{
 const {panel,root,transport,calls}=setup('nl');const data=normal();data.activity={events:[],incomplete:false};transport.callbacks.at(-1)(data);panel.go('activity');assert.ok(root.querySelector('main').textContent.includes('Nog geen gebeurtenissen'));
 data.activity.events=[{id:'observed',observed_at:'2026-11-15T12:00:00Z',category:'alarm',kind:'source',result:'SMOKE_REPORTED',source:source.entity_id,groups:[],target:'',correlation:'incident-observation'}];transport.callbacks.at(-1)(data);
 assert.equal(root.querySelector(".more-filters").open,false);assert.ok(root.querySelector(".activity-row"));
 const filter=root.querySelector('[name="activity-source"]');filter.querySelector(`[value="${source.entity_id}"]`).selected=true;filter.dispatchEvent(new Event('change'));root.querySelector('.activity-row').click();assert.ok(root.querySelector('dialog').textContent.includes('Waargenomen door AlarmMesh'));panel.closeDialog();assert.equal(panel.activityFilters.source,source.entity_id);assert.deepEqual(calls,[]);panel.remove();
});

test("reminder draft, exact confirmation, cancellation and offline guard",async()=>{
 const {panel,root,transport,calls}=setup();const data=normal();data.sources[0].reminder_identity='a'.repeat(64);data.reminders={items:[],revision:0,time_zone:'Europe/Brussels'};data.automation={recipients:[{service:'mobile_app_mock',name:'SIMULATED phone'}]};transport.callbacks.at(-1)(data);panel.openDialog({kind:'reminder',id:source.entity_id});
 let form=root.querySelector('dialog form');form.querySelector('[name="reminder-date"]').value='2027-04-01';form.querySelector('[name="reminder-enabled"]').checked=true;form.querySelector('[name="reminder-recipient"] option[value="mobile_app_mock"]').selected=true;
 transport.event('disconnected');assert.equal(form.querySelector('[name="reminder-date"]').value,'2027-04-01');assert.equal(form.querySelector('[type="submit"]').disabled,true);assert.deepEqual(calls,[]);
 transport.event('ready');await tick();transport.callbacks.at(-1)(data);assert.equal(root.querySelector('dialog form'),form);
 form.dispatchEvent(new Event('submit',{cancelable:true}));assert.deepEqual(calls,[]);assert.ok(form.querySelector('.request-confirmation').textContent.includes('No self-test or sound is started'));
 form.querySelector('[name="confirm-request"]').checked=true;form.querySelector('.confirm-execute').click();await tick();assert.equal(calls[0].type,'alarmmesh/reminder');assert.equal(calls[0].value.enabled,true);assert.equal(calls[0].value.date,'2027-04-01');assert.equal(calls[0].confirmed,true);
 panel.openDialog({kind:'reminder',id:source.entity_id});[...root.querySelectorAll('dialog button')].find(b=>b.textContent==='Cancel').click();assert.equal(calls.length,1);panel.remove();
});

test("group copy previews only organizational choices without execution fields",async()=>{
 const {panel,root,transport,calls}=setup();const data=normal();data.groups=[{id:'g',name:'SIMULATION floor',members:[source.entity_id],origins:[source.entity_id],unselected:[],linking:{enabled:true,bindings:[{target:'siren.mock'}]},actions:{enabled:true,start:[{entity_id:'script.mock'}],recovery:[]}}];transport.callbacks.at(-1)(data);panel.openDialog({kind:'copy',id:'g'});
 const form=root.querySelector('dialog form');form.dispatchEvent(new Event('submit',{cancelable:true}));assert.deepEqual(calls,[]);assert.ok(form.querySelector('.request-confirmation').textContent.includes('off and empty'));form.querySelector('[name="confirm-request"]').checked=true;form.querySelector('.confirm-execute').click();await tick();assert.equal(calls[0].type,'alarmmesh/group_copy');assert.deepEqual(calls[0].members,[source.entity_id]);assert.ok(!('actions' in calls[0]) && !('linking' in calls[0]));assert.equal(data.groups[0].linking.enabled,true);panel.remove();
});

test("member search hides rows without losing selected members and origin counts",()=>{
 const {panel,root}=setup();panel.openDialog({kind:'edit',group:null});const member=root.querySelector('[name="member"]');member.checked=true;member.dispatchEvent(new Event('change',{bubbles:true}));const search=root.querySelector('[type="search"]');search.value='missing';search.dispatchEvent(new Event('input'));assert.equal(member.checked,true);assert.equal(member.parentNode.hidden,true);assert.ok(root.querySelector('.member-count').textContent.includes('1'));panel.remove();
});

test("detector search and reminder controls use their own bilingual labels",()=>{
 for(const [lang,search,save,choose] of [['nl','Zoek melder','Herinnering bewaren','Kies een ontvanger'],['en','Find detector','Save reminder','Choose a recipient']]) {
  const {panel,root,transport}=setup(lang);const data=normal();data.sources[0].reminder_identity='a'.repeat(64);data.reminders={items:[],revision:0,time_zone:'Europe/Brussels'};data.automation={recipients:[{service:'mobile_app_mock',name:'SIMULATED phone'}]};transport.callbacks.at(-1)(data);
  panel.go('devices');assert.equal(root.querySelector('[name="device-name"]').parentNode.textContent,search);
  panel.openDialog({kind:'reminder',id:source.entity_id});assert.equal(root.querySelector('dialog [type="submit"]').textContent,save);assert.equal(root.querySelector('[name="reminder-recipient"] option').textContent,choose);panel.remove();
 }
});
test("reminder confirmation includes enabled state and repeat preference",()=>{
 const {panel,root,transport,calls}=setup('nl');const data=normal();data.sources[0].reminder_identity='a'.repeat(64);data.reminders={items:[],revision:0,time_zone:'Europe/Brussels'};data.automation={recipients:[{service:'mobile_app_mock',name:'SIMULATED phone'}]};transport.callbacks.at(-1)(data);panel.openDialog({kind:'reminder',id:source.entity_id});
 const form=root.querySelector('dialog form');form.querySelector('[name="reminder-enabled"]').checked=true;form.querySelector('[name="reminder-date"]').value='2027-04-01';form.querySelector('[name="reminder-interval"] option[value="90"]').selected=true;form.querySelector('[name="reminder-recipient"] option[value="mobile_app_mock"]').selected=true;form.dispatchEvent(new Event('submit',{cancelable:true}));
 const text=form.querySelector('.request-confirmation').textContent;assert.ok(text.includes('Herinnering inschakelen: Aan'));assert.ok(text.includes('90 dagen'));assert.deepEqual(calls,[]);panel.remove();
});

test("reminder removal is named independently of group deletion",()=>{
 const {panel,root,transport}=setup('nl');const data=normal();data.sources[0].reminder_identity='a'.repeat(64);data.reminders={items:[{source:source.entity_id,date:'2027-04-01',interval:0,enabled:false,recipient:'mobile_app_mock'}],revision:1,time_zone:'Europe/Brussels'};data.automation={recipients:[{service:'mobile_app_mock',name:'SIMULATED phone'}]};transport.callbacks.at(-1)(data);panel.openDialog({kind:'reminder',id:source.entity_id});
 const remove=[...root.querySelectorAll('dialog button')].find(b=>b.textContent==='Herinnering verwijderen');assert.ok(remove);remove.click();assert.ok(root.querySelector('.request-confirmation').textContent.includes('Herinnering verwijderen'));panel.remove();
});

test("activity result filters retain explicit device test result wording",()=>{
 const {panel,root,transport}=setup('nl');const data=normal();data.activity={events:[{id:'test-result',observed_at:'2026-11-15T12:00:00Z',category:'selftest',kind:'selftest',result:'device_success',source:source.entity_id,groups:[],target:'',correlation:'request'}],incomplete:false};transport.callbacks.at(-1)(data);panel.go('activity');assert.ok(root.querySelector('[name="activity-result"]').parentNode.textContent.startsWith('Resultaat'));assert.ok(root.querySelector('[name="activity-result"] option[value="device_success"]').textContent.includes('expliciet succes'));panel.remove();
});

// Matter and local-draft regressions. DOM behavior, not visual acceptance.
const { Drafts, validDraft } = await import('../../custom_components/alarmmesh/frontend/drafts.js');
class LocalDraftStorage {
 getItem(k){return this[k] ?? null;}
 setItem(k,v){this[k]=String(v);}
 removeItem(k){delete this[k];}
}
const draftValue=()=>({enabled:false,recovery:false,recipients:[{service:'mobile_app_simulated',enabled:true}]});
test('local drafts separate users and entries, expire, and cannot contain permissions',()=>{
 const storage=new LocalDraftStorage(),d=new Drafts(storage); d.switchUser('user-a');
 assert.equal(d.put('user-a','entry-a','settings','new',4,'identity-list',draftValue()),true);
 assert.deepEqual(d.read('user-a','entry-b'),{}); assert.deepEqual(d.read('user-b','entry-a'),{});
 assert.equal(validDraft('settings',{...draftValue(),confirmed:true}),false);
 assert.equal(d.put('user-a','entry-a','settings','new',4,'identity-list',{...draftValue(),token:'NO'}),false);
 const key=d.bucket('user-a','entry-a'),raw=JSON.parse(storage.getItem(key));raw['settings:new'].time-=7200001;storage.setItem(key,JSON.stringify(raw));
 assert.deepEqual(d.read('user-a','entry-a'),{});
 d.put('user-a','entry-a','settings','new',4,'s',draftValue());d.switchUser('user-b');assert.deepEqual(d.read('user-a','entry-a'),{});
});
test('tampered, misaddressed, oversized and unavailable draft storage fails closed',()=>{
 const storage=new LocalDraftStorage(),d=new Drafts(storage),key=d.bucket('a','b');
 d.put('a','b','settings','new',7,'s',draftValue());const saved=JSON.parse(storage.getItem(key));
 saved['settings:new'].confirmed=true;storage.setItem(key,JSON.stringify(saved));assert.deepEqual(d.read('a','b'),{});
 delete saved['settings:new'].confirmed;storage.setItem(key,JSON.stringify({'edit:new':saved['settings:new']}));assert.deepEqual(d.read('a','b'),{});
 storage.setItem(key,' '.repeat(250001));assert.deepEqual(d.read('a','b'),{});assert.equal(d.error,true);
 assert.equal(new Drafts(null).put('a','b','settings','new',7,'s',draftValue()),false);
 const failed=new Drafts({getItem(){throw Error('blocked');}});assert.deepEqual(failed.read('a','b'),{});
});
function withDraftUser(view,storage) {
 view.panel.drafts=new Drafts(storage);view.panel.hass={...view.panel._hass,user:{id:'simulated-user',is_admin:true}};view.transport.callbacks.at(-1)(normal());
}
test('full panel recreation restores input only, retains original revision and clears successful save',async()=>{
 const storage=new LocalDraftStorage();let view=setup();withDraftUser(view,storage);
 view.panel.openDialog({kind:'edit',group:null});let name=view.root.querySelector('#group-name');name.value='Unsent simulation';name.dispatchEvent(new Event('input',{bubbles:true}));
 assert.ok(storage.getItem(view.panel.drafts.bucket('simulated-user','test-entry')));assert.deepEqual(view.calls,[]);view.panel.remove();
 view=setup();withDraftUser(view,storage);const current=normal();current.revision=9;view.transport.callbacks.at(-1)(current);
 view.panel.openDialog({kind:'edit',group:null});assert.equal(view.root.querySelector('form'),null);
 [...view.root.querySelectorAll('dialog button')].find(b=>b.textContent===view.panel.t.continueDraft).click();
 assert.equal(view.root.querySelector('#group-name').value,'Unsent simulation');assert.deepEqual(view.calls,[]);
 assert.ok(view.root.querySelector('dialog').textContent.includes(view.panel.t.draftRestored));
 view.root.querySelector('form').dispatchEvent(new Event('submit',{cancelable:true}));await tick();
 assert.equal(view.calls[0].revision,0);assert.equal(view.calls[0].operation,'create');assert.equal(view.calls[0].confirmed,undefined);
 assert.deepEqual(view.panel.drafts.read('simulated-user','test-entry'),{});view.panel.remove();
});
test('restored enabled notification draft requires a fresh exact confirmation and keeps old revision',async()=>{
 const view=setup(),storage=new LocalDraftStorage();withDraftUser(view,storage);view.transport.callbacks.at(-1)(featureData());
 const value={...featureData().automation.settings,enabled:true,recipients:[{service:'mobile_app_simulated_phone',enabled:true}]};delete value.revision;
 assert.ok(view.panel.drafts.put('simulated-user','test-entry','settings','new',2,view.panel.draftSignature(),value));
 view.panel.openDialog({kind:'settings'});[...view.root.querySelectorAll('dialog button')].find(b=>b.textContent===view.panel.t.continueDraft).click();
 assert.deepEqual(view.calls,[]);view.root.querySelector('form').dispatchEvent(new Event('submit',{cancelable:true}));await tick();
 assert.ok(view.root.querySelector('.request-confirmation'));assert.equal(view.root.querySelector('[name="confirm-request"]').checked,false);assert.deepEqual(view.calls,[]);
 view.panel.closeDialog();assert.deepEqual(view.calls,[]);view.panel.remove();
});
test('identity changes prevent local-draft restoration; discard makes no request',()=>{
 const view=setup(),storage=new LocalDraftStorage();withDraftUser(view,storage);
 view.panel.drafts.put('simulated-user','test-entry','settings','new',2,'OLD_IDENTITIES',draftValue());view.panel.openDialog({kind:'settings'});
 assert.ok(view.root.querySelector('dialog').textContent.includes(view.panel.t.draftChanged));assert.equal([...view.root.querySelectorAll('dialog button')].some(b=>b.textContent===view.panel.t.continueDraft),false);
 [...view.root.querySelectorAll('dialog button')].find(b=>b.textContent===view.panel.t.discardDraft).click();assert.deepEqual(view.calls,[]);assert.deepEqual(view.panel.drafts.read('simulated-user','test-entry'),{});view.panel.remove();
});
test('Matter details and help separate transport, CO, unavailable functions and unknown physical outcome',()=>{
 for(const lang of ['en','nl']) {const v=setup(lang),data=normal();data.matter_revision=0;
 data.sources[0].capability={origin:'matter',status:'detection_only',reason:'matter_no_sounder_route',controls:[],details:{values:[]},matter:{transport:'unknown',source_kind:'local_smoke',functions:[{key:'self_test_result',reason:'matter_no_correlated_result'},{key:'activation',reason:'matter_no_sounder_route'},{key:'co',reason:'matter_entity_available'}]}};
 v.transport.callbacks.at(-1)(data);v.panel.go('devices');assert.ok([...v.root.childNodes].map(n=>n.textContent).join(' ').includes(v.panel.t.transport_unknown));v.panel.openDialog({kind:'source',id:source.entity_id});
 const dialog=v.root.querySelector('dialog');assert.ok(dialog.textContent.includes(v.panel.t.matter_no_correlated_result));assert.ok(dialog.textContent.includes(v.panel.t.matter_function_co));assert.deepEqual(v.calls,[]);
 v.panel.go('matterHelp');assert.equal(v.root.querySelector('ol').children.length,6);assert.ok(v.root.querySelector('a[href="https://www.home-assistant.io/integrations/thread/"]'));assert.deepEqual(v.calls,[]);v.panel.remove();}
});

test('changed Matter fingerprint blocks a draft even without optional controls',()=>{
 const view=setup();withDraftUser(view,new LocalDraftStorage());const d=normal();d.sources[0].capability={origin:'matter',controls:[],matter:{fingerprint:'a'.repeat(64)}};view.transport.callbacks.at(-1)(d);
 view.panel.drafts.put('simulated-user','test-entry','settings','new',0,view.panel.draftSignature(),draftValue());
 d.sources[0].capability.matter.fingerprint='b'.repeat(64);view.transport.callbacks.at(-1)(d);view.panel.openDialog({kind:'settings'});
 assert.ok(view.root.querySelector('dialog').textContent.includes(view.panel.t.draftChanged));assert.deepEqual(view.calls,[]);view.panel.remove();
});

test('Matter combination and secondary value labels are readable in both languages',()=>{
 for(const [lang,kind,co,interconnect] of [['nl','Rook- en CO-melder','CO-waarde (afzonderlijk)','Native interconnectwaarde (alleen lezen)'],['en','Smoke and CO detector','CO report (separate)','Native interconnect report (read-only)']]) {
  const v=setup(lang),data=normal();data.sources[0].capability={origin:'matter',kind:'smoke_co',status:'detection_only',reason:'matter_no_sounder_route',controls:[],details:{values:[{key:'co',value:'off'},{key:'interconnect_smoke',value:'off'}]}};v.transport.callbacks.at(-1)(data);v.panel.openDialog({kind:'source',id:source.entity_id});const labels=[...v.root.querySelectorAll('dialog .diagnostics dt')].map(n=>n.textContent);const values=[...v.root.querySelectorAll('dialog .diagnostics dd')].map(n=>n.textContent);assert.ok(values.includes(kind));assert.ok(labels.includes(co));assert.ok(labels.includes(interconnect));assert.deepEqual(v.calls,[]);v.panel.remove();
 }
});

test('cancelling a standalone self-test closes its dialog without dispatch',()=>{
 const v=setup();v.panel.openDialog({kind:'test',actionKind:'selftest',target:source.entity_id,identity:'mock-identity',name:'SIMULATED Matter detector'});const cancel=[...v.root.querySelectorAll('dialog button')].find(b=>b.textContent==='Cancel');assert.ok(cancel);cancel.click();assert.ok(!v.root.querySelector('dialog'));assert.deepEqual(v.calls,[]);v.panel.remove();
});

for (const language of ["nl", "en"]) test(`Z-Wave provider filter and honest details (${language})`, () => {
  const { panel, root, transport, calls } = setup(language);
  const data=normal();data.sources[0].capability={origin:"zwave_js",status:"detection_only",reason:"zwave_observation_only",controls:[],kind:"smoke",zwave:{self_test:false,sounder:false},details:{values:[],maintenance:{}}};
  transport.callbacks.at(-1)(data);panel.go("devices");
  assert.ok([...root.querySelectorAll("option")].some(o=>o.value==="zwave_js" && o.textContent==="Z-Wave JS"));
  panel.openDialog({kind:"source",id:source.entity_id});
  const dialog=root.querySelector("dialog");assert.ok(dialog.textContent.includes("Z-Wave JS"));
  assert.equal(dialog.querySelector('a[href="https://www.home-assistant.io/integrations/zwave_js/"]').getAttribute("rel"),"noopener noreferrer");
  assert.ok(dialog.textContent.includes(language==="nl" ? "Een ping is geen zelftest" : "A ping is not a detector self-test"));
  assert.deepEqual(calls,[]);panel.remove();
});

test('source alarm route merges backend targets and refresh sends only read requests',async()=>{
 const v=setup();v.panel._hass.callWS=async command=>{v.calls.push(command);return {readonly:true,revision:0,targets:[{source:source.entity_id,target:'select.simulated',eligible:true,via:[{group:'a',reason:'preview_eligible'},{group:'b',reason:'disabled'}]}],phones:[],groups:[]};};
 v.panel.openDialog({kind:'route',id:source.entity_id});await tick();assert.ok(v.root.querySelector('dialog').textContent.includes(v.panel.t.routeOnce));
 [...v.root.querySelectorAll('dialog button')].find(b=>b.textContent===v.panel.t.refreshData).click();await tick();v.panel.closeDialog();
 assert.equal(v.calls.length,2);assert.ok(v.calls.every(c=>c.type==='alarmmesh/route'));v.panel.remove();
});
test('recovery conflict preserves selection and never retries automatically',async()=>{
 const v=setup();v.panel._hass.callWS=async c=>{v.calls.push(c);if(c.target)throw {code:'conflict'};return {token:'old',selected:true,blocked:false,outputs_enabled:false,groups:['g'],candidates:[{entity_id:'binary_sensor.simulation_b',name:'SIMULATED replacement'}]};};
 v.panel.openDialog({kind:'recovery',id:source.entity_id});await tick();const form=v.root.querySelector('form');form.querySelector('select option').selected=true;form.querySelector('[name="recovery-group"]').checked=true;form.dispatchEvent(new Event('submit',{cancelable:true}));await tick();
 assert.equal(v.calls.length,1);v.root.querySelector('[name="confirm-request"]').checked=true;v.root.querySelector('.confirm-execute').click();await tick();
 assert.ok(v.root.querySelector('.form-error').textContent.includes(v.panel.t.conflict));assert.equal(v.calls.length,2);v.panel.closeDialog();assert.equal(v.calls.length,2);v.panel.remove();
});
test('refresh self-test discards acknowledgement and cannot adopt another request result',async()=>{
 const v=setup();v.transport.callbacks.at(-1)(featureData());const s=featureData().sources[0];v.panel.openDialog({kind:'test',actionKind:'selftest',target:s.entity_id,name:s.name,identity:s.selftest.control.identity});
 v.root.querySelector('[name="confirm-request"]').checked=true;const data=featureData();data.sources[0].selftest.control.identity='e'.repeat(64);data.selftest={request_id:'other',status:'device_success'};v.transport.callbacks.at(-1)(data);
 v.panel._hass.callWS=async c=>{v.calls.push(c);return data;};[...v.root.querySelectorAll('dialog button')].find(b=>b.textContent===v.panel.t.refreshData).click();await tick();assert.equal(v.root.querySelector('[name="confirm-request"]').checked,false);assert.equal(v.root.querySelector('.request-status').textContent,'');assert.deepEqual(v.calls,[{type:'alarmmesh/current'}]);v.panel.remove();
});

test('live smoke remains visible inside recovery without replacing choices',async()=>{
 const v=setup();v.panel._hass.callWS=async()=>({token:'t',selected:true,groups:['g'],candidates:[{entity_id:'binary_sensor.new',name:'Replacement'}]});v.panel.data.groups=[{id:'g',name:'Group'}];v.panel.openDialog({kind:'recovery',id:source.entity_id});await tick();const form=v.root.querySelector('dialog form'),choice=form.querySelector('input');choice.checked=true;const data=normal();data.result.smoke='SMOKE_REPORTED';data.sources[0].status='SMOKE_REPORTED';v.transport.callbacks.at(-1)(data);assert.ok(v.root.querySelector('dialog form')===form);assert.equal(choice.checked,true);assert.ok(v.root.querySelector('dialog [role="alert"]').textContent.includes('Smoke reported'));assert.ok(v.root.querySelector('dialog [role="alert"]').textContent.includes('Detector A'));v.panel.remove();
});

test('recovery choices survive disconnect and reconnect without automatic save',async()=>{
 const v=setup();const data=normal();data.groups=[{id:'g',name:'Group'}];v.transport.callbacks.at(-1)(data);v.panel._hass.callWS=async c=>{v.calls.push(c);return{token:'t',selected:true,groups:['g'],candidates:[{entity_id:'binary_sensor.new',name:'Replacement'}]};};v.panel.openDialog({kind:'recovery',id:source.entity_id});await tick();const form=v.root.querySelector('dialog form'),choice=form.querySelector('input');choice.checked=true;v.transport.event('disconnected');assert.ok(v.root.querySelector('dialog form')===form);assert.equal(form.querySelector('[type=submit]').disabled,true);assert.ok(v.root.querySelector('.offline-draft'));v.transport.event('ready');await tick();v.transport.callbacks.at(-1)(data);assert.equal(choice.checked,true);assert.equal(form.querySelector('[type=submit]').disabled,false);assert.equal(v.calls.length,1);v.panel.remove();
});

for (const committed of [false, true]) {
  test(`reconnected recovery shows actual membership when committed=${committed}`, async () => {
    const v = setup(), data = normal(), target = "binary_sensor.replacement";
    data.groups = [{id:"g", name:"Hall", members:[source.entity_id]}];
    v.transport.callbacks.at(-1)(data);
    let rejectSave;
    v.panel._hass.callWS = async command => {
      v.calls.push(command);
      if (command.confirmed) return new Promise((_, reject) => { rejectSave = reject; });
      return {token:"t", selected:true, groups:["g"], candidates:[{entity_id:target, name:"Replacement"}]};
    };
    v.panel.openDialog({kind:"recovery", id:source.entity_id});
    await tick();
    const form = v.root.querySelector("dialog form");
    form.querySelector("select option").selected = true;
    form.querySelector("[name=recovery-group]").checked = true;
    form.dispatchEvent(new Event("submit", {cancelable:true}));
    v.root.querySelector("[name=confirm-request]").checked = true;
    v.root.querySelector(".confirm-execute").click();
    v.transport.event("disconnected");
    rejectSave({code:"connection_lost"});
    await tick();
    v.transport.event("ready");
    await tick();
    data.groups[0].members = [committed ? target : source.entity_id];
    v.transport.callbacks.at(-1)(data);
    const summary = v.root.querySelector(".recovery-summary");
    assert.ok(summary.textContent.includes("Hall · " + v.panel.sourceName(data.groups[0].members[0])));
    assert.equal(v.root.querySelector(".confirm-execute"), null);
    assert.equal(v.calls.filter(command => command.confirmed).length, 1);
    v.panel.remove();
  });
}

test("daily overview keeps setup collapsed and navigation read only", async () => {
  const view = setup();
  assert.equal(view.root.querySelector(".setup-guide").open, false);
  view.root.querySelector('.stat[aria-label="Detectors"]').click();
  assert.equal(view.panel.page, "devices");
  view.panel._hass.callWS = async command => {
    view.calls.push(command);
    return {readonly:true, revision:0, targets:[], groups:[], phones:[]};
  };
  view.root.querySelector(".source-route").click();
  await tick();
  assert.deepEqual(view.calls, [{type:"alarmmesh/route", source:source.entity_id}]);
  view.panel.closeDialog();
  assert.equal(view.panel.page, "devices");
  view.panel.remove();
});

test("ordinary group hides optional controls and duplicate submits save once", async () => {
  const view = setup();
  view.panel.openDialog({kind:"edit", group:null});
  const form = view.root.querySelector("form");
  assert.equal(form.querySelector(".advanced-options").open, false);
  assert.equal(form.querySelector('[name="link-enabled"]').checked, false);
  form.querySelector('#group-name').value = "Upstairs";
  form.querySelector('[name="member"]').checked = true;
  let finish;
  view.panel._hass.callWS = command => { view.calls.push(command); return new Promise(resolve => {finish=resolve;}); };
  form.dispatchEvent(new Event("submit", {cancelable:true}));
  form.dispatchEvent(new Event("submit", {cancelable:true}));
  assert.equal(view.calls.length, 1);
  assert.equal(view.calls[0].linking, undefined);
  assert.equal(view.calls[0].actions, undefined);
  finish({revision:1}); await tick();
  view.panel.remove();
});

test("smoke remains visible in settings with area and forwarded provenance", () => {
  const view = setup();
  const data = featureData();
  view.transport.callbacks.at(-1)(data);
  view.panel.openDialog({kind:"settings"});
  const form = view.root.querySelector("form");
  const input = form.querySelector('[name="notifications-enabled"]');
  input.checked = true;
  data.result.smoke = "SMOKE_REPORTED";
  Object.assign(data.sources[0], {status:"SMOKE_REPORTED", area_name:"Landing", capability:{...data.sources[0].capability, matter:{source_kind:"interconnect_smoke"}}});
  view.transport.callbacks.at(-1)(data);
  assert.equal(view.root.querySelector("form"), form);
  assert.equal(input.checked, true);
  const warning = view.root.querySelector("dialog .recovery-smoke");
  assert.ok(warning.textContent.includes("Landing"));
  assert.ok(warning.textContent.includes("Forwarded smoke"));
  assert.deepEqual(view.calls, []);
  view.panel.remove();
});

test("duplicate detector names expose identity and notification preview is visible", () => {
  const view = setup();
  const data = featureData();
  data.sources[1].name = data.sources[0].name;
  data.sources[1].area_id = data.sources[0].area_id;
  view.transport.callbacks.at(-1)(data);
  view.panel.go("devices");
  assert.equal(view.root.querySelectorAll(".source-identity").length, 2);
  view.panel.openDialog({kind:"settings"});
  assert.ok(view.root.querySelector(".message-preview").parentNode.open);
  data.result.smoke = "SMOKE_REPORTED";
  data.sources[0].status = "SMOKE_REPORTED";
  view.transport.callbacks.at(-1)(data);
  assert.ok(view.root.querySelector(".recovery-smoke").textContent.includes(data.sources[0].entity_id));
  assert.deepEqual(view.calls, []);
  view.panel.remove();
});


test("incomplete overview names the affected source before summaries", () => {
  const view = setup();
  const data = normal();
  data.result = {smoke:"INDETERMINATE", availability:"INCOMPLETE"};
  Object.assign(data.sources[0], {status:"UNREACHABLE", area_name:"Landing"});
  view.transport.callbacks.at(-1)(data);
  const affected = view.root.querySelector(".hero-missing button");
  assert.ok(affected.textContent.includes("Detector A"));
  assert.ok(affected.textContent.includes("Landing"));
  assert.ok(affected.textContent.includes(view.panel.t.UNREACHABLE));
  affected.click();
  assert.ok(view.root.querySelector("dialog").textContent.includes(view.panel.t.recovery_temporary));
  assert.deepEqual(view.calls, []);
  view.panel.remove();
});

test("notification acknowledgement expires with its server confirmation context", async () => {
  const v = setup(), data = featureData(), target = "mobile_app_simulated_phone";
  data.automation.confirmations = {[target]: "a".repeat(64)};
  v.transport.callbacks.at(-1)(data);
  v.panel.openDialog({kind:"test", actionKind:"notification", target, name:"Phone"});
  v.root.querySelector('[name="confirm-request"]').checked = true;
  data.automation.confirmations[target] = "b".repeat(64);
  v.transport.callbacks.at(-1)(data);
  v.root.querySelector('.confirm-execute').click(); await tick();
  assert.equal(v.calls.length, 0);
  assert.equal(v.root.querySelector('[name="confirm-request"]').checked, false);
  assert.ok(v.root.querySelector('.request-status').textContent.includes(v.panel.t.notification_confirmation_stale));
  v.panel.remove();
});

test("lost notification reply reconciles only its matching receipt without replay", async () => {
  const v = setup(), data = featureData(), target = "mobile_app_simulated_phone";
  data.automation.confirmations = {[target]: "a".repeat(64)};
  v.transport.callbacks.at(-1)(data);
  v.panel._hass.callWS = async c => {v.calls.push(c);throw {code:"connection_lost"};};
  v.panel.openDialog({kind:"settings"});
  [...v.root.querySelectorAll('button')].find(b=>b.textContent==='Prepare test notification').click();
  v.root.querySelector('[name="confirm-request"]').checked = true;
  v.root.querySelector('.confirm-execute').click();await tick();
  assert.ok(v.root.querySelector('.request-status').textContent.includes(v.panel.t.delivery_outcome_unknown));
  data.automation.manual_results = [{kind:"notification",target,request_id:v.calls[0].request_id,status:"accepted"}];
  v.transport.callbacks.at(-1)(data);
  assert.ok(v.root.querySelector('.request-status').textContent.includes(v.panel.t.delivery_accepted));
  assert.equal(v.calls.length,1);
  assert.equal(v.root.querySelector('.confirm-execute').disabled,true);
  v.panel.remove();
});

test("phone refresh retains unsaved choices and original revision without sending", async () => {
  const v=setup(),data=featureData();v.transport.callbacks.at(-1)(data);
  v.panel.openDialog({kind:"settings"});
  v.root.querySelector('[name="recipient"]').checked=true;
  v.root.querySelector('[name="notifications-recovery"]').checked=true;
  const updated=structuredClone(data);updated.automation.settings.revision=8;updated.automation.recipients=[];
  v.panel._hass.callWS=async m=>{v.calls.push(m);return updated;};
  [...v.root.querySelectorAll('button')].find(b=>b.textContent===v.panel.t.refreshRecipients).click();await tick();
  assert.equal(v.root.querySelector('[name="recipient"]').checked,true);
  assert.equal(v.root.querySelector('[name="notifications-recovery"]').checked,true);
  assert.ok(v.root.querySelector('dialog').textContent.includes(v.panel.t.phoneMissingHelp));
  assert.equal(v.panel.detail.restoredDraft.revision,0);
  assert.deepEqual(v.calls,[{type:"alarmmesh/current"}]);v.panel.remove();
});

for (const state of ["MISSING", "UNREACHABLE", "changed"]) {
  test(`overview distinguishes connection help from replacement for ${state} without dispatch`, async () => {
    const v = setup("nl"), data = normal();
    data.sources[0].status = state === "changed" ? "NO_SMOKE_REPORTED" : state;
    data.sources[0].identity_changed = state === "changed";
    v.transport.callbacks.at(-1)(data);
    const action = v.root.querySelector(".hero-missing .source-recovery");
    assert.ok(action);
    assert.ok(action.getAttribute("aria-label").includes("Detector A"));
    if (state === "UNREACHABLE") assert.ok(v.root.querySelector(".hero-missing").textContent.includes(v.panel.t.recovery_temporary));
    v.panel._hass.callWS = async c => { v.calls.push(c); return {selected:true,groups:[],candidates:[]}; };
    action.click(); await tick();
    assert.equal(v.panel.detail.kind, state === "UNREACHABLE" ? "source" : "recovery");
    assert.deepEqual(v.calls, state === "UNREACHABLE" ? [] : [{type:"alarmmesh/recovery",source:source.entity_id}]);
    if(state === "UNREACHABLE") {
      assert.ok(action.textContent.includes(v.panel.t.checkConnection));
      assert.ok(v.root.querySelector('.detector-technical').textContent.includes(v.panel.t.recoverSource));
    }
    v.panel.remove();
  });
}
for (const scenario of ['edit', 'reopen', 'confirmation', 'reconnect']) {
  test(`late phone refresh preserves ${scenario}`, async () => {
    const v=setup(), data=featureData();
    data.automation.confirmations={mobile_app_simulated_phone:'a'.repeat(64)};
    v.transport.callbacks.at(-1)(data);v.panel.openDialog({kind:'settings'});
    let resolve;v.panel._hass.callWS=()=>new Promise(r=>{resolve=r;});
    [...v.root.querySelectorAll('button')].find(b=>b.textContent===v.panel.t.refreshRecipients).click();
    if(scenario==='reopen'){v.panel.closeDialog();v.panel.openDialog({kind:'settings'});}
    if(scenario==='confirmation') [...v.root.querySelectorAll('button')].find(b=>b.textContent===v.panel.t.testNotification).click();
    if(scenario==='reconnect'){v.transport.event('disconnected');v.transport.event('ready');await tick();v.transport.callbacks.at(-1)(data);}
    const form=v.root.querySelector('dialog form');
    form.querySelector('[name=notifications-recovery]').checked=true;
    resolve(data);await tick();
    assert.equal(v.root.querySelector('[name=notifications-recovery]').checked,true);
    if(scenario!=='edit')assert.equal(v.root.querySelector('dialog form'),form);
    if(scenario==='confirmation')assert.ok(v.root.querySelector('.request-confirmation'));
    v.panel.remove();
  });
}


function phoneData() {
  const data=featureData(),a=data.automation,target=a.recipients[0].service;
  a.profile_support=true;a.ios_sounds={default:'sound_default'};
  a.phone_metadata={[target]:{platform:'ios',origin:'metadata',identity:'b'.repeat(64),identity_scope:'registration'}};
  a.phone_plans={};a.test_preview={title:'Test',message:'No physical result'};
  return data;
}
test("phone wizard keeps legacy ordinary choice until explicit edit and preserves profile on pushes", async()=>{
  const v=setup('en'),data=phoneData();v.transport.callbacks.at(-1)(data);v.panel.openDialog({kind:'settings'});
  const root=v.root,critical=root.querySelector('[name=phone-critical]'),form=root.querySelector('form');
  assert.equal(critical.checked,false);assert.match(root.querySelector('dialog').textContent,/Saving sends nothing/);
  root.querySelector('[name=recipient]').checked=true;
  critical.checked=true;critical.dispatchEvent(new Event('change',{bubbles:true}));
  v.transport.callbacks.at(-1)(data);assert.equal(root.querySelector('[name=phone-critical]'),critical);assert.equal(critical.checked,true);
  form.dispatchEvent(new Event('submit',{cancelable:true}));await tick();assert.equal(v.calls.length,0);
  assert.match(root.querySelector('.request-confirmation').textContent,/Critical smoke alert/);
  root.querySelector('[name=confirm-request]').checked=true;root.querySelector('.confirm-execute').click();await tick();
  assert.equal(v.calls.length,1);assert.equal(v.calls[0].type,'alarmmesh/settings');
  assert.equal(v.calls[0].notifications.enabled,false);assert.equal(v.calls[0].notifications.recipients[0].profile.critical,true);
  v.panel.remove();
});
test("critical preview binds server request id and sends only after explicit acknowledgement",async()=>{
  const v=setup(),data=phoneData(),target=data.automation.recipients[0].service;
  v.transport.callbacks.at(-1)(data);const calls=[];v.panel._hass.callWS=async m=>{calls.push(m);return m.type==='alarmmesh/notification_preview'?{context:'a'.repeat(64),confirmation:'c'.repeat(64),request_id:m.request_id,profile:{platform:'android',critical:true},message:{title:'Test',message:'Simulation only'}}:{status:'accepted'};};
  v.panel.openDialog({kind:'test',actionKind:'notification',target,name:'Mock phone'});await tick();
  assert.equal(calls.length,1);assert.equal(calls[0].type,'alarmmesh/notification_preview');
  assert.match(v.root.querySelector('.request-confirmation').textContent,/may make sound even in silent mode/);
  v.root.querySelector('[name=confirm-request]').checked=true;v.root.querySelector('.confirm-execute').click();await tick();
  assert.equal(calls.length,2);assert.equal(calls[1].identity,'c'.repeat(64));assert.equal(calls[1].request_id,calls[0].request_id);
  v.root.querySelector('.confirm-execute').click();await tick();assert.equal(calls.length,2);v.panel.remove();
});


test("lost settings acknowledgement offers read-only verification without resubmitting or clearing form",async()=>{
  const v=setup(),data=phoneData();v.transport.callbacks.at(-1)(data);let saved,calls=[];
  v.panel._hass.callWS=async m=>{calls.push(m.type);if(m.type==='alarmmesh/settings'){saved=m.notifications;throw {code:'connection_lost'};}return {...data,automation:{...data.automation,settings:{...saved,revision:1}}};};
  v.panel.openDialog({kind:'settings'});const form=v.root.querySelector('form');
  v.root.querySelector('[name=recipient]').checked=true;form.dispatchEvent(new Event('submit',{cancelable:true}));await tick();
  const check=v.root.querySelector('[data-check-saved-phones]');assert.ok(check);
  assert.equal(v.root.querySelector('form'),form);check.click();await tick();
  assert.deepEqual(calls,['alarmmesh/settings','alarmmesh/current']);
  assert.match(v.root.querySelector('.save-reconcile').textContent,/These choices are saved/);
  assert.equal(v.root.querySelector('.form-error').textContent,'');
  assert.equal(v.root.querySelector('button[type=submit]').disabled,true);
  assert.equal(v.root.querySelector('form'),form);assert.equal(v.root.querySelector('[name=recipient]').checked,true);v.panel.remove();
});


test("verified save stays read-only after reconnect until the form is reopened",async()=>{
  const v=setup(),data=phoneData();v.transport.callbacks.at(-1)(data);let saved;
  v.panel._hass.callWS=async m=>{if(m.type==='alarmmesh/settings'){saved=m.notifications;throw {code:'connection_lost'};}return {...data,automation:{...data.automation,settings:{...saved,revision:1}}};};
  v.panel.openDialog({kind:'settings'});v.root.querySelector('[name=recipient]').checked=true;
  v.root.querySelector('form').dispatchEvent(new Event('submit',{cancelable:true}));await tick();
  v.root.querySelector('[data-check-saved-phones]').click();await tick();
  assert.equal(v.root.querySelector('button[type=submit]').disabled,true);
  v.transport.event('disconnected');v.transport.event('ready');await tick();v.transport.callbacks.at(-1)(data);
  assert.equal(v.root.querySelector('button[type=submit]').disabled,true);
  assert.equal(v.root.querySelector('[name=recipient]').checked,true);v.panel.remove();
});


test("closing a critical-save confirmation cannot re-enable a verified stale form",async()=>{
  const v=setup(),data=phoneData();v.transport.callbacks.at(-1)(data);let saved;
  v.panel._hass.callWS=async m=>{if(m.type==='alarmmesh/settings'){saved=m.notifications;throw {code:'connection_lost'};}return {...data,automation:{...data.automation,settings:{...saved,revision:1}}};};
  v.panel.openDialog({kind:'settings'});v.root.querySelector('[name=recipient]').checked=true;
  const critical=v.root.querySelector('[name=phone-critical]');critical.checked=true;critical.dispatchEvent(new Event('change',{bubbles:true}));
  const form=v.root.querySelector('form');form.dispatchEvent(new Event('submit',{cancelable:true}));
  v.root.querySelector('[name=confirm-request]').checked=true;v.root.querySelector('.confirm-execute').click();await tick();
  v.root.querySelector('[data-check-saved-phones]').click();await tick();
  const cancel=[...v.root.querySelectorAll('.request-confirmation button')].find(b=>b.textContent===v.panel.t.cancel);cancel.click();
  assert.equal(form.querySelector('button[type=submit]').disabled,true);assert.equal(critical.checked,true);v.panel.remove();
});

test("task settings separate global phone choices from per-group outputs without commands",()=>{
  const v=setup('nl'),data=phoneData();data.groups=guidedGroupData().groups;data.groups[0].linking={enabled:true,bindings:[]};data.groups[0].actions={enabled:true,start:[],recovery:[]};
  v.transport.callbacks.at(-1)(data);v.panel.go('settings');
  assert.equal(v.root.querySelectorAll('.settings-task').length,4);
  assert.ok(v.root.querySelector('[data-setting=groups]').textContent.includes('1 met samen afgaan ingeschakeld'));
  assert.ok(v.root.querySelector('[data-setting=groups]').textContent.includes('1 groepen met extra acties aan'));
  assert.ok(v.root.querySelector('[data-setting=phones]').textContent.includes('Automatisch melden uit'));
  assert.equal(v.root.querySelectorAll('.settings-grid .primary').length,1);assert.deepEqual(v.calls,[]);v.panel.remove();
});

for (const when of ['before-check', 'pending-check', 'after-check']) {
  test(`save readback never claims newer form edits are saved: ${when}`, async()=>{
    const v=setup(),data=phoneData();v.transport.callbacks.at(-1)(data);let saved,resolve;
    v.panel._hass.callWS=async m=>{
      v.calls.push(m.type);
      if(m.type==='alarmmesh/settings'){saved=structuredClone(m.notifications);throw {code:'connection_lost'};}
      if(when==='pending-check')return new Promise(r=>{resolve=r;});
      return {...data,automation:{...data.automation,settings:{...saved,revision:1}}};
    };
    v.panel.openDialog({kind:'settings'});v.root.querySelector('[name=recipient]').checked=true;
    v.root.querySelector('form').dispatchEvent(new Event('submit',{cancelable:true}));await tick();
    const edit=()=>{const input=v.root.querySelector('[name=notifications-recovery]');input.checked=true;input.dispatchEvent(new Event('input',{bubbles:true}));};
    if(when==='before-check')edit();
    v.root.querySelector('[data-check-saved-phones]').click();await tick();
    if(when==='pending-check'){edit();resolve({...data,automation:{...data.automation,settings:{...saved,revision:1}}});await tick();}
    if(when==='after-check')edit();
    assert.ok(!v.root.querySelector('.save-reconcile').textContent.includes(v.panel.t.phonesSavedVerified));
    assert.equal(v.root.querySelector('[name=notifications-recovery]').checked,true);
    assert.deepEqual(v.calls,['alarmmesh/settings','alarmmesh/current']);v.panel.remove();
  });
}


test("all-detector alarm settings use only the read-only endpoint and refresh problems",async()=>{
  const v=setup('nl'),d=phoneData();v.transport.callbacks.at(-1)(d);let unavailable=false;
  v.panel._hass.callWS=async m=>{v.calls.push(m);return {readonly:true,revision:d.revision,rows:[{source:source.entity_id,status:unavailable?'UNREACHABLE':'NO_SMOKE_REPORTED',targets:[],groups:[],phones:[{target:'mobile_app_simulated_phone',profile:null,eligible:false,reason:'disabled'}]}]};};
  v.panel.openDialog({kind:'alarmsettings'});await tick();assert.deepEqual(v.calls.map(c=>c.type),['alarmmesh/alarm_settings']);
  assert.equal(v.root.querySelectorAll('.alarm-setting-card').length,1);assert.match(v.root.querySelector('dialog').textContent,/alle geselecteerde rookmelders/);
  unavailable=true;v.transport.callbacks.at(-1)(d);await tick();assert.match(v.root.querySelector('dialog').textContent,/tijdelijk onbereikbaar/);
  unavailable=false;v.transport.callbacks.at(-1)(d);await tick();assert.ok(!v.root.querySelector('dialog').textContent.includes('tijdelijk onbereikbaar'));
  assert.ok(v.calls.every(c=>c.type==='alarmmesh/alarm_settings'));v.panel.remove();
});
function evidenceData(){const d=phoneData();d.phone_evidence={revision:2,error:null,requests:[{request_id:'a'.repeat(32),target:'mobile_app_simulated_phone',profile:null,started:'2026-11-18T10:00:00Z',attempted:true,status:'accepted',current:true,reason:'phone_request_current',observations:[]}]};return d;}
test("own observations are independent, request-bound and send no phone command",async()=>{
  const v=setup(),d=evidenceData();v.transport.callbacks.at(-1)(d);v.panel.openDialog({kind:'phoneObservation',id:'a'.repeat(32)});
  v.root.querySelector('[name=received]').querySelector('[value=yes]').selected=true;v.root.querySelector('[name=heard]').querySelector('[value=no]').selected=true;v.root.querySelector('[name=simulation-observation]').checked=true;
  const form=v.root.querySelector('form');form.dispatchEvent(new Event('submit',{cancelable:true}));form.dispatchEvent(new Event('submit',{cancelable:true}));await tick();
  assert.deepEqual(v.calls,[{type:'alarmmesh/phone_observation',request_id:'a'.repeat(32),revision:2,received:true,heard:false,simulation:true}]);
  assert.match(v.root.querySelector('.observation-status').textContent,/observation is saved/);assert.equal(v.root.querySelector('[type=submit]').disabled,true);v.panel.remove();
});
test("observation readback compares the latest edits and stays read-only after reconnect",async()=>{
  const v=setup(),d=evidenceData();v.transport.callbacks.at(-1)(d);let finish;
  v.panel._hass.callWS=async m=>{v.calls.push(m);if(m.type==='alarmmesh/phone_observation')throw {code:'connection_lost'};return new Promise(r=>{finish=r;});};
  v.panel.openDialog({kind:'phoneObservation',id:'a'.repeat(32)});v.root.querySelector('[name=received]').querySelector('[value=yes]').selected=true;v.root.querySelector('form').dispatchEvent(new Event('submit',{cancelable:true}));await tick();
  [...v.root.querySelectorAll('button')].find(b=>b.textContent===v.panel.t.checkSavedPhones).click();await tick();
  v.root.querySelector('[name=heard]').querySelector('[value=yes]').selected=true;d.phone_evidence.requests[0].observations=[{at:'2026-11-18T10:01:00Z',received:true,heard:null,simulation:false}];finish(d);await tick();
  assert.match(v.root.querySelector('.observation-status').textContent,/not confirmed saved/);
  v.transport.event('disconnected');v.transport.event('ready');await tick();v.transport.callbacks.at(-1)(d);
  assert.equal(v.root.querySelector('[name=heard]').value,'yes');assert.equal(v.root.querySelector('[type=submit]').disabled,true);assert.equal(v.calls.filter(c=>c.type==='alarmmesh/phone_observation').length,1);v.panel.remove();
});
test("old-profile observations remain history and simulation is explicit",()=>{
  const v=setup('nl'),d=evidenceData();d.phone_evidence.requests[0].current=false;d.phone_evidence.requests[0].reason='phone_observation_old_profile';d.phone_evidence.requests[0].observations=[{at:'2026-11-18T10:01:00Z',received:true,heard:false,simulation:true}];
  v.transport.callbacks.at(-1)(d);v.panel.go('settings');const text=v.root.querySelector('.phone-user-evidence').textContent;assert.match(text,/Eerdere test/);assert.match(text,/Simulatie: geen echte telefoon/);assert.match(text,/gehoord: Nee/);assert.equal(v.calls.length,0);v.panel.remove();
});
test("change summary distinguishes additions, disabled choices and unchanged forms",()=>{
  const v=setup('nl'),d=phoneData();v.transport.callbacks.at(-1)(d);const original=d.automation.settings;
  assert.deepEqual(v.panel.changeRows('phones',original,structuredClone(original)),[]);
  const modified=structuredClone(original);modified.enabled=true;modified.recipients=[{service:'mobile_app_new',enabled:true,profile:{platform:'ios',critical:true,sound:'default',volume:1}}];
  const rows=v.panel.changeRows('phones',original,modified);assert.ok(rows.some(r=>r.includes('Toegevoegd: new')));assert.ok(rows.some(r=>r.includes('Gewijzigd:')));assert.deepEqual(d.automation.settings,original);assert.deepEqual(v.calls,[]);v.panel.remove();
});
test("incident timeline shows recorded transitions once and keeps unknown separate",()=>{
  const v=setup(),d=evidenceData();d.activity={incomplete:true,events:[{id:'new',category:'alarm',kind:'notification',result:'outcome_unknown',target:'mobile_app_simulated_phone',correlation:'episode',observed_at:'2026-11-18T10:01:00Z'},{id:'old',category:'alarm',kind:'source',result:'SMOKE_REPORTED',source:source.entity_id,groups:[],correlation:'source',observed_at:'2026-11-18T10:00:00Z'}]};
  v.transport.callbacks.at(-1)(d);v.panel.go('incidents');for(let i=0;i<3;i++)v.transport.callbacks.at(-1)(d);
  const rows=v.root.querySelectorAll('.incident-timeline li');assert.equal(rows.length,2);assert.match(rows[0].textContent,/unknown/);assert.match(rows[1].textContent,/Smoke reported/);assert.equal(v.calls.length,0);v.panel.remove();
});

test("configuration summary cannot authorize a revision changed while open",async()=>{
 const v=setup(),d=phoneData();v.transport.callbacks.at(-1)(d);let executed=0;
 v.panel.openDialog({kind:'settings'});const form=v.root.querySelector('form');
 v.panel.confirmRequest(form,{changes:{kind:'phones',before:d.automation.settings,after:{...d.automation.settings,enabled:true}},confirmationOnly:true,execute:async()=>{executed++;}});
 v.root.querySelector('[name=confirm-request]').checked=true;
 const next=structuredClone(d);next.automation.settings.revision++;v.transport.callbacks.at(-1)(next);
 v.root.querySelector('.confirm-execute').click();await tick();assert.equal(executed,0);assert.equal(v.root.querySelector('[name=confirm-request]').checked,false);v.panel.remove();
});

test("phone volume stays readable and reloadable without binary floating-point noise",()=>{
 const v=setup(),d=phoneData();d.automation.settings.recipients=[{service:d.automation.recipients[0].service,enabled:true,profile:{version:1,platform:'ios',origin:'metadata',identity:'b'.repeat(64),critical:true,sound:'default',sound_source:'bundled',volume:0.55}}];v.transport.callbacks.at(-1)(d);
 assert.match(v.panel.phoneSummary(d.automation.settings.recipients[0].profile),/55%/);
 assert.doesNotMatch(v.panel.phoneSummary(d.automation.settings.recipients[0].profile),/000000/);
 v.panel.openDialog({kind:'settings'});assert.equal(v.root.querySelector('[name=phone-volume]').value,'55');v.panel.remove();
});

test("lost confirmed-save response never leaves a fictional running request after readback",async()=>{
 const v=setup(),data=phoneData();v.transport.callbacks.at(-1)(data);let saved;
 v.panel._hass.callWS=async m=>{if(m.type==='alarmmesh/settings'){saved=m.notifications;throw {code:'connection_lost'};}return {...data,automation:{...data.automation,settings:{...saved,revision:1}}};};
 v.panel.openDialog({kind:'settings'});v.root.querySelector('[name=recipient]').checked=true;
 const critical=v.root.querySelector('[name=phone-critical]');critical.checked=true;critical.dispatchEvent(new Event('change',{bubbles:true}));
 v.root.querySelector('form').dispatchEvent(new Event('submit',{cancelable:true}));v.root.querySelector('[name=confirm-request]').checked=true;v.root.querySelector('.confirm-execute').click();await tick();
 assert.notEqual(v.root.querySelector('.request-status').textContent,v.panel.t.delivery_sending);
 v.root.querySelector('[data-check-saved-phones]').click();await tick();assert.equal(v.root.querySelector('.request-status').textContent,'');assert.match(v.root.querySelector('.save-reconcile').textContent,/These choices are saved/);v.panel.remove();
});


test("detector cards show validated battery percentages including zero without inventing missing values", () => {
  const v=setup('nl'),d=normal();
  for(const [value,expected] of [[87,'87%'],[0,'0%'],[null,'Batterij onbekend'],[-1,'Batterij onbekend'],[120,'Batterij onbekend'],['50','Batterij onbekend']]) {
    d.sources[0].capability={status:'detection_only',controls:[],details:{maintenance:{battery_percent:value,battery_low:null}}};
    v.transport.callbacks.at(-1)(d);v.panel.go('devices');
    assert.ok(v.root.querySelector('.source-battery')?.textContent.includes(expected),String(value));
  }
  d.sources[0].capability.details.maintenance={battery_percent:null,battery_low:true};v.transport.callbacks.at(-1)(d);
  assert.ok(v.root.querySelector('.source-battery').textContent.includes('Batterij bijna leeg'));
  assert.deepEqual(v.calls,[]);v.panel.remove();
});

test("route phone cards separate chosen, unavailable and unchosen phones without sending", async () => {
 const v=setup('nl');v.panel._hass.callWS=async c=>{v.calls.push(c);return {readonly:true,revision:0,targets:[],groups:[],phones:[
  {target:'mobile_app_a',selected:true,enabled:true,available:true,eligible:true,reason:'preview_eligible'},
  {target:'mobile_app_b',selected:false,enabled:true,available:true,eligible:false,reason:'preview_recipient_disabled'},
  {target:'mobile_app_c',selected:true,enabled:true,available:false,eligible:false,reason:'recipient_unavailable'}]};};
 v.panel.openDialog({kind:'route',id:source.entity_id});await tick();
 assert.equal(v.root.querySelectorAll('.phone-route-active > .phone-route-card').length,2);
 const others=v.root.querySelector('.phone-route-others');assert.equal(others.hasAttribute("open"),false);assert.equal(others.querySelectorAll('.phone-route-card').length,1);
 assert.ok(v.root.querySelector('.phone-route-active').textContent.includes('Niet beschikbaar'));
 assert.ok(v.root.querySelector('.phone-route-active').textContent.includes('Ingesteld voor rookmeldingen'));
 assert.deepEqual(v.calls,[{type:'alarmmesh/route',source:source.entity_id}]);v.panel.remove();
});

test("setup has one group entry and retains separate linked-sound and script assessments", () => {
 const v=setup('nl'),d=featureData();d.review={steps:[{id:'groups',status:'configured',count:2},{id:'sounders',status:'needs_attention',count:1},{id:'scripts',status:'disabled',count:0}]};
 v.transport.callbacks.at(-1)(d);
 assert.equal(v.root.querySelectorAll('.setup-steps > li').length,5);
 const group=v.root.querySelector('[data-step=groups]');assert.equal(group.querySelectorAll('button').length,1);
 assert.ok(group.querySelector('[data-step=sounders]').textContent.includes('Aandacht nodig'));
 assert.ok(group.querySelector('[data-step=scripts]').textContent.includes('Uit'));
 assert.deepEqual(v.calls,[]);v.panel.remove();
});

test("practice disconnect drops its branches and resumes only on request; live smoke interrupts",async()=>{
  const v=setup(), model=normal();
  const second={...source,entity_id:"binary_sensor.hall",name:"Hall"};
  model.sources.push(second);v.transport.callbacks.at(-1)(model);
  v.panel._hass.callWS=async message=>{
    v.calls.push(message);
    return {readonly:true,revision:0,targets:[],phones:[],groups:[]};
  };
  v.panel.openDialog({kind:"route",id:source.entity_id});await tick();
  const exercise=()=>v.root.querySelector(".exercise");
  exercise().querySelector(".exercise-controls button").click();
  exercise().querySelector("details:last-child button").click();await tick();
  assert.deepEqual(v.calls.at(-1).other_sources,[source.entity_id]);
  const calls=v.calls.length;
  v.transport.event("disconnected");
  assert.equal(exercise().querySelector(".exercise-branches"),null);
  v.transport.event("ready");await tick();v.transport.callbacks.at(-1)(model);
  assert.equal(v.calls.length,calls);
  assert.match(exercise().textContent,/Paused/);
  exercise().querySelector("button").click();await tick();
  assert.ok(exercise().querySelector(".exercise-branches"));
  model.result.smoke="SMOKE_REPORTED";model.sources[0].status="SMOKE_REPORTED";
  v.transport.callbacks.at(-1)(model);
  assert.equal(exercise(),null);assert.equal(v.panel.page,"incidents");
  assert.ok(v.calls.every(c=>c.type==="alarmmesh/route"));v.panel.remove();
});

test("dashboard card clears private data on role loss and ignores a late push",async()=>{
  await import("../../custom_components/alarmmesh/frontend/dashboard.js");
  const v=setup(),card=document.createElement("alarmmesh-family-card");
  document.body.append(card);
  card.hass={...v.panel._hass,user:{id:"admin",is_admin:true}};
  const push=v.transport.callbacks.at(-1);
  push({...normal(),sources:[]});
  assert.match(card.textContent,/No detectors selected/);
  push(normal());assert.match(card.textContent,/no smoke reported/);
  v.transport.event("disconnected");assert.match(card.textContent,/unknown/);
  card.hass={...v.panel._hass,user:{id:"reader",is_admin:false}};
  push(normal());assert.match(card.textContent,/Administrator access required/);
  assert.equal(card.querySelector("a"),null);card.remove();v.panel.remove();
});

test("practice draws only eligible branches and keeps disabled destinations in their explanation", async () => {
  const v = setup('nl');
  const route = {readonly:true, revision:0, groups:[], targets:[], phones:[
    {target:'phone_a', name:'Telefoon A', selected:true, eligible:false, reason:'disabled'},
    {target:'phone_b', name:'Telefoon B', selected:true, eligible:false, reason:'disabled'}
  ]};
  v.panel._hass.callWS = async message => { v.calls.push(message); return route; };
  async function preview() {
    v.panel.openDialog({kind:'route', id:source.entity_id});
    await tick();
    const map = v.root.querySelector('.exercise');
    map.querySelector('.exercise-controls button').click();
    return map;
  }
  let map = await preview();
  assert.ok(map.querySelector('.exercise-stop'));
  assert.equal(map.querySelector('.exercise-stop section'), null);
  assert.ok(map.querySelector('.exercise-example').textContent.includes('Voorbeeldwoning'));
  assert.equal(map.querySelector('.exercise-example').hasAttribute('open'), false);
  assert.ok(map.querySelector('.exercise-blocked').textContent.includes('Telefoon A'));
  assert.equal(map.querySelector('.exercise-blocked').hasAttribute('open'), false);
  assert.ok(map.querySelector('.exercise-controls').textContent.includes('Laat de oefenrook verdwijnen'));
  assert.ok(!map.querySelector('.exercise-origin').textContent.includes('Geen ruimte'));
  route.phones[0].eligible = true;
  route.phones[0].reason = 'preview_eligible';
  map = await preview();
  assert.equal(map.querySelector('.exercise-stop'), null);
  assert.equal(map.querySelector('.exercise-example'), null);
  assert.equal(map.querySelectorAll('.exercise-branches section').length, 1);
  assert.ok(map.querySelector('.exercise-branches').textContent.includes('Telefoon A'));
  assert.ok(!map.querySelector('.exercise-branches').textContent.includes('Telefoon B'));
  assert.ok(map.querySelector('.exercise-blocked').textContent.includes('Telefoon B'));
  map.querySelector('.exercise-controls button').click(); await tick();
  assert.ok(map.querySelector('h2').textContent.includes('afgerond'));
  assert.equal(map.querySelector('.exercise-branches'), null);
  assert.ok(v.calls.every(message => message.type === 'alarmmesh/route'));
  v.panel.remove();
});

test("open practice drops the previous phone route when notification settings change", async () => {
  const v = setup(), model = normal();
  model.automation = featureData().automation;
  v.transport.callbacks.at(-1)(model);
  v.panel._hass.callWS = async message => {
    v.calls.push(message);
    return {readonly:true, revision:0, targets:[], groups:[], phones:[]};
  };
  v.panel.openDialog({kind:"route", id:source.entity_id});
  await tick();
  const drill = v.root.querySelector(".exercise");
  drill.querySelector(".exercise-controls button").click();
  assert.ok(drill.querySelector(".exercise-branches"));
  const changed = structuredClone(model);
  changed.automation.settings.revision++;
  v.transport.callbacks.at(-1)(changed);
  assert.ok(!drill.querySelector(".exercise-branches"));
  assert.match(drill.textContent, /Paused/);
  assert.equal(v.root.querySelector(".route-sections .phone-route-active"), null);
  assert.equal(v.calls.length,1);
  v.panel.remove();
});

test("maintenance readback can only unlock an uncertain save after an authoritative result", async () => {
  const v = setup(), model = normal(), identity = "a".repeat(64);
  model.sources[0].reminder_identity = identity;
  v.transport.callbacks.at(-1)(model);
  let rejectSave, current = {...model,care_error:true,care_log:[]};
  v.panel._hass.callWS = message => {
    v.calls.push(message);
    if (message.type === "alarmmesh/current") return Promise.resolve(current);
    return new Promise((resolve,reject) => { rejectSave=reject; });
  };
  v.panel.openDialog({kind:"care", id:source.entity_id});
  const form = v.root.querySelector("dialog form"), save = form.querySelector('[type="submit"]'), check = form.querySelector('button[type="button"]');
  form.querySelector("option").selected = true;
  form.querySelector('input[type="date"]').value = "2026-11-19";
  form.querySelectorAll("input")[1].value = "";
  form.dispatchEvent(new Event("submit",{cancelable:true}));
  check.click(); await tick();
  assert.equal(v.calls.filter(c=>c.type==="alarmmesh/current").length,0);
  assert.equal(save.disabled,true);
  rejectSave(Error("lost reply")); await tick();
  check.click(); await tick();
  assert.equal(save.disabled,true);
  current = {...current,care_error:false};
  check.click(); await tick();
  assert.equal(save.disabled,false);
  assert.equal(v.calls.filter(c=>c.type==="alarmmesh/care").length,1);
  v.panel.remove();
});


test("old incident link shows current smoke before the cleared history", () => {
  const v = setup("nl"), model = normal();
  const time = "2026-11-19T00:00:00Z";
  model.result.smoke = model.sources[0].status = "SMOKE_REPORTED";
  model.activity = {events:[
    {category:"alarm",kind:"incident_clear",result:"NO_SMOKE_REPORTED",correlation:"old",observed_at:time},
    {category:"alarm",kind:"incident_origin",result:"SMOKE_REPORTED",correlation:"old",source:"old-source",observed_at:time}
  ]};
  v.panel.linkedIncident = "old";
  v.panel.page = "incidents";
  v.transport.callbacks.at(-1)(model);
  const content = v.root.querySelector("main").textContent;
  assert.ok(content.includes("Detector A"));
  assert.ok(content.indexOf("Detector A") < content.indexOf("vrijgegeven"));
  assert.ok(content.includes("Eerst vastgelegd"));
  assert.equal(v.panel.linkedIncident, "old");
  assert.deepEqual(v.calls, []);
  v.panel.remove();
});
