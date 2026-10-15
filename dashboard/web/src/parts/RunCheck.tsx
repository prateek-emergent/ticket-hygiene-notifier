// "Run check now": asks the notifier for a cycle right away (checks, then a full refresh of its copy of Trinity
// data). The notifier picks it up within seconds; one request a minute.
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type RunState } from "../api";
import { ago } from "../lib";
import { useLive } from "../live";

export function RunCheck({ initial, onDone }: { initial?: RunState | null; onDone?: () => void }) {
  const { status } = useLive();
  const [state, setState] = useState<RunState | null>(initial ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (initial) setState(initial); }, [initial]);
  useEffect(() => { if (!initial) api.runState().then(setState).catch(() => {}); }, [initial]);
  // While a request is waiting, look every 3 s; refresh the page's data once it has run.
  useEffect(() => {
    if (!state?.pending) return;
    const t = setInterval(() => {
      api.runState().then((s) => {
        setState(s);
        if (!s.pending) onDone?.();
      }).catch(() => {});
    }, 3000);
    return () => clearInterval(t);
  }, [state?.pending, onDone]);

  const run = async () => {
    setError(null);
    try {
      setState(await api.runCheck());
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) setError("Already asked under a minute ago.");
      else setError(e instanceof Error ? e.message : String(e));
    }
  };

  const stopped = status && !status.live;
  const note = error ?? (state?.pending
    ? (stopped ? "Waiting: the notifier isn't running" : "Running…")
    : state?.done_at
      ? `Last run ${ago(state.done_at)}${state.result && state.result !== "ok" ? `: ${state.result}` : ""}`
      : null);

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <button className="btn" onClick={run} disabled={!!state?.pending} aria-busy={state?.pending || undefined}
        title="Run the checks and refresh the copy of Trinity data now, instead of waiting for the next poll">
        <RefreshCw size={15} aria-hidden="true" /> Run check now
      </button>
      {note && <span className={error || (state?.result && state.result !== "ok" && !state.pending) ? "error-line" : "faint"} style={{ fontSize: 12 }} role="status">{note}</span>}
    </span>
  );
}
