/* Family-facing views. The drill reads route assessments; its clock and sources
 * belong exclusively to the open dialog. */
const node = (tag, text) => {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  return element;
};
const action = (text, handler) => {
  const element = node("button", text);
  element.type = "button";
  element.className = "button";
  element.onclick = handler;
  return element;
};
const language = panel => (nl, en) => panel._hass.language?.startsWith("nl") ? nl : en;

export function exercise(panel, host, detail, initial) {
  const say = language(panel), t = panel.t;
  const map = node("section");
  map.className = "exercise";
  host.querySelector(".drill-route-details")?.before(map);
  if (!map.isConnected) host.append(map);
  const sources = new Set([detail.id]);
  let routes = [initial], phase = 0, timer, generation = 0, paused = false;
  const stop = () => { clearTimeout(timer); timer = undefined; };
  detail.dispose = () => { generation++; stop(); };
  detail.pauseExercise = () => { generation++; stop(); paused = true; routes = []; draw(); };
  const groupName = id => panel.data?.groups.find(g => g.id === id)?.name || id;
  async function refresh() {
    stop();
    const request = ++generation;
    routes = [];
    draw();
    if (!panel.data || !map.isConnected) return;
    try {
      const next = await Promise.all([...sources].map(source => panel._hass.callWS({
        type:"alarmmesh/route", source, other_sources:[...sources].filter(id => id !== source)
      })));
      if (request !== generation || !map.isConnected) return;
      paused = next.some(r => !r.readonly || r.revision !== panel.data?.revision);
      if (!paused) routes = next;
    } catch { if (request === generation) paused = true; }
    if (request === generation) draw();
  }
  detail.resumeExercise = () => { if (paused) draw(); };
  function draw() {
    const badge = node("span", say("Stille oefening", "Silent practice"));
    badge.className = "exercise-label";
    map.replaceChildren(badge);
    if (paused || !panel.data) {
      map.append(node("h2", say("Oefening gepauzeerd", "Paused. Refresh to continue")));
      map.append(node("p", say("Haal de huidige instellingen op om de route te bekijken.", "Refresh the settings to see the route.")));
      const resume = action(say("Gegevens ophalen en hervatten", "Refresh and resume"), refresh);
      resume.disabled = !panel.data;
      map.append(resume);
      return;
    }
    const nameOf = id => {
      const src = panel.data.sources.find(source => source.entity_id === id);
      if (!src || panel.data.sources.some(other => other.entity_id !== id && other.name === src.name)) return panel.sourceName(id);
      return src.name;
    };
    const ids = [...sources], names = ids.map(nameOf);
    const title = names.length ? say("Rook bij ", "Smoke at ") + names.join(say(" en ", " and ")) : say("Oefening afgerond", "Practice complete");
    const origin = node("div");
    origin.className = "exercise-origin";
    origin.append(icon(names.length ? "smoke-detector" : "check-circle-outline"));
    const originText = node("div");
    const heading = node("h2", title);
    heading.tabIndex = -1;
    originText.append(heading, node("p", names.length
      ? say("Tijdens deze oefening blijven melders en telefoons stil.", "Detectors and phones stay silent during practice.")
      : say("Alle oefenmelders zijn weer vrijgegeven.", "Practice smoke has cleared at every detector.")));
    origin.append(originText);
    map.append(origin);

    const controls = node("div");
    controls.className = "exercise-controls";
    const focusHeading = () => map.querySelector("h2")?.focus?.({preventScroll:true});
    const step = () => { phase = 1; stop(); draw(); focusHeading(); };
    if (!phase && sources.size) {
      const next = action(say("Toon de alarmroute", "Show alarm route"), step);
      next.classList.add("primary");
      controls.append(next, action(timer ? say("Pauze", "Pause") : say("Speel af", "Play"), () => {
        if (timer) stop(); else timer = setTimeout(step, 1800);
        draw();
        map.querySelector(".exercise-controls button:last-child")?.focus?.();
      }));
    }
    if (phase && sources.size) {
      if (!routes.length) map.append(node("p", t.loading));
      else drawRoutes(names, nameOf);
    }
    if (phase) {
      for (const id of sources) {
        const clear = action(say("Laat de oefenrook verdwijnen bij ", "Clear practice smoke at ") + nameOf(id), async () => {
          sources.delete(id); await refresh(); focusHeading();
        });
        controls.append(clear);
      }
      controls.append(action(say("Opnieuw beginnen", "Start again"), async () => {
        sources.clear(); sources.add(detail.id); phase = 0; await refresh(); focusHeading();
      }));
    }
    map.append(controls);
    const remaining = panel.data.sources.filter(source => !sources.has(source.entity_id));
    if (phase && sources.size === 1 && remaining.length) {
      const chooser = node("details");
      chooser.append(node("summary", say("Voeg een tweede oefenmelder toe", "Add a second practice detector")));
      for (const source of remaining) chooser.append(action(nameOf(source.entity_id), async () => {
        sources.add(source.entity_id); await refresh(); focusHeading();
      }));
      map.append(chooser);
    }
  }

  function icon(name) {
    const element = node("ha-icon");
    element.setAttribute("icon", "mdi:" + name);
    element.setAttribute("aria-hidden", "true");
    return element;
  }

  function drawRoutes(names, nameOf) {
    const sound = new Map(), phones = new Map(), scripts = new Map();
    const excluded = new Set();
    const reasonText = reason => t[reason] || t.guide_unknown;
    function collect(rows, id, name, eligible, reason) {
      const row = rows.get(id) || {name, eligible:false, reasons:new Set()};
      row.eligible ||= eligible === true;
      row.reasons.add(reason);
      rows.set(id, row);
      return row;
    }
    const participating = new Set(sources);
    for (const [i, route] of routes.entries()) {
      for (const target of route.targets) {
        participating.add(target.source);
        for (const via of target.via) {
          const path = [names[i], groupName(via.group), nameOf(target.source)].join(" → ");
          const row = collect(sound, target.target, nameOf(target.source), target.eligible, path + " · " + reasonText(via.reason));
          if (!via.safe_stop) row.reasons.add(say("Automatisch stoppen is op deze route niet beschikbaar.", "Automatic stopping is unavailable on this route."));
        }
      }
      for (const phone of route.phones) {
        const name = panel.data.automation?.recipients?.find(r => r.service === phone.target)?.name || phone.name || phone.target;
        if (phone.selected) collect(phones, phone.target, name, phone.eligible, names[i] + " · " + reasonText(phone.reason));
        else excluded.add(name);
      }
      for (const group of route.groups) for (const script of group.scripts || []) {
        const label = groupName(group.group) + " · " + t["phase_" + script.phase] + " " + script.order + " · " + script.name;
        collect(scripts, [group.group, script.phase, script.order].join("/"), label, script.eligible, names[i] + " · " + reasonText(script.reason));
      }
    }
    for (const source of panel.data.sources) if (!participating.has(source.entity_id)) excluded.add(nameOf(source.entity_id));

    const flow = node("div");
    flow.className = "exercise-branches";
    const blocked = node("details");
    blocked.className = "exercise-blocked";
    let activeCount = 0, blockedCount = 0;
    for (const [rows, symbol, title, inactiveTitle] of [
      [sound, "volume-high", say("Zouden meeklinken", "Would sound along"), say("Meeklinken", "Linked sound")],
      [phones, "cellphone-message", say("Zouden een bericht krijgen", "Would be sent an alert"), t.notifications],
      [scripts, "lightning-bolt-outline", t.incidentActions, t.incidentActions]
    ]) {
      for (const [eligible, parent] of [[true, flow], [false, blocked]]) {
        const items = [...rows.values()].filter(item => item.eligible === eligible);
        if (!items.length) continue;
        const section = node("section"), heading = node("h3");
        heading.append(icon(symbol), node("span", eligible ? title : inactiveTitle));
        section.append(heading);
        for (const item of items) {
          const detail = node("details");
          detail.append(node("summary", item.name));
          for (const reason of item.reasons) detail.append(node("p", reason));
          section.append(detail);
        }
        parent.append(section);
        if (eligible) activeCount += items.length; else blockedCount += items.length;
      }
    }
    if (!activeCount) {
      flow.classList.add("exercise-stop");
      flow.append(icon("stop-circle-outline"), node("h3", say("De route stopt hier", "The route ends here")),
        node("p", say("Met deze instellingen zou AlarmMesh geen andere melder laten meeklinken, geen telefoonbericht sturen en geen extra actie starten.", "With these settings AlarmMesh would trigger no additional detector, phone alert or action.")));
    }
    map.append(flow);
    if (blockedCount) {
      const summary = node("summary", say("Waarom blijven deze acties uit?", "Why would these actions stay off?") + " (" + blockedCount + ")");
      blocked.prepend(summary);
      map.append(blocked);
    }
    if (!activeCount) {
      const example = node("details");
      example.className = "exercise-example";
      example.append(node("summary", say("Bekijk een voorbeeld met gekoppelde melders", "See an example with linked detectors")));
      const title = node("h3", say("Voorbeeldwoning", "Example home"));
      example.append(title, node("p", say("In dit voorbeeld zijn meeklinken en telefoonmeldingen ingeschakeld.", "Linked sound and phone alerts are enabled in this example.")));
      const start = node("strong", say("De keukenmelder meldt rook", "The kitchen detector reports smoke"));
      start.className = "exercise-demo-origin";
      const paths = node("div");
      paths.className = "exercise-branches";
      for (const [symbol, label, message] of [
        ["volume-high", say("Melder op de overloop", "Landing detector"), say("Zou meeklinken via de groep Boven.", "Would sound through the Upstairs group.")],
        ["cellphone-message", say("Gezinstelefoon", "Family phone"), say("AlarmMesh zou een rookmelding aanvragen.", "AlarmMesh would request a smoke alert.")]
      ]) {
        const section = node("section"), heading = node("h3");
        heading.append(icon(symbol), node("span", label));
        section.append(heading, node("p", message));
        paths.append(section);
      }
      example.append(start, paths);
      map.append(example);
    }
    if (excluded.size) {
      const others = node("details");
      others.append(node("summary", say("Buiten deze route", "Outside this route") + " (" + excluded.size + ")"));
      for (const label of excluded) others.append(node("p", label));
      map.append(others);
    }
  }
  draw();
}

