import { ArrowDown, ArrowUp } from "lucide-react";
import { useState } from "react";
import { api, type Engineer } from "../api";
import { ago, RULES, useData, windowLabel } from "../lib";
import { useLive } from "../live";
import { linkProps } from "../router";
import { useScope } from "../scope";
import { Empty, Failed, Loading } from "../parts/Common";

type Key = "name" | "alerts" | "false_alarms" | "checks" | string;

export function TeamView() {
  const { team, hours } = useScope();
  const { version } = useLive();
  const [sort, setSort] = useState<{ key: Key; desc: boolean }>({ key: "alerts", desc: true });
  const { data, error, loading, reload } = useData(() => api.engineers(hours, team), [hours, team], version);

  const value = (e: Engineer, k: Key): string | number =>
    k === "name" ? e.name : k === "alerts" ? e.alerts : k === "false_alarms" ? e.false_alarms : k === "checks" ? e.checks : e.by_rule[k] ?? 0;
  const rows = [...(data ?? [])].sort((a, b) => {
    const x = value(a, sort.key), y = value(b, sort.key);
    const c = typeof x === "string" ? x.localeCompare(String(y)) : x - (y as number);
    return sort.desc ? -c : c;
  });
  const head = (k: Key, label: string, num = true) => (
    <th className={num ? "num" : undefined} aria-sort={sort.key === k ? (sort.desc ? "descending" : "ascending") : "none"}>
      <button onClick={() => setSort((s) => ({ key: k, desc: s.key === k ? !s.desc : k !== "name" }))}>
        {label}{sort.key === k && (sort.desc ? <ArrowDown size={12} /> : <ArrowUp size={12} />)}
      </button>
    </th>
  );

  return (
    <div className="page">
      <div className="page-head">
        <div><h2>{team ?? "All teams"}</h2><p>Who was flagged, for what, and how many of those alerts were marked false alarms, {windowLabel(hours)}.</p></div>
      </div>
      <section className="glass" style={{ padding: "6px 10px" }}>
        {loading && !data ? <div style={{ padding: 12 }}><Loading lines={8} /></div> : error && !data ? <Failed error={error} retry={reload} /> : rows.length === 0 ? (
          <Empty title="No engineers in this team.">Check config/teams.yaml.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr>
                {head("name", "Engineer", false)}
                {head("alerts", "Alerts")}
                {RULES.map((r) => <th key={r.id} className="num" style={{ whiteSpace: "normal", maxWidth: 110 }}><button onClick={() => setSort((s) => ({ key: r.id, desc: s.key === r.id ? !s.desc : true }))}>{r.short}</button></th>)}
                {head("false_alarms", "False alarms")}
                {head("checks", "Checks")}
                <th>Last checked</th>
              </tr></thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.email}>
                    <td><a {...linkProps(`/alerts?q=${encodeURIComponent(e.email)}`)}>{e.name}</a>{!team && <div className="faint" style={{ fontSize: 12 }}>{e.team}</div>}</td>
                    <td className={`n${e.alerts ? "" : " zero"}`} style={{ fontWeight: 600 }}>{e.alerts}</td>
                    {RULES.map((r) => <td key={r.id} className={`n${e.by_rule[r.id] ? "" : " zero"}`}>{e.by_rule[r.id] ?? 0}</td>)}
                    <td className={`n${e.false_alarms ? "" : " zero"}`}>{e.false_alarms}</td>
                    <td className={`n${e.checks ? "" : " zero"}`}>{e.checks}</td>
                    <td className="faint">{e.last_activity ? <time dateTime={e.last_activity}>{ago(e.last_activity)}</time> : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
