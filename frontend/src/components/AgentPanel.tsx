import type { AgentStatus } from "../api";

interface Props {
  agents: AgentStatus[];
}

const STATE_COLORS: Record<string, string> = {
  idle: "bg-(--stone)",
  observing: "bg-(--azure)",
  suggesting: "bg-(--amber)",
  auto_full: "bg-(--forest)",
};

export default function AgentPanel({ agents }: Props) {
  return (
    <div className="flex items-center gap-4 px-6 py-2 text-xs text-(--ink-60)">
      <span className="text-(--ink-60)">Agenter:</span>
      {agents.length === 0 && <span className="italic">väntar på backend…</span>}
      {agents.map((a) => (
        <div key={a.name} className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${STATE_COLORS[a.state] ?? "bg-(--stone)"}`} />
          <span>{a.name}</span>
          {a.suggestions > 0 && (
            <span className="rounded bg-(--amber)/20 px-1.5 text-[10px] text-(--amber)">
              {a.suggestions}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
