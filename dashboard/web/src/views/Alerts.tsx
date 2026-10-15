import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type Alert } from "../api";
import { RULES, ruleShort, ticketLabel, useData, windowLabel, dayRange } from "../lib";
import { useLive } from "../live";
import { linkProps, navigate } from "../router";
import { useScope } from "../scope";
import { ExportLink } from "../parts/Export";
import { Empty, Failed, Loading, When } from "../parts/Common";

const REVIEW = [
  { id: "", label: "All" },
  { id: "unreviewed", label: "Unreviewed" },
  { id: "correct", label: "Correct" },
  { id: "false_alarm", label: "False alarm" },
];

export function AlertsView({ params }: { params: URLSearchParams }) {
  const { team, hours: scopeHours } = useScope();
  const { version } = useLive();
  const rule = params.get("rule") ?? "";
  const review = params.get("review") ?? "";
  const q = params.get("q") ?? "";
  // One window for the whole app: the header's. (No per-page override, so the two can never disagree.)
  const hours = scopeHours;
  const [text, setText] = useState(q);
  const [extra, setExtra] = useState<Alert[]>([]);
  const [more, setMore] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    navigate(`/alerts${p.toString() ? `?${p}` : ""}`, true);
  };
  useEffect(() => {
    const t = setTimeout(() => text !== q && set("q", text.trim()), 300);
    return () => clearTimeout(t);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.key === "/" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);

  const { data, error, loading, reload } = useData(
    () => api.alerts({ team, rule, review, q, hours, limit: 60 }),
    [team, rule, review, q, hours], version,
  );
  useEffect(() => { setExtra([]); setMore(!!data?.more); }, [data]);
  const items = [...(data?.items ?? []), ...extra];

  async function loadMore() {
    const last = items[items.length - 1];
    const page = await api.alerts({ team, rule, review, q, hours, limit: 60, before: last?.id });
    setExtra((x) => [...x, ...page.items]);
    setMore(page.more);
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>Alerts</h2>
          <p>{team ? `${team}` : "All teams"}, {windowLabel(hours)}.</p>
        </div>
        <span className="grow" />
        <ExportLink kind="alerts" {...dayRange(hours)} team={team} />
        <label className="search">
          <Search size={15} aria-hidden="true" />
          <input ref={searchRef} className="input" placeholder="Search ticket, engineer, reason   /" value={text} onChange={(e) => setText(e.target.value)} aria-label="Search alerts" />
        </label>
      </div>
      <div className="chips" role="group" aria-label="Theme" style={{ marginBottom: 10 }}>
        <button className="chip" aria-pressed={!rule} onClick={() => set("rule", "")}>All themes</button>
        {RULES.map((r) => <button key={r.id} className="chip" aria-pressed={rule === r.id} onClick={() => set("rule", rule === r.id ? "" : r.id)}>{r.short}</button>)}
      </div>
      <div className="chips" role="group" aria-label="Review state" style={{ marginBottom: 18 }}>
        {REVIEW.map((r) => <button key={r.id} className="chip" aria-pressed={review === r.id} onClick={() => set("review", r.id)}>{r.label}</button>)}
      </div>
      <section className="glass" style={{ padding: "6px 10px" }}>
        {loading && !data ? <div style={{ padding: 12 }}><Loading lines={6} /></div> : error && !data ? <Failed error={error} retry={reload} /> : items.length === 0 ? (
          <Empty title="No alerts match.">{q || rule || review ? "Try clearing a filter." : "Nothing has been flagged in this window."}</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>When</th><th>Engineer</th><th>Theme</th><th>Ticket</th><th>Why</th><th>Verdict</th></tr></thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} onClick={() => navigate(`/alerts/${a.id}`)} style={{ cursor: "pointer" }}>
                    <td><When at={a.sent_at} /></td>
                    <td><a {...linkProps(`/alerts/${a.id}`)}>{a.engineer_name}</a><div className="faint" style={{ fontSize: 12 }}>{a.team ?? ""}</div></td>
                    <td style={{ whiteSpace: "nowrap" }}>{ruleShort(a.rule)}</td>
                    <td className="mono">{ticketLabel(a.ticket_num, a.ticket_id)}</td>
                    <td className="muted" style={{ maxWidth: 520 }}>{a.reason}</td>
                    <td>{a.review ? <span className={`tag ${a.review.verdict}`} style={{ fontSize: 12, fontWeight: 600 }}>{a.review.verdict === "correct" ? "Correct" : "False alarm"}</span> : <span className="faint">Unreviewed</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {more && <div style={{ padding: 12 }}><button className="btn" onClick={loadMore}>Load older alerts</button></div>}
      </section>
    </div>
  );
}
