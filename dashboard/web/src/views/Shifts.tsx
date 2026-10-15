// Shifts: who is still Online after their shift (R1), who is off shift with tickets still assigned (R6), and
// today's roster for any team (R7); release 2 adds per-associate team cards, "Mark actioned" and a week grid.
// Read from the notifier's copy of Trinity data; nothing here asks or changes Trinity.
import { ExternalLink } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type RosterPerson, type TicketLink } from "../api";
import { ago, clock, dayRange, duration, minutesSince, useData, useNow } from "../lib";
import { useLive } from "../live";
import { useScope } from "../scope";
import { Empty, Failed, Loading, When } from "../parts/Common";
import { RunCheck } from "../parts/RunCheck";
import { ExportLink } from "../parts/Export";
import { ActionCell, TeamCards, WeekGrid } from "../parts/ShiftParts";

const ROSTER_KEY = "hygiene-roster";
const ROSTER_MODE_KEY = "hygiene-roster-mode";
const STATUS_ALERT_AFTER = 45; // minutes: theme 4's Slack alert
const STATE_LABEL: Record<RosterPerson["state"], string> = { on: "On shift", later: "Later today", done: "Shift over", off: "Off", unknown: "Unclear in roster", none: "Not on roster today" };
const OUTCOME_LABEL: Record<string, string> = {
  went_offline_late: "Went Offline late", online_until_next_shift: "Online until next shift", not_observed: "Not observed (app was down)",
};

function Tickets({ items, max = 6 }: { items: TicketLink[]; max?: number }) {
  if (!items.length) return <span className="faint">none</span>;
  return (
    <span style={{ display: "inline-flex", flexWrap: "wrap", gap: "4px 10px" }}>
      {items.slice(0, max).map((t) => (
        <a key={t.ticket_id} href={t.url ?? undefined} target="_blank" rel="noreferrer" title={t.subject ?? undefined}>
          #{t.num ?? t.ticket_id.slice(0, 8)}<ExternalLink size={11} aria-hidden="true" style={{ marginLeft: 2, verticalAlign: -1 }} />
        </a>
      ))}
      {items.length > max && <span className="faint">and {items.length - max} more</span>}
    </span>
  );
}

function Presence({ p }: { p: string | null }) {
  const on = p === "ONLINE";
  return <span className="outcome" style={{ ["--c" as string]: on ? "var(--ok)" : "var(--ink-4)" }}>{p ? p[0] + p.slice(1).toLowerCase() : "Unknown"}</span>;
}

