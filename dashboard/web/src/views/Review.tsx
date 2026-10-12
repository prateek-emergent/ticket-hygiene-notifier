// The review queue: your team's unreviewed alerts, one at a time. The next one is already loaded.
// J / K move, C marks correct, F marks a false alarm; after a verdict the queue moves on by itself.
import { useEffect, useRef, useState } from "react";
import { api, type Alert, type AlertDetail } from "../api";
import { useScope } from "../scope";
import { Empty, Failed, Loading } from "../parts/Common";
import { AlertBody } from "./Alert";

export function ReviewView() {
  const { team } = useScope();
  const [queue, setQueue] = useState<Alert[] | null>(null);
  const [i, setI] = useState(0);
  const [current, setCurrent] = useState<AlertDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cache = useRef(new Map<number, Promise<AlertDetail>>());

  const detail = (id: number) => {
    if (!cache.current.has(id)) cache.current.set(id, api.alert(id));
    return cache.current.get(id)!;
  };

  useEffect(() => {
    setQueue(null); setI(0); setCurrent(null); cache.current.clear();
    api.alerts({ team, review: "unreviewed", limit: 100 }).then((r) => setQueue(r.items)).catch((e) => setError(String(e.message ?? e)));
  }, [team]);

  useEffect(() => {
    if (!queue || !queue[i]) { setCurrent(null); return; }
    let live = true;
    detail(queue[i].id).then((d) => live && setCurrent(d)).catch((e) => setError(String(e.message ?? e)));
    if (queue[i + 1]) void detail(queue[i + 1].id); // preload the next one
    return () => { live = false; };
  }, [queue, i]);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLInputElement) return;
      if (e.key === "j") setI((x) => Math.min((queue?.length ?? 1) - 1, x + 1));
      if (e.key === "k") setI((x) => Math.max(0, x - 1));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [queue]);

  function saved(a: AlertDetail) {
    setCurrent(a);
    cache.current.set(a.id, Promise.resolve(a));
    setTimeout(() => setI((x) => x + 1), 700);
  }

  const total = queue?.length ?? 0;
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>Review queue</h2>
          <p>{team ?? "All teams"} · {queue ? (i < total ? `${i + 1} of ${total} unreviewed` : `${total} reviewed this session`) : "loading"}</p>
        </div>
        <span className="grow" />
        <span className="faint" style={{ fontSize: 12 }}><span className="kbd">J</span> next · <span className="kbd">K</span> previous · <span className="kbd">C</span> correct · <span className="kbd">F</span> false alarm</span>
      </div>
      {error ? <Failed error={error} /> : !queue ? <Loading lines={8} /> : i >= total ? (
        <section className="glass" style={{ padding: "8px 22px" }}>
          <Empty title={total ? "That's the queue." : "Nothing to review."}>{total ? "Every alert in it now has your verdict. New alerts land on the Live page." : `No unreviewed alerts for ${team ?? "any team"}.`}</Empty>
        </section>
      ) : !current ? <Loading lines={8} /> : <AlertBody alert={current} onSaved={saved} hotkeys />}
    </div>
  );
}
