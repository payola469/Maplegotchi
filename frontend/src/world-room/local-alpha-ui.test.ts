import { describe, expect, it } from 'vitest';
import { connectionTransition, currentRoom, human, type Frame } from '../../tools/room-ui/model';
const frame:Frame={controller_pid:10,session:'owned',digest:'persisted',revision:7,at:'2026-10-14T12:15:00Z',activity:'write',moving:true,paused:true,error:null,tick:6,action:1,decision:1,grid:[44,26,16],position:[24,61],destination:['desk.writing','chair'],needs:{mood:60},goal:null,task:null,rooms:[{id:'bedroom',status:'open',x:1,y:3,w:8,h:7}],doors:[],objects:[],visual:{pose:'sit_write',facing:'left',offset:[0,0]},travel:null,events:[]};
describe('private alpha presentation contracts',()=>{
 it('keeps saved coordinates, actions and digest untouched while naming the current room',()=>{const before=structuredClone(frame);expect(currentRoom(frame)?.id).toBe('bedroom');expect(frame).toEqual(before);});
 it('does not pretend a passage belongs to a room',()=>{expect(currentRoom({...frame,position:[0,0]})).toBeUndefined();});
 it('distinguishes a new controller from a different Maple session',()=>{expect(connectionTransition(undefined,frame)).toBe('initial');expect(connectionTransition(frame,{...frame,revision:8})).toBe('same');expect(connectionTransition(frame,{...frame,controller_pid:11})).toBe('restored');expect(connectionTransition(frame,{...frame,session:'foreign'})).toBe('different');});
 it('formats identifiers without HTML or invented activity state',()=>{expect(human('work_studio')).toBe('work studio');expect(human('desk.writing')).toBe('desk · writing');expect(human('<img>')).toBe('<img>');});
});
