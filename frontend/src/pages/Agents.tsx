import { useEffect, useMemo, useState } from "react";
import { api, type AgentStatus, type JournalEntry, type LeaderboardEntry } from "../api";

type PulseState = "active" | "idle" | "failed";

const STATE_PULSE: Record<string, PulseState> = {
  idle: "idle",
  observing: "active",
  suggesting: "active",
  auto_full: "active",
};

const STATE_LABEL: Record<string, string> = {
  idle: "inaktiv",
  observing: "observerar",
  suggesting: "föreslår",
  auto_full: "auto",
};

const PULSE_COLOR: Record<PulseState, string> = {
  active: "var(--forest)",
  idle: "var(--amber)",
  failed: "var(--barn)",
};

const PULSE_KEYFRAMES = `@keyframes solar-pulse {
  0% { transform: scale(0.6); opacity: 0.55; }
  100% { transform: scale(1.4); opacity: 0; }
}`;

function PulseDot({ state }: { state: PulseState }) {
  const color = PULSE_COLOR[state];
  return (
    <span
      aria-label={state}
      style={{
        position: "relative",
        display: "inline-block",
        width: 10,
        height: 10,
      }}
    >
      <span
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: color,
          opacity: state === "active" ? 1 : 0.6,
        }}
      />
      {state === "active" && (
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: -4,
            borderRadius: "50%",
            background: color,
            animation: "solar-pulse 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
          }}
        />
      )}
    </span>
  );
}

