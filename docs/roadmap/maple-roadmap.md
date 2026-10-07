MAPLE ROADMAP — ROOM / WORKSPACE / SYSTEM INVESTIGATOR



ภาพรวมลำดับการพัฒนา



1\. Maple Room

&#x20;  ↓

2\. Maple Workspace

&#x20;  ↓

3\. Maple System Investigator



เหตุผลของลำดับนี้:

\- Maple Room เป็น world/visual layer และเป็นจุดที่ activity, object, project, library และ system awareness จะมาแสดงผล

\- Maple Workspace ทำให้ Maple “สร้างสิ่งของจริง” ได้ เช่น project, file, note, code, artifact

\- Maple System Investigator ทำให้ Maple “เข้าใจเครื่องที่ตัวเองอยู่” และเชื่อมผลการวิเคราะห์เข้ากับ System Room

\- ทั้ง 3 ระบบต้องออกแบบให้เชื่อมกันตั้งแต่แรก แม้จะ implement คนละช่วง



==================================================

1\. MAPLE ROOM

==================================================



เป้าหมาย:

สร้าง “บ้าน/โลกของ Maple” ที่ไม่ใช่แค่ UI หรือ dashboard แต่เป็นพื้นที่ที่สะท้อนชีวิต กิจกรรม งาน ความรู้ และสิ่งที่ Maple สร้าง



สถานะการออกแบบ:

Concept หลักค่อนข้างชัดแล้ว

ก่อน implement จริงยังต้องทำ Final Design Spec + ตรวจ architecture ปัจจุบันก่อน



จำนวนเฟสที่แนะนำ:

6 เฟส



\--------------------------------

PHASE R1 — ROOM FOUNDATION

\--------------------------------



เป้าหมาย:

สร้างโครงหลักของโลก Maple



ขอบเขต:

\- มุมมอง 3/4 Top-down Pixel Art

\- Layout หลัก:

&#x20; - Bedroom

&#x20; - Living Room

&#x20; - Library

&#x20; - Work Studio

&#x20; - Creation Room

&#x20; - System Room

&#x20; - Central Hall

&#x20; - Future Space

\- Room graph

\- ประตู

\- walkable area

\- collision

\- interaction points

\- pathfinding

\- 4-direction movement

\- camera overview/follow/focus

\- map scale / tile/grid logic

\- day/night visual foundation



เงื่อนไข:

\- ห้องต้องขยายในอนาคตได้

\- ห้าม hardcode route ระหว่างห้อง

\- ต้องใช้ room graph

\- movement ต้องไม่ teleport เป็นค่า default

\- functional object ต้องมี interaction point



ยังไม่ต้องมี:

\- Workspace จริง

\- Coding จริง

\- System Investigator จริง

\- Advanced editor



\--------------------------------

PHASE R2 — OBJECT / ACTIVITY FOUNDATION

\--------------------------------



เป้าหมาย:

ทำให้ furniture/object มีความหมายกับชีวิต Maple จริง



Object แบ่งเป็น:

1\. Functional Object

2\. Decorative Object

3\. Persistent Creation Object



Object metadata ต้องรองรับ:

\- ID

\- type

\- room

\- position

\- orientation

\- category

\- capability tags

\- allowed activity

\- interaction point

\- facing

\- state

\- linked project/file/creation

\- movable

\- deletable

\- owner



แนวคิด Activity:

\- ยังใช้ activity หลักเดิมก่อน

\- แต่ schema ต้องรองรับ activity/task ใหม่ในอนาคต



ตัวอย่าง:

Activity = READ

Task = Study "Linux Networking.pdf"



Activity = WRITE

Task = Work on "note-organizer"



Activity = OBSERVE\_SERVER

Task = Investigate high CPU



หลักสำคัญ:

\- Activity = พฤติกรรมระดับใหญ่

\- Task = สิ่งที่ Maple กำลังทำจริง

\- Furniture = เครื่องมือ/สถานที่ที่รองรับ



