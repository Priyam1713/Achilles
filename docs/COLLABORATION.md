# Native collaboration plane

This subsystem takes inspiration from the strongest public ideas in Block's Apache-2.0
[Buzz repository](https://github.com/block/buzz)—humans and agents sharing rooms,
mention-driven work, durable conversation, canvases and visible audit history—but it does
not embed, install, fork or depend on Buzz.

## What is native here

- `Commons` and `Build Lab` bootstrap rooms
- human, system and routed-agent identities
- room membership
- messages and threaded replies
- reactions
- versioned Markdown canvases
- durable `@agent` dispatch through the existing job journal
- automatic result/failure events in the source thread
- per-room SHA-256 event chains
- one SQLite database at `state/collaboration.db`

The default agents are routing personalities, not separate ungoverned processes:

- `@swift`: fast coordination through `orchestration_fast`
- `@sage`: smart systems synthesis through `reasoning`
- `@forge`: deep engineering review through `coding`

Their model choice remains replaceable and hardware-aware because the normal capability
router selects the engine and checkpoint.

## Authority boundary

Rooms coordinate work; they do not authorize it. A mention creates a `chat` job only. The
room transcript and shared canvas are sent as untrusted context, and generated responses are
stored as untrusted model output. Neither may directly mutate a workspace, execute a command,
post to an external network or access credentials.

The collaboration database is separate from semantic memory. A future learning step may
promote a verified decision into durable memory, but conversation is never silently promoted.

## API map

- `GET /collaboration/status`
- `GET|POST /collaboration/identities`
- `GET|POST /collaboration/rooms`
- `POST /collaboration/rooms/{room_id}/members/{identity_id}`
- `GET /collaboration/rooms/{room_id}/events`
- `POST /collaboration/rooms/{room_id}/messages`
- `POST /collaboration/rooms/{room_id}/reactions`
- `GET|PUT /collaboration/rooms/{room_id}/canvas`
- `GET /collaboration/rooms/{room_id}/verify`

Configuration lives in `configs/collaboration.yaml`. Additional agents must declare a
capability, routing mode and system prompt; membership is explicit per room.

## Deliberately omitted

- external relays or federation
- Nostr identities
- Postgres, Redis and MinIO
- bundled shell/MCP authority
- parallel agent subprocess pools
- a second workflow, memory, policy or secrets system

Those would duplicate kernel responsibilities or add background resource cost without
improving this single-workstation architecture.
