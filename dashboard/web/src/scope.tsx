// Who is looking, and at what: the signed-in associate, the team filter (their own team by default,
// "all teams" one click away) and the time window. Shared by every view.
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Me, People } from "./api";

interface Scope {
  me: Me;
  people: People | null;
  team: string | null; // null = all teams
  setTeam: (t: string | null) => void;
  hours: number;
  setHours: (h: number) => void;
  members: Set<string> | null; // engineers of the selected team
}

const ScopeContext = createContext<Scope | null>(null);
const KEY = "hygiene-team";

export function ScopeProvider({ me, people, children }: { me: Me; people: People | null; children: ReactNode }) {
  const [team, setTeamState] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved !== null) return saved === "*" ? null : saved;
    } catch { /* not remembered */ }
    return me.teams[0] ?? null;
  });
  const [hours, setHoursState] = useState(() => {
    try {
      const h = Number(localStorage.getItem("hygiene-hours"));
      if ([1, 24, 168, 720].includes(h)) return h;
    } catch { /* not remembered */ }
    return 24;
  });
  const setHours = (h: number) => {
    setHoursState(h);
    try { localStorage.setItem("hygiene-hours", String(h)); } catch { /* not remembered */ }
  };
  const setTeam = (t: string | null) => {
    setTeamState(t);
    try { localStorage.setItem(KEY, t ?? "*"); } catch { /* not remembered */ }
  };
  const members = useMemo(() => {
    if (!team || !people) return null;
    const t = people.teams.find((x) => x.name === team);
    return t ? new Set(t.engineers.map((e) => e.email.toLowerCase())) : null;
  }, [team, people]);
  const value = useMemo(() => ({ me, people, team, setTeam, hours, setHours, members }), [me, people, team, hours, members]);
  return <ScopeContext.Provider value={value}>{children}</ScopeContext.Provider>;
}

export function useScope(): Scope {
  const s = useContext(ScopeContext);
  if (!s) throw new Error("useScope outside ScopeProvider");
  return s;
}
