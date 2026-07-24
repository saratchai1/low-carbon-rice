import * as maplibregl from "/static/vendor/maplibre-gl.mjs";

const BOUNDARY_WARNING = "DEMO-PLOT-001 is a synthetic demonstration boundary. It is not a cadastral, surveyed, legal, ownership, or officially verified plot boundary.";
const state = { overview:null, plots:null, observations:[], devices:[], publicData:null, imagery:[], evidence:[], reports:[], scenarios:[], run:null, map:null, timer:null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const esc = (value) => String(value ?? "—").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[char]));
const fmt = value => value ? new Intl.DateTimeFormat("th-TH",{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Bangkok"}).format(new Date(value)) : "—";
const badge = type => `<span class="provenance ${String(type).toLowerCase()}">${esc(type)}</span>`;

async function api(path, options={}) {
  const response = await fetch(path, options);
  const type = response.headers.get("content-type") || "";
  const body = type.includes("json") ? await response.json() : await response.text();
  if (!response.ok) throw new Error(typeof body === "object" ? JSON.stringify(body.detail || body) : body);
  return body?.data === undefined ? body : body.data;
}
function toast(message) {
  const node=$("#toast"); node.textContent=message; node.classList.add("show");
  clearTimeout(toast.timer); toast.timer=setTimeout(()=>node.classList.remove("show"),2800);
}
function pair(label,value,source) { return `<div><span>${esc(label)}</span><strong>${esc(value)} ${source ? badge(source) : ""}</strong></div>`; }
function route() {
  const view=(location.hash || "#command").slice(1);
  const safe=$("#view-"+view) ? view : "command";
  $$(".view").forEach(node=>node.classList.toggle("active",node.id===`view-${safe}`));
  $$("#mainNav a").forEach(node=>node.classList.toggle("active",node.dataset.view===safe));
  const active=$(`#mainNav a[data-view="${safe}"]`);
  $("#pageTitle").textContent=active?.querySelector("b")?.textContent || "Rice Twin";
  $(".sidebar").classList.remove("open");
  if (safe==="command" && state.map) setTimeout(()=>state.map.resize(),50);
}
function renderKpis() {
  $("#kpiGrid").innerHTML=state.overview.kpis.map(item=>`<article class="kpi-card">
    <div class="kpi-top"><span class="kpi-label">${esc(item.label)}</span>${badge(item.source_type)}</div>
    <strong>${esc(item.value)} <small>${esc(item.unit)}</small></strong><small>${esc(item.period)}</small>
  </article>`).join("");
}
function renderTwin() {
  const twin=state.overview.twin_state;
  $("#twinSummary").innerHTML=[
    ["ระยะข้าว",`${twin.crop_stage} · ${twin.crop_age_days} วัน`,"DERIVED"],
    ["สถานะน้ำ",twin.water_state,twin.provenance.water_level_cm],
    ["ระดับน้ำ",`${twin.water_level_cm} cm`,twin.provenance.water_level_cm],
    ["ความชื้นดิน",`${twin.soil_moisture_percent}%`,twin.provenance.soil_moisture_percent],
    ["ฝนพยากรณ์ 24 ชม.",`${twin.forecast_rainfall_24h_mm} mm`,"PUBLIC"],
    ["คำแนะนำ",twin.irrigation_recommendation,"DERIVED"],
    ["ความเชื่อมั่น",`${twin.data_confidence}%`,"DERIVED"],
  ].map(x=>pair(...x)).join("");
  $("#plotConfidence").textContent=`Confidence ${twin.data_confidence}%`;
  $("#plotTwinCards").innerHTML=[
    ["ระดับน้ำ",`${twin.water_level_cm} cm`,"เทียบผิวดิน",twin.provenance.water_level_cm],
    ["ความชื้นดิน",`${twin.soil_moisture_percent}%`,twin.soil_moisture_status,twin.provenance.soil_moisture_percent],
    ["AWD cycle",twin.awd_cycle_number,`${twin.dry_period_days} วันช่วงแห้ง`,"DERIVED"],
    ["Yield risk",twin.yield_risk,`Flood risk: ${twin.flood_risk}`,"DERIVED"],
  ].map(x=>`<article class="detail-card"><span>${x[0]}</span><strong>${x[1]}</strong><small>${esc(x[2])}</small><div>${badge(x[3])}</div></article>`).join("");
  const rule=twin.rule_evaluation;
  $("#ruleExplanation").innerHTML=`<div class="decision-box"><h3>${esc(rule.recommendation)}</h3><p>${esc(rule.disclaimer)}</p><ul>${rule.reasons.map(r=>`<li>${esc(r)}</li>`).join("")}</ul><small>${esc(rule.rule_version)} · confidence ${rule.confidence}%</small></div>`;
  renderAwd(rule);
}
function renderAwd(rule) {
  $("#awdDecision").innerHTML=`<h3>${esc(rule.recommendation)}</h3><p>ระดับความสำคัญ: <b>${esc(rule.severity)}</b></p><ul>${rule.reasons.map(x=>`<li>${esc(x)}</li>`).join("")}</ul><small>${esc(rule.disclaimer)}</small>`;
  const input=rule.inputs_used;
  $("#awdInputs").innerHTML=[
    ["ระดับน้ำ",`${input.water_level_cm} cm`,input.provenance?.water_level_cm || "DERIVED"],
    ["ความชื้นดิน",`${input.soil_moisture_percent}%`,input.provenance?.soil_moisture_percent || "DERIVED"],
    ["ฝนพยากรณ์",`${input.forecast_rainfall_24h_mm} mm`,"PUBLIC"],
    ["ระยะข้าว",input.crop_stage,"DERIVED"],
    ["ช่วงแห้ง",`${input.dry_period_days} วัน`,"DERIVED"],
    ["ความเชื่อมั่น",`${input.data_confidence}%`,"DERIVED"],
  ].map(x=>pair(...x)).join("");
}
function renderChart() {
  const values=state.observations.filter(x=>x.metric==="water_level_cm").reverse();
  const svg=$("#waterChart"); if(!values.length){svg.innerHTML="";return}
  const W=680,H=240,p=34,min=-25,max=15;
  const x=i=>p+i*(W-2*p)/Math.max(1,values.length-1);
  const y=v=>p+(max-v)*(H-2*p)/(max-min);
  const grid=[10,0,-10,-20].map(v=>`<line x1="${p}" y1="${y(v)}" x2="${W-p}" y2="${y(v)}" stroke="#dfe7e2"/><text x="3" y="${y(v)+4}" fill="#708078" font-size="10">${v}</text>`).join("");
  const points=values.map((v,i)=>`${x(i)},${y(v.value)}`).join(" ");
  const trigger=y(-15);
  svg.innerHTML=`${grid}<line x1="${p}" y1="${trigger}" x2="${W-p}" y2="${trigger}" stroke="#c17a20" stroke-dasharray="6 5"/><polyline points="${points}" fill="none" stroke="#176b49" stroke-width="3" stroke-linejoin="round"/><circle cx="${x(values.length-1)}" cy="${y(values.at(-1).value)}" r="5" fill="#176b49"/>`;
}
function renderAlerts(alerts) {
  $("#alertList").innerHTML=alerts.length ? alerts.slice(0,6).map(item=>`<div class="feed-item ${item.severity==="HIGH"?"high":""}"><strong>${esc(item.title)}</strong><span>${esc(item.detail)}</span><small>${esc(item.severity)} · ${fmt(item.created_at)} · ${esc(item.source_type)}</small></div>`).join("") : `<div class="empty-state">ไม่มี alert ที่เปิดอยู่</div>`;
}
function renderDevices() {
  $("#iotCount").textContent=`${state.devices.length} devices`;
  $("#deviceGrid").innerHTML=state.devices.map(d=>`<article class="device-card">
    <div class="device-top">${badge(d.source_type)}<span class="device-status ${d.status==="WARNING"?"warning":""}">${esc(d.status)}</span></div>
    <h3>${esc(d.device_name)}</h3><p>${esc(d.device_type)} · ${esc(d.device_id)}</p>
    <dl><div><dt>Battery</dt><dd>${esc(d.battery_percent)}%</dd></div><div><dt>Signal</dt><dd>${esc(d.signal_rssi)} dBm</dd></div><div><dt>Protocol</dt><dd>${esc(d.communication_protocol)}</dd></div><div><dt>Last seen</dt><dd>${fmt(d.last_seen_at)}</dd></div></dl>
  </article>`).join("");
}
function renderPublic() {
  const adapters=state.publicData.adapters || {};
  $("#adapterGrid").innerHTML=Object.entries(adapters).map(([key,v])=>`<article class="detail-card"><span>${esc(v.status.category || key)}</span><strong>${esc(v.status.provider)}</strong><small>โหมด ${esc(v.status.mode)} · ยังไม่เชื่อม live API</small><div>${badge("PUBLIC")}</div></article>`).join("");
  $("#publicTable").innerHTML=state.publicData.snapshots.map(x=>`<tr><td>${esc(x.category)}</td><td>${esc(x.provider)}</td><td>${fmt(x.observed_at)}</td><td>${esc(x.distance_km)} km</td><td>${esc(x.limitations)}</td></tr>`).join("");
}
const bandHelp={
  rice_true_color:"สีธรรมชาติใช้สำรวจเมฆ แนวคันนา และสภาพผิวทั่วไป ไม่ใช่ตัวชี้วัดการให้น้ำโดยตรง",
  rice_false_color:"สีเท็จเน้นพืชพรรณ ช่วยแยกความหนาแน่นและพื้นที่ข้าวจากพื้นดิน/น้ำ",
  rice_ndvi:"NDVI ใช้ดูความเขียวและ vigor ของข้าว ควรอ่านร่วมกับระยะการเจริญเติบโต",
  rice_lswi:"LSWI ไวต่อความชื้นในพืชและผิวดิน เหมาะดู candidate wetness ในนาข้าว",
  rice_ndwi:"NDWI ช่วยชี้พื้นที่น้ำขังหรือเปียก แต่เมฆ เงา และพืชหนาแน่นอาจรบกวน",
  rice_evi:"EVI เหมาะกับพืชหนาแน่นและลดผลจากบรรยากาศบางส่วน",
  stored:"ภาพ preview ที่ระบบสร้างจากไฟล์ต้นฉบับตาม metadata ที่มี"
};
function renderImagery() {
  $("#sceneSelect").innerHTML=state.imagery.map((x,i)=>`<option value="${esc(x.id)}">${i===0?"ล่าสุด · ":""}${fmt(x.acquired_at)} · ${esc(x.sensor)}</option>`).join("");
  updateImagery();
}
function updateImagery() {
  const item=state.imagery.find(x=>x.id===$("#sceneSelect").value) || state.imagery[0];
  if(!item){$("#satelliteImage").removeAttribute("src");return}
  const mode=$("#bandSelect").value;
  const allowed=item.sensor==="Sentinel-2" || mode==="stored";
  const renderMode=allowed ? mode : "stored";
  $("#imageLoading").hidden=false;
  $("#satelliteImage").src=`${item.preview_url}?render_mode=${encodeURIComponent(renderMode)}&v=${Date.now()}`;
  $("#bandHelp").textContent=bandHelp[renderMode] || bandHelp.stored;
  $("#imageMetadata").innerHTML=[
    ["วันที่รับภาพ",fmt(item.acquired_at),"PUBLIC"],["ดาวเทียม",item.sensor,"PUBLIC"],
    ["CRS",item.crs,"REFERENCE"],["ขนาด",`${item.width} × ${item.height} px`,"DERIVED"],
    ["จำนวน band",item.band_count,"REFERENCE"],["ตัดกับแปลง",item.plot_intersection?"ผ่าน":"ต้องทบทวน","DERIVED"],
    ["Processing",item.processing_status,"DERIVED"],["SHA-256",String(item.sha256).slice(0,18)+"…","DERIVED"],
  ].map(x=>pair(...x)).join("")+`<div class="info-callout">${esc(item.limitations)}</div>`;
}
function renderCarbon(carbon) {
  $("#carbonStatus").innerHTML=`<div class="method-warning"><h3>ยังไม่ได้กำหนด methodology</h3><p>${esc(carbon.message)}</p><small>${esc(carbon.limitations.join(" · "))}</small></div>
  <div class="mrv-grid">
    <article class="mrv-card"><span>Readiness</span><strong>${carbon.readiness_percent}%</strong>${badge("DERIVED")}</article>
    <article class="mrv-card"><span>Calculated estimate</span><strong>ไม่คำนวณ</strong>${badge("DERIVED")}</article>
    <article class="mrv-card"><span>Verified amount</span><strong>ไม่มี</strong>${badge("REFERENCE")}</article>
    <article class="mrv-card"><span>Issued credits</span><strong>ไม่มีการกล่าวอ้าง</strong>${badge("REFERENCE")}</article>
  </div>`;
}
function renderEvidence() {
  $("#evidenceTable").innerHTML=state.evidence.map(x=>`<tr><td><b>${esc(x.title)}</b><br><small>${esc(x.evidence_id)}</small></td><td>${esc(x.evidence_type)}</td><td>${fmt(x.captured_at)}</td><td>${badge(x.source_type)}</td><td><code>${esc(String(x.file_hash).slice(0,16))}…</code></td><td>${esc(x.review_status)}</td></tr>`).join("");
  $("#reportGrid").innerHTML=state.reports.map(x=>`<a class="report-card" href="${x.html_url}" target="_blank"><b>${esc(x.title)}</b><br><span>HTML · JSON · CSV</span></a>`).join("");
}
function renderScenarios() {
  $("#scenarioGrid").innerHTML=state.scenarios.map(x=>`<button class="scenario-card" data-scenario="${x.key}"><span class="scenario-number">SCENARIO ${x.number}</span><b>${esc(x.name_th)}</b><small>${esc(x.summary)}</small></button>`).join("");
}
async function startScenario(key) {
  clearInterval(state.timer);
  state.run=await api("/api/v1/scenarios/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scenario_key:key,speed:60,seed:20260724})});
  renderRun(); toast("เริ่มสถานการณ์แล้ว");
  state.timer=setInterval(async()=>{if(state.run?.status!=="RUNNING")return;try{await controlScenario("tick")}catch(e){clearInterval(state.timer)}},2200);
}
async function controlScenario(action) {
  if(!state.run){toast("กรุณาเลือกสถานการณ์ก่อน");return}
  state.run=await api(`/api/v1/scenarios/${state.run.id}/control`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action})});
  renderRun();
  if(state.run.status==="COMPLETED") clearInterval(state.timer);
}
function renderRun() {
  const run=state.run;if(!run)return;
  $$(".scenario-card").forEach(x=>x.classList.toggle("selected",x.dataset.scenario===run.scenario_key));
  $("#scenarioTitle").textContent=run.definition?.name_th || run.scenario_key;
  $("#scenarioStatus").textContent=run.status;
  $("#scenarioProgress").style.width=`${run.state.progress_percent || 0}%`;
  const values={tick:run.tick,...run.state,...run.outcome};
  $("#scenarioState").innerHTML=Object.entries(values).filter(([,v])=>v!==null&&typeof v!=="object").slice(0,14).map(([k,v])=>pair(k,v,k==="source_type"?null:"SIMULATED")).join("");
}
function loadDrafts(){try{return JSON.parse(localStorage.getItem("riceTwinDrafts")||"[]")}catch{return[]}}
function saveDrafts(items){localStorage.setItem("riceTwinDrafts",JSON.stringify(items));renderDrafts()}
function renderDrafts(){const drafts=loadDrafts();$("#draftCount").textContent=drafts.length;$("#draftList").innerHTML=drafts.length?drafts.map(x=>`<div class="feed-item"><strong>${esc(x.activity_type)}</strong><span>${esc(x.notes||"ไม่มีหมายเหตุ")}</span><small>${esc(x.sync_status)} · ${fmt(x.occurred_at)}</small></div>`).join(""):`<div class="empty-state">ไม่มีรายการรอซิงก์</div>`}
async function syncDrafts(){const drafts=loadDrafts();const pending=[];for(const item of drafts){try{await api("/api/plots/DEMO-PLOT-001/activities",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({activity_type:item.activity_type,occurred_at:item.occurred_at,water_level_cm:item.water_level_cm,note:`[${item.local_id}] ${item.notes||""}`,source:"offline_field_demo",evidence:{local_id:item.local_id,sync_origin:"localStorage"}})})}catch{pending.push({...item,sync_status:"SYNC_FAILED"})}}saveDrafts(pending);toast(pending.length?`ยังซิงก์ไม่ได้ ${pending.length} รายการ`:"ซิงก์เรียบร้อย")}
async function initMap() {
  try{
    state.map=new maplibregl.Map({container:"executiveMap",center:[100.274733,14.469728],zoom:15.5,style:{version:8,sources:{satellite:{type:"raster",tiles:["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],tileSize:256,attribution:"Tiles © Esri"}},layers:[{id:"satellite",type:"raster",source:"satellite"}]}});
    state.map.addControl(new maplibregl.NavigationControl(),"top-right");
    await new Promise(resolve=>state.map.once("load",resolve));
    state.map.addSource("plots",{type:"geojson",data:state.plots});
    state.map.addLayer({id:"plot-fill",type:"fill",source:"plots",paint:{"fill-color":["case",["==",["get","id"],"DEMO-PLOT-001"],"#d5ad3d","#2f7d5d"],"fill-opacity":.2}});
    state.map.addLayer({id:"plot-line",type:"line",source:"plots",paint:{"line-color":["case",["==",["get","id"],"DEMO-PLOT-001"],"#f0c44d","#f5f8f6"],"line-width":["case",["==",["get","id"],"DEMO-PLOT-001"],4,2]}});
    state.map.on("click","plot-fill",e=>new maplibregl.Popup().setLngLat(e.lngLat).setHTML(`<b>${esc(e.features[0].properties.name)}</b><p>${BOUNDARY_WARNING}</p>`).addTo(state.map));
  }catch(error){$("#executiveMap").innerHTML=`<div class="map-error">โหลดแผนที่พื้นหลังไม่สำเร็จ แต่ข้อมูลแปลงและระบบส่วนอื่นยังใช้งานได้<br>${esc(error.message)}</div>`}
}
async function loadAll() {
  $("#systemStatus").textContent="กำลังโหลดข้อมูล";
  const [overview,plots,obs,devices,alerts,pub,imagery,carbon,evidence,reports,scenarios,roles]=await Promise.all([
    api("/api/v1/overview"),api("/api/plots"),api("/api/v1/observations?metric=water_level_cm&limit=30"),
    api("/api/v1/devices"),api("/api/v1/alerts?status=OPEN"),api("/api/v1/public-data"),
    api("/api/v1/imagery"),api("/api/v1/carbon"),api("/api/v1/evidence"),api("/api/v1/reports"),
    api("/api/v1/scenarios"),api("/api/v1/roles")
  ]);
  Object.assign(state,{overview,plots,observations:obs,devices,publicData:pub,imagery,evidence,reports,scenarios});
  $("#roleSelect").innerHTML=roles.roles.map(x=>`<option>${x}</option>`).join("");$("#roleSelect").value="EXECUTIVE";
  renderKpis();renderTwin();renderChart();renderAlerts(alerts);renderDevices();renderPublic();renderImagery();renderCarbon(carbon);renderEvidence();renderScenarios();renderDrafts();
  $("#systemDot").classList.add("online");$("#systemStatus").textContent="ระบบออนไลน์ · DEMO";
  if(!state.map) initMap();
}
function bind() {
  addEventListener("hashchange",route);route();
  $("#menuButton").onclick=()=>$(".sidebar").classList.toggle("open");
  $("#refreshButton").onclick=()=>loadAll().then(()=>toast("อัปเดตข้อมูลแล้ว")).catch(showError);
  $("#evaluateButton").onclick=async()=>{try{renderAwd(await api("/api/v1/rules/evaluate"));toast("ประเมินกฎแล้ว")}catch(e){showError(e)}};
  $("#sceneSelect").onchange=updateImagery;$("#bandSelect").onchange=updateImagery;
  $("#satelliteImage").onload=()=>$("#imageLoading").hidden=true;$("#satelliteImage").onerror=()=>{$("#imageLoading").textContent="ไม่สามารถสร้างภาพโหมดนี้ได้ ลองเลือกภาพที่จัดเก็บไว้"};
  $("#scenarioGrid").onclick=e=>{const card=e.target.closest("[data-scenario]");if(card)startScenario(card.dataset.scenario).catch(showError)};
  $$("[data-scenario-action]").forEach(x=>x.onclick=()=>controlScenario(x.dataset.scenarioAction).catch(showError));
  $("#fieldForm").onsubmit=e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));const drafts=loadDrafts();drafts.push({...data,water_level_cm:Number(data.water_level_cm),local_id:crypto.randomUUID(),occurred_at:new Date().toISOString(),sync_status:"LOCAL_DRAFT"});saveDrafts(drafts);e.target.reset();toast("บันทึกฉบับร่างในเครื่องแล้ว")};
  $("#syncDraftsButton").onclick=()=>syncDrafts();
  $("#assistantToggle").onclick=()=>$("#assistantPanel").hidden=false;$("#assistantClose").onclick=()=>$("#assistantPanel").hidden=true;
  $("#assistantForm").onsubmit=async e=>{e.preventDefault();const q=$("#assistantQuestion").value;$("#assistantAnswer").textContent="กำลังค้นเหตุผลจากข้อมูลในระบบ…";try{const data=await api(`/api/v1/assistant?question=${encodeURIComponent(q)}`);$("#assistantAnswer").innerHTML=`<b>${esc(data.topic)}</b><ul>${data.answer.map(x=>`<li>${esc(x)}</li>`).join("")}</ul><small>ไม่ใช้ external LLM · ${esc(data.source_type)}</small>`}catch(error){showError(error)}};
  $("#roleSelect").onchange=()=>toast(`สลับเป็นมุมมอง ${$("#roleSelect").value} (demo UI)`);
  $("#languageButton").onclick=()=>toast("โครงสร้างสองภาษาพร้อมแล้ว; เนื้อหาสาธิตหลักเป็นภาษาไทย");
}
function showError(error){console.error(error);$("#systemDot").classList.remove("online");$("#systemStatus").textContent="ระบบมีข้อผิดพลาด";toast(`เกิดข้อผิดพลาด: ${error.message}`)}
bind();loadAll().catch(showError);
