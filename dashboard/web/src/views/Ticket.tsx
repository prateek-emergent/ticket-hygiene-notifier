import { ExternalLink, Search } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { OUTCOME_LABEL, ruleShort, ticketLabel, useData } from "../lib";
import { useLive } from "../live";
import { linkProps, navigate } from "../router";
import { Empty, Failed, Loading, Outcome, When } from "../parts/Common";
import { TraceTimeline } from "../parts/Trace";

export function TicketFinder() {
  const [ref, setRef] = useState("");
  return (
    <div className="page">
      <div className="page-head"><div><h2>Tickets</h2><p>Everything the notifier recorded about one ticket: checks, model calls, alerts.</p></div></div>
      <form className="search" style={{ maxWidth: 420 }} onSubmit={(e) => { e.preventDefault(); if (ref.trim()) navigate(`/tickets/${encodeURIComponent(ref.trim().replace(/^#/, ""))}`); }}>
        <Search size={15} aria-hidden="true" />
        <input className="input" style={{ width: "100%" }} placeholder="Ticket number, e.g. 273283" value={ref} onChange={(e) => setRef(e.target.value)} aria-label="Ticket number or id" autoFocus />
      </form>
    </div>
  );
}

export function TicketView({ ticketRef }: { ticketRef: string }) {
  const { version } = useLive();
  const { data, error, loading, reload } = useData(() => api.ticket(ticketRef), [ticketRef], version);
  if (loading && !data) return <div className="page"><Loading lines={8} /></div>;
  if (error && !data) {
    return (
      <div className="page">
        {error.toLowerCase().includes("not found") ? (
          <Empty title={`Nothing recorded for ${ticketRef}.`}>The notifier only records tickets it checked. <a {...linkProps("/tickets")}>Find another ticket</a></Empty>
        ) : <Failed error={error} retry={reload} />}
      </div>
    );
  }
  const t = data!;
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2 className="mono" style={{ fontFamily: "inherit" }}>Ticket {ticketLabel(t.ticket_num, t.ticket_id)}</h2>
          <p>{t.subject ?? "Subject not recorded"}</p>
        </div>
        <span className="grow" />
        {t.url && <a className="btn" href={t.url} target="_blank" rel="noreferrer">Open in Trinity <ExternalLink size={14} /></a>}
      </div>
      <div className="detail">
        <section className="glass pane">
          <div className="pane-head"><h3>Trace</h3><span className="aside">{t.trace.length} records</span></div>
          <TraceTimeline rows={t.trace} showRule />
        </section>
        <div style={{ display: "grid", gap: 20 }}>
          <section className="glass pane">
            <div className="pane-head"><h3>Alerts</h3><span className="aside">{t.alerts.length}</span></div>
            {t.alerts.length === 0 ? <Empty title="No alerts on this ticket." /> : (
              <div className="rows">
                {t.alerts.map((a) => (
                  <a key={a.id} className="arow" {...linkProps(`/alerts/${a.id}`)}>
                    <i className={`pip${a.review ? " reviewed" : ""}`} aria-hidden="true" />
                    <div><div className="who">{a.engineer_name}</div><div className="why">{ruleShort(a.rule)}{a.review ? ` · ${a.review.verdict === "correct" ? "correct" : "false alarm"}` : ""}</div></div>
                    <When at={a.sent_at} />
                  </a>
                ))}
              </div>
            )}
          </section>
          <section className="glass pane">
            <div className="pane-head"><h3>Checks</h3><span className="aside">{t.checks.length}</span></div>
            <div className="rows">
              {t.checks.map((c) => (
                <div key={c.rule + c.trigger_event_id} className="kv" style={{ alignItems: "baseline" }}>
                  <span>{ruleShort(c.rule)}<div className="faint" style={{ fontSize: 12 }}>{c.engineer ?? ""}</div></span>
                  <span>{c.done ? <Outcome a={{ kind: "check", outcome: (c.outcome ?? "").split(":")[0].replace("flagged-unclassified", "flagged") }} /> : <span className="faint">due <When at={c.due_at} /></span>}
                    {c.done && c.outcome && !OUTCOME_LABEL[c.outcome] && <div className="faint" style={{ fontSize: 12, maxWidth: 260 }}>{c.outcome}</div>}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