export function incidentDetail(panel, parent, id) {
  const say=language(panel), events=(panel.data.activity?.events || []).filter(e=>e.category==="alarm" && e.correlation===id);
  const viewCurrent = action(say("Bekijk de huidige situatie","View current situation"),()=>{panel.linkedIncident=null;panel.go("incidents");});
  if (panel.data.result.smoke === "SMOKE_REPORTED") {
    const current = node("section");
    current.className = "notice incident-now";
    current.append(node("h2", panel.t.currentSituation), panel.badge(panel.data.result));
    for (const source of panel.data.sources.filter(s => s.status === "SMOKE_REPORTED")) {
      current.append(node("p", panel.sourceName(source.entity_id)));
    }
    current.append(viewCurrent);
    parent.append(current);
  }
  parent.append(node("h2",say("Incident uit deze melding","Incident from this alert")));
  if(!events.length)parent.append(node("p",say("Geen bewaarde gebeurtenissen bij deze verwijzing. De historie kan verlopen zijn.","No retained events match this link. Its history may have expired.")));
  const origins=events.filter(e=>e.kind==="incident_origin" || e.kind==="source" && e.result==="SMOKE_REPORTED").reverse();
  if(events.some(e=>e.kind==="incident_clear" || e.kind==="source" && e.result==="NO_SMOKE_REPORTED"))parent.append(node("strong",say("De geregistreerde rookmelding is vrijgegeven.","The recorded smoke report has cleared.")));
  if(origins.length){
    const first=origins.filter(e=>e.observed_at===origins[0].observed_at);
    parent.append(node("strong",say("Eerst vastgelegd: ","First recorded: ")+first.map(e=>panel.sourceName(e.source)).join(" + ")+" · "+panel.formatTime(origins[0].observed_at)));
    const active=panel.data.automation?.episodes?.find(e=>e.id===id && e.phase==="start");
    const more=panel.data.sources.filter(s=>s.status==="SMOKE_REPORTED" && active?.origins.includes(s.entity_id) && !first.some(e=>e.source===s.entity_id));
    if(more.length)parent.append(node("p",say("Ook nu rook gemeld door ", "Also reporting smoke now: ")+more.map(s=>panel.sourceName(s.entity_id)).join(", ")));
  }
  for(const event of [...events].reverse()) {
    const name=event.source ? panel.sourceName(event.source) : event.target;
    const label=event.kind==="incident_clear" ? say("Alle betrokken melders meldden geen rook meer","All involved detectors reported clear") :
      event.kind==="incident_origin" ? say("Rook waargenomen","Smoke observed") : panel.activityResult(event);
    parent.append(node("p",[panel.formatTime(event.observed_at),name,label].filter(Boolean).join(" · ")));
  }
  if (!viewCurrent.parentElement) parent.append(viewCurrent);
}

