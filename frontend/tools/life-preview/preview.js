/* global PIXI */
// Private preview transport only. No public DTO/SSE or fixture gate is changed.
const byId = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="preview-token"]').content;
let busy = false;
let pending = Promise.resolve();
let state;
const app = new PIXI.Application();
const needs = ["mood", "energy", "curiosity", "social"];
for (const name of needs) {
  const row = document.createElement("div"); row.className = "need";
  const label = document.createElement("label"); label.htmlFor = `need-${name}`;
  const title = document.createElement("span"); title.textContent = name[0].toUpperCase() + name.slice(1);
  const value = document.createElement("span"); value.id = `value-${name}`;
  const bar = document.createElement("progress"); bar.id = `need-${name}`; bar.max = 100;
  label.append(title, value); row.append(label, bar); byId("needs").append(row);
}
function draw(s) {
  app.stage.removeChildren().forEach((item) => item.destroy({ children: true }));
  const [width, height, t] = s.grid;
  app.renderer.resize(width * t, height * t);
  const g = new PIXI.Graphics(); app.stage.addChild(g);
  const text = (value, x, y, fill = "#b6c6b7", size = 9) => {
    const label = new PIXI.Text({text:value, style:{fontFamily:"monospace",fontSize:size,fill}});
    label.position.set(x,y); app.stage.addChild(label);
  };
  for (const room of s.rooms) {
    const open = room.status === "open";
    g.rect(room.x*t,room.y*t,room.w*t,room.h*t).fill(open ? 0xd6c5a6 : 0x3c4541);
    for (let y=room.y;y<room.y+room.h;y++) for(let x=room.x;x<room.x+room.w;x++)
      g.rect(x*t,y*t,t,t).stroke({color:open?0xc8b898:0x46514a,width:.5});
    text(room.id.replaceAll("_"," "),room.x*t+5,room.y*t+3,open?"#625f47":"#78877c");
  }
  for (const door of s.doors) g.rect(door.x*t,door.y*t,door.w*t,door.h*t).fill(0xc7b697);
  for (const object of s.objects) {
    const active = object.id === s.destination[0];
    const color = object.type.includes("bed")?0x8eaaa0:object.type.includes("sofa")?0x88a87a:object.type.includes("desk")?0xb28f6b:0x8f8266;
    g.roundRect(object.x*t+1,object.y*t+1,object.w*t-2,object.h*t-2,3).fill(color).stroke({color:active?0xeec76d:0x76694e,width:active?2:1});
  }
  if(s.travel) {
    const route=s.travel.route.waypoints;
    for(let i=0;i<route.length;i++) {
      const point=route[i];
      if(i===0) g.moveTo(point.tx*t+8,point.ty*t+13);
      else g.lineTo(point.tx*t+8,point.ty*t+13);
    }
    g.stroke({color:0x6f8468,width:1.5,alpha:.7});
  }
  // A stationary placeholder at the backend-derived feet position, no client movement clock.
  const [x,y]=s.position;
  g.ellipse(x,y,7,3).fill({color:0x243a2b,alpha:.3});
  g.rect(x-5,y-13,10,10).fill(0x547c58);
  g.rect(x-4,y-3,3,3).fill(0x493b32);g.rect(x+1,y-3,3,3).fill(0x493b32);
  g.roundRect(x-6,y-24,12,12,3).fill(0x624637);g.rect(x-4,y-20,8,7).fill(0xebc69c);
  g.rect(x-2,y-18,1,1).fill(0x3a332b);g.rect(x+2,y-18,1,1).fill(0x3a332b);
  text("Maple",Math.max(3,x-14),y-35,"#253e2c",10);
  app.render();
}
function show(s) {
  state=s; draw(s);
  byId("mode").textContent=s.error?"STOPPED":s.paused?"Paused · saved":"Live · canonical heartbeat";
  byId("notice").className=s.error?"error":"";
  byId("notice").textContent=s.error??`Saved revision ${s.revision} · ${s.moving?"Walking to ":"Doing "}${s.activity} · restart checks ${s.restarts}`;
  byId("activity").textContent=`${s.moving?"Walking → ":""}${s.activity.replaceAll("_"," ")}`;
  byId("position").textContent=`Canonical feet (${s.position.join(", ")}) · destination ${s.destination.join(" / ")}`;
  byId("room").setAttribute("aria-label",`Maple ${s.moving?"walking to":"doing"} ${s.activity} at canonical feet ${s.position.join(", ")}`);
  for(const name of needs) {byId(`need-${name}`).value=s.needs[name];byId(`value-${name}`).textContent=s.needs[name].toFixed(3);}
  byId("goal").textContent=s.goal?.summary??"No active goal";
  byId("task").textContent=s.task?`${s.task.tool}: ${s.task.title}`:"No tool task for this activity";
  byId("clock").textContent=`Preview clock (UTC): ${s.at}`;
  byId("saved").textContent=`Tick ${s.tick} · action ${s.action} · decision ${s.decision}`;
  byId("next").disabled=s.moving||busy||Boolean(s.error);
  byId("evidence").textContent=JSON.stringify({revision:s.revision,layout_revision:s.layout_revision,tick:s.tick,action:s.action,pid:s.pid,previous_pid:s.previous_pid,restarts:s.restarts,digest:s.digest,recent_action_events:s.events},null,2);
}
async function request(operation) {
  if(busy) {
    if(!operation)return;
    await pending;
    return request(operation);
  }
  busy=true;
  if(operation)for(const button of document.querySelectorAll("button"))button.disabled=true;
  pending=(async()=>{
    try {
      const response=await fetch(operation?`/${operation}`:"/state",operation?{method:"POST",headers:{"X-Preview-Token":token}}:{});
      if(!response.ok)throw new Error("Request refused; no automatic retry.");
      const next=await response.json();show(next);
    } catch(error) {
      byId("mode").textContent="Display frozen";
      byId("notice").className="error";byId("notice").textContent=`Last saved frame only — ${error.message}`;
      clearInterval(poll);
    } finally {
      busy=false;for(const button of document.querySelectorAll("button"))button.disabled=false;
      if(state)byId("next").disabled=state.moving||Boolean(state.error);
    }
  })();
  await pending;
}
let poll;
async function start() {
  await app.init({width:704,height:416,background:0x242e2b,antialias:false,resolution:1,autoStart:false});
  byId("room").append(app.canvas);
  // Rendering occurs only on received saved snapshots.
  for(const op of ["play","pause","tick","next","restart"])byId(op).addEventListener("click",()=>void request(op));
  await request();poll=setInterval(()=>{if(!busy)void request();},750);
}
void start().catch((error)=>{byId("notice").textContent=`Preview renderer unavailable: ${error.message}`;});
