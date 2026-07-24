import * as maplibregl from "/static/vendor/maplibre-gl.mjs";

const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const state={baseline:null,timeline:[],filtered:[],cycles:[],zones:[],evidence:[],sensors:[],index:0,map:null,timer:null,markers:[]};
const modeOptions={
  "Sentinel-2":[["true_color","สีธรรมชาติ"],["false_color","สีเท็จพืชพรรณ"],["ndvi","NDVI · ความเขียว"],["evi","EVI · พืชหนาแน่น"],["lswi","LSWI · ความชื้น"],["ndwi","NDWI · น้ำ/ความเปียก"]],
  "Sentinel-1":[["vv","Radar VV"],["vh","Radar VH"],["vh_vv_diff","Radar VH−VV"]],
};

async function api(path){
  const response=await fetch(path);
  const body=await response.json();
  if(!response.ok)throw new Error(body?.error?.message||body?.detail||"API error");
  return body.data;
}
function toast(message){$("#toast").textContent=message;$("#toast").classList.add("show");setTimeout(()=>$("#toast").classList.remove("show"),2600)}
function tag(text){return `<span class="tag">${esc(text)}</span>`}
function formatDate(value){return value?new Intl.DateTimeFormat("th-TH",{dateStyle:"medium"}).format(new Date(`${value}T00:00:00Z`)):"—"}
function range(value,unit=""){return Array.isArray(value)?`${value[0]??"—"}–${value[1]??"—"} ${unit}`:"—"}