เงื่อนไข:

\- ห้าม hardcode เช่น READ = bookshelf เท่านั้น

\- ควรใช้ capability tags

\- Room ต้องเพิ่ม activity ใหม่ได้โดยไม่รื้อ architecture



\--------------------------------

PHASE R3 — WORLD PERSISTENCE / GROWTH

\--------------------------------



เป้าหมาย:

ทำให้โลก Maple อยู่ต่อจริงและค่อย ๆ เติบโต



ต้องรองรับ:

\- World State

\- Object State

\- Maple Position

\- Room State

\- Project/Creation representation

\- Library representation

\- Object placement

\- Archive

\- Inventory

\- history ขั้นพื้นฐาน



หลัก:

\- Renderer ไม่ใช่ source of truth

\- world data ต้องอยู่ใน persistent data model

\- restart/deploy แล้วโลกไม่หาย



Room Growth:

\- Maple สร้างสิ่งใหม่ → ของสามารถปรากฏในห้อง

\- Bookshelf เต็มขึ้น

\- Artwork เพิ่มบนผนัง

\- Project เพิ่มบน desk/shelf

\- Creation Room โตตามสิ่งที่ Maple สร้าง



Placement:

\- Maple ย้ายของได้เฉพาะ valid placement slot

\- Core validate ทุกครั้ง

\- ห้ามบังประตู

\- ห้ามบังทางเดิน

\- ห้ามชน functional object

\- ห้ามทำ pathfinding พัง



Functional furniture สำคัญ:

Maple ย้ายไม่ได้ในช่วงแรก



\--------------------------------

PHASE R4 — ROOM EDITOR / OWNER CONTROL

\--------------------------------



เป้าหมาย:

ให้ Paolo จัดบ้านเหมือน light room-builder



Live Mode:

\- ดู Maple ใช้ชีวิต



Edit Mode:

\- จัด layout/furniture



Paolo ทำได้:

\- เพิ่ม/ลบห้อง

\- ปรับขนาด

\- ย้าย functional furniture

\- ย้ายประตู

\- เปลี่ยน layout

\- กำหนด placement zones

\- เปลี่ยน theme/lighting preset



Maple ทำได้:

\- วาง creation

\- ย้าย decoration ที่อนุญาต

\- เลือกของที่จะ display

\- จัดพื้นที่ส่วนตัวใน valid slot



Core:

\- validate collision

\- validate path

\- validate interaction point

\- validate room boundary



ควรมี:

\- grid overlay

\- drag/drop

\- snap

\- undo/redo

\- preview before save



\--------------------------------

PHASE R5 — PROJECT / LIBRARY / CREATION INTEGRATION

\--------------------------------



เป้าหมาย:

ให้ Room สะท้อนสิ่งที่ Maple ทำจริง



Work Studio:

\- project

\- coding

\- writing

\- task

\- progress



Library:

\- PDF

\- books

\- document

\- notes

\- research

\- reading progress



Creation Room:

\- artwork

\- creation

\- artifact

\- experiment



Project representation:

planned → board

active → desk

paused → side shelf

completed → archive/display



เงื่อนไข:

\- ไม่แสดงทุก file เป็น object

\- แสดงเฉพาะ project / major artifact / selected creation

\- object ต้อง link กลับไปยัง source จริงได้



\--------------------------------

PHASE R6 — ROOM POLISH / LIVING WORLD

\--------------------------------



เป้าหมาย:

ทำให้โลก Maple มีชีวิตและดูสมบูรณ์



รวม:

\- ambient animation

\- expression

\- micro-animation

\- day/night lighting

\- room-specific lighting

\- ambient sound

\- interaction SFX

\- music layer ในอนาคต

\- Digital Nature / Quiet City Edge นอกหน้าต่าง

\- UI overlay minimal

\- contextual room interaction



Maple Character:

\- female

\- 3/4 top-down pixel sprite

\- เสื้อเรียบ ๆ + กระโปรงเรียบ ๆ

