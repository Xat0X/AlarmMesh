/* The same authenticated snapshot as the admin panel. Drop it on disconnect,
 * user changes or unload, including when an older subscription resolves late. */
class FamilyCard extends HTMLElement {
  static getStubConfig() { return {}; }
  getCardSize() { return 2; }
  setConfig() { this.draw(); }
  set hass(value) {
    const changed=this.ha?.connection!==value.connection || this.ha?.user?.id!==value.user?.id || this.admin!==value.user?.is_admin;
    const languageChanged=this.ha?.language!==value.language;
    this.ha=value; this.admin=value.user?.is_admin;
    if(changed && this.isConnected)this.bind();
    else if(languageChanged)this.draw();
  }
  connectedCallback() { this.bind(); }
  disconnectedCallback() { this.unbind(); }
  unbind() {
    this.token={};this.data=null;
    if(this.stop)Promise.resolve(this.stop()).catch(()=>{});
    this.stop=null;
    this.conn?.removeEventListener("disconnected",this.offline);
    this.conn?.removeEventListener("ready",this.ready);
  }
  bind() {
    this.unbind();this.draw();
    if(!this.admin || !this.ha?.connection)return;
    const conn=this.conn=this.ha.connection, token=this.token;
    this.offline=()=>{this.data=null;this.down=true;this.draw();};
    this.ready=()=>this.bind();
    conn.addEventListener("disconnected",this.offline);conn.addEventListener("ready",this.ready);
    this.down=false;
    conn.subscribeMessage(data=>{if(token===this.token && !this.down){this.data=data.available?data:null;this.draw();}}, {type:"alarmmesh/subscribe"}, {resubscribe:false})
      .then(stop=>{if(token===this.token)this.stop=stop;else Promise.resolve(stop()).catch(()=>{});}).catch(()=>{if(token===this.token)this.offline();});
  }
  draw() {
    const nl=this.ha?.language?.startsWith("nl"), data=this.data;
    const card=document.createElement("ha-card"),content=document.createElement("div");
    content.style.padding="16px";card.header="AlarmMesh";
    let href;
    if(!this.admin)content.textContent=nl?"Beheerderstoegang vereist":"Administrator access required";
    else if(!data) content.textContent=nl?"Actuele situatie onbekend":"Current situation unknown";
    else {
      const smoke=data.sources.filter(s=>s.status==="SMOKE_REPORTED");
      const missing=data.sources.filter(s=>!["SMOKE_REPORTED","NO_SMOKE_REPORTED"].includes(s.status));
      const names=items=>items.map(s=>[s.name,s.area_name].filter(Boolean).join(" · ")).join(", ");
      if(smoke.length){content.textContent=(nl?"Rook gemeld · ":"Smoke reported · ")+names(smoke);
        const episode=data.automation?.episodes.find(e=>e.group_id==="notifications" && e.phase==="start" && e.origins.some(id=>smoke.some(s=>s.entity_id===id)));
        const origin=data.activity?.events.find(e=>e.kind==="source" && e.result==="SMOKE_REPORTED" && data.activity.source_incidents?.[e.source]===e.correlation && smoke.some(s=>s.entity_id===e.source));
        href=episode || origin?.correlation ? "/alarmmesh?incident="+encodeURIComponent(episode?.id || origin.correlation) : "/alarmmesh?view=incidents";
      }else if(missing.length){content.textContent=names(missing)+(nl?" · broninformatie ontbreekt":" · source information missing");href="/alarmmesh?source="+encodeURIComponent(missing[0].entity_id);}
      else {content.textContent=data.sources.length ? data.sources.length+(nl?" melders · geen rook gemeld":" detectors · no smoke reported") : (nl?"Nog geen melders gekozen":"No detectors selected");href="/alarmmesh";}
    }
    if(href){const link=document.createElement("a");link.href=href;link.style.cssText="display:block;color:inherit";link.append(content);card.append(link);}else card.append(content);
    this.replaceChildren(card);
  }
}
if(!customElements.get("alarmmesh-family-card")){
  customElements.define("alarmmesh-family-card",FamilyCard);
  (window.customCards ||= []).push({type:"alarmmesh-family-card",name:"AlarmMesh",description:"AlarmMesh · Melders / Detectors",preview:true});
}
