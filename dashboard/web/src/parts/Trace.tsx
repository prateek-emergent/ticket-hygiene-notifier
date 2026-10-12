// A check's (or a ticket's) story in order: scheduled -> model call -> alert -> finished.
import type { Activity } from "../api";
import { KIND_LABEL, OUTCOME_LABEL, ruleShort, tone } from "../lib";
import { When } from "./Common";

function headline(a: Activity): string {
  const kind = KIND_LABEL[a.kind] ?? a.kind;
  if (a.kind === "check") return `${kind}: ${OUTCOME_LABEL[a.outcome ?? ""] ?? a.outcome ?? ""}`;
  if (a.kind === "model") {
    const d = a.data ?? {};
    return `${kind}: ${String(d.model ?? "model")}`;
  }
  return kind;
}

function detail(a: Activity): string | null {
  const d = a.data ?? {};
  if (a.kind === "model") {
    const bits = [
      typeof d.probability === "number" ? `${Math.round((d.probability as number) * 100)}% that it asks the customer` : null,
      d.language && d.language !== "en" ? `reply in ${String(d.language)}` : null,
      typeof d.latency_ms === "number" ? `${((d.latency_ms as number) / 1000).toFixed(1)} s` : null,
      d.confidence ? `confidence ${String(d.confidence)}` : null,
    ].filter(Boolean);
    return [bits.join(" · "), d.reason ? String(d.reason) : null].filter(Boolean).join("\n");
  }
  return null;
}

export function TraceTimeline({ rows, showRule = false }: { rows: Activity[]; showRule?: boolean }) {
  if (!rows.length) return <div className="empty">Nothing recorded yet.</div>;
  return (
    <ol className="timeline" style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {rows.map((a) => {
        const extra = detail(a);
        const raw = a.data && (a.kind === "alert" || a.kind === "model" || a.kind === "start" || a.kind === "status");
        return (
          <li key={a.id} className="step" style={{ ["--c" as string]: tone(a) }}>
            <span className="k" aria-hidden="true" />
            <div>
              <div className="h">
                <b>{headline(a)}</b>
                <When at={a.at} />
                {showRule && a.rule && <span className="faint">{ruleShort(a.rule)}</span>}
              </div>
              {/* A model row's own detail says everything its summary does, and more. */}
              {extra ? <div className="b" style={{ whiteSpace: "pre-wrap" }}>{extra}</div>
                : <div className="b">{a.kind === "check" ? a.summary.replace(/^(flagged|ok|clean|skipped)(:\s*)?/i, "") || OUTCOME_LABEL[a.outcome ?? ""] : a.summary}</div>}
              {raw && (
                <details>
                  <summary>Raw record</summary>
                  <pre>{JSON.stringify(a.data, null, 2)}</pre>
                </details>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
