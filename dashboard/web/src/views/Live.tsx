// First viewport: the river, then your team's unreviewed alerts, the themes, and the notifier's health.
// Below: the live feed, its head naming the span in view.
import { ArrowRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Activity } from "../api";
import { ago, clock, ruleShort, RULES, ticketLabel, tone, useData, windowLabel } from "../lib";
import { useLive } from "../live";
import { linkProps, navigate } from "../router";
import { useScope } from "../scope";
import { Empty, Failed, Loading, When } from "../parts/Common";
import { River } from "../parts/River";

export function LiveView() {
  const { team, members, hours } = useScope();
  const { version } = useLive();
  return (
    <>
      <River team={team} members={members} />
      <div className="panes">
        <Unreviewed team={team} refresh={version} />
        <Rules team={team} hours={hours} refresh={version} />
        <Health />
      </div>
      <Feed members={members} />
    </>
  );
}

function Unreviewed({ team, refresh }: { team: string | null; refresh: number }) {
  const { data, error, loading, reload } = useData(() => api.alerts({ team, review: "unreviewed", limit: 6 }), [team], refresh);
  // J: straight into the review queue, at the first unreviewed alert.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.key !== "j" || e.metaKey || e.ctrlKey || e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
      e.preventDefault();
      navigate("/review");
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
  return (
    <section className="glass pane" aria-labelledby="unrev-h">
      <div className="pane-head">
        <h3 id="unrev-h">{team ? "Your team, unreviewed" : "Unreviewed, all teams"}</h3>
        {data && data.items.length > 0 && <a className="aside" {...linkProps("/review")}>Review queue <span className="kbd">J</span></a>}
      </div>
      {loading && !data ? <Loading /> : error && !data ? <Failed error={error} retry={reload} /> : data && data.items.length === 0 ? (
        <Empty title="Nothing waiting for review.">Every alert for {team ?? "all teams"} has a verdict. New ones appear here as they fire.</Empty>
      ) : (
        <div className="rows">
          {data!.items.map((a) => (
            <a key={a.id} className="arow" {...linkProps(`/alerts/${a.id}`)}>
              <i className="pip" aria-hidden="true" />
              <div style={{ minWidth: 0 }}>
                <div className="who">{a.engineer_name} <span className="mono faint">· {ticketLabel(a.ticket_num, a.ticket_id)}</span></div>
                <div className="why">{ruleShort(a.rule)}: {a.reason}</div>
              </div>
              <When at={a.sent_at} />
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function Rules({ team, hours, refresh }: { team: string | null; hours: number; refresh: number }) {
  const { data, error, loading, reload } = useData(() => api.overview(hours, team), [team, hours], refresh);
  const { status } = useLive();
  const on = new Set(status?.info?.rules ?? RULES.map((r) => r.id));
  const peak = Math.max(1, ...(data?.per_rule.flatMap((r) => r.last12h.checks) ?? [1]));
  return (
    <section className="glass pane" aria-labelledby="rules-h">
      <div className="pane-head"><h3 id="rules-h">Themes, {windowLabel(hours)}</h3><span className="aside">alerts</span></div>
      {loading && !data ? <Loading lines={6} /> : error && !data ? <Failed error={error} retry={reload} /> : (
        <div className="rows">
          {data!.per_rule.map((r) => (
            <a key={r.rule} className={`rule-row${on.has(r.rule) ? "" : " off"}`} {...linkProps(`/alerts?rule=${r.rule}`)} style={{ textDecoration: "none" }}
              aria-label={`${ruleShort(r.rule)}: ${r.alerts} alerts in the last ${hours} hours`}>
              <span>{ruleShort(r.rule)}{on.has(r.rule) ? "" : " (off)"}</span>
              <span className="hours" aria-hidden="true" title="Checks per hour over the last 12 hours; red where it alerted">
                {r.last12h.checks.map((c, i) => (
                  <i key={i} className={r.last12h.alerts[i] ? "hot" : c ? "" : "none"} style={{ height: `${c || r.last12h.alerts[i] ? Math.max(12, (Math.max(c, r.last12h.alerts[i]) / peak) * 100) : 0}%` }} />
                ))}
              </span>
              <span className={`n num${r.alerts ? "" : " zero"}`}>{r.alerts}</span>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function Health() {
  const { status, connected } = useLive();
  const info = status?.info;
  const word = !status ? "Connecting" : !status.heartbeat ? "Not started" : status.live ? "Healthy" : "Not running";
  const cls = !status || status.live ? "" : !status.heartbeat ? "stale" : "down";
  return (
    <section className="glass pane" aria-labelledby="health-h">
      <div className="pane-head"><h3 id="health-h">Notifier</h3>{info && <span className="aside">{info.mode === "run" ? "Polling" : "Event-driven"}{info.dry_run ? " · dry run" : ""}</span>}</div>
      <div className={`health-word ${cls}`}>{word}</div>
      <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
        {status?.live ? `Heartbeat ${ago(status.heartbeat)}` : status?.heartbeat ? `Last heartbeat ${ago(status.heartbeat)}. Start it with: python -m notifier run` : "Waiting for the first heartbeat."}
        {!connected && " · reconnecting to the live stream"}
      </p>
      <div className="rows">
        <div className="kv"><span>Theme 1 model</span><span>{info ? `${info.pending_model.option} · ${info.pending_model.models.join(" + ")}` : "-"}</span></div>
        <div className="kv"><span>Checks waiting</span><span className="num">{status?.checks_waiting ?? "-"}</span></div>
        <div className="kv"><span>Last poll</span><span>{status?.last_cycle ? <When at={status.last_cycle.at} /> : "-"}</span></div>
        <div className="kv"><span>Last error</span><span className={status?.last_error ? "" : "faint"}>{status?.last_error ? <time dateTime={status.last_error.at}>{ago(status.last_error.at)}</time> : "none"}</span></div>
      </div>
      <a className="aside" style={{ display: "inline-block", marginTop: 10, fontSize: 12 }} {...linkProps("/system")}>System details <ArrowRight size={12} style={{ verticalAlign: -1 }} /></a>
    </section>
  );
}

/** Decisions: one row per conclusion. A check whose model call or alert is already shown isn't repeated.
 *  Everything: also scheduling, clean checks, the check rows behind each decision, and poll cycles. */
function decisions(rows: Activity[]): Activity[] {
  const told = new Set(rows.filter((a) => a.kind === "model" || a.kind === "alert").map((a) => `${a.rule}|${a.trigger_event_id}`));
  return rows.filter((a) => {
    if (a.kind === "check") return a.outcome !== "clean" && a.outcome !== "duplicate" && !told.has(`${a.rule}|${a.trigger_event_id}`);
    if (a.kind === "status") return a.outcome !== "ok";
    if (a.kind === "model") return !rows.some((b) => b.kind === "alert" && b.trigger_event_id === a.trigger_event_id && b.rule === a.rule);
    return a.kind === "alert" || a.kind === "error" || a.kind === "start";
  });
}

function Feed({ members }: { members: Set<string> | null }) {
  const { recent } = useLive();
  const [everything, setEverything] = useState(false);
  const rows = useMemo(() => {
    const mine = recent.filter((a) => !members || !a.engineer || members.has(a.engineer.toLowerCase()));
    return (everything ? mine : decisions(mine)).slice(-250).reverse();
  }, [recent, members, everything]);
  const firstId = useRef<number | null>(null);
  if (firstId.current === null && recent.length) firstId.current = recent[recent.length - 1].id;

  // Guide words: the span of rows currently in view, recomputed as you scroll.
  const [span, setSpan] = useState<[string, string, number] | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const update = () => {
      const top = 64 + 52;
      const visible = [...list.children].filter((el) => {
        const r = el.getBoundingClientRect();
        return r.bottom > top && r.top < window.innerHeight;
      }) as HTMLElement[];
      if (!visible.length) return setSpan(null);
      const a = visible[visible.length - 1].dataset.at!, b = visible[0].dataset.at!;
      setSpan([a, b, visible.length]);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, [rows]);

  return (
    <section className="glass feed" aria-labelledby="feed-h">
      <div className="feed-head">
        <h3 id="feed-h">Everything, as it happens</h3>
        {span && <span className="span mono">{clock(span[0])}–{clock(span[1])} · {span[2]} in view</span>}
        <span className="grow" />
        <div className="chips" role="group" aria-label="Show">
          <button className="chip" aria-pressed={!everything} onClick={() => setEverything(false)}>Decisions</button>
          <button className="chip" aria-pressed={everything} onClick={() => setEverything(true)}>Everything</button>
        </div>
      </div>
      {rows.length === 0 ? (
        <Empty title={everything ? "No activity yet." : "No decisions yet."}>
          {everything ? "The notifier writes here as it scans Trinity and runs checks." : "Alerts, model calls and skipped checks appear here. Everything shows the routine work too."}
        </Empty>
      ) : (
        <div ref={listRef}>
          {rows.map((a) => <FeedRow key={a.id} a={a} isNew={firstId.current !== null && a.id > firstId.current} />)}
        </div>
      )}
    </section>
  );
}

function FeedRow({ a, isNew }: { a: Activity; isNew: boolean }) {
  const target = a.ticket_id ? `/tickets/${encodeURIComponent(a.ticket_id)}` : null;
  return (
    <div className={`erow${isNew ? " new" : ""}`} data-at={a.at} style={{ ["--c" as string]: tone(a) }}>
      <When at={a.at} />
      <i className="k" aria-hidden="true" />
      <span className="r">{a.rule ? ruleShort(a.rule) : a.kind === "cycle" ? "Poll" : "System"}</span>
      <span className="s">
        {a.engineer_name && <b style={{ fontWeight: 500 }}>{a.engineer_name}: </b>}
        {target ? <a {...linkProps(target)}>{a.summary}</a> : a.summary}
      </span>
      <span className="tk mono">{a.ticket_id ? ticketLabel(a.ticket_num, a.ticket_id) : ""}</span>
    </div>
  );
}
