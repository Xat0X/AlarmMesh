// Local configuration input only. Never persist confirmations, requests or HA snapshots.
const PREFIX="alarmmesh.drafts.v1:", USER=PREFIX+"user", TTL=2*60*60*1000;
const record=v=>v && typeof v==="object" && !Array.isArray(v);
const keys=(v,allowed)=>record(v) && Object.keys(v).every(k=>allowed.includes(k));
const text=(v,max=255)=>typeof v==="string" && v.length<=max;
const bool=v=>typeof v==="boolean";
const list=(v,max,check)=>Array.isArray(v) && v.length<=max && v.every(check);
const identity=v=>typeof v==="string" && /^[a-f0-9]{64}$/.test(v);
const targetValid=(kind,target)=>text(target) && (kind==="edit" ? target==="new" || /^[a-f0-9]{32}$/.test(target) : kind==="reminder" ? /^binary_sensor\.[a-z0-9_]+$/.test(target) : target==="new");
const validRecord=r=>keys(r,["kind","target","revision","signature","value","time"]) && targetValid(r.kind,r.target) && Number.isSafeInteger(r.revision) && r.revision>=0 && typeof r.signature==="string" && r.signature.length<=100000 && Number.isFinite(r.time) && r.time<=Date.now() && Date.now()-r.time<TTL && validDraft(r.kind,r.value);
const phoneProfile=p=>keys(p,["version","platform","origin","identity","critical","sound","sound_source","volume"]) && p.version===1 && ["unknown","ios","android"].includes(p.platform) && ["user","metadata"].includes(p.origin) && identity(p.identity) && bool(p.critical) && (p.platform!=="ios" || text(p.sound,100) && ["bundled","imported"].includes(p.sound_source) && Number.isFinite(p.volume) && p.volume>=0 && p.volume<=1);
const phones=v=>list(v,20,r=>keys(r,["service","enabled","profile"]) && /^mobile_app_[a-z0-9_]+$/.test(r.service) && bool(r.enabled) && (!('profile' in r) || phoneProfile(r.profile)));
const scripts=v=>list(v,20,r=>keys(r,["entity_id","identity"]) && /^script\.[a-z0-9_]+$/.test(r.entity_id) && identity(r.identity));
export function validDraft(kind,v) {
 if(kind==="settings" || kind==="maintenance") return keys(v,kind==="settings" ? ["enabled","recovery","recipients"] : ["enabled","recovery","recipients","battery","fault","unavailable","delay"]) && bool(v.enabled) && bool(v.recovery) && phones(v.recipients) && (kind!=="maintenance" || [v.battery,v.fault,v.unavailable].every(bool) && [5,15,30,60].includes(v.delay));
 if(kind==="reminder") return keys(v,["identity","enabled","date","interval","recipient"]) && identity(v.identity) && bool(v.enabled) && /^\d{4}-\d{2}-\d{2}$/.test(v.date) && [0,30,90,180,365].includes(v.interval) && /^mobile_app_[a-z0-9_]+$/.test(v.recipient);
 if(kind==="edit") return keys(v,["name","members","origins","linking","actions","unselected"]) && text(v.name,64) && list(v.members,256,s=>text(s) && /^binary_sensor\.[a-z0-9_]+$/.test(s)) && list(v.origins,256,s=>v.members.includes(s)) && list(v.unselected,256,s=>text(s)) && keys(v.linking,["enabled","bindings"]) && bool(v.linking.enabled) && list(v.linking.bindings,256,b=>keys(b,["source","target","profile","identity"]) && [b.source,b.target,b.profile].every(s=>text(s)) && identity(b.identity)) && keys(v.actions,["enabled","start","recovery"]) && bool(v.actions.enabled) && scripts(v.actions.start) && scripts(v.actions.recovery);
 return false;
}
export class Drafts {
 constructor(storage) {this.storage=storage;this.error=false;this.user=null;}
 switchUser(user) {
  if(!user || !this.storage)return;
  try {const prior=this.storage.getItem(USER);if(prior && prior!==user) {for(const key of Object.keys(this.storage)) if(key.startsWith(PREFIX) && key!==USER)this.storage.removeItem(key);}this.storage.setItem(USER,user);this.user=user;}catch {this.error=true;}
 }
 bucket(user,entry) {return user && entry ? PREFIX+user+":"+entry : null;}
 clearUser(user) {if(!user || !this.storage)return;try{for(const key of Object.keys(this.storage))if(key.startsWith(PREFIX+user+":"))this.storage.removeItem(key);if(this.storage.getItem(USER)===user)this.storage.removeItem(USER);}catch{this.error=true;}}
 read(user,entry) {
  const key=this.bucket(user,entry);if(!key || !this.storage)return {};
  try {const raw=this.storage.getItem(key) || "{}";if(raw.length>250000)throw Error();const value=JSON.parse(raw);if(!record(value))throw Error();const entries=Object.entries(value).filter(([id,r])=>validRecord(r) && id===r.kind+":"+r.target).slice(-5);const result=Object.fromEntries(entries);if(entries.length!==Object.keys(value).length)this.storage.setItem(key,JSON.stringify(result));return result;}catch {this.error=true;return {};}
 }
 put(user,entry,kind,target,revision,signature,value) {
  const key=this.bucket(user,entry);if(!key || !this.storage)return false;
  try {const row={kind,target,revision,signature,value,time:Date.now()};if(!validRecord(row))return false;const data=this.read(user,entry);const id=kind+":"+target;delete data[id];const entries=[...Object.entries(data),[id,row]].slice(-5);const raw=JSON.stringify(Object.fromEntries(entries));if(raw.length>250000)throw Error();this.storage.setItem(key,raw);return true;}catch {this.error=true;return false;}
 }
 remove(user,entry,id) {const key=this.bucket(user,entry);if(!key || !this.storage)return;try {const data=this.read(user,entry);delete data[id];this.storage.setItem(key,JSON.stringify(data));}catch{this.error=true;}}
}