export function ShiftsView() {
  const { team, setTeam } = useScope();
  const [mode, setModeState] = useState<"today" | "week">(() => {
    try { return localStorage.getItem(ROSTER_MODE_KEY) === "week" ? "week" : "today"; } catch { return "today"; }
  });
  const setMode = (m: "today" | "week") => {
    setModeState(m);
    try { localStorage.setItem(ROSTER_MODE_KEY, m); } catch { /* not remembered */ }
  };
  const { version } = useLive();
  const now = useNow(15_000);
  const [roster, setRosterState] = useState<string | null>(() => {
    try { return localStorage.getItem(ROSTER_KEY); } catch { return null; }
  });
  const setRoster = (r: string) => {
    setRosterState(r);
    try { localStorage.setItem(ROSTER_KEY, r); } catch { /* not remembered */ }
  };
  const { data, error, loading, reload } = useData(() => api.shifts(team, roster), [team, roster], version);
  // The copy of presence refreshes every minute: so does this page, even when no activity arrives.
  useEffect(() => {
    const t = setInterval(() => void reload(), 60_000);
    return () => clearInterval(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const refreshed = useCallback(() => void reload(), [reload]);

  if (loading && !data) return <div className="page"><Loading lines={10} /></div>;
  if (error && !data) return <div className="page"><Failed error={error} retry={reload} /></div>;
  const d = data!;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>Shifts</h2>
          <p>
            {team ?? "All teams"}. {d.synced.presence
              ? <>Status from the copy of Trinity data, refreshed {ago(d.synced.presence)}; open tickets {d.synced.open_tickets ? ago(d.synced.open_tickets) : "not yet"}.</>
              : <>Not synced from Trinity yet: the lists fill in once the notifier runs.</>}
          </p>
        </div>
        <span className="grow" />
        <RunCheck initial={d.run_check} onDone={refreshed} />
      </div>

      <TeamCards cards={d.teams} onPick={team ? undefined : setTeam} />

      <section className="glass pane" style={{ marginBottom: 20 }} aria-labelledby="still-online">
        <div className="pane-head">
          <h3 id="still-online">Still Online after shift</h3>
          <span className="aside">Slack alert at {STATUS_ALERT_AFTER} min (theme 4)</span>
        </div>
        {d.still_online.length === 0 ? <Empty title="Nobody is Online past their shift." /> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Engineer</th><th>Shift ended</th><th className="num">Online for</th><th>Still assigned</th><th>Action</th></tr></thead>
              <tbody>
                {d.still_online.map((r) => {
                  const mins = minutesSince(r.shift_end, now);
                  return (
                    <tr key={r.email + r.shift_end}>
                      <td>{r.name}{!team && <div className="faint" style={{ fontSize: 12 }}>{r.team}</div>}</td>
                      <td><When at={r.shift_end} /></td>
                      <td className="n" style={{ fontWeight: 600, color: mins >= STATUS_ALERT_AFTER ? "var(--alert-ink)" : undefined }}>
                        {duration(mins)}{mins >= STATUS_ALERT_AFTER && <div className="faint" style={{ fontSize: 12, fontWeight: 400 }}>alerted</div>}
                      </td>
                      <td><Tickets items={r.open_tickets} /></td>
                      <td><ActionCell engineer={r.email} context="still_online" action={r.action} onSaved={refreshed}
                        tickets={r.open_tickets.map((t) => ({ ticket_id: t.ticket_id, num: t.num }))} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="glass pane" style={{ marginBottom: 20 }} aria-labelledby="off-shift">
        <div className="pane-head">
          <h3 id="off-shift">Off shift, tickets still assigned</h3>
          <span className="aside">reassign in Trinity · Slack alert after 3 h of customer waiting (theme 5)</span>
        </div>
        {d.off_shift_with_tickets.length === 0 ? <Empty title="No off-shift engineer holds an open ticket." /> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Engineer</th><th>Status</th><th>Shift ended</th><th>Next shift</th><th className="num">Open</th><th>Tickets</th><th>Action</th></tr></thead>
              <tbody>
                {d.off_shift_with_tickets.map((r) => (
                  <tr key={r.email}>
                    <td>{r.name}{!team && <div className="faint" style={{ fontSize: 12 }}>{r.team}</div>}</td>
                    <td><Presence p={r.presence} /></td>
                    <td>{r.shift_ended ? <When at={r.shift_ended} /> : "-"}</td>
                    <td>{r.next_shift ? <When at={r.next_shift} /> : "-"}</td>
                    <td className="n" style={{ fontWeight: 600 }}>{r.tickets.length}</td>
                    <td><Tickets items={r.tickets} /></td>
                    <td><ActionCell engineer={r.email} context="off_shift" action={r.action} onSaved={refreshed}
                      tickets={r.tickets.map((t) => ({ ticket_id: t.ticket_id, num: t.num }))} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="panes" style={{ padding: 0, gridTemplateColumns: "1.5fr 1fr" }}>
        <section className="glass pane" aria-labelledby="roster">
          <div className="pane-head">
            <h3 id="roster">{mode === "week" ? "Roster, next 7 days" : "Today's roster"}</h3>
            <span className="chips" role="group" aria-label="Roster view">
              <button className="chip" aria-pressed={mode === "today"} onClick={() => setMode("today")}>Today</button>
              <button className="chip" aria-pressed={mode === "week"} onClick={() => setMode("week")}>Week</button>
            </span>
          </div>
          {mode === "week" ? <WeekGrid roster={roster ?? d.roster.name} team={team} onRoster={setRoster} /> : (<>
          <div style={{ marginBottom: 8 }}>
            {d.roster.views.length > 1 && (
              <select className="select" value={d.roster.name ?? ""} onChange={(e) => setRoster(e.target.value)} aria-label="Roster">
                {d.roster.views.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            )}
          </div>
          {d.roster.roster_only && <p className="faint" style={{ fontSize: 12, margin: "0 0 6px" }}>Roster only: this team isn't monitored by the notifier.</p>}
          {d.roster.people.length === 0 ? <Empty title="No roster for today." /> : (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Name</th><th>Shift</th><th>Today</th>{!d.roster.roster_only && <th>Status</th>}</tr></thead>
                <tbody>
                  {d.roster.people.map((p) => (
                    <tr key={p.email} style={p.state === "off" || p.state === "none" ? { opacity: 0.6 } : undefined}>
                      <td>{p.name}{p.role && p.role !== "Agent" && <span className="faint" style={{ fontSize: 12 }}> · {p.role}</span>}</td>
                      <td className="mono" style={{ fontSize: 12 }}>{p.code || "-"}{p.start && <div className="faint">{clock(p.start)}–{clock(p.end)}</div>}</td>
                      <td>{STATE_LABEL[p.state]}</td>
                      {!d.roster.roster_only && <td>{p.monitored ? <Presence p={p.presence} /> : <span className="faint">not monitored</span>}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          </>)}
        </section>
        <div style={{ display: "grid", gap: 20, alignContent: "start" }}>
        <section className="glass pane" aria-labelledby="ends">
          <div className="pane-head"><h3 id="ends">Shift ends, last 24 h</h3><span className="aside">on time not shown</span></div>
          {d.recent_ends.length === 0 ? <Empty title="Everyone went Offline on time." /> : (
            <div className="rows">
              {d.recent_ends.map((r) => (
                <div key={r.email + r.shift_end} className="kv">
                  <span>{r.name}<div className="faint" style={{ fontSize: 12 }}>{OUTCOME_LABEL[r.outcome] ?? r.outcome}{r.online_minutes !== null && r.outcome !== "not_observed" ? `, ${duration(r.online_minutes)}` : ""}</div></span>
                  <When at={r.shift_end} />
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="glass pane" aria-labelledby="actioned">
          <div className="pane-head"><h3 id="actioned">Actioned, last 24 h</h3><ExportLink kind="actions" {...dayRange(24 * 7)} team={team} label="Last 7 days" /></div>
          <p className="faint" style={{ fontSize: 12, margin: 0 }}>Recorded in this app only; nothing changes in Trinity.</p>
          {d.actions.length === 0 ? <Empty title="Nothing marked actioned yet." /> : (
            <div className="rows">
              {d.actions.map((a) => (
                <div key={a.id} className="kv" style={{ alignItems: "baseline" }}>
                  <span>{a.engineer_name}<div className="faint" style={{ fontSize: 12 }}>
                    {a.context === "still_online" ? "Still Online after shift" : "Off shift with tickets"}{a.note ? `: ${a.note}` : ""} · {a.by_name}
                  </div></span>
                  <When at={a.at} />
                </div>
              ))}
            </div>
          )}
        </section>
        </div>
      </div>
    </div>
  );
}
