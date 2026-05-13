import { useEffect } from "react";
import { api } from "../api";

const HOTKEY_TO_STATUS: Record<string, string> = {
  "1": "new",
  "2": "interested",
  "3": "callback",
  "4": "rejected",
};

export function useProspectHotkeys(selectedId: number | null, onChange: () => void): void {
  useEffect(() => {
    async function onKey(e: KeyboardEvent) {
      if (e.defaultPrevented) return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const status = HOTKEY_TO_STATUS[e.key];
      if (!status || selectedId == null) return;
      e.preventDefault();
      await api.bulkStatus([selectedId], status);
      onChange();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [selectedId, onChange]);
}
