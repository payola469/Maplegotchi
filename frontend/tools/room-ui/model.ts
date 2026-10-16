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
