const slides=[...document.querySelectorAll(".slide")];
let index=0,runId=null,timer=null;
function show(next){index=(next+slides.length)%slides.length;slides.forEach((s,i)=>s.classList.toggle("active",i===index));document.querySelector("#counter").textContent=`${index+1} / ${slides.length}`}
document.querySelector("#prev").onclick=()=>show(index-1);
document.querySelector("#next").onclick=()=>show(index+1);
document.querySelector("#fullscreen").onclick=()=>document.documentElement.requestFullscreen?.();
addEventListener("keydown",e=>{if(["ArrowRight"," ","PageDown"].includes(e.key))show(index+1);if(["ArrowLeft","PageUp"].includes(e.key))show(index-1);if(e.key==="Escape"&&document.fullscreenElement)document.exitFullscreen()});
async function request(path,options={}){const response=await fetch(path,options);const body=await response.json();if(!response.ok)throw new Error(body.detail||"API error");return body.data}
function render(run){document.querySelector("#scenarioBar").style.width=`${run.state.progress_percent||0}%`;document.querySelector("#pWater").textContent=run.state.water_level_cm??"—";document.querySelector("#pDecision").textContent=run.state.recommendation||"MONITOR";const o=run.outcome||{};document.querySelector("#scenarioNarrative").textContent=o.water_saved_m3?`ฝนมาถึง: หลีกเลี่ยงการสูบน้ำ ${o.pumping_hours_avoided} ชม. ประหยัดน้ำโดยประมาณ ${o.water_saved_m3} m³ (DERIVED)`:(run.state.evidence_event||"กำลังติดตามข้อมูล")}
document.querySelector("#runScenario").onclick=async()=>{clearInterval(timer);const run=await request("/api/v1/scenarios/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scenario_key:"wait_rainfall",speed:60,seed:20260724})});runId=run.id;render(run);timer=setInterval(async()=>{const tick=await request(`/api/v1/scenarios/${runId}/control`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"tick"})});render(tick);if(tick.status==="COMPLETED")clearInterval(timer)},1200)};
show(0);
