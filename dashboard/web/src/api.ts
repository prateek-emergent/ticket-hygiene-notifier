// Typed client for the dashboard API (dashboard/app.py). Every call sends the session cookie;
// POSTs carry X-Requested-With, which the server requires (blocks forged cross-site posts).

export type Outcome = "clean" | "ok" | "flagged" | "skipped" | "duplicate" | "error" | "waiting" | string;

export interface Me { email: string; name: string; picture: string | null; teams: string[] }
export interface Person { email: string; name: string }
export interface Team { name: string; associates: Person[]; engineers: Person[] }
export interface People { teams: Team[]; rules: { id: string; title: string }[] }

export interface Activity {
  id: number; at: string; kind: string; rule: string | null; trigger_event_id: string | null;
  ticket_id: string | null; ticket_num: number | null; engineer: string | null; engineer_name: string | null;
  team: string | null; outcome: Outcome | null; summary: string; data: Record<string, unknown> | null;
}

export interface Review { verdict: "correct" | "false_alarm"; by: string; by_name: string; at: string; note: string | null }

export interface Alert {
  id: number; rule: string; rule_title: string; ticket_id: string | null; ticket_num: number | null;
  subject: string | null; engineer: string; engineer_name: string; team: string | null; associates: string[];
  reason: string | null; url: string | null; dry_run: boolean | null; sent_at: string; review: Review | null;
}

export interface AlertDetail extends Alert {
  payload: Record<string, unknown> | null;
  trace: Activity[];
  feedback_history: { id: number; verdict: string; note: string | null; by_email: string; by_name: string; at: string }[];
}

export interface Status {
  live: boolean; heartbeat: string | null; checks_waiting: number; last_activity_id: number;
  info: {
    mode: string; started: string; rules: string[]; dry_run: boolean; poll_seconds: number;
    pending_model: { option: string; models: string[]; url: string };
    l3_judge: { model: string | null; fallback: string | null } | null;
    slack_channel: string; shifts_file: string;
  } | null;
  last_error: { at: string; summary: string } | null;
  last_cycle: { at: string; summary: string } | null;
}

export interface Overview {
  hours: number; team: string | null;
  totals: { alerts: number; checks: number; outcomes: Record<string, number>; reviewed: Record<string, number>; unreviewed: number };
  per_rule: { rule: string; title: string; alerts: number; outcomes: Record<string, number>; last12h: { checks: number[]; alerts: number[] } }[];
  timeline: { step_hours: number; buckets: { t: string; alerts: number; checks: number }[] };
  models: { calls: number; outcomes: Record<string, number>; latency: { model: string; calls: number; p50_ms: number | null; p95_ms: number | null }[] };
  top_engineers: { email: string; name: string; team: string | null; alerts: number }[];
}

export interface Engineer {
  email: string; name: string; team: string; associates: string[]; alerts: number;
  by_rule: Record<string, number>; checks: number; false_alarms: number; last_activity: string | null;
}

export interface TicketTrace {
  ticket_id: string; ticket_num: number | null; subject: string | null; url: string | null;
  trace: Activity[]; alerts: Alert[];
  checks: { rule: string; trigger_event_id: string; due_at: string; attempts: number; done: number; outcome: string | null; engineer: string | null; created_at: string | null; finished_at: string | null }[];
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: "same-origin", ...init });
  if (!res.ok) {
    let message = res.statusText;
    try { message = (await res.json()).error ?? message; } catch { /* not JSON */ }
    if (res.status === 401) window.dispatchEvent(new Event("hygiene:signed-out"));
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Requested-With": "dashboard" },
    body: JSON.stringify(body),
  });
}

function qs(params: Record<string, string | number | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  public: () => request<{ google_client_id: string | null; dev_login: boolean }>("/api/public"),
  me: () => request<Me>("/api/me"),
  loginGoogle: (credential: string) => post<Me>("/api/auth/google", { credential }),
  loginDev: (email: string) => post<Me>("/api/auth/dev", { email }),
  logout: () => post<{ ok: boolean }>("/api/auth/logout", {}),
  people: () => request<People>("/api/people"),
  status: () => request<Status>("/api/status"),
  overview: (hours: number, team: string | null) => request<Overview>(`/api/overview${qs({ hours, team })}`),
  alerts: (f: { rule?: string; team?: string | null; engineer?: string; review?: string; q?: string; hours?: number; before?: number; limit?: number }) =>
    request<{ items: Alert[]; more: boolean }>(`/api/alerts${qs(f)}`),
  alert: (id: number) => request<AlertDetail>(`/api/alerts/${id}`),
  feedback: (id: number, verdict: "correct" | "false_alarm", note: string) => post<AlertDetail>(`/api/alerts/${id}/feedback`, { verdict, note }),
  activity: (f: { before?: number; after?: number; kinds?: string; rule?: string; team?: string | null; limit?: number }) =>
    request<Activity[]>(`/api/activity${qs(f)}`),
  ticket: (ref: string) => request<TicketTrace>(`/api/tickets/${encodeURIComponent(ref)}`),
  engineers: (hours: number, team: string | null) => request<Engineer[]>(`/api/engineers${qs({ hours, team })}`),
};
