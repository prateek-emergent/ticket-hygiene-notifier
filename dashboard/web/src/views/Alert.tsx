// One alert's whole story: why it fired, the reply that was judged and its score, the Slack message,
// the trace from trigger to alert, and the associate's verdict.
import { ArrowLeft, ExternalLink } from "lucide-react";
import { api, type AlertDetail } from "../api";
import { fullTime, ruleShort, ticketLabel, useData } from "../lib";
import { linkProps } from "../router";
import { Failed, Loading, ScoreBar, When } from "../parts/Common";
import { TraceTimeline } from "../parts/Trace";
import { VerdictBox } from "../parts/Verdict";

export function AlertView({ id }: { id: number }) {
  const { data, error, loading, reload, setData } = useData(() => api.alert(id), [id]);
  return (
    <div className="page">
      <a className="faint" style={{ fontSize: 13, textDecoration: "none" }} {...linkProps("/alerts")}><ArrowLeft size={14} style={{ verticalAlign: -2 }} /> Alerts</a>
      {loading && !data ? <Loading lines={8} /> : error && !data ? <Failed error={error} retry={reload} /> : data && <AlertBody alert={data} onSaved={setData} />}
    </div>
  );
}

const DETAIL_LABELS: Record<string, string> = {
  previous_assignee: "Taken from", previous_held_for_minutes: "They had held it (min)", closed_by: "Closed by",
  pending_at: "Moved to Pending", kb_reference: "Knowledge base", judge_confidence: "Judge confidence", judged_by: "Judged by",
  waiting_since_local: "Customer waiting since", shift_ended_local: "Shift ended", language: "Reply language",
  kind: "Shift boundary", presence: "Status seen",
};

const LANGUAGES: Record<string, string> = { en: "English", it: "Italian", es: "Spanish", pt: "Portuguese", fr: "French", de: "German" };
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

function factValue(key: string, v: unknown) {
  if (key === "language") return LANGUAGES[String(v)] ?? String(v);
  if (typeof v === "string" && ISO.test(v)) return <time dateTime={v}>{fullTime(v)}</time>;
  return String(v);
}

export function AlertBody({ alert, onSaved, hotkeys = false }: { alert: AlertDetail; onSaved: (a: AlertDetail) => void; hotkeys?: boolean }) {
  const model = alert.trace.find((t) => t.kind === "model")?.data ?? null;
  const sent = alert.trace.find((t) => t.kind === "alert")?.data ?? null;
  const details = ((alert.payload?.details as Record<string, unknown> | undefined) ?? alert.payload ?? {}) as Record<string, unknown>;
  const facts = Object.entries(DETAIL_LABELS).filter(([k]) => details[k] !== undefined && details[k] !== null && details[k] !== "");
  const p = typeof model?.probability === "number" ? (model.probability as number) : null;
  const reply = typeof model?.reply_tail === "string" ? (model.reply_tail as string) : null;

  return (
    <div className="detail" style={{ marginTop: 14 }}>
      <article>
        <h2>{alert.engineer_name}: {ruleShort(alert.rule).toLowerCase()}</h2>
        <p className="muted" style={{ marginTop: 4 }}>{alert.rule_title}</p>
        <div className="facts">
          <div className="fact"><div className="l">Ticket</div><div className="v mono">
            {alert.url ? <a href={alert.url} target="_blank" rel="noreferrer">{ticketLabel(alert.ticket_num, alert.ticket_id)} <ExternalLink size={12} style={{ verticalAlign: -1 }} /></a> : ticketLabel(alert.ticket_num, alert.ticket_id)}
          </div></div>
          <div className="fact"><div className="l">Alerted</div><div className="v"><When at={alert.sent_at} /></div></div>
          <div className="fact"><div className="l">Team</div><div className="v">{alert.team ?? "-"}</div></div>
          <div className="fact"><div className="l">Sent to</div><div className="v">{alert.dry_run ? "Terminal only (dry run)" : "Slack"}</div></div>
        </div>
        {alert.subject && <p className="faint" style={{ marginTop: 10 }}>Subject: {alert.subject}</p>}
        <p className="reason">{alert.reason}</p>
        {p !== null && <ScoreBar p={p} model={String(model?.model ?? "")} />}
        {reply && (
          <>
            <h3 style={{ fontSize: 14, marginTop: 22 }}>The reply that was judged <span className="faint" style={{ fontWeight: 400 }}>(its last 600 characters)</span></h3>
            <div className="quote">{reply}</div>
          </>
        )}
        {facts.length > 0 && (
          <div className="facts" style={{ marginTop: 20 }}>
            {facts.map(([k, l]) => <div key={k} className="fact"><div className="l">{l}</div><div className="v">{factValue(k, details[k])}</div></div>)}
          </div>
        )}
        {typeof sent?.text === "string" && (
          <>
            <h3 style={{ fontSize: 14, marginTop: 22 }}>Message posted</h3>
            <div className="slack-msg">{sent.text as string}</div>
          </>
        )}
        <h3 style={{ fontSize: 14, marginTop: 26 }}>Trace</h3>
        <p className="faint" style={{ fontSize: 12 }}>Every step the notifier took for this check, in order. Times shown in your timezone; hover for the full date.</p>
        <TraceTimeline rows={alert.trace} />
        {alert.ticket_id && <a style={{ display: "inline-block", marginTop: 14, fontSize: 13 }} {...linkProps(`/tickets/${encodeURIComponent(alert.ticket_id)}`)}>Everything recorded for this ticket</a>}
      </article>
      <div>
        <VerdictBox alert={alert} onSaved={onSaved} hotkeys={hotkeys} />
        <p className="faint" style={{ fontSize: 12, marginTop: 10, padding: "0 6px" }} title={fullTime(alert.sent_at)}>
          Associates tagged: {alert.associates.join(", ") || "none"}
        </p>
      </div>
    </div>
  );
}
