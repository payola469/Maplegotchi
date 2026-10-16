import { Application, Container, Graphics, Sprite, Text } from 'pixi.js';
import { artManifest } from '../../src/world-room/generated';
import { loadAtlasArt, type AtlasArt } from '../../src/world-room/atlas';
import { clampTranslation, deviceZoom } from '../../src/world-room/camera';
import { floorVariant, overview, routeSample } from '../../src/world-room/presentation';
import { currentRoom, human, connectionTransition, pollFrame, type Frame, type Room } from './model';
import './room.css';
const el=<T extends HTMLElement=HTMLElement>(id:string):T=>{const node=document.getElementById(id);if(!node)throw Error(`Missing ${id}`);return node as T;};
let token=document.querySelector<HTMLMetaElement>('meta[name="preview-token"]')?.content??'';
let state:Frame|undefined, busy=false, online=false, needsToken=false, focus:string|null=null;
const app=new Application();let art:AtlasArt;
const host=el('room');
const names=['mood','energy','curiosity','social'];
for(const name of names){
 const row=document.createElement('div');row.className='need';const label=document.createElement('label');label.htmlFor=`need-${name}`;
 const title=document.createElement('span');title.textContent=human(name);const value=document.createElement('span');value.id=`value-${name}`;
 const bar=document.createElement('progress');bar.id=`need-${name}`;bar.max=100;label.append(title,value);row.append(label,bar);el('needs').append(row);
}
function paint(s:Frame){
 app.stage.removeChildren().forEach(child=>child.destroy({children:true}));
 const dpr=window.devicePixelRatio||1,w=Math.round(host.clientWidth*dpr),h=Math.round(host.clientHeight*dpr);
 app.renderer.resize(w,h);app.canvas.style.width=`${host.clientWidth}px`;app.canvas.style.height=`${host.clientHeight}px`;
 const t=s.grid[2];const room=s.rooms.find(r=>r.id===focus);const fallback=!overview(w,h,s.grid[0]*t,s.grid[1]*t,dpr);
 const target=room??(fallback?currentRoom(s):undefined);const bounds=target?{x:(target.x-1)*t,y:(target.y-3)*t,w:(target.w+2)*t,h:(target.h+4)*t}:{x:0,y:0,w:s.grid[0]*t,h:s.grid[1]*t};
 const fit=overview(w,h,bounds.w,bounds.h,dpr),zoom=fit?.zoom??deviceZoom(1,dpr);
 const crop=clampTranslation({x:w/2-(s.position[0]-bounds.x)*zoom,y:h/2-(s.position[1]-bounds.y)*zoom},{width:w,height:h},{x:0,y:0,w:bounds.w,h:bounds.h},zoom);
 const view=fit??{zoom,...crop};
 const world=new Container();world.scale.set(view.zoom);world.position.set(view.x-bounds.x*view.zoom,view.y-bounds.y*view.zoom);app.stage.addChild(world);
 const base=new Graphics().rect(0,0,s.grid[0]*t,s.grid[1]*t).fill(0xb2a18b);world.addChild(base);
 for(const r of s.rooms){
  if(r.status!=='open'){base.rect(r.x*t,r.y*t,r.w*t,r.h*t).fill(0xc1b7a6);continue;}
  for(let y=r.y;y<r.y+r.h;y++)for(let x=r.x;x<r.x+r.w;x++){
   const tile=new Sprite(art.floor(floorVariant(r.id,x,y)));tile.position.set(x*t,y*t);world.addChild(tile);
  }
 }
 for(const door of s.doors)base.rect(door.x*t,door.y*t,door.w*t,door.h*t).fill(0xcbb897);
 // Existing atlas parts and canonical instance origins; no replacement geometry.
 const manifest=artManifest as Record<string,{parts:{part:string;sort?:string}[]}>;
 const entities=new Container({sortableChildren:true});world.addChild(entities);
 for(const o of s.objects){
  if(!o.art_id)continue;
  const part=art.part(o.art_id,'base');const sprite=new Sprite(part.texture);const region=s.rooms.find(r=>r.id===o.room_id);const anchorY=o.surface==='north_band'&&region?region.y*t-(o.mount_y_px??0):(o.y+o.h)*t;sprite.position.set(o.x*t-part.anchor.x,anchorY-part.anchor.y);sprite.zIndex=(o.y+o.h)*t;entities.addChild(sprite);
  for(const extra of manifest[o.art_id]?.parts??[]){if(extra.sort!=='above_occupant')continue;const cover=art.part(o.art_id,extra.part);const overlay=new Sprite(cover.texture);overlay.position.set(o.x*t-cover.anchor.x,anchorY-cover.anchor.y);overlay.zIndex=sprite.zIndex+1;entities.addChild(overlay);}
 }
 const marker=new Graphics();world.addChild(marker);const destination=s.objects.find(o=>o.id===s.destination[0]);
 if(destination)marker.roundRect(destination.x*t-2,destination.y*t-2,destination.w*t+4,destination.h*t+4,3).stroke({color:0xd9773a,width:1});
 // Coordinates are saved backend feet. No interpolation clock or client simulation.
 const sampled=s.travel?routeSample({...s.travel,...s.travel.route},Date.parse(s.at),{width_tiles:s.grid[0],height_tiles:s.grid[1],tile_size_px:t,feet_in_tile_px:[8,13]},s.visual.facing):null;
 const direction=s.moving&&sampled?sampled.facing:s.visual.facing;
 const pose=s.moving?'walk':s.visual.pose,frame=s.moving&&sampled?sampled.frame:0;const sprite=new Sprite(art.body(direction,frame,pose));
 const offset=s.moving?[0,0]:s.visual.offset; sprite.position.set(s.position[0]-16+(offset[0]??0),s.position[1]-47+(offset[1]??0));sprite.zIndex=(!s.moving&&destination?(destination.y+destination.h)*t:(Math.floor((s.position[1]-13)/t)+1)*t)+.5;entities.addChild(sprite);
 const anchor=art.faceAnchor(direction,frame,pose);
 if(anchor){const face=new Sprite(art.face(pose==='lie_sleep'?'sleepy':'calm',direction));face.position.set(sprite.x+anchor.x,sprite.y+anchor.y);face.zIndex=sprite.zIndex+.1;entities.addChild(face);}
 const label=new Text({text:'Maple',style:{fontFamily:'system-ui',fontSize:9,fill:0x2f5d46}});label.position.set(s.position[0]-13,s.position[1]+5);world.addChild(label);
 app.render();
}
function controls(){for(const op of ['play','pause','tick','next','restart'])el<HTMLButtonElement>(op).disabled=busy||!online||Boolean(state?.error)||(op==='next'&&Boolean(state?.moving));}
function render(s:Frame){
 const transition=connectionTransition(state,s);
 if(transition==='different')throw Error('Different session detected; display frozen');
 if(transition==='restored')needsToken=true;
 state=s;online=true;paint(s);
 el('connection').textContent='Connected · local';el('connection').className='';
 el('mode').textContent=s.error?'Runtime stopped':s.paused?'Paused · saved':'Live heartbeat';
 el('room-name').textContent=human(currentRoom(s)?.id??'Door passage');
 el('activity').textContent=`${s.moving?'Walking → ':''}${human(s.activity)}`;
 el('destination').textContent=`Destination · ${human(s.destination.join(' / '))}`;
 host.setAttribute('aria-label',`Maple ${s.moving?'walking to':'doing'} ${s.activity}; canonical feet ${s.position.join(', ')}; ${currentRoom(s)?.id??'passage'}`);
 for(const name of names){el<HTMLProgressElement>(`need-${name}`).value=s.needs[name]??0;el(`value-${name}`).textContent=(s.needs[name]??0).toFixed(3);}
 el('mood').textContent=`Mood · ${(s.needs.mood??0).toFixed(1)} / 100`;
 el('goal').textContent=s.goal?.summary??'A quiet moment';el('task').textContent=s.task?`${human(s.task.tool)} · ${s.task.title}`:'No active tool task';
 el('saved').textContent=`✓ SQLite saved · revision ${s.revision}`;el('clock').textContent=`Tick ${s.tick} · action ${s.action} · ${s.at}`;
 el('notice').textContent=s.error??(transition==='restored'?'Controller reconnected. Same saved life restored; no command replayed.':'Position, needs and activities come from the saved canonical runtime.');el('notice').className=s.error?'error':'';
 el('evidence').textContent=JSON.stringify(s,null,2);buildRooms(s.rooms);controls();
}
function buildRooms(rooms:Room[]){
 const list=el('room-list');list.replaceChildren();
 for(const r of rooms){const b=document.createElement('button');b.textContent=`${r.status==='open'?'':'Closed · '}${human(r.id)}`;b.setAttribute('aria-current',r.id===(state?currentRoom(state)?.id:undefined)?'location':'false');b.onclick=()=>{focus=r.id;if(state)paint(state);};list.append(b);}
 const all=document.createElement('button');all.textContent='Overview';all.onclick=()=>{focus=null;if(state)paint(state);};list.append(all);
}
async function renewToken(){const reply=await fetch('/',{signal:AbortSignal.timeout(6000)});if(!reply.ok)throw Error('Controller page unavailable');const doc=new DOMParser().parseFromString(await reply.text(),'text/html');const fresh=doc.querySelector<HTMLMetaElement>('meta[name="preview-token"]')?.content;if(!fresh)throw Error('Controller token unavailable');token=fresh;needsToken=false;}
async function request(operation?:string){
 if(busy)return;busy=true;controls();
 try{
  if(operation&&needsToken)await renewToken();
  const response=await fetch(operation?`/${operation}`:'/local-alpha/v1/state',{...(operation?{method:'POST',headers:{'X-Preview-Token':token}}:{}),signal:AbortSignal.timeout(65000)});
  if(!response.ok)throw Error(`Request refused (${response.status}); command was not retried`);
  const body:unknown=await response.json();render(operation?body as Frame:pollFrame(body));
 }catch(error){online=false;needsToken=true;el('connection').textContent='Offline / unavailable · last committed frame';el('connection').className='offline';el('mode').textContent='Stale · no live updates';el('saved').textContent=state?`Last confirmed revision ${state.revision}`:'No confirmed state';el('notice').className='error';el('notice').textContent=`${error instanceof Error?error.message:'Connection lost'}. Reconnecting read-only; no actions are replayed.`;}
 finally{busy=false;controls();}
}
async function start(){
 await app.init({width:704,height:416,background:0xe9e1d3,antialias:false,resolution:1,autoStart:false,roundPixels:true});
 art=await loadAtlasArt();host.append(app.canvas);
 for(const op of ['play','pause','tick','next','restart'])el(op).addEventListener('click',()=>void request(op));
 new ResizeObserver(()=>{if(state)paint(state);}).observe(host);
 await request();setInterval(()=>void request(),1000);
}
void start().catch(error=>{el('notice').textContent=`Renderer unavailable: ${String(error)}`;});