\- idle

\- walk

\- sit

\- sleep

\- read

\- type/write

\- observe monitor

\- think/rest



==================================================

2\. MAPLE WORKSPACE

==================================================



เป้าหมาย:

ให้ Maple มีพื้นที่ของตัวเองที่สามารถสร้าง อ่าน เขียน แก้ไข ทดลอง และรันสิ่งที่ตัวเองสร้างได้ โดยทั้งหมดอยู่ใน boundary ที่กำหนด



จำนวนเฟสที่แนะนำ:

5 เฟส



\--------------------------------

PHASE W1 — WORKSPACE BOUNDARY

\--------------------------------



เป้าหมาย:

สร้างพื้นที่ของ Maple ที่ปลอดภัยก่อน



ต้องออกแบบก่อน implement:

\- workspace path สุดท้าย

\- folder structure

\- ownership

\- permissions

\- mount/bind boundary

\- quota

\- sandbox boundary

\- protected paths



แนวคิดพื้นที่:

อาจประมาณ:



/data/maple/world/

├── projects/

├── creations/

├── code/

├── library/

├── notes/

└── scratch/



แต่ path นี้ยังไม่ล็อกจนกว่าจะตรวจ architecture ปัจจุบัน



Permission ภายใน:

\- Read

\- Write

\- Modify

\- Delete

\- Execute



นอก Workspace:

\- Write ❌

\- Modify ❌

\- Delete ❌

\- Execute ❌



Protected:

\- /etc

\- systemd

\- Docker config

\- Maplegotchi runtime/source

\- /home/paolo

\- /data/private

\- secrets

\- tokens

\- SSH keys

\- credentials



หลักสำคัญ:

ต้อง enforce ด้วย OS/sandbox จริง

ห้ามพึ่ง prompt อย่างเดียว



\--------------------------------

PHASE W2 — FILE / LIBRARY CAPABILITY

\--------------------------------



เป้าหมาย:

ให้ Maple อ่าน/เขียนไฟล์ของตัวเองได้



รองรับ:

\- text

\- notes

\- documents

\- metadata

\- file lifecycle

\- create/read/update/delete

\- safe file naming

\- version metadata

\- archive/recovery



Library:

\- PDF

\- document

\- notes

\- reference

\- reading progress

\- status:

&#x20; - unread

&#x20; - reading

&#x20; - completed

&#x20; - reference

&#x20; - archived



ในอนาคต:

PDF → extract text → Maple read → notes → memory/reference



\--------------------------------

PHASE W3 — PROJECT SYSTEM

\--------------------------------



เป้าหมาย:

ให้ Maple ทำงานระยะยาวต่อเนื่องหลายวันได้



Project lifecycle:

\- idea

\- planned

\- active

\- paused

\- completed

\- archived



Project ควรมี:

\- project id

\- goal

\- status

\- files

\- notes

\- tasks

\- progress

\- created\_at

\- updated\_at

\- artifacts

\- history



ต้องรองรับ:

\- กลับมาทำต่อวันหลัง

\- project state ไม่หาย

\- linked object ใน Room

\- archive/restore

\- versioning



\--------------------------------

PHASE W4 — CODING SANDBOX

\--------------------------------



เป้าหมาย:

ให้ Maple เขียนและรันโค้ดของตัวเองได้



ต้องตัดสินใจก่อน:

\- runtime ที่อนุญาต

\- Python?

\- JavaScript?

\- shell?

\- package manager?

\- dependency install?

\- internet access?

\- subprocess?

\- network?

\- execution time limit

\- CPU limit

\- RAM limit

\- disk quota



Sandbox ต้องป้องกัน:

\- filesystem escape

\- symlink escape

\- privilege escalation

\- host mutation

\- network misuse

\- secret access

\- fork bomb

\- runaway process



Maple ทำได้:

\- write

\- run

\- test

\- debug

\- modify

\- rerun



แต่ทั้งหมดต้องอยู่ใน sandbox



\--------------------------------

