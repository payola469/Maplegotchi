# ADR-0032: Discord conversations with the same Maple

- **Status:** Accepted — FIXED (CLAUDE.md D31)
- **Date:** 2026-10-06
- **Decided by:** owner (v0.2 autonomy program, Phase A9: Discord as a channel to the
  same Maple; ordinary messages in `#maple-chat` are conversations; slash commands are
  separate read-only utilities; the bot token never enters maplegotchi.service; Paolo's
  real messages may be high-priority; Discord downtime never stops Maple).
- **Supersedes in part:** ADR-0003 (D3) — "no chat" no longer holds for v0.2. Greet and
  Pet remain the only *room* interactions; conversation is a separate, authenticated
  channel with its own rules. No other game system is added.
- **Related:** ADR-0025/0026 (companion boundary), ADR-0030 (memory), ADR-0016 (security).

## Decision

1. **Topology**: Discord ⇄ `maple-discord` (separate service and system account, holds
   the bot token) ⇄ Maple API on 127.0.0.1 ⇄ the single writer ⇄ a replier (rule, or
   the loopback Brain companion's `/reply`). The bot token is only in
   `/etc/maple-discord/maple-discord.env`; Maplegotchi never sees it.
2. **One write endpoint**: `POST /api/conversation/messages`, enabled only when
   `MAPLE_GATEWAY_TOKEN` (≥ 32 chars, a shared secret distinct from the bot token) is set.
   It requires `Authorization: Bearer <token>` (constant-time comparison), refuses any
   browser `Origin`, accepts only `{message_id, channel: "discord", speaker: "paolo",
   text ≤ 2000}` with its own 8 KB body limit, and is idempotent by `message_id`.
   Who "paolo" is (the owner's Discord user id, the channel) is checked by the gateway.
3. **Effects (explicit rules, core)**: a message from Paolo raises social (+6) and mood
   (+2), halved for each other message in the last 10 minutes; it is a **high-priority**
   signal (`owner_message`): it interrupts a normal/low action (Maple stops to listen
   in the open area, suspending its goal for the usual resume/abandon), but never wakes
   a sleeping Maple and never overrides a critical/high response. Greet/Pet are unchanged.
4. **Replies use real context**: core builds a frozen `maple.reply.v1` context (activity
   and task, goal, phase, needs, expression, server summary, relevant memories, recent
   conversation, the message). The rule replier answers from those facts only (English,
   or Thai when the message is in Thai). An external reply is validated (non-empty,
   ≤ 1500 chars, printable) and falls back to the rule reply on any failure. Replies
   are requested outside the writer lock with a timeout.
5. **Records**: both directions are stored append-only in `conversation_message` (text,
   time, channel, speaker, replier, fallback code); each incoming message becomes a
   short-term `conversation` memory. No prompt, raw response, or model reasoning is
   stored. Conversations join the life-event stream (`conversation_received`,
   `conversation_replied`).
6. **Slash commands** (`/status`, `/needs`, `/goal`, `/journal`, `/server`, `/memory`,
   `/brain`, `/help`) are read-only and answer only Paolo: the gateway calls GET endpoints
   (`/needs` reads `/api/snapshot`, `/brain` reads `/api/brain-health` and shows only its
   status, provider, model and per-caller summary). No mutation/admin commands exist; any
   future one needs its own ADR and approval rules.
7. **Failure isolation**: Discord or gateway outages do not touch Maple; Maple outages
   produce a short "Maple can't be reached" reply from the gateway; replier failures
   produce a rule reply.

## Schema v9 and rollback

One new append-only table; forward-only; verified pre-migration copy first; ADR-0028
R1-R8 apply. Disabling the channel: unset `MAPLE_GATEWAY_TOKEN` (endpoint disappears)
and stop `maple-discord`.

## Amendment 2026-10-07 (owner-requested): reply voice and `/needs`, `/brain`

- **Replies answer the message first.** Maple's state (activity, task, goal, mood,
  needs, memories, server, history) is background: mentioned only when Paolo asks about
  it or it matters. No repeated greeting (only when Paolo greets). The rule replier
  stays deterministic and narrow: grounded answers about activity, goal, feelings and
  the server; small-integer arithmetic (`1+1=?` → `1 + 1 = 2`); otherwise a brief honest
  "not sure" or acknowledgement, never a status dump. Thai rule replies use natural
  casual sentences without forced particles.
- **External replies** (companion `reply_prompt`): claims about Maple, her room or the
  server come only from the supplied facts; ordinary general knowledge and simple
  reasoning are allowed; tools, commands, workspace files, and external/live
  information stay forbidden; no reasoning is shown. Maple speaks as a young woman, in
  the first person, not as an assistant; Thai avoids habitual จ้ะ/จ๊ะ/นะจ๊ะ/เลยจ้ะ.
  The Director prompt is unchanged (facts only).
- **`/needs`** and **`/brain`** join the read-only, owner-only slash commands (§6). No
  write, endpoint, schema or authentication change.
