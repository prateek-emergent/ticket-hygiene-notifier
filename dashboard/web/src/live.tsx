// The live connection: one EventSource for the whole app. Keeps the notifier's status and a rolling
// buffer of recent activity; views subscribe instead of polling. EventSource reconnects on its own and
// resumes from the last event id, so nothing is missed across blips.
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, type Activity, type Status } from "./api";

const KEEP = 600; // rows held in memory for the river and the feed

interface Live {
  status: Status | null;
  recent: Activity[]; // newest last
  connected: boolean;
  version: number; // bumps on every new row: views use it to refetch
}

const LiveContext = createContext<Live>({ status: null, recent: [], connected: false, version: 0 });

export function LiveProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [recent, setRecent] = useState<Activity[]>([]);
  const [connected, setConnected] = useState(false);
  const [version, setVersion] = useState(0);
  const seeded = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let cleanup = () => {};
    // Seed the buffer with the last hour or so, then stream from its last id.
    (async () => {
      let after = 0;
      try {
        const rows = await api.activity({ limit: 400 });
        if (cancelled) return;
        rows.reverse();
        setRecent(rows);
        after = rows.length ? rows[rows.length - 1].id : 0;
      } catch { /* the stream still starts */ }
      seeded.current = true;
      if (cancelled) return;
      const es = new EventSource(`/api/stream?after=${after}`);
      es.addEventListener("open", () => setConnected(true));
      es.addEventListener("error", () => setConnected(false));
      es.addEventListener("status", (e) => setStatus(JSON.parse((e as MessageEvent).data)));
      es.addEventListener("activity", (e) => {
        const row: Activity = JSON.parse((e as MessageEvent).data);
        setRecent((prev) => (prev.length && prev[prev.length - 1].id >= row.id ? prev : [...prev.slice(-(KEEP - 1)), row]));
        setVersion((v) => v + 1);
      });
      es.addEventListener("signed_out", () => {
        es.close();
        window.dispatchEvent(new Event("hygiene:signed-out"));
      });
      cleanup = () => es.close();
    })();
    return () => { cancelled = true; cleanup(); };
  }, []);

  const value = useMemo(() => ({ status, recent, connected, version }), [status, recent, connected, version]);
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export const useLive = () => useContext(LiveContext);
