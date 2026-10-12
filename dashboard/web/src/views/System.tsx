// The notifier itself: is it running, with what, how the models perform, what was skipped, what failed.
import { api } from "../api";
import { ago, OUTCOME_LABEL, ruleShort, useData, windowLabel } from "../lib";
import { useLive } from "../live";
import { useScope } from "../scope";
import { Empty, Failed, Loading, When } from "../parts/Common";


export function SystemView({ params }: { params: URLSearchParams }) {
  const { status, version, connected } = useLive();
  const { hours } = useScope();
  void params;
  const ov = useData(() => api.overview(hours, null), [hours], version);
  const errors = useData(() => api.activity({ kinds: "error", limit: 30 }), [], version);
  const info = status?.info;
  const outcomes = ov.data?.totals.outcomes ?? {};
  const totalChecks = Object.values(outcomes).reduce((a, b) => a + b, 0);

  return (
    <div className="page">
      <div className="page-head">
        <div><h2>System</h2><p>The notifier's own health, configuration and model performance, {windowLabel(hours)}. All teams.</p></div>
      </div>
      <div className="panes" style={{ padding: 0 }}>
        <section className="glass pane">
          <div className="pane-head"><h3>Running</h3><span className="aside">{connected ? "live stream connected" : "reconnecting"}</span></div>
          <div className={`health-word ${!status || status.live ? "" : status.heartbeat ? "down" : "stale"}`}>{!status ? "Connecting" : status.live ? "Healthy" : status.heartbeat ? "Not running" : "Not started"}</div>
          <div className="rows" style={{ marginTop: 8 }}>
            <div className="kv"><span>Heartbeat</span><span>{status?.heartbeat ? <time dateTime={status.heartbeat}>{ago(status.heartbeat)}</time> : "never"}</span></div>
            <div className="kv"><span>Mode</span><span>{info ? `${info.mode}, every ${info.poll_seconds} s` : "-"}</span></div>
            <div className="kv"><span>Posting</span><span>{info ? (info.dry_run ? "Dry run: terminal only" : `Slack ${info.slack_channel}`) : "-"}</span></div>
            <div className="kv"><span>Started</span><span>{info ? <When at={info.started} /> : "-"}</span></div>
            <div className="kv"><span>Checks waiting</span><span className="num">{status?.checks_waiting ?? "-"}</span></div>
            <div className="kv"><span>Last poll</span><span title={status?.last_cycle?.summary}>{status?.last_cycle ? <When at={status.last_cycle.at} /> : "-"}</span></div>
          </div>
        </section>
        <section className="glass pane">
          <div className="pane-head"><h3>Configuration</h3><span className="aside">from config.py</span></div>
          <div className="rows">
            <div className="kv"><span>Theme 1 model</span><span>{info ? `Option ${info.pending_model.option}: ${info.pending_model.models.join(" + ")}` : "-"}</span></div>
            <div className="kv"><span>Theme 6 judge</span><span>{info?.l3_judge ? `${info.l3_judge.model}${info.l3_judge.fallback ? `, ${info.l3_judge.fallback} fallback` : ""}` : "off"}</span></div>
            {info?.rules && ["pending_without_open_question", "reassigned_from_colleague", "picked_up_during_overwatch_run", "status_not_matching_shift", "ticket_held_off_shift", "l3_escalation_check", "escalation_note_quality"].map((r) => (
              <div key={r} className="kv"><span>{ruleShort(r)}</span><span className={info.rules.includes(r) ? "" : "faint"}>{info.rules.includes(r) ? "On" : "Off"}</span></div>
            ))}
          </div>
        </section>
        <section className="glass pane">
          <div className="pane-head"><h3>Models</h3><span className="aside">{ov.data?.models.calls ?? 0} calls</span></div>
          {ov.loading && !ov.data ? <Loading /> : ov.error && !ov.data ? <Failed error={ov.error} retry={ov.reload} /> : !ov.data!.models.latency.length ? <Empty title="No model calls in this window." /> : (
            <div className="rows">
              {ov.data!.models.latency.map((m) => (
                <div key={m.model} className="kv"><span>{m.model}<div className="faint" style={{ fontSize: 12 }}>{m.calls} calls</div></span>
                  <span className="num">{m.p50_ms !== null ? `${(m.p50_ms / 1000).toFixed(1)} s` : "-"}<div className="faint" style={{ fontSize: 12 }}>p95 {m.p95_ms !== null ? `${(m.p95_ms / 1000).toFixed(1)} s` : "-"}</div></span></div>
              ))}
              {Object.entries(ov.data!.models.outcomes).map(([k, v]) => <div key={k} className="kv"><span>{OUTCOME_LABEL[k] ?? k}</span><span className="num">{v}</span></div>)}
            </div>
          )}
        </section>
      </div>
      <div className="panes" style={{ padding: 0, marginTop: 20, gridTemplateColumns: "1fr 1.4fr" }}>
        <section className="glass pane">
          <div className="pane-head"><h3>Check outcomes</h3><span className="aside">{totalChecks} checks</span></div>
          {!totalChecks ? <Empty title="No checks finished in this window." /> : (
            <div className="rows">
              {Object.entries(outcomes).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                <div key={k} className="kv"><span>{OUTCOME_LABEL[k] ?? k}</span><span className="num">{v} <span className="faint">· {Math.round((v / totalChecks) * 100)}%</span></span></div>
              ))}
            </div>
          )}
        </section>
        <section className="glass pane">
          <div className="pane-head"><h3>Recent errors</h3><span className="aside">retried automatically</span></div>
          {errors.loading && !errors.data ? <Loading /> : !errors.data?.length ? <Empty title="No errors recorded." /> : (
            <div className="rows">
              {errors.data.map((e) => <div key={e.id} className="kv" style={{ alignItems: "baseline" }}><span style={{ color: "var(--ink-2)", overflowWrap: "anywhere" }}>{e.summary}</span><When at={e.at} /></div>)}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
