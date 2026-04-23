"use client";

import { useEffect, useState } from "react";

/**
 * Demo Operator Mode badge (design-spec §3.D, FR-D-*).
 *
 * Toggle: ``Cmd+Shift+D`` (or ``Ctrl+Shift+D`` on Windows/Linux).
 * Active only when the ``rv_demoop`` cookie is set by the BFF route
 * ``/api/demoop/enable`` (which requires ``DEMOOP_TOKEN`` to be set
 * server-side). A missing token server-side means the client JS still lets
 * the user try, but the BFF rejects and the badge stays hidden.
 */
export function DemoOperatorBadge() {
  const [enabled, setEnabled] = useState(false);
  const [scene, setScene] = useState(1);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const has = document.cookie.split("; ").some((c) => c.startsWith("rv_demoop=1"));
    setEnabled(has);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const isToggle =
        (e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "d";
      if (isToggle) {
        e.preventDefault();
        const newState = !enabled;
        fetch(newState ? "/api/demoop/enable" : "/api/demoop/disable", {
          method: "POST",
        }).then(() => setEnabled(newState));
      }
      if (enabled && e.key >= "1" && e.key <= "7" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        const scenes: Record<string, string> = {
          "1": "/",
          "2": "/",
          "3": "/hospital",
          "4": "/search",
          "5": "/orders",
          "6": "/hospital",
          "7": "/",
        };
        window.location.href = scenes[e.key] ?? "/";
      }
      if (enabled && (e.key === "." || e.key === ">") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setScene((s) => (s >= 7 ? 1 : s + 1));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);

  if (!enabled) return null;
  return (
    <div
      className="pointer-events-none fixed right-4 top-4 z-[100] flex items-center gap-2 rounded-full bg-danger px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white shadow"
      role="status"
    >
      <span className="size-1.5 animate-pulse rounded-full bg-white" />
      Demo mode · Scene {scene}/7
    </div>
  );
}
