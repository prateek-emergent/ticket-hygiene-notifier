import { Activity as ActivityIcon, Bell, Clock, Inbox, LogOut, Moon, Server, Sun, Ticket, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Me, type People } from "./api";
import { ago, initials, useData, useNow, WINDOWS } from "./lib";
import { LiveProvider, useLive } from "./live";
import { linkProps, useRoute } from "./router";
import { ScopeProvider, useScope } from "./scope";
import { useTheme, type Theme } from "./theme";
import { Mark } from "./parts/Mark";
import { Field } from "./parts/River";
import { Empty } from "./parts/Common";
import { AlertsView } from "./views/Alerts";
import { AlertView } from "./views/Alert";
import { Gate } from "./views/Gate";
import { LiveView } from "./views/Live";
import { ReviewView } from "./views/Review";
import { ShiftsView } from "./views/Shifts";
import { SystemView } from "./views/System";
import { TeamView } from "./views/Team";
import { TicketFinder, TicketView } from "./views/Ticket";

export function App() {
  const [theme, toggleTheme] = useTheme();
  const [me, setMe] = useState<Me | null | undefined>(undefined); // undefined = checking
  const [people, setPeople] = useState<People | null>(null);

  useEffect(() => {
    api.me().then(setMe).catch((e) => setMe(e instanceof ApiError && e.status === 401 ? null : null));
    const out = () => setMe(null);
    window.addEventListener("hygiene:signed-out", out);
    return () => window.removeEventListener("hygiene:signed-out", out);
  }, []);
  useEffect(() => { if (me) api.people().then(setPeople).catch(() => setPeople(null)); }, [me]);
  const signedIn = useCallback((m: Me) => setMe(m), []);

  if (me === undefined) return null;
  if (me === null) return <Gate onSignedIn={signedIn} theme={theme} toggleTheme={toggleTheme} />;
  return (
    <LiveProvider>
      <ScopeProvider me={me} people={people}>
        <Field />
        <Shell theme={theme} toggleTheme={toggleTheme} onSignOut={async () => { await api.logout().catch(() => {}); setMe(null); }} />
      </ScopeProvider>
    </LiveProvider>
  );
}

const NAV = [
  { to: "/", label: "Live", icon: ActivityIcon, match: ["live"] },
  { to: "/alerts", label: "Alerts", icon: Bell, match: ["alerts", "alert"] },
  { to: "/review", label: "Review", icon: Inbox, match: ["review"] },
  { to: "/shifts", label: "Shifts", icon: Clock, match: ["shifts"] },
  { to: "/team", label: "Team", icon: Users, match: ["team"] },
  { to: "/tickets", label: "Tickets", icon: Ticket, match: ["ticket", "tickets"] },
  { to: "/system", label: "System", icon: Server, match: ["system"] },
];

function Shell({ theme, toggleTheme, onSignOut }: { theme: Theme; toggleTheme: () => void; onSignOut: () => void }) {
  const [route, params] = useRoute();
  const { me, people, team, setTeam, hours, setHours } = useScope();
  useNow(5000); // keeps "last poll Ns ago" current
  const { status, version } = useLive();
  const unreviewed = useData(() => api.alerts({ team, review: "unreviewed", limit: 99 }), [team], version);
  const count = unreviewed.data?.items.length ?? 0;
  const dot = !status ? "stale" : status.live ? "" : "down";

  useEffect(() => {
    const titles: Record<string, string> = { live: "Live", alerts: "Alerts", alert: "Alert", review: "Review", shifts: "Shifts", team: "Team", ticket: "Ticket", tickets: "Tickets", system: "System" };
    document.title = `${count ? `(${count}) ` : ""}${titles[route.name] ?? "Ticket Hygiene"} · Ticket Hygiene`;
  }, [route.name, count]);

  return (
    <div className="shell">
      <nav className="rail" aria-label="Main">
        <a className="mark" {...linkProps("/")} aria-label="Ticket Hygiene, live"><Mark /></a>
        {NAV.map((n) => (
          <a key={n.to} {...linkProps(n.to)} aria-current={n.match.includes(route.name) ? "page" : undefined}>
            <n.icon size={19} strokeWidth={1.75} aria-hidden="true" />
            {n.label}
            {n.to === "/review" && count > 0 && <span className="count" aria-label={`${count} unreviewed`}>{count > 98 ? "99+" : count}</span>}
          </a>
        ))}
        <span className="spacer" />
      </nav>
      <header className="topbar">
        <h1>Ticket Hygiene</h1>
        <select className="select" value={team ?? ""} onChange={(e) => setTeam(e.target.value || null)} aria-label="Team">
          {people?.teams.map((t) => <option key={t.name} value={t.name}>{t.name}{me.teams.includes(t.name) ? " (yours)" : ""}</option>)}
          <option value="">All teams</option>
        </select>
        <select className="select hide-sm" value={hours} onChange={(e) => setHours(Number(e.target.value))} aria-label="Time window">
          {WINDOWS.map((w) => <option key={w.h} value={w.h}>{w.label}</option>)}
        </select>
        <span className="grow" />
        <span className="livestate hide-sm" title={status?.heartbeat ? `Notifier heartbeat ${status.heartbeat}` : undefined}>
          <span className={`dot ${dot}`} aria-hidden="true" />
          <span className="word">
            {!status ? "Connecting" : status.live ? `Live${status.last_cycle ? ` · last poll ${ago(status.last_cycle.at)}` : ""}` : status.heartbeat ? "Notifier stopped" : "Notifier not started"}
          </span>
        </span>
        <button className="theme-switch" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} aria-pressed={theme === "dark"} title="Dark / light">
          <span className="knob">{theme === "dark" ? <Moon size={12} /> : <Sun size={12} />}</span>
        </button>
        <span className="me hide-sm" title={me.email}>
          <span className="avatar">{me.picture ? <img src={me.picture} alt="" referrerPolicy="no-referrer" /> : initials(me.name)}</span>
        </span>
        <button className="iconbtn" onClick={onSignOut} aria-label="Sign out" title="Sign out"><LogOut size={15} /></button>
      </header>
      {status && !status.live && status.heartbeat && (
        <div className="banner" role="status">The notifier hasn't checked in since {new Date(status.heartbeat).toLocaleTimeString()}. Nothing new is being checked until it's restarted (python -m notifier run).</div>
      )}
      <main>
        {route.name === "live" && <LiveView />}
        {route.name === "alerts" && <AlertsView params={params} />}
        {route.name === "alert" && <AlertView id={route.id} />}
        {route.name === "review" && <ReviewView />}
        {route.name === "shifts" && <ShiftsView />}
        {route.name === "team" && <TeamView />}
        {route.name === "tickets" && <TicketFinder />}
        {route.name === "ticket" && <TicketView ticketRef={route.ref} />}
        {route.name === "system" && <SystemView params={params} />}
        {route.name === "notfound" && <div className="page"><Empty title="There's no page here.">Head back to <a {...linkProps("/")}>Live</a>.</Empty></div>}
      </main>
    </div>
  );
}
