// The live river: the last hour of the notifier's real work, drifting left behind the glass.
// x = when it happened, lane = which rule, colour = outcome (red only for alerts), size = weight.
// Lights slide continuously (a 5 s linear transition between 5 s re-renders); new ones arrive blurred
// and settle. Hover sharpens a light into what it was; click opens its ticket's trace.
import { useMemo, useRef, useState } from "react";
import type { Activity } from "../api";
import { clock, ruleShort, RULES, ticketLabel, tone, useNow, OUTCOME_LABEL, KIND_LABEL } from "../lib";
import { useLive } from "../live";
import { navigate } from "../router";

const WINDOW_MS = 60 * 60 * 1000;
// Finished work only, so the river agrees with the counts: a check's outcome, a status check, an alert.
const SHOWN = new Set(["check", "status", "alert"]);

function size(a: Activity): number {
  if (a.kind === "alert") return 20;
  return a.outcome === "skipped" || a.outcome === "error" ? 14 : 12;
}

export function River({ team, members }: { team: string | null; members: Set<string> | null }) {
  const { recent, status } = useLive();
  const now = useNow(5000);
  const [hover, setHover] = useState<{ a: Activity; x: number; y: number } | null>(null);
  const firstSeen = useRef<number | null>(null);
  if (firstSeen.current === null && recent.length) firstSeen.current = recent[recent.length - 1].id;

  const start = now - WINDOW_MS;
  const rows = useMemo(
    () =>
      recent.filter(
        (a) =>
          SHOWN.has(a.kind) && a.rule && new Date(a.at).getTime() >= start - 60_000 &&
          // a team view shows that team's engineers only (as the counts do); rows with no engineer are all-teams
          (!members || (!!a.engineer && members.has(a.engineer.toLowerCase()))),
      ),
    [recent, start, members],
  );
  const checks = rows.filter((a) => a.kind === "check" || a.kind === "status").length;
  const alerts = rows.filter((a) => a.kind === "alert").length;
  const unsure = rows.filter((a) => a.kind === "check" && a.outcome === "skipped").length;
  const ticks = [60, 45, 30, 15, 0].map((m) => (m === 0 ? "now" : clock(new Date(now - m * 60_000).toISOString())));
  // Mark when the notifier started, so an empty stretch reads as "not running yet", not "nothing happened".
  const started = status?.info?.started ? new Date(status.info.started).getTime() : null;
  const startedX = started && started > start && !rows.some((a) => new Date(a.at).getTime() < started)
    ? ((started - start) / WINDOW_MS) * 100 : null;

  return (
    <section className="river" aria-label="Live activity in the last hour">
      <div className="caption">
        <b>Last hour{team ? `, ${team}` : ""}</b> · {checks} {checks === 1 ? "check" : "checks"} ·{" "}
        <span className={alerts ? "alerts" : undefined}>{alerts} {alerts === 1 ? "alert" : "alerts"}</span>
        {unsure ? ` · ${unsure} skipped` : ""}
      </div>
      <div className="lanes" aria-hidden="true">
        {RULES.map((r, i) => {
          const top = `${(i + 0.5) * (100 / RULES.length)}%`;
          return (
            <div key={r.id}>
              <div className="lane" style={{ top }} />
              <div className="lane-label" style={{ top }}>{r.short}</div>
            </div>
          );
        })}
      </div>
      <div className="track" onMouseLeave={() => setHover(null)}>
        {startedX !== null && (
          <div className="started" style={{ left: `${startedX}%` }}><span className="mono">started {clock(status!.info!.started)}</span></div>
        )}
        <div className="lanes" style={{ left: 0, right: 0 }}>
          {rows.map((a) => {
            const lane = Math.max(0, RULES.findIndex((r) => r.id === a.rule));
            const x = Math.max(0, Math.min(100, ((new Date(a.at).getTime() - start) / WINDOW_MS) * 100));
            const y = (lane + 0.5) * (100 / RULES.length);
            const s = size(a);
            const isNew = firstSeen.current !== null && a.id > firstSeen.current;
            const label = `${KIND_LABEL[a.kind] ?? a.kind}: ${a.summary}`;
            return (
              <span key={a.id}>
                {a.kind === "alert" ? (
                  <i className="streak" style={{ left: `calc(${x}% - 110px)`, top: `${y}%`, width: 110 }} />
                ) : (
                  // every light leaves a short exposure trail along its direction of travel
                  <i className="trail" style={{ left: `calc(${x}% - 28px)`, top: `${y}%`, ["--c" as string]: tone(a) }} />
                )}
                <button
                  className={`light${isNew ? " arrive" : ""}`}
                  style={{ left: `${x}%`, top: `${y}%`, width: s, height: s, ["--c" as string]: tone(a), ["--b" as string]: `${a.kind === "alert" ? 3 : 4.5}px` }}
                  aria-label={label}
                  onMouseEnter={(e) => {
                    const box = (e.currentTarget.parentElement?.parentElement?.parentElement as HTMLElement).getBoundingClientRect();
                    const r = e.currentTarget.getBoundingClientRect();
                    setHover({ a, x: r.left - box.left, y: r.top - box.top });
                  }}
                  onFocus={(e) => {
                    const box = (e.currentTarget.parentElement?.parentElement?.parentElement as HTMLElement).getBoundingClientRect();
                    const r = e.currentTarget.getBoundingClientRect();
                    setHover({ a, x: r.left - box.left, y: r.top - box.top });
                  }}
                  onBlur={() => setHover(null)}
                  onClick={() => a.ticket_id && navigate(`/tickets/${encodeURIComponent(a.ticket_id)}`)}
                />
              </span>
            );
          })}
        </div>
        {hover && (
          <div
            className="tip"
            role="status"
            style={{ left: Math.max(0, Math.min(hover.x - 150, (document.body.clientWidth || 1200) - 460)), top: hover.y > 120 ? hover.y - 118 : hover.y + 24 }}
          >
            <div className="t">
              <time>{clock(hover.a.at)}</time> · {ruleShort(hover.a.rule)} · {OUTCOME_LABEL[hover.a.outcome ?? ""] ?? KIND_LABEL[hover.a.kind]}
            </div>
            <div style={{ marginTop: 4 }}>
              {hover.a.engineer_name ?? "System"}
              {hover.a.ticket_id ? <span className="mono faint"> · {ticketLabel(hover.a.ticket_num, hover.a.ticket_id)}</span> : null}
            </div>
            <div className="muted" style={{ marginTop: 2 }}>{hover.a.summary}</div>
          </div>
        )}
      </div>
      <div className="axis mono" aria-hidden="true">{ticks.map((t) => <span key={t}>{t}</span>)}</div>
      <div className="veil" />
    </section>
  );
}

