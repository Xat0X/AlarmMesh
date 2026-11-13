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
  const js = await readFile(new URL("../../custom_components/alarmmesh/frontend/panel.js", import.meta.url), "utf8");
  assert.ok(!/innerHTML|window\.openai|Tweak|https?:\/\//.test(js));
});
