// Local alpha transport only; does not define public API/SSE or a new life engine.
import type { CharacterDirection, WorldRouteOut } from '../../src/api/world.generated';
export interface Room { id:string; status:string; x:number; y:number; w:number; h:number }
export interface Frame {
  controller_pid:number; session:string|null; digest:string; revision:number;
  at:string; activity:string; moving:boolean; paused:boolean; error:string|null;
  tick:number; action:number; decision:number; grid:[number,number,number]; position:[number,number];
  destination:string[]; needs:Record<string,number>; goal:{summary:string}|null;
  task:{tool:string;title:string}|null; rooms:Room[]; doors:{x:number;y:number;w:number;h:number}[];
  objects:{id:string;type:string;x:number;y:number;w:number;h:number;art_id:string|null;surface:string;mount_y_px:number|null;room_id:string}[];
  visual:{pose:string;facing:CharacterDirection;offset:[number,number]}; travel:(Omit<WorldRouteOut,'waypoints'> & {route:Pick<WorldRouteOut,'waypoints'>})|null; events:unknown[];
}
export const human = (value:string) => value.replaceAll('_',' ').replaceAll('.',' · ');
export function currentRoom(s:Frame):Room|undefined {
  const [x,y]=s.position,t=s.grid[2];
  return s.rooms.find(r=>x>=r.x*t&&x<(r.x+r.w)*t&&y>=r.y*t&&y<(r.y+r.h)*t);
}
export function connectionTransition(previous:Frame|undefined, next:Frame):'initial'|'same'|'restored'|'different' {
  if(!previous)return 'initial';
  if(previous.session!==next.session)return 'different';
  return previous.controller_pid===next.controller_pid?'same':'restored';
}

// Separate opt-in polling envelope. Existing public DTO/SSE types are unchanged.
interface PollSnapshot {
  identity:{maple_id:number;born_at:string}; life_revision:number; layout_revision:number;
  committed_at:string; position:[number,number]; activity:string; needs:Record<string,number>;
  action_counter:number; tick_counter:number; decision_counter:number;
}
export function pollFrame(value:unknown):Frame {
  const reply=value as {contract_version?:string;source?:string;status?:string;reason?:string;snapshot?:PollSnapshot;display?:Frame & {layout_revision:number}}|null;
  if(!reply||reply.contract_version!=='maple-canonical-poll.v1'||reply.source!=='opt_in_canonical')throw Error('Unrecognized read contract');
  if(reply.status!=='available'||!reply.snapshot||!reply.display)throw Error(`Canonical state unavailable (${reply.reason??'read refused'})`);
  const s=reply.snapshot,f=reply.display;
  if(f.revision!==s.life_revision||f.layout_revision!==s.layout_revision||Date.parse(f.at)!==Date.parse(s.committed_at)||f.activity!==s.activity||f.action!==s.action_counter||f.tick!==s.tick_counter||f.decision!==s.decision_counter||!Array.isArray(f.position)||f.position.length!==2||f.position.some((n,i)=>n!==s.position[i])||Object.entries(s.needs).some(([k,v])=>f.needs[k]!==v))throw Error('Mixed revision read refused');
  return f;
}
