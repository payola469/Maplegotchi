import { describe, expect, it } from 'vitest';
import { connectionTransition, currentRoom, human, pollFrame, type Frame } from '../../tools/room-ui/model';
const frame:Frame={controller_pid:10,session:'owned',digest:'persisted',revision:7,at:'2026-10-14T12:15:00Z',activity:'write',moving:true,paused:true,error:null,tick:6,action:1,decision:1,grid:[44,26,16],position:[24,61],destination:['desk.writing','chair'],needs:{mood:60},goal:null,task:null,rooms:[{id:'bedroom',status:'open',x:1,y:3,w:8,h:7}],doors:[],objects:[],visual:{pose:'sit_write',facing:'left',offset:[0,0]},travel:null,events:[]};
describe('private alpha presentation contracts',()=>{
 it('keeps saved coordinates, actions and digest untouched while naming the current room',()=>{const before=structuredClone(frame);expect(currentRoom(frame)?.id).toBe('bedroom');expect(frame).toEqual(before);});
 it('does not pretend a passage belongs to a room',()=>{expect(currentRoom({...frame,position:[0,0]})).toBeUndefined();});
 it('distinguishes a new controller from a different Maple session',()=>{expect(connectionTransition(undefined,frame)).toBe('initial');expect(connectionTransition(frame,{...frame,revision:8})).toBe('same');expect(connectionTransition(frame,{...frame,controller_pid:11})).toBe('restored');expect(connectionTransition(frame,{...frame,session:'foreign'})).toBe('different');});
 it('formats identifiers without HTML or invented activity state',()=>{expect(human('work_studio')).toBe('work studio');expect(human('desk.writing')).toBe('desk · writing');expect(human('<img>')).toBe('<img>');});
});

describe('versioned opt-in committed polling',()=>{
 const display={...frame,layout_revision:1};
 const reply={contract_version:'maple-canonical-poll.v1',source:'opt_in_canonical',status:'available',display,snapshot:{identity:{maple_id:1,born_at:'2026-10-14T12:00:00Z'},life_revision:7,layout_revision:1,committed_at:frame.at,position:frame.position,activity:frame.activity,needs:frame.needs,action_counter:frame.action,tick_counter:frame.tick,decision_counter:frame.decision}};
 it('accepts the matching committed frame without ticking or changing it',()=>{const before=structuredClone(reply);expect(pollFrame(reply)).toBe(display);expect(reply).toEqual(before);});
 it('accepts equivalent UTC timestamp spellings from the backend serializers',()=>{expect(pollFrame({...reply,snapshot:{...reply.snapshot,committed_at:frame.at.replace('Z','+00:00')}})).toBe(display);});
 it.each(['life_revision','layout_revision','committed_at','activity','action_counter','tick_counter','decision_counter'])('refuses mixed %s',key=>{expect(()=>pollFrame({...reply,snapshot:{...reply.snapshot,[key]:'wrong'}})).toThrow('Mixed revision');});
 it('refuses position and needs from another revision',()=>{expect(()=>pollFrame({...reply,snapshot:{...reply.snapshot,position:[99,99]}})).toThrow('Mixed revision');expect(()=>pollFrame({...reply,snapshot:{...reply.snapshot,needs:{mood:1}}})).toThrow('Mixed revision');});
 it('does not accept unavailable or fixture data as live',()=>{expect(()=>pollFrame({...reply,status:'unavailable',snapshot:null,display:null,reason:'read_refused'})).toThrow('unavailable');expect(()=>pollFrame({...reply,source:'development_fixture'})).toThrow('Unrecognized');});
});
