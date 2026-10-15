// "Export CSV": a plain download link; the server builds the file (dashboard/shiftviews.py export).
import { Download } from "lucide-react";
import { api } from "../api";

export function ExportLink({ kind, from, to, team, label = "Export CSV" }: {
  kind: "alerts" | "reviews" | "report" | "actions"; from?: string; to?: string; team?: string | null; label?: string;
}) {
  return (
    <a className="btn" href={api.exportUrl(kind, { from, to, team })} download title={`Download as CSV${from ? `, ${from} to ${to}` : ""}`}>
      <Download size={15} aria-hidden="true" /> {label}
    </a>
  );
}