export function careView(panel,parent,source,edit=false) {
  const say=language(panel), t=panel.t, identity=source.reminder_identity;
  const health=source.capability?.details?.maintenance, record=source.selftest?.record;
  const entryId = panel.data.entry_id;
  const kinds={battery:say("Batterij vervangen","Battery replaced"),clean:say("Melder schoongemaakt","Detector cleaned"),note:say("Notitie","Note")};
  if (edit) parent.append(action(t.backToDetector + " · " + panel.sourceName(source.entity_id), () => panel.openDialog({kind:"source",id:source.entity_id})));
  parent.append(node("h3",t.maintenance));
  const percent=health?.battery_percent;
  parent.append(node("p",t.battery+" · "+(!source.identity_changed && Number.isFinite(percent) && percent>=0 && percent<=100 ? percent+"%" : t.guide_unknown)));
  if(!source.identity_changed && health?.battery_low===true)parent.append(node("p",t.lowBatteryShort));
  parent.append(node("p",t.lastTest+" · "+(record && !source.identity_changed ? (t["test_"+record.status] || t.guide_unknown)+" · "+panel.formatTime(record.started) : t.guide_unknown)));
  const rows=(panel.data.care_log || []).filter(r=>r.identity===identity).reverse();
  for(const row of rows)parent.append(node("p",[row.date,say("Zelf genoteerd","User entry"),kinds[row.kind],row.note].filter(Boolean).join(" · ")));
  if(!rows.length)parent.append(node("p",say("Nog geen onderhoud genoteerd.","No maintenance recorded yet.")));
  if(!identity || panel.data.care_error){parent.append(node("p",say("Logboek niet beschikbaar.","Journal unavailable.")));return;}
  if(!edit){parent.append(action(say("Onderhoud noteren","Record maintenance"),()=>panel.openDialog({kind:"care",id:source.entity_id})));return;}
  const form=node("form"),kind=node("select"),day=node("input"),note=node("input"),status=node("p");
  day.type="date";day.value=new Date().toLocaleDateString("sv-SE");note.maxLength=200;
  for(const [key,label] of Object.entries(kinds)){const option=node("option",label);option.value=key;kind.append(option);}
  for(const [field,title] of [[kind,t.maintenance],[day,say("Datum","Date")],[note,kinds.note]]){const label=node("label",title);label.append(field);form.append(label);}
  const save=node("button",say("Vermelding opslaan","Save entry"));save.type="submit";save.className="button primary";form.append(save,status);parent.append(form);
  const newId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,"0")).join("");
  let id = newId();
  let pending = null;
  let uncertain = false;
  const check = action(say("Controleer opgeslagen vermelding","Check saved entry"), async () => {
    if (!uncertain || !pending || check.disabled || !panel.data) return;
    check.disabled = true;
    const generation = panel.generation;
    try {
      const fresh = await panel._hass.callWS({type:"alarmmesh/current"});
      if (!form.isConnected || generation !== panel.generation) return;
      if (!fresh.available || fresh.entry_id !== entryId || fresh.care_error || !Array.isArray(fresh.care_log) ||
          !fresh.sources?.some(s => s.entity_id === source.entity_id && s.reminder_identity === identity)) {
        status.textContent = t.saveResultUnknown;
        return;
      }
      const row = fresh.care_log.find(r => r.id === id);
      if (row && Object.keys(pending).every(key => row[key] === pending[key])) {
        const same = day.value === row.date && kind.value === row.kind && note.value.trim() === row.note;
        status.textContent = [same ? say("Opgeslagen","Saved") : say("Eerdere vermelding teruggevonden. Je nieuwe invoer is nog niet opgeslagen.","Earlier entry found. Your new edits are unsaved."),row.date,kinds[row.kind],row.note].filter(Boolean).join(" · ");
        uncertain = false;
        if (same) {
          for (const field of [day,kind,note]) field.disabled = true;
        } else {
          id = newId();
          pending = null;
          delete save.dataset.started;
          save.disabled = false;
        }
      } else if (!row) {
        status.textContent = say("Geen opgeslagen vermelding gevonden. Je kunt opnieuw opslaan.","No saved entry found. You can save again.");
        pending = null;
        uncertain = false;
        delete save.dataset.started;
        for (const field of [day,kind,note,save]) field.disabled = false;
      } else {
        status.textContent = t.saveResultUnknown;
      }
    } catch {
      status.textContent = t.saveResultUnknown;
    } finally {
      check.disabled = !uncertain;
    }
  });
  check.disabled = true;
  status.setAttribute("role", "status");
  form.append(check);
  form.onsubmit = async ev => {
    ev.preventDefault();
    if (!panel.data || save.disabled || pending) return;
    if (!day.value || (kind.value === "note" && !note.value.trim())) {
      status.textContent = say("Vul de datum en de gevraagde notitie in.","Enter the date and the requested note.");
      return;
    }
    pending = {id,identity,date:day.value,kind:kind.value,note:note.value.trim()};
    save.dataset.started = "true";
    for (const field of [day,kind,note,save]) field.disabled = true;
    status.textContent = say("Bezig met opslaan…","Saving…");
    try {
      await panel._hass.callWS({type:"alarmmesh/care",source:source.entity_id,record:pending});
      status.textContent = say("Opgeslagen","Saved");
    } catch {
      uncertain = true;
      for (const field of [day,kind,note]) field.disabled = false;
      check.disabled = false;
      status.textContent = t.saveResultUnknown;
    }
  };
}
