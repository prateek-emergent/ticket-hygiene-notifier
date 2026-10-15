// The Team page's reports (R8) and scorecard (R9), over the header's time window (days, up to 90), plus the
// daily report for one day. Alerts marked false alarm never count here.
import { useState } from "react";
import { api, type Reports } from "../api";
import { duration, isoDay, ruleShort, useData } from "../lib";
import { useLive } from "../live";
import { linkProps } from "../router";
import { useScope } from "../scope";
import { Empty, Failed, Loading, When } from "../parts/Common";

const RATING: Record<Reports["scorecard"][number]["rating"], { label: string; c: string }> = {
  needs_attention: { label: "Needs attention", c: "var(--alert)" },
  watch: { label: "Watch", c: "var(--wait)" },
  good: { label: "Good", c: "var(--ok)" },
};

function Who({ p, team }: { p: { email: string; name: string; team: string | null }; team: string | null }) {
  return <><a {...linkProps(`/alerts?q=${encodeURIComponent(p.email)}`)}>{p.name}</a>{!team && <div className="faint" style={{ fontSize: 12 }}>{p.team}</div>}</>;
}

function List<T>({ title, aside, items, empty, row }: { title: string; aside?: string; items: T[]; empty: string; row: (x: T, i: number) => React.ReactNode }) {
  return (
    <section className="glass pane">
      <div className="pane-head"><h3>{title}</h3><span className="aside">{aside ?? `${items.length}`}</span></div>
      {items.length === 0 ? <Empty title={empty} /> : <div className="rows">{items.map(row)}</div>}
    </section>
  );
}

