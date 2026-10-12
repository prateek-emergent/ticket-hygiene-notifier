import type { ReactNode } from "react";
import type { Activity } from "../api";
import { KIND_LABEL, OUTCOME_LABEL, clock, fullTime, tone } from "../lib";

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><b>{title}</b>{children}</div>;
}

export function Loading({ lines = 4 }: { lines?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => <div key={i} className="skeleton" style={{ width: `${90 - i * 12}%` }} />)}
    </div>
  );
}

export function Failed({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <div className="empty">
      <b>Couldn't load this.</b>
      <span className="error-line">{error}</span>
      {retry && <> · <button className="chip" onClick={retry}>Try again</button></>}
    </div>
  );
}

export function Outcome({ a }: { a: Pick<Activity, "kind" | "outcome"> }) {
  const label = OUTCOME_LABEL[a.outcome ?? ""] ?? KIND_LABEL[a.kind] ?? a.outcome ?? a.kind;
  return <span className="outcome" style={{ ["--c" as string]: tone(a) }}>{label}</span>;
}

export function When({ at }: { at: string | null | undefined }) {
  return <time dateTime={at ?? undefined} title={fullTime(at)}>{clock(at)}</time>;
}

/** The model's probability on the 0-100% line, with the uncertain band (no alert) in the middle. */
export function ScoreBar({ p, model }: { p: number; model?: string | null }) {
  return (
    <div className="score">
      <div className="muted" style={{ fontSize: 13 }}>
        Chance the reply asks the customer something{model ? `, judged by ${model}` : ""}
      </div>
      <div className="bar" role="img" aria-label={`${Math.round(p * 100)} percent`}>
        <div className="marker" style={{ left: `${p * 100}%` }}><span>{Math.round(p * 100)}%</span></div>
      </div>
      <div className="zones"><span>Asks nothing: alert</span><span>Unsure: no alert</span><span>Asks: no alert</span></div>
    </div>
  );
}