function initMap(){
  state.map=new maplibregl.Map({
    container:"map",center:[100.274733,14.469728],zoom:16.2,
    style:{version:8,sources:{
      satellite:{type:"raster",tiles:["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],tileSize:256,attribution:"Tiles © Esri"},
      streets:{type:"raster",tiles:["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],tileSize:256,attribution:"© OpenStreetMap contributors"},
    },layers:[{id:"satellite",type:"raster",source:"satellite"},{id:"streets",type:"raster",source:"streets",layout:{visibility:"none"}}]},
  });
  state.map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),"top-right");
  state.map.on("load",()=>{
    state.map.addSource("plot",{type:"geojson",data:{type:"Feature",properties:{},geometry:{type:"Polygon",coordinates:[[[100.27361993687678,14.470451039387699],[100.27584606312321,14.470451039387699],[100.27584605591937,14.469004955303385],[100.27361994408062,14.469004955303385],[100.27361993687678,14.470451039387699]]]}}});
    state.map.addLayer({id:"plot-fill",type:"fill",source:"plot",paint:{"fill-color":"#39aa71","fill-opacity":.08}});
    state.map.addLayer({id:"plot-line",type:"line",source:"plot",paint:{"line-color":"#f0c34f","line-width":3,"line-dasharray":[2,1]}});
    addZonesAndSensors();
    updateScene();
  });
}

function addZonesAndSensors(){
  if(!state.map?.isStyleLoaded())return;
  const collection={type:"FeatureCollection",features:state.zones.map(zone=>({type:"Feature",properties:{type:zone.zone_type,id:zone.zone_id},geometry:zone.geometry}))};
  if(state.map.getSource("zones"))state.map.getSource("zones").setData(collection);
  else{
    state.map.addSource("zones",{type:"geojson",data:collection});
    state.map.addLayer({id:"zones-fill",type:"fill",source:"zones",paint:{"fill-color":["case",["==",["get","type"],"RECURRING_WETNESS_CANDIDATE"],"#3b7fa0","#c1883b"],"fill-opacity":.23}});
    state.map.addLayer({id:"zones-line",type:"line",source:"zones",paint:{"line-color":["case",["==",["get","type"],"RECURRING_WETNESS_CANDIDATE"],"#2f6e8c","#a86d22"],"line-width":2}});
  }
  state.markers.forEach(marker=>marker.remove());
  state.markers=[];
  state.sensors.forEach(sensor=>{
    const node=document.createElement("div");
    node.style.cssText="width:16px;height:16px;border-radius:50%;background:#fff;border:4px solid #176b49;box-shadow:0 2px 8px #0006";
    node.title=sensor.sensor_type;
    state.markers.push(new maplibregl.Marker({element:node}).setLngLat([sensor.longitude,sensor.latitude]).setPopup(new maplibregl.Popup().setHTML(`<b>${esc(sensor.sensor_type)}</b><p>${esc(sensor.rationale)}</p><small>PROPOSED · NOT FIELD VERIFIED</small>`)).addTo(state.map));
  });
}

function modesFor(sensor){return modeOptions[sensor]||modeOptions["Sentinel-2"]}
function refreshModes(){
  const scene=state.filtered[state.index];
  if(!scene)return;
  const previous=$("#mode").value;
  const options=modesFor(scene.sensor);
  $("#mode").innerHTML=options.map(([value,label])=>`<option value="${value}">${label}</option>`).join("");
  if(options.some(item=>item[0]===previous))$("#mode").value=previous;
}
function updateOverlay(scene){
  if(!state.map?.isStyleLoaded()||!scene?.bounds)return;
  if(state.map.getLayer("historical-image"))state.map.removeLayer("historical-image");
  if(state.map.getSource("historical-image"))state.map.removeSource("historical-image");
  const [west,south,east,north]=scene.bounds;
  const url=`/api/v1/imagery/${scene.image_id}/preview.png?mode=${encodeURIComponent($("#mode").value)}`;
  state.map.addSource("historical-image",{type:"image",url,coordinates:[[west,north],[east,north],[east,south],[west,south]]});
  state.map.addLayer({id:"historical-image",type:"raster",source:"historical-image",paint:{"raster-opacity":.78}},state.map.getLayer("plot-fill")?"plot-fill":undefined);
}

function updateScene(){
  const scene=state.filtered[state.index];
  if(!scene)return;
  refreshModes();
  updateOverlay(scene);
  $("#timeline").max=Math.max(0,state.filtered.length-1);
  $("#timeline").value=state.index;
  $("#position").textContent=`${state.index+1} / ${state.filtered.length}`;
  $("#sceneTitle").textContent=`${formatDate(scene.date)} · ${scene.sensor}`;
  $("#sceneBadges").innerHTML=`${tag(scene.provenance)} ${tag(scene.confidence)} ${tag(scene.status)}`;
  const crop=scene.derived_field_state||{};
  $("#sceneMeta").innerHTML=`<h4>Scene metadata</h4>
    <div><span>Acquired</span><b>${formatDate(scene.date)}</b></div><div><span>Sensor</span><b>${esc(scene.sensor)}</b></div>
    <div><span>Quality</span><b>${scene.quality?.toFixed?.(1)??"—"} / 100</b></div><div><span>Plot coverage</span><b>${scene.plot_coverage_percent?.toFixed?.(1)??"—"}%</b></div>
    <div><span>Vegetation</span><b>${scene.vegetation_score?.toFixed?.(3)??"—"}</b></div><div><span>Wetness candidate</span><b>${scene.water_candidate_fraction!=null?(scene.water_candidate_fraction*100).toFixed(1)+"%":"—"}</b></div>
    <div><span>Cultivated estimate</span><b>${scene.cultivated_area_estimate_rai?.toFixed?.(2)??"—"} ไร่</b></div><div><span>Derived state</span><b>${esc(crop.state)}</b></div>
    <p>${esc(crop.explanation||scene.limitations?.[0]||"Analytical observation")}<br><b>ข้อจำกัด:</b> ${esc(scene.limitations?.join(" · "))}</p>`;
  $("#filmstrip").innerHTML=state.filtered.map((item,index)=>`<button class="${index===state.index?"active":""}" data-index="${index}">${item.sensor.replace("Sentinel-","S")}<br>${esc(item.date)}</button>`).join("");
  $("#filmstrip .active")?.scrollIntoView({inline:"center",block:"nearest"});
}

function filterTimeline(){
  const sensor=$("#sensor").value,year=$("#year").value;
  state.filtered=state.timeline.filter(item=>(sensor==="all"||item.sensor===sensor)&&(year==="all"||item.date.startsWith(year)));
  state.index=Math.min(state.index,Math.max(0,state.filtered.length-1));
  if(!state.filtered.length){toast("ไม่มีภาพในตัวกรองนี้");return}
  updateScene();
}

function drawChart(){
  const data=state.timeline.filter(item=>item.sensor==="Sentinel-2"&&item.vegetation_score!=null);
  const svg=$("#chart");
  if(!data.length)return;
  const W=1100,H=280,p=45,start=new Date(data[0].date),end=new Date(data.at(-1).date),span=Math.max(1,end-start);
  const x=item=>p+(new Date(item.date)-start)/span*(W-2*p);
  const y=value=>H-p-Math.max(0,Math.min(1,value))*(H-2*p);
  const grid=[0,.25,.5,.75,1].map(v=>`<line x1="${p}" y1="${y(v)}" x2="${W-p}" y2="${y(v)}" stroke="#e3eae6"/><text x="8" y="${y(v)+4}" font-size="10" fill="#73837b">${v.toFixed(2)}</text>`).join("");
  const line=(key,color,width,dash="")=>`<polyline points="${data.filter(d=>d[key]!=null).map(d=>`${x(d)},${y(d[key])}`).join(" ")}" fill="none" stroke="${color}" stroke-width="${width}" ${dash?`stroke-dasharray="${dash}"`:""}/>`;
  const years=[...new Set(data.map(d=>d.date.slice(0,4)))].map(year=>{const item=data.find(d=>d.date.startsWith(year));return `<text x="${x(item)}" y="${H-10}" font-size="11" fill="#667970">${year}</text>`}).join("");
  svg.innerHTML=grid+line("vegetation_score","#70a78e",1.4,"3 3")+line("smoothed_vegetation_score","#155d40",3)+line("water_candidate_fraction","#3b7fa0",2)+years;
}

function render(){
  const b=state.baseline,q=b.quality_scores;
  $("#boundaryWarning").textContent=b.synthetic_boundary_warning;
  $("#runBadge").textContent=b.algorithm.version;
  const kpis=[
    ["ช่วงภาพ",`${b.period[0]} → ${b.period[1]}`,"OBSERVED"],["ภาพในคลัง",b.image_count,"OBSERVED"],["ภาพใช้วิเคราะห์",b.usable_image_count,"DERIVED"],["เฉลี่ยต่อเดือน",b.average_images_per_month,"DERIVED"],["รอบปลูกที่เป็นไปได้",b.probable_crop_cycles,"ESTIMATED"],
    ["พื้นที่ปลูก",range(b.cultivated_area_range_rai,"ไร่"),"ESTIMATED"],["พื้นที่เก็บเกี่ยว candidate",range(b.harvested_area_range_rai,"ไร่"),"ESTIMATED"],["Recurring zones",state.zones.length,"DERIVED"],["Baseline completeness",`${q.historical_baseline_completeness}%`,"DERIVED"],["Imagery confidence",b.confidence,"DERIVED"],
  ];
  $("#kpis").innerHTML=kpis.map(item=>`<article class="kpi"><span>${esc(item[0])}</span><strong>${esc(item[1])}</strong><small>${tag(item[2])} · ${esc(b.algorithm.processing_timestamp)}</small></article>`).join("");
  $("#cycleCount").textContent=`${state.cycles.length} cycles`;
  $("#cycleList").innerHTML=state.cycles.length?state.cycles.map((cycle,index)=>`<article class="cycle"><div><h4>Cycle ${index+1} · peak ${formatDate(cycle.probable_peak_date)}</h4>${tag(cycle.confidence)}</div><p>ปลูก ${formatDate(cycle.probable_planting_window[0])} – ${formatDate(cycle.probable_planting_window[1])}<br>เก็บเกี่ยว ${formatDate(cycle.probable_harvest_window[0])} – ${formatDate(cycle.probable_harvest_window[1])} · ${cycle.number_of_supporting_images} ภาพสนับสนุน</p></article>`).join(""):"<p>ยังไม่พบรอบที่มีหลักฐานเพียงพอ</p>";
  $("#yearTable").innerHTML=b.years.map(year=>`<tr><td>${year.year}</td><td>${year.probable_crop_cycles}</td><td>${range(year.cultivated_area_range_rai)}</td><td>${year.image_count}</td><td>${tag(year.confidence)}</td></tr>`).join("");
  $("#zoneCards").innerHTML=state.zones.map(zone=>`<article class="zone"><span>${tag(zone.provenance)}</span><h4>${esc(zone.zone_type)}</h4><strong>${zone.number_of_occurrences}<small> / ${zone.number_of_usable_images}</small></strong><p>พบในปี ${zone.years_detected.join(", ")||"—"} · ${esc(zone.recommended_field_check)}</p></article>`).join("");
  $("#evidenceTable").innerHTML=state.evidence.map(item=>`<tr><td><b>${esc(item.claim_label)}</b></td><td><span class="support ${item.support_level.toLowerCase()}">${esc(item.support_level)}</span></td><td>${tag(item.provenance)}</td><td>${esc(item.conclusion)}</td></tr>`).join("");
  $("#sensorCards").innerHTML=state.sensors.map(sensor=>`<article class="sensor-card">${tag(sensor.status)} ${tag(sensor.field_verification_status)}<h4>${esc(sensor.sensor_type)}</h4><p>${esc(sensor.rationale)}</p><small>${sensor.latitude.toFixed(6)}, ${sensor.longitude.toFixed(6)} · ${esc(sensor.confidence)}</small></article>`).join("");
  const labels={imagery_availability_score:"Imagery availability",image_quality_score:"Image quality",temporal_coverage_score:"Temporal coverage",spatial_coverage_score:"Spatial coverage",classification_confidence:"Classification",crop_cycle_confidence:"Crop-cycle detection",cultivated_area_confidence:"Cultivated-area estimate",historical_baseline_completeness:"Baseline completeness"};
  $("#quality").innerHTML=Object.entries(q).map(([key,value])=>`<div class="quality-row"><div><span>${labels[key]||key}</span><b>${value}%</b></div><i><b style="width:${value}%"></b></i></div>`).join("");
  $("#limitationList").innerHTML=b.limitations.map(item=>`<li>${esc(item)}</li>`).join("");
  const years=[...new Set(state.timeline.map(item=>item.date.slice(0,4)))];
  $("#year").innerHTML='<option value="all">ทุกปี</option>'+years.map(year=>`<option>${year}</option>`).join("");
  state.filtered=state.timeline;
  drawChart();
  updateScene();
}

async function load(){
  try{
    const base="/api/v1/plots/DEMO-PLOT-001";
    const [baseline,timeline,cycles,zones,evidence,sensors]=await Promise.all([
      api(`${base}/historical-baseline`),api(`${base}/imagery-timeline`),api(`${base}/crop-cycles`),
      api(`${base}/recurring-zones`),api(`${base}/baseline-evidence`),api(`${base}/sensor-location-proposals`),
    ]);
    Object.assign(state,{baseline,timeline:timeline.raw_observations,cycles,zones,evidence,sensors});
    $("#loading").hidden=true;
    $("#app").hidden=false;
    render();
    initMap();
  }catch(error){
    $("#loading").innerHTML=`<b>เปิด Historical Baseline ไม่สำเร็จ</b><p>${esc(error.message)}</p><button id="retry">ลองอีกครั้ง</button>`;
    $("#retry")?.addEventListener("click",()=>location.reload());
  }
}

$("#sensor").addEventListener("change",filterTimeline);
$("#year").addEventListener("change",filterTimeline);
$("#mode").addEventListener("change",()=>updateOverlay(state.filtered[state.index]));
$("#basemap").addEventListener("change",event=>{
  const satellite=event.target.value==="satellite";
  state.map?.setLayoutProperty("satellite","visibility",satellite?"visible":"none");
  state.map?.setLayoutProperty("streets","visibility",satellite?"none":"visible");
});
$("#timeline").addEventListener("input",event=>{state.index=Number(event.target.value);updateScene()});
$("#previous").addEventListener("click",()=>{state.index=(state.index-1+state.filtered.length)%state.filtered.length;updateScene()});
$("#next").addEventListener("click",()=>{state.index=(state.index+1)%state.filtered.length;updateScene()});
$("#play").addEventListener("click",()=>{
  if(state.timer){clearInterval(state.timer);state.timer=null;$("#play").textContent="▶ เล่น"}
  else{state.timer=setInterval(()=>{state.index=(state.index+1)%state.filtered.length;updateScene()},Number($("#speed").value));$("#play").textContent="❚❚ หยุด"}
});
$("#speed").addEventListener("change",()=>{
  if(state.timer){clearInterval(state.timer);state.timer=setInterval(()=>{state.index=(state.index+1)%state.filtered.length;updateScene()},Number($("#speed").value))}
});
$("#filmstrip").addEventListener("click",event=>{const button=event.target.closest("button[data-index]");if(button){state.index=Number(button.dataset.index);updateScene()}});
$("#menu").addEventListener("click",()=>$(".side").classList.toggle("open"));
document.querySelectorAll(".side nav a").forEach(link=>link.addEventListener("click",()=>$(".side").classList.remove("open")));
load();
