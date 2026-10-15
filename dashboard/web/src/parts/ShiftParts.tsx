// Release 2 pieces of the Shifts page: per-associate team cards, "Mark actioned" (recorded in our app only,
// nothing changes in Trinity), and the week grid of a roster.
import { Check } from "lucide-react";
import { useState } from "react";
import { api, ApiError, type Action, type TeamCard, type Week } from "../api";
import { ago, useData } from "../lib";
import { Empty, Failed, Loading } from "./Common";

export function TeamCards({ cards, onPick }: { cards: TeamCard[]; onPick?: (team: string) => void }) {
  if (!cards.length) return null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: 16, marginBottom: 20 }}>
      {cards.map((c) => {
        const problems = c.on_shift_not_online.length + c.still_online + c.off_shift_with_tickets;
        return (
          <section key={c.name} className="glass pane" style={{ padding: "16px 18px" }} aria-label={c.name}>
            <div className="pane-head" style={{ marginBottom: 4 }}>
              <h3 style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {onPick ? <button className="linklike" onClick={() => onPick(c.name)} style={{ all: "unset", cursor: "pointer" }}>{c.name}</button> : c.name}
              </h3>
              <span className="outcome" style={{ ["--c" as string]: problems ? "var(--wait)" : "var(--ok)" }}>{problems ? `${problems} to look at` : "All fine"}</span>
            </div>
            <div className="faint" style={{ fontSize: 12, marginBottom: 6 }}>{c.associates.join(", ") || "No associate"}</div>
            <div className="rows">
              <div className="kv"><span>On shift now</span><span className="num">{c.on_shift} <span className="faint">of {c.engineers}</span></span></div>
              <div className="kv">
                <span>On shift, not Online</span>
                <span className="num" title={c.on_shift_not_online.map((p) => p.name).join(", ") || undefined}
                  style={c.on_shift_not_online.length ? { color: "var(--alert-ink)" } : undefined}>{c.on_shift_not_online.length}</span>
              </div>
              {c.on_shift_not_online.length > 0 && <div className="faint" style={{ fontSize: 12, padding: "0 0 8px", borderTop: 0 }}>{c.on_shift_not_online.map((p) => p.name).join(", ")}</div>}
              <div className="kv"><span>Still Online after shift</span><span className="num">{c.still_online}</span></div>
              <div className="kv"><span>Off shift with tickets</span><span className="num">{c.off_shift_with_tickets} <span className="faint">· {c.open_tickets} open in team</span></span></div>
              <div className="kv"><span>Alerts today</span><span className="num">{c.alerts_today}</span></div>
            </div>
          </section>
        );
      })}
    </div>
  );
}

/** "Mark actioned" for one row: shows who actioned it, or a button that opens a short note. */
export function ActionCell({ engineer, context, tickets, action, onSaved }: {
  engineer: string; context: Action["context"]; tickets: { ticket_id: string; num: number | null }[];
  action: Action | null; onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (action && !open) {
    return (
      <span style={{ fontSize: 12 }} title={action.note ?? undefined}>
        <span className="outcome" style={{ ["--c" as string]: "var(--ok)" }}>Actioned</span>
        <div className="faint">{action.by_name}, {ago(action.at)}{action.note ? `: ${action.note.length > 60 ? `${action.note.slice(0, 60)}…` : action.note}` : ""}</div>
      </span>
    );
  }
  if (!open) return <button className="chip" onClick={() => setOpen(true)}>Mark actioned</button>;

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.addAction({ engineer, context, tickets, note });
      setOpen(false);
      setNote("");
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={(e) => { e.preventDefault(); void save(); }} style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", minWidth: 220 }}>
      <input className="input" autoFocus value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000}
        placeholder="What did you do? e.g. reassigned to Bala" aria-label="Note" style={{ height: 32, padding: "4px 10px", fontSize: 13, flex: 1, minWidth: 160 }} />
      <button className="chip" type="submit" disabled={busy} aria-busy={busy || undefined}><Check size={13} aria-hidden="true" /> Save</button>
      <button className="chip" type="button" onClick={() => setOpen(false)}>Cancel</button>
      {error && <span className="error-line" style={{ fontSize: 12, width: "100%" }}>{error}</span>}
    </form>
  );
}

const CELL_STYLE: Record<string, React.CSSProperties> = {
  shift: {},
  off: { color: "var(--ink-4)" },
  none: { color: "var(--ink-4)", opacity: 0.5 },
  unknown: { color: "var(--wait)" },
};
const dayLabel = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });

/** One week of a roster, as written in its file: a row per person, a column per day. */
export function WeekGrid({ roster, team, onRoster }: { roster: string | null; team: string | null; onRoster: (r: string) => void }) {
  const { data, error, loading, reload } = useData(() => api.week(roster, team), [roster, team]);
  if (loading && !data) return <Loading lines={6} />;
  if (error && !data) return <Failed error={error} retry={reload} />;
  const w: Week = data!;
  const today = w.days[0];
  return (
    <>
      {w.views.length > 1 && (
        <div style={{ marginBottom: 8 }}>
          <select className="select" value={w.name ?? ""} onChange={(e) => onRoster(e.target.value)} aria-label="Roster">
            {w.views.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
      )}
      {w.roster_only && <p className="faint" style={{ fontSize: 12, margin: "0 0 6px" }}>Roster only: this team isn't monitored by the notifier.</p>}
      {w.people.length === 0 ? <Empty title="Nobody on this roster this week." /> : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr>
              <th>Name</th>
              {w.days.map((d) => <th key={d} style={d === today ? { color: "var(--ink)" } : undefined}>{dayLabel.format(new Date(`${d}T12:00:00`))}</th>)}
            </tr></thead>
            <tbody>
              {w.people.map((p) => (
                <tr key={p.email}>
                  <td style={{ whiteSpace: "nowrap" }}>{p.name}{p.role && p.role !== "Agent" && <span className="faint" style={{ fontSize: 12 }}> · {p.role}</span>}</td>
                  {p.cells.map((c, i) => (
                    <td key={i} className="mono" style={{ fontSize: 12, whiteSpace: "nowrap", ...(CELL_STYLE[c.kind] ?? {}) }} title={c.kind === "unknown" ? "Unclear in roster" : undefined}>
                      {c.code || "–"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
