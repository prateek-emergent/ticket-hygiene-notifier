// Mark an alert correct or a false alarm. Verdicts stamp on and stay: a newer one strikes the older.
import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type AlertDetail } from "../api";
import { clock } from "../lib";

export function VerdictBox({ alert, onSaved, hotkeys = false }: { alert: AlertDetail; onSaved: (a: AlertDetail) => void; hotkeys?: boolean }) {
  const current = alert.review?.verdict ?? null;
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState<null | "correct" | "false_alarm">(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setNote(""); setError(null); }, [alert.id]);

  async function save(verdict: "correct" | "false_alarm") {
    setSaving(verdict);
    setError(null);
    try {
      onSaved(await api.feedback(alert.id, verdict, note));
      setNote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save. Try again.");
    } finally {
      setSaving(null);
    }
  }

  useEffect(() => {
    if (!hotkeys) return;
    const on = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey) return;
      if (e.key === "c") { e.preventDefault(); void save("correct"); }
      if (e.key === "f") { e.preventDefault(); void save("false_alarm"); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  return (
    <aside className="glass verdict-box" aria-label="Your verdict">
      <h3>Was this alert right?</h3>
      <p className="muted" style={{ fontSize: 13 }}>Your answer is saved with your name. It's how the models get measured and tuned.</p>
      <div className="choice">
        <button className="btn right" aria-pressed={current === "correct"} disabled={saving !== null} onClick={() => save("correct")}>
          <Check size={16} /> Correct{hotkeys && <span className="kbd">C</span>}
        </button>
        <button className="btn alarm" aria-pressed={current === "false_alarm"} disabled={saving !== null} onClick={() => save("false_alarm")}>
          <X size={16} /> False alarm{hotkeys && <span className="kbd">F</span>}
        </button>
      </div>
      <label className="faint" htmlFor={`note-${alert.id}`} style={{ fontSize: 12 }}>Note for the team (optional, saved with your answer)</label>
      <textarea id={`note-${alert.id}`} className="textarea" rows={3} value={note} onChange={(e) => setNote(e.target.value)}
        placeholder="e.g. the question was asked on a call" style={{ marginTop: 6 }} />
      {error && <p className="error-line" style={{ marginTop: 8 }}>{error}</p>}
      {alert.feedback_history.length > 0 && (
        <div className="stamp">
          {alert.feedback_history.map((f, i) => (
            <div key={f.id} className={`line${i > 0 ? " old" : ""}`}>
              <span className={`tag ${f.verdict}`}>{f.verdict === "correct" ? "Correct" : "False alarm"}</span>
              <span>{f.by_name} · <time>{clock(f.at)}</time>{f.note ? ` · ${f.note}` : ""}</span>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