PHASE W5 — SELF-DIRECTED CREATION

\--------------------------------



เป้าหมาย:

ให้ Maple เป็นคนคิดเองว่าจะสร้างอะไร



ตัวอย่าง:

“วันนี้อยากทำโปรแกรมสำหรับจัดโน้ตของฉัน”



Flow:

Idea

↓

Project

↓

Plan

↓

Create files

↓

Code/write

↓

Run/test

↓

Debug

↓

Save artifact

↓

Display/archive in Room

↓

Resume later



เงื่อนไข:

\- Core ยังเป็น validator

\- resource budget

\- rate limit

\- project count limit

\- stop conditions

\- approval requirement สำหรับบางประเภท

\- ไม่มีสิทธิ์ออกนอก Workspace



==================================================

3\. MAPLE SYSTEM INVESTIGATOR

==================================================



เป้าหมาย:

ให้ Maple เข้าใจ paolo-core ที่ตัวเองอาศัยอยู่ และสามารถสืบเหตุผิดปกติจาก symptom ไปถึง probable cause



จำนวนเฟสที่แนะนำ:

5 เฟส



\--------------------------------

PHASE S1 — READ-ONLY SYSTEM OBSERVABILITY

\--------------------------------



เป้าหมาย:

ให้ Maple เข้าถึงข้อมูลระบบที่อนุญาตแบบ read-only



ข้อมูลที่อาจรองรับ:

\- CPU

\- temperature

\- load average

\- RAM

\- swap

\- disk usage

\- disk I/O

\- process list

\- network

\- interface state

\- service status

\- systemd

\- selected journal logs

\- Docker health

\- Tailscale

\- backup

\- Maple health

\- Brain health

\- Discord health

\- monitoring SQLite

\- historical metrics



ต้องออกแบบ:

\- allowlist

\- data source interface

\- permissions

\- secret filtering

\- retention

\- query limits



Protected:

\- password

\- API keys

\- OAuth token

\- SSH keys

\- credential store

\- /data/private

\- secret env/config



\--------------------------------

PHASE S2 — ANOMALY DETECTION

\--------------------------------



เป้าหมาย:

ให้ Maple รู้ว่า “มีอะไรผิดปกติ”



ตัวอย่าง:

\- CPU temp สูง

\- RAM สูง

\- disk ใกล้เต็ม

\- service restart บ่อย

\- backup fail

\- network issue

\- Maple/Brain/Discord degraded



ต้องกำหนด:

\- threshold

\- baseline

\- severity

\- duration

\- recurrence

\- false-positive protection

\- cooldown



ผลลัพธ์:

Maple รู้ว่า “ควรตรวจต่อ” หรือ “แค่ transient event”



\--------------------------------

PHASE S3 — INVESTIGATION ENGINE

\--------------------------------



เป้าหมาย:

ให้ Maple สืบเหตุได้



Flow:

Observe

↓

Detect anomaly

↓

Generate hypothesis

↓

Query related data

↓

Inspect process/service/log/metrics

↓

Correlate evidence

↓

Refine hypothesis



ตัวอย่าง:

CPU temp สูง

↓

ดู CPU usage

↓

ดู process

↓

หา service

↓

ดู logs

↓

ดู disk/network/GPU ถ้าจำเป็น

↓

หาความสัมพันธ์ตามเวลา



เงื่อนไข:

\- จำกัด investigation depth

\- จำกัด command/query count

\- จำกัดเวลา

\- allowlist commands/data sources

\- ไม่มี write action



\--------------------------------

PHASE S4 — ROOT CAUSE / EXPLANATION

\--------------------------------



เป้าหมาย:

ให้ Maple สรุปว่าเกิดอะไรขึ้นอย่างมีหลักฐาน



รายงานควรมี:

\- Symptom

\- Probable cause

\- Supporting evidence

\- Confidence

\- Impact

\- What changed

\- What to check next

\- Uncertainty



ตัวอย่าง:

