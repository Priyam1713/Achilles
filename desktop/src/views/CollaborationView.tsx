import { useEffect, useState } from "react";
import type { KernelClient } from "../api/kernelClient";
import type { ChainVerification, CollaborationEvent, CollaborationRoom } from "../api/types";

/**
 * Native React port of the same rooms/mentions/timeline/reactions interaction design
 * already proven in web/index.html -- not an extraction of block/buzz's actual source.
 * D-010's revisit trigger explicitly allows this: "if extraction is more expensive than
 * rebuilding, retain the interaction design and create native components; do not accept
 * a second backend to save UI effort." Buzz is Nostr-based (relay, its own identity and
 * storage layers, all excluded by D-010 itself); this project already built and shipped
 * its own native equivalent against its own kernel API, so there is nothing left in
 * Buzz's actual codebase this view would gain by extracting rather than porting the
 * proven design directly.
 */
export function CollaborationView({ client }: { client: KernelClient }) {
  const [rooms, setRooms] = useState<CollaborationRoom[] | null>(null);
  const [currentRoomId, setCurrentRoomId] = useState<string | null>(null);
  const [events, setEvents] = useState<CollaborationEvent[]>([]);
  const [chain, setChain] = useState<ChainVerification | null>(null);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { rooms: list } = await client.listRooms();
        if (cancelled) return;
        setRooms(list);
        const preferred = list.find((r) => r.id === "build-lab") || list[0];
        if (preferred) setCurrentRoomId(preferred.id);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client]);

  useEffect(() => {
    if (!currentRoomId) return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const [ev, verify] = await Promise.all([
          client.listRoomEvents(currentRoomId),
          client.verifyRoomChain(currentRoomId),
        ]);
        if (cancelled) return;
        setEvents(ev.events);
        setChain(verify);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    refresh();
    const id = setInterval(refresh, 4000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [client, currentRoomId]);

  const room = rooms?.find((r) => r.id === currentRoomId);

  const send = async () => {
    const content = message.trim();
    if (!content || !currentRoomId) return;
    setSending(true);
    try {
      await client.postMessage(currentRoomId, "owner", content);
      setMessage("");
      const ev = await client.listRoomEvents(currentRoomId);
      setEvents(ev.events);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  if (error) return <div className="panel error">{error}</div>;
  if (!rooms) return <div className="panel">Loading rooms...</div>;

  const visible = events.filter(
    (e) => e.event_type === "message.posted" || e.event_type === "job.failed",
  );

  return (
    <div className="panel collab-panel">
      <div className="collab-head">
        <div className="title">Collaboration rooms</div>
        <div className="chain">
          {chain
            ? chain.valid
              ? `chain verified · ${chain.events} events`
              : `CHAIN BROKEN · ${chain.broken_at}`
            : "verifying..."}
        </div>
      </div>
      <div className="collab-grid">
        <nav className="rooms">
          {rooms.map((r) => (
            <button
              key={r.id}
              className={`room-button ${r.id === currentRoomId ? "active" : ""}`}
              onClick={() => setCurrentRoomId(r.id)}
            >
              <b># {r.name}</b>
              <small>{r.purpose}</small>
            </button>
          ))}
        </nav>
        <main className="room-main">
          {room && (
            <>
              <div className="room-meta">
                <h2>{room.name}</h2>
                <div className="members">
                  {room.members
                    .filter((m) => m.kind !== "system")
                    .map((m) => (
                      <span key={m.id} className={`member ${m.kind}`} title={m.display_name}>
                        @{m.id}
                      </span>
                    ))}
                </div>
              </div>
              <div className="timeline">
                {visible.length === 0 && (
                  <div className="empty">No messages yet. Mention an agent to begin.</div>
                )}
                {visible.map((e) => (
                  <article
                    key={e.event_id}
                    className={`event ${e.event_type === "job.failed" ? "failure" : ""}`}
                  >
                    <div className="who">
                      {e.actor_id} ·{" "}
                      {new Date(Number(e.created_at_ns) / 1e6).toLocaleTimeString()}
                    </div>
                    <div className="body">
                      {e.event_type === "job.failed"
                        ? `Job failed: ${String(e.payload.error)}`
                        : String(e.payload.content)}
                    </div>
                  </article>
                ))}
              </div>
              <div className="composer">
                <textarea
                  rows={2}
                  placeholder="Try: @swift summarize our next step"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <button disabled={sending} onClick={send}>
                  {sending ? "Sending..." : "Send"}
                </button>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
