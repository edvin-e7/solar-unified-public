import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { AppNav } from "./components/AppNav";
import { api } from "./api";

export default function AppShell() {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        await api.agentsStatus();
        if (mounted) setOnline(true);
      } catch {
        if (mounted) setOnline(false);
      }
    };
    void check();
    const id = setInterval(check, 5000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-(--paper) text-(--ink)">
      <AppNav />
      <main className="flex-1 overflow-auto">
        <div
          className="flex items-center justify-end border-b border-(--rule) bg-(--paper) px-4"
          style={{ height: 48 }}
        >
          <span
            className={`rounded-full px-2 py-0.5 text-xs ${
              online ? "bg-(--forest)/20 text-(--forest)" : "bg-(--barn)/20 text-(--barn)"
            }`}
          >
            {online ? "Server ansluten" : "Frånkopplad"}
          </span>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
