// A small history-API router: real URLs (/alerts/12) so links from Slack and the browser's back button work.
import { useEffect, useState } from "react";

export type Route =
  | { name: "live" }
  | { name: "alerts" }
  | { name: "alert"; id: number }
  | { name: "review" }
  | { name: "team" }
  | { name: "tickets" }
  | { name: "ticket"; ref: string }
  | { name: "system" }
  | { name: "notfound" };

export function parse(path: string): Route {
  const parts = path.replace(/\/+$/, "").split("/").filter(Boolean);
  if (parts.length === 0) return { name: "live" };
  const [head, arg] = parts;
  if (head === "alerts" && !arg) return { name: "alerts" };
  if (head === "alerts" && /^\d+$/.test(arg)) return { name: "alert", id: Number(arg) };
  if (head === "review") return { name: "review" };
  if (head === "team") return { name: "team" };
  if (head === "tickets") return arg ? { name: "ticket", ref: decodeURIComponent(arg) } : { name: "tickets" };
  if (head === "system") return { name: "system" };
  return { name: "notfound" };
}

export function navigate(to: string, replace = false) {
  if (to === location.pathname + location.search) return;
  if (replace) history.replaceState(null, "", to);
  else history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useRoute(): [Route, URLSearchParams] {
  const [loc, setLoc] = useState(() => location.pathname + location.search);
  useEffect(() => {
    const on = () => setLoc(location.pathname + location.search);
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);
  const url = new URL(loc, location.origin);
  return [parse(url.pathname), url.searchParams];
}

/** <a> that navigates in-app on a plain click and still opens in a new tab with a modifier key. */
export function linkProps(to: string) {
  return {
    href: to,
    onClick: (e: React.MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      navigate(to);
    },
  };
}