export function TeamReports() {
  const { team, hours } = useScope();
  const { version } = useLive();
  const days = Math.min(90, Math.max(1, Math.round(hours / 24)));
  const today = isoDay(new Date());
  const from = isoDay(new Date(Date.now() - (days - 1) * 86_400_000));
  const [day, setDay] = useState(today);
  const { data, error, loading, reload } = useData(() => api.reports({ from, to: today, day, team }), [from, today, day, team], version);

  if (loading && !data) return <div style={{ marginTop: 20 }}><Loading lines={6} /></div>;
  if (error && !data) return <Failed error={error} retry={reload} />;
  const r = data!;
  const range = r.from === r.to ? r.from : `${r.from} to ${r.to}`;

  return (
    <>
      <div className="page-head" style={{ marginTop: 32 }}>
        <div><h2 style={{ fontSize: 20 }}>Scorecard</h2><p>{range}. Offline after shift ×3, un-assigned without a note ×2, other self-un-assignments ×1, +5 for a repeated pattern. False alarms don't count.</p></div>
      </div>
      <section className="glass" style={{ padding: "6px 10px" }}>
        {r.scorecard.length === 0 ? <Empty title="No engineers in this team." /> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr>
                <th>Engineer</th><th>Rating</th><th className="num">Score</th><th className="num">Offline after shift</th>
                <th className="num">Un-assigned, no note</th><th className="num">Un-assigned, with note</th><th>Patterns</th>
                <th className="num">Other alerts</th><th className="num">False alarms</th>
              </tr></thead>
              <tbody>
                {r.scorecard.map((c) => (
                  <tr key={c.email}>
                    <td><Who p={c} team={team} /></td>
                    <td><span className="outcome" style={{ ["--c" as string]: RATING[c.rating].c }}>{RATING[c.rating].label}</span></td>
                    <td className={`n${c.score ? "" : " zero"}`} style={{ fontWeight: 600 }}>{c.score}</td>
                    <td className={`n${c.offline_violations ? "" : " zero"}`}>{c.offline_violations}</td>
                    <td className={`n${c.unassign_without_note ? "" : " zero"}`}>{c.unassign_without_note}</td>
                    <td className={`n${c.unassign_with_note ? "" : " zero"}`}>{c.unassign_with_note}</td>
                    <td style={{ fontSize: 12, whiteSpace: "normal", maxWidth: 260 }}>{c.patterns.length ? c.patterns.join("; ") : <span className="faint">-</span>}</td>
                    <td className={`n${c.other_alerts ? "" : " zero"}`}>{c.other_alerts}</td>
                    <td className={`n${c.false_alarms ? "" : " zero"}`}>{c.false_alarms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="panes" style={{ padding: 0, marginTop: 20, gridTemplateColumns: "1fr 1fr" }}>
        <List title="Heavy days" aside="3+ alerts in a day" items={r.heavy_days} empty="No heavy days." row={(h) => (
          <div key={h.email + h.day} className="kv">
            <span><Who p={h} team={team} /><div className="faint" style={{ fontSize: 12 }}>{Object.entries(h.by_rule).map(([k, v]) => `${ruleShort(k)} ${v}`).join(", ")}</div></span>
            <span className="num">{h.count}<div className="faint" style={{ fontSize: 12 }}>{h.day}</div></span>
          </div>
        )} />
        <List title="Repeated tickets" aside="flagged 2+ times" items={r.repeated_tickets} empty="No ticket was flagged twice." row={(t) => (
          <div key={t.ticket_id} className="kv">
            <span>
              {t.url ? <a href={t.url} target="_blank" rel="noreferrer">#{t.num ?? t.ticket_id.slice(0, 8)}</a> : `#${t.num}`} <span className="faint">{t.subject}</span>
              <div className="faint" style={{ fontSize: 12 }}>{t.engineers.map((e) => e.name).join(", ")} · {t.rules.map(ruleShort).join(", ")}</div>
            </span>
            <span className="num">{t.count}×</span>
          </div>
        )} />
      </div>

      <div className="page-head" style={{ marginTop: 32 }}>
        <div><h2 style={{ fontSize: 20 }}>Daily report</h2><p>One day's shift and un-assignment problems. Patterns look back {r.daily.pattern_days} days.</p></div>
        <span className="grow" />
        <input className="input" type="date" value={day} max={today} onChange={(e) => e.target.value && setDay(e.target.value)} aria-label="Day" style={{ width: "auto" }} />
      </div>
      <div className="panes" style={{ padding: 0, gridTemplateColumns: "1fr 1fr" }}>
        <List title="Didn't go Offline" items={r.daily.didnt_go_offline} empty="Everyone went Offline after their shift." row={(x) => (
          <div key={x.email + x.shift_end} className="kv">
            <span><Who p={x} team={team} /><div className="faint" style={{ fontSize: 12 }}>{x.outcome === "open" ? `still Online, ${duration(x.online_minutes)}` : x.outcome === "alerted" ? "alerted at 45 min" : "Online until their next shift"}</div></span>
            <span>shift ended <When at={x.shift_end} /></span>
          </div>
        )} />
        <List title="Stayed Online late" items={r.daily.stayed_online_late} empty="Nobody stayed Online late." row={(x) => (
          <div key={x.email + x.shift_end} className="kv">
            <span><Who p={x} team={team} /></span>
            <span className="num">{duration(x.online_minutes)}<div className="faint" style={{ fontSize: 12 }}>after <When at={x.shift_end} /></div></span>
          </div>
        )} />
        <List title="Un-assigned without a note" items={r.daily.unassigned_without_note} empty="No un-assignments without a note." row={(x, i) => (
          <div key={x.ticket_id + i} className="kv">
            <span><Who p={x} team={team} /><div className="faint" style={{ fontSize: 12 }}>held {duration(x.held_minutes)}</div></span>
            <span>{x.url ? <a href={x.url} target="_blank" rel="noreferrer">#{x.num ?? x.ticket_id.slice(0, 8)}</a> : `#${x.num}`}<div className="faint" style={{ fontSize: 12 }}><When at={x.at} /></div></span>
          </div>
        )} />
        <List title="Repeated patterns" items={r.daily.patterns} empty="No repeated patterns." row={(x, i) => (
          <div key={x.email + i} className="kv">
            <span><Who p={x} team={team} /></span>
            <span style={{ fontSize: 12 }}>{x.url ? <a href={x.url} target="_blank" rel="noreferrer">{x.what}</a> : x.what}</span>
          </div>
        )} />
      </div>
    </>
  );
}
