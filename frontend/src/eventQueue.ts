import { api, ApiError } from "./api";
import type { EventResult } from "./types";
export interface PendingEvent {
  client_event_id: string;
  kind: string;
  payload: Record<string, unknown>;
}
interface StoredEvent {
  version: 2;
  event: PendingEvent;
  queued_at: number;
  insertion_order: number;
}

/** Per-event durable storage: another workspace cannot overwrite unsent UUIDs. */
export class EventQueue {
  readonly key: string;
  private running: Promise<void> | null = null;
  onResult?: (r: EventResult) => void;
  onChange?: () => void;
  constructor(
    user_id: string,
    readonly session_id: string,
  ) {
    this.key = `kontur:events:${user_id}:${session_id}`;
    this.migrateLegacy();
  }
  private get eventPrefix() {
    return this.key + ":event:";
  }
  private eventKey(id: string) {
    return this.eventPrefix + id;
  }
  private validEvent(value: unknown): value is PendingEvent {
    if (!value || typeof value !== "object") return false;
    const event = value as PendingEvent;
    return (
      typeof event.client_event_id === "string" &&
      !!event.client_event_id &&
      typeof event.kind === "string" &&
      !!event.kind &&
      !!event.payload &&
      typeof event.payload === "object" &&
      !Array.isArray(event.payload)
    );
  }
  private migrateLegacy() {
    const raw = localStorage.getItem(this.key);
    if (!raw) return;
    let legacy: unknown;
    try {
      legacy = JSON.parse(raw);
    } catch {
      return;
    }
    if (
      !Array.isArray(legacy) ||
      !legacy.every((event) => this.validEvent(event))
    )
      return;
    // The old array remains until every event is copied, so quota failures can
    // be retried. Existing per-event records retain their original ordering.
    for (let index = 0; index < legacy.length; index++) {
      const event = legacy[index] as PendingEvent;
      if (localStorage.getItem(this.eventKey(event.client_event_id)) !== null)
        continue;
      const stored: StoredEvent = {
        version: 2,
        event,
        queued_at: 0,
        insertion_order: index + 1,
      };
      localStorage.setItem(
        this.eventKey(event.client_event_id),
        JSON.stringify(stored),
      );
    }
    localStorage.removeItem(this.key);
  }
  private read(): StoredEvent[] {
    const keys: string[] = [];
    for (let index = 0; index < localStorage.length; index++) {
      const key = localStorage.key(index);
      if (key?.startsWith(this.eventPrefix)) keys.push(key);
    }
    const records: StoredEvent[] = [];
    for (const key of keys) {
      const raw = localStorage.getItem(key);
      if (!raw) continue; // Another instance may have just acknowledged this UUID.
      try {
        const item = JSON.parse(raw) as StoredEvent;
        if (
          item.version === 2 &&
          this.validEvent(item.event) &&
          key === this.eventKey(item.event.client_event_id) &&
          Number.isFinite(item.queued_at) &&
          Number.isFinite(item.insertion_order)
        )
          records.push(item);
      } catch {
        /* Leave corrupt data in storage; it is never sent as an event. */
      }
    }
    return records.sort(
      (a, b) =>
        a.queued_at - b.queued_at ||
        a.insertion_order - b.insertion_order ||
        a.event.client_event_id.localeCompare(b.event.client_event_id),
    );
  }
  get count() {
    return this.read().length;
  }
  get events() {
    return this.read().map((item) => item.event);
  }
  enqueue(kind: string, payload: Record<string, unknown> = {}) {
    const event = { client_event_id: crypto.randomUUID(), kind, payload };
    const existing = this.read();
    const stored: StoredEvent = {
      version: 2,
      event,
      queued_at: Math.max(
        Date.now(),
        ...existing.map((item) => item.queued_at),
      ),
      insertion_order:
        Math.max(0, ...existing.map((item) => item.insertion_order)) + 1,
    };
    // No in-memory-only success: if storage rejects the write, the caller sees it.
    localStorage.setItem(
      this.eventKey(event.client_event_id),
      JSON.stringify(stored),
    );
    this.onChange?.();
    return event;
  }
  private outage() {
    const value = Number(localStorage.getItem(this.key + ":outage"));
    return Number.isFinite(value) && value > 0 ? value : null;
  }
  flush() {
    if (this.running) return this.running;
    this.running = this.drain().finally(() => {
      this.running = null;
    });
    return this.running;
  }
  private async drain() {
    while (true) {
      // Read shared storage on every iteration, including work queued by another
      // mounted workspace while this instance was waiting for its response.
      const event = this.read()[0]?.event;
      if (!event) return;
      let result: EventResult;
      try {
        result = await api<EventResult>(
          `/sessions/${this.session_id}/events`,
          "POST",
          event,
        );
      } catch (error) {
        if (error instanceof ApiError && error.status === 0 && !this.outage())
          localStorage.setItem(this.key + ":outage", String(Date.now()));
        throw error;
      }
      const failureAt = this.outage();
      if (failureAt) {
        const seconds = Math.min(
          86400,
          Math.max(0, (Date.now() - failureAt) / 1000),
        );
        this.enqueue("connection_restored", { offline_seconds: seconds });
        localStorage.removeItem(this.key + ":outage");
      }
      // Acknowledgement removes only this event. Never replace a whole array:
      // two tabs or an unmounted instance may be handling the same response.
      localStorage.removeItem(this.eventKey(event.client_event_id));
      this.onChange?.();
      this.onResult?.(result);
    }
  }
}