“CPU ร้อนขึ้นเพราะ ffmpeg ใช้งานสูงจาก Jellyfin transcoding

พบ CPU usage สูงพร้อมกับ ffmpeg process และ Jellyfin session ในช่วงเวลาเดียวกัน

ยังไม่เห็น service failure”



เงื่อนไข:

\- แยก symptom กับ cause

\- ห้ามฟันธงถ้าหลักฐานไม่พอ

\- ต้องระบุ confidence

\- บอก next investigation step ถ้ายังไม่แน่ใจ



\--------------------------------

PHASE S5 — ROOM / ALERT / FUTURE REMEDIATION

\--------------------------------



เป้าหมาย:

เชื่อม System Investigator เข้ากับโลก Maple



System Room:

\- monitor state

\- alert state

\- investigation state

\- recent finding

\- historical investigation



เมื่อ anomaly:

Maple อาจเดินไป System Room

↓

ใช้ console

↓

investigate

↓

รายงาน Paolo



Default permissions:

\- Restart service ❌

\- Kill process ❌

\- Modify config ❌

\- Change network ❌

\- Modify Docker/systemd ❌

\- Write system file ❌



อนาคตอาจเพิ่ม remediation แบบ approval-gated ได้

แต่ไม่ใช่ default



==================================================

OVERALL IMPLEMENTATION ORDER

==================================================



แนะนำลำดับรวม:



STEP 1

Maple Room Final Design Spec



STEP 2

ตรวจ architecture/code ปัจจุบัน

\- CLAUDE.md

\- ADR

\- current room

\- activity model

\- persistence

\- SQLite schema

\- systemd permissions

\- security boundary



STEP 3

Room R1 — Foundation



STEP 4

Room R2 — Object / Activity Foundation



STEP 5

Room R3 — Persistence / Growth



STEP 6

Workspace W1 — Workspace Boundary



STEP 7

Workspace W2 — File / Library



STEP 8

Workspace W3 — Project System



STEP 9

Room R4 — Room Editor



STEP 10

Room R5 — Project / Library / Creation Integration



STEP 11

Workspace W4 — Coding Sandbox



STEP 12

Workspace W5 — Self-directed Creation



STEP 13

System Investigator S1 — Read-only observability



STEP 14

System Investigator S2 — Anomaly Detection



STEP 15

System Investigator S3 — Investigation Engine



STEP 16

System Investigator S4 — Root Cause / Explanation



STEP 17

System Investigator S5 — Room / Alert Integration



STEP 18

Room R6 — Polish / Living World



==================================================

GLOBAL RULES

==================================================



1\. Maple Room, Workspace และ System Investigator ต้องใช้ architecture ที่เชื่อมกัน แต่ไม่ hard dependency กันจน subsystem หนึ่งพังแล้วอีกระบบพังทั้งหมด



2\. Core เป็น source of truth / validator

Brain เสนอ intent/action

Core ตรวจแล้วค่อย execute



3\. Maple Room เป็น visual/world layer

ไม่ใช่ source of truth



4\. Maple Workspace:

Maple มีอิสระสูงภายในพื้นที่ของตัวเอง

แต่ไม่มีสิทธิ์แก้ host system



5\. System Investigator:

อ่านและวิเคราะห์ได้กว้าง

แต่ default เป็น read-only



6\. Protected data:

Maple ต้องไม่เห็น secrets/private data ที่ไม่จำเป็น



7\. Future capability:

schema, object model, activity/task, room graph และ persistence ต้องออกแบบให้เพิ่ม capability ใหม่ได้โดยไม่ต้องรื้อระบบหลัก



8\. ทุก feature ที่เกี่ยวกับ execution ต้อง enforce ด้วย OS/sandbox/permissions จริง

ห้ามใช้ prompt เป็น security boundary



9\. ทุก data ที่ Maple สร้างต้อง backup/recover ได้



10\. ก่อน implement แต่ละ subsystem:

###### ต้องทำ design review + threat model + boundary tests ก่อน