export default function Agents() {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const refresh = async () => {
    const tasks = await Promise.allSettled([
      api.agentsStatus(),
      api.leaderboard(),
      api.journalTail(15),
    ]);
    const [statusRes, leaderRes, journalRes] = tasks;
    if (statusRes.status === "fulfilled") setAgents(statusRes.value.agents);
    if (leaderRes.status === "fulfilled") setLeaderboard(leaderRes.value);
    if (journalRes.status === "fulfilled") {
      setJournal(journalRes.value.entries);
    } else {
      setJournal([]);
    }
  };

  useEffect(() => {
    void refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const agentByName = useMemo(() => {
    const m = new Map<string, AgentStatus>();
    for (const a of agents) m.set(a.name, a);
    return m;
  }, [agents]);

  const runCycle = async () => {
    if (busy) return;
    setBusy(true);
    setToast("Kör inlärningscykel…");
    try {
      await api.runLearningCycle();
      setToast("Cykel klar");
      await refresh();
    } catch (e) {
      setToast(`Fel: ${e instanceof Error ? e.message : "okänt"}`);
    } finally {
      setBusy(false);
    }
  };

  const formatTime = (iso?: string | null) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleTimeString("sv-SE", { hour12: false });
    } catch {
      return "—";
    }
  };

  return (
    <section className="p-6">
      <style>{PULSE_KEYFRAMES}</style>

      <div className="flex items-end justify-between">
        <div>
          <h2 className="display text-3xl text-(--ink)">Agenter</h2>
          <p className="caps text-(--ink-60)">Leaderboard · status · journal</p>
        </div>
        <button
          disabled={busy}
          onClick={runCycle}
          className="rounded bg-(--ink) px-4 py-2 text-sm text-(--paper) hover:bg-(--ink-60) disabled:opacity-50"
        >
          {busy ? "Kör…" : "Kör inlärningscykel"}
        </button>
      </div>

      {toast && (
        <div className="mt-3 rounded border border-(--rule) bg-(--paper-tint) px-3 py-2 text-sm text-(--ink-60)">
          {toast}
        </div>
      )}

      <div
        className="mt-6 overflow-hidden rounded border"
        style={{ borderColor: "var(--rule)", background: "var(--paper)" }}
      >
        <div
          className="border-b px-3 py-2"
          style={{ borderColor: "var(--rule)", background: "var(--paper-tint)" }}
        >
          <h3 className="caps text-(--ink-60)">Leaderboard</h3>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr
              className="text-left"
              style={{ borderBottom: "1px solid var(--rule)", background: "var(--paper-tint)" }}
            >
              <th className="caps px-3 py-2 text-(--ink-60)">#</th>
              <th className="caps px-3 py-2 text-(--ink-60)">Agent</th>
              <th className="caps px-3 py-2 text-(--ink-60)">Status</th>
              <th className="caps px-3 py-2 text-right text-(--ink-60)">Poäng</th>
              <th className="caps px-3 py-2 text-right text-(--ink-60)">Körningar 24h</th>
              <th className="caps px-3 py-2 text-right text-(--ink-60)">Senaste körning</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.map((e) => {
              const agent = agentByName.get(e.agent);
              const pulse: PulseState = agent ? (STATE_PULSE[agent.state] ?? "idle") : "idle";
              const stateLabel = agent ? (STATE_LABEL[agent.state] ?? agent.state) : "—";
              return (
                <tr
                  key={e.agent}
                  className="hover:bg-(--paper-tint)"
                  style={{ borderBottom: "1px solid var(--rule)" }}
                >
                  <td className="tabular px-3 py-2 text-(--ink-60)">{e.rank}</td>
                  <td className="px-3 py-2 text-(--ink)">{e.agent}</td>
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center gap-2">
                      <PulseDot state={pulse} />
                      <span
                        className="caps"
                        style={{ fontSize: "var(--t-micro)", color: "var(--ink-60)" }}
                      >
                        {stateLabel}
                      </span>
                    </span>
                  </td>
                  <td className="tabular px-3 py-2 text-right text-(--ink)">
                    {e.score.toFixed(2)}
                  </td>
                  <td className="tabular px-3 py-2 text-right text-(--ink-60)">
                    {agent ? agent.suggestions + agent.auto_full_actions : 0}
                  </td>
                  <td
                    className="tabular px-3 py-2 text-right text-(--ink-60)"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {formatTime(agent?.last_run)}
                  </td>
                </tr>
              );
            })}
            {leaderboard.length === 0 && (
              <tr>
                <td colSpan={6} className="caps px-3 py-4 text-center text-(--ink-60)">
                  Ingen data än
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-8">
        <h3 className="caps text-(--ink-60)">Journal (15 senaste)</h3>
        <div
          className="mt-2 overflow-auto rounded border"
          style={{
            borderColor: "var(--rule)",
            background: "var(--paper)",
            maxHeight: 384,
            fontFamily: "var(--font-mono)",
            fontSize: "var(--t-small)",
          }}
        >
          {journal.length === 0 ? (
            <div
              className="caps px-3 py-4 text-center text-(--ink-60)"
              style={{ fontFamily: "var(--font-body)" }}
            >
              Inga inlärningshändelser än — kör en cykel för att logga första
            </div>
          ) : (
            <ul className="list-none" style={{ margin: 0, padding: 0 }}>
              {journal.map((e, i) => {
                const ts = (() => {
                  try {
                    return new Date(e.ts).toLocaleTimeString("sv-SE", { hour12: false });
                  } catch {
                    return "—";
                  }
                })();
                const isPass = e.outcome === "passed";
                return (
                  <li
                    key={`${e.ts}-${i}`}
                    className="grid items-start"
                    style={{
                      gridTemplateColumns: "88px 140px 1fr auto",
                      gap: 12,
                      padding: "6px 12px",
                      borderBottom: i === journal.length - 1 ? "none" : "1px solid var(--rule)",
                    }}
                  >
                    <span className="tabular" style={{ color: "var(--ink-60)" }}>
                      {ts}
                    </span>
                    <span style={{ color: "var(--ink)" }}>{e.phase}</span>
                    <span style={{ color: "var(--ink-80)" }}>{e.lesson}</span>
                    <span
                      className="caps"
                      style={{
                        fontSize: 10,
                        padding: "1px 6px",
                        borderRadius: "var(--r-1)",
                        background: isPass
                          ? "color-mix(in srgb, var(--forest) 18%, transparent)"
                          : "color-mix(in srgb, var(--barn) 18%, transparent)",
                        color: isPass ? "var(--forest)" : "var(--barn)",
                        fontFamily: "var(--font-body)",
                      }}
                    >
                      {e.outcome}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <div className="mt-8">
        <h3 className="caps text-(--ink-60)">Live status</h3>
        <ul
          className="mt-2 divide-y rounded border"
          style={{ borderColor: "var(--rule)", background: "var(--paper-tint)" }}
        >
          {agents.length === 0 && (
            <li className="caps px-3 py-4 text-center text-(--ink-60)">väntar på backend…</li>
          )}
          {agents.map((a) => {
            const pulse: PulseState = STATE_PULSE[a.state] ?? "idle";
            return (
              <li key={a.name} className="flex items-center gap-3 px-3 py-2 text-sm">
                <PulseDot state={pulse} />
                <span className="font-medium text-(--ink)">{a.name}</span>
                <span className="caps text-(--ink-60)">{STATE_LABEL[a.state] ?? a.state}</span>
                <span className="caps tabular ml-auto text-(--ink-60)">
                  {a.suggestions} förslag · {a.auto_full_actions} auto
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
