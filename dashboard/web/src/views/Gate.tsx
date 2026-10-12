// The sign-in gate. Google accounts on the allow-list only; the server checks both.
import { Moon, Sun } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { StillField } from "../parts/River";
import { api, type Me } from "../api";
import { Mark } from "../parts/Mark";
import type { Theme } from "../theme";

declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string }) => void;
      renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
    } } };
  }
}

function loadGoogle(): Promise<void> {
  if (window.google?.accounts) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Couldn't reach Google. Check your connection."));
    document.head.appendChild(s);
  });
}

export function Gate({ onSignedIn, theme, toggleTheme }: { onSignedIn: (m: Me) => void; theme: Theme; toggleTheme: () => void }) {
  const [cfg, setCfg] = useState<{ google_client_id: string | null; dev_login: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devEmail, setDevEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const btn = useRef<HTMLDivElement>(null);

  useEffect(() => { api.public().then(setCfg).catch(() => setError("The dashboard server isn't answering.")); }, []);

  useEffect(() => {
    if (!cfg?.google_client_id || !btn.current) return;
    let alive = true;
    loadGoogle().then(() => {
      if (!alive || !btn.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: cfg.google_client_id!,
        callback: async ({ credential }) => {
          setBusy(true); setError(null);
          try { onSignedIn(await api.loginGoogle(credential)); } catch (e) { setError(e instanceof Error ? e.message : "Sign-in failed."); } finally { setBusy(false); }
        },
      });
      btn.current.innerHTML = "";
      window.google.accounts.id.renderButton(btn.current, {
        theme: theme === "dark" ? "filled_black" : "outline", size: "large", shape: "pill", text: "signin_with", width: 320,
      });
    }).catch((e) => setError(e.message));
    return () => { alive = false; };
  }, [cfg, theme, onSignedIn]);

  async function dev(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try { onSignedIn(await api.loginDev(devEmail.trim())); } catch (err) { setError(err instanceof Error ? err.message : "Sign-in failed."); } finally { setBusy(false); }
  }

  return (
    <main className="gate">
      {/* A still frame of the river: the glass needs something to frost. */}
      <StillField />
      <button className="theme-switch gate-theme" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} aria-pressed={theme === "dark"} title="Dark / light">
        <span className="knob">{theme === "dark" ? <Moon size={12} /> : <Sun size={12} />}</span>
      </button>
      <section className="glass card" aria-labelledby="gate-h">
        <Mark size={44} />
        <h1 id="gate-h">Ticket Hygiene</h1>
        <p>Sign in with your Emergent Google account. Only associates on the access list can enter. Everything here is read-only on Trinity.</p>
        <div className="gbtn" ref={btn} aria-busy={busy}>
          {cfg && !cfg.google_client_id && <p className="faint" style={{ fontSize: 13 }}>Google sign-in isn't set up on this server yet (GOOGLE_CLIENT_ID).</p>}
        </div>
        {cfg?.dev_login && (
          <form className="dev" onSubmit={dev}>
            <label htmlFor="dev-email">Local sign-in (this machine only, for testing)</label>
            <input id="dev-email" className="input" type="email" required placeholder="you@emergent.sh" value={devEmail} onChange={(e) => setDevEmail(e.target.value)} />
            <button className="btn primary" disabled={busy}>Sign in</button>
          </form>
        )}
        {error && <p className="error-line" role="alert" style={{ marginTop: 14 }}>{error}</p>}
      </section>
    </main>
  );
}
