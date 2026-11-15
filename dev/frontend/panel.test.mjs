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
  assert.ok(root.querySelector(".setup-guide").open);
  assert.equal(root.querySelectorAll(".setup-steps li").length, 7);
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
  assert.ok(root.querySelector('[data-check="binding"]').textContent.includes("identity or capability changed"));
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
  assert.ok(root.querySelector('[data-check="targets"]').textContent.includes("alleen rookbronnen"));
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
  data.automation = { settings: { revision: 0, enabled: false, recovery: false, recipients: [] }, recipients: [{ service: "mobile_app_simulated_phone", name: "SIMULATED phone" }], scripts: [{ entity_id: "script.simulated_start", identity: "c".repeat(64), name: "SIMULATED action" }], missing_recipients: [], episodes: [], manual_results: [], preview: { title: "AlarmMesh preview", message: "Example source and room" } };
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
  [...form.querySelectorAll("button")].find(b => b.textContent === "Send test notification").click();
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
  assert.ok(form.querySelector(".link-confirmation").textContent.includes("own physical or external consequences"));
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
  assert.ok(![...root.querySelectorAll("dialog button")].some(b => b.textContent === "Start built-in self-test"));
  panel.openDialog({ kind: "source", id: data.sources[0].entity_id });
  [...root.querySelectorAll("dialog button")].find(b => b.textContent === "Start built-in self-test").click();
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
  assert.ok(text.includes("Actuele rookmeldingen staan los")); panel.remove();
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
  const target = form.querySelectorAll('[name="link-target"]')[1]; target.options[1].selected = true;
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

test("seven guided steps follow server state, allow skipping and never enable anything", async () => {
  const { panel, root, transport, calls } = setup("nl");
  const data = featureData();
  data.review = { steps: [
    ["sources", "configured"], ["rooms", "needs_attention"], ["groups", "configured"],
    ["sounders", "not_supported"], ["notifications", "disabled"], ["scripts", "disabled"], ["check", "needs_attention"]
  ].map(([id, status]) => ({id, status, count: 0})), issues: [] };
  transport.callbacks.at(-1)(data);
  assert.equal(root.querySelectorAll(".setup-steps li").length, 7);
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
  assert.ok(missing.textContent.includes("unavailable")); assert.equal(missing.querySelectorAll("button").length,1);
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
  assert.ok(!flow.textContent.includes("recovery recorded"));
  assert.ok(root.querySelector(".incident-episode").textContent.includes("physical result unconfirmed"));
  assert.ok(root.querySelector(".selftest-result").textContent.includes("not a pass"));
  const recovered=structuredClone(data); recovered.automation.episodes[0].phase="recovery"; recovered.automation.episodes[0].updated="2026-11-15T08:05:00Z";
  transport.callbacks.at(-1)(recovered); assert.ok(root.querySelector(".incident-flow").textContent.includes("recovery recorded"));
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