/** Stable pseudo-random 0..1 from a number, so a light keeps its size and depth across renders. */
const jitter = (n: number, salt: number) => {
  const x = Math.sin(n * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
};

/** The traffic behind the glass: the same last hour as the river, defocused across the whole window.
 *  The panes blur this, so the glass always has real, moving work behind it. */
export function Field() {
  const { recent } = useLive();
  const now = useNow(5000);
  const start = now - WINDOW_MS;
  const rows = recent.filter((a) => (a.kind === "check" || a.kind === "status" || a.kind === "alert") && new Date(a.at).getTime() >= start);
  // Lights close in time and rule merge into one larger, softer light, so a busy minute never piles up
  // into a bright block; an alert in the cell gives the merged light its colour.
  const cells = new Map<string, { a: Activity; n: number; x: number; lane: number }>();
  for (const a of rows) {
    const lane = Math.max(0, RULES.findIndex((r) => r.id === a.rule));
    const x = (new Date(a.at).getTime() - start) / WINDOW_MS;
    const key = `${lane}|${Math.floor(x * 30)}`;
    const cell = cells.get(key);
    if (!cell) cells.set(key, { a, n: 1, x, lane });
    else { cell.n += 1; if (a.kind === "alert") cell.a = a; }
  }
  return (
    <div className="field" aria-hidden="true">
      {[...cells.values()].map(({ a, n, x, lane }) => {
        const y = 42 + ((lane + jitter(a.id, 1)) / RULES.length) * 52; // below the river, behind the panes
        const s = Math.min(80, 16 + jitter(a.id, 2) * 26 + n * 6);
        return (
          // same x as the river's track, so the field is the river's traffic, defocused
          <span key={`${lane}-${a.id}`} className="bokeh" style={{ left: `calc(var(--field-left) + (100% - var(--field-left) - 32px) * ${x})`, top: `${y}%`,
            width: s, height: s, ["--c" as string]: tone(a), ["--b" as string]: `${8 + jitter(a.id, 3) * 6}px`,
            ["--o" as string]: `${0.12 + jitter(a.id, 4) * 0.1}` }} />
        );
      })}
    </div>
  );
}

/** A still frame of the same traffic for the sign-in gate, where there is no live data yet. */
export function StillField() {
  const lights = Array.from({ length: 22 }, (_, i) => i);
  return (
    <div className="field" aria-hidden="true">
      {lights.map((i) => {
        const tones = ["var(--clean)", "var(--ok)", "var(--clean)", "var(--wait)", "var(--ok)"];
        const s = 14 + jitter(i, 2) * 50;
        return <span key={i} className="bokeh" style={{ left: `${6 + jitter(i, 5) * 88}%`, top: `${10 + jitter(i, 6) * 80}%`, width: s, height: s,
          ["--c" as string]: tones[i % tones.length], ["--b" as string]: `${6 + jitter(i, 3) * 6}px`, ["--o" as string]: `${0.18 + jitter(i, 4) * 0.15}` }} />;
      })}
      <i className="streak far" style={{ left: "22%", top: "64%", width: 240 }} />
      <i className="streak far" style={{ left: "60%", top: "30%", width: 160 }} />
    </div>
  );
}
