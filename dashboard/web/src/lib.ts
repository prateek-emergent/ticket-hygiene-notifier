import { useCallback, useEffect, useRef, useState } from "react";
import type { Activity } from "./api";

export const RULES: { id: string; short: string }[] = [
  { id: "pending_without_open_question", short: "Pending, no question" },
  { id: "reassigned_from_colleague", short: "Taken from a colleague" },
  { id: "picked_up_during_overwatch_run", short: "Grabbed during Overwatch" },
  { id: "status_not_matching_shift", short: "Status vs shift" },
  { id: "ticket_held_off_shift", short: "Held while off shift" },
  { id: "l3_escalation_check", short: "6a · L3 escalation" },
  { id: "escalation_note_quality", short: "6b · Escalation note" },
  { id: "held_then_unassigned", short: "Held, then dropped" },
  { id: "assigned_without_reply", short: "No reply 60+ min" },
];
/** The one time window, chosen in the header and shared by every page. */
export const WINDOWS = [
  { h: 1, label: "Last hour" }, { h: 24, label: "Last 24 h" }, { h: 24 * 7, label: "Last 7 days" }, { h: 24 * 30, label: "Last 30 days" },
  { h: 24 * 90, label: "Last 90 days" },
];
export const windowLabel = (h: number) => WINDOWS.find((w) => w.h === h)?.label.toLowerCase() ?? `last ${h} h`;

export const ruleShort = (id: string | null | undefined) => RULES.find((r) => r.id === id)?.short ?? (id ?? "System");

/** The colour a light, pip or row takes: red is reserved for alerts. */
export function tone(a: Pick<Activity, "kind" | "outcome">): string {
  if (a.kind === "alert" || a.outcome === "flagged") return "var(--alert)";
  if (a.kind === "error" || a.outcome === "error") return "var(--wait)";
  if (a.outcome === "skipped" || a.outcome === "uncertain" || a.outcome === "waiting" || a.kind === "scheduled" || a.kind === "recheck") return "var(--wait)";
  if (a.outcome === "ok" || a.outcome === "asks" || a.outcome === "needs_l3") return "var(--ok)";
  if (a.kind === "cycle" || a.kind === "start" || a.kind === "sweep") return "var(--ink-4)";
  return "var(--clean)";
}

export const OUTCOME_LABEL: Record<string, string> = {
  flagged: "Alerted", clean: "Clean", ok: "Fine", skipped: "Skipped", duplicate: "Duplicate", error: "Error",
  waiting: "Waiting for reply", uncertain: "Uncertain", asks: "Asks the customer", no_ask: "Asks nothing",
  needs_l3: "Needed L3", l2_could: "L2 could handle",
};

export const KIND_LABEL: Record<string, string> = {
  scheduled: "Check scheduled", recheck: "Rechecking", check: "Check finished", model: "Model call",
  alert: "Alert sent", status: "Status checked", sweep: "Off-shift sweep", cycle: "Poll cycle", error: "Error", start: "Notifier started", run: "Run check now",
};

const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const fullFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" });

export function clock(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return Date.now() - d.getTime() < 20 * 3600_000 ? timeFmt.format(d) : dayFmt.format(d);
}
export const fullTime = (iso: string | null | undefined) => (iso ? fullFmt.format(new Date(iso)) : "");
export function ago(iso: string | null | undefined): string {
  if (!iso) return "never";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.round(s)} s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}
export const initials = (name: string) => name.split(/[\s.]+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("");
export const ticketLabel = (num: number | null | undefined, id: string | null | undefined) => (num ? `#${num}` : id ? id.slice(0, 8) : "-");

/** Load data, refetching when `deps` change; `refreshKey` changes trigger a quiet background refresh. */
export function useData<T>(load: () => Promise<T>, deps: unknown[], refreshKey?: unknown) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const loadRef = useRef(load);
  loadRef.current = load;
  const run = useCallback(async (quiet: boolean) => {
    if (!quiet) setLoading(true);
    try {
      const d = await loadRef.current();
      setData(d);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { setData(null); void run(false); }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    const t = setTimeout(() => void run(true), 800); // coalesce bursts of live rows
    return () => clearTimeout(t);
  }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, loading, reload: () => run(true), setData };
}

export function useNow(intervalMs = 5000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

/** "1 h 05 min" from minutes. */
export function duration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "-";
  const m = Math.max(0, Math.round(minutes));
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}
/** Minutes from `iso` until `now` (ms). */
export const minutesSince = (iso: string, now: number) => (now - new Date(iso).getTime()) / 60_000;
/** A date as YYYY-MM-DD in the viewer's timezone. */
export const isoDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
/** The header's time window as whole days for reports and exports: { from, to } (YYYY-MM-DD, up to 90 days). */
export function dayRange(hours: number): { from: string; to: string } {
  const days = Math.min(90, Math.max(1, Math.round(hours / 24)));
  return { from: isoDay(new Date(Date.now() - (days - 1) * 86_400_000)), to: isoDay(new Date()) };
}
