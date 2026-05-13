import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Prospect, type Stats, type AgentStatus } from "../api";
import { AgentThoughtStream } from "../components/AgentThoughtStream";
import { KpiTile } from "../components/ui/KpiTile";
import { StepCard } from "../components/ui/StepCard";
import { EventList } from "../components/ui/EventList";
import { Scoreboard } from "../components/ui/Scoreboard";

const GREETING_HOURS: Array<[number, string]> = [
  [5, "God morgon"],
  [11, "God förmiddag"],
  [13, "God eftermiddag"],
  [18, "God kväll"],
];

function greeting(now: Date): string {
  const h = now.getHours();
  let label = "God natt";
  for (const [from, text] of GREETING_HOURS) {
    if (h >= from) label = text;
  }
  return label;
}

function formatNumber(n: number): string {
  return n.toLocaleString("sv-SE");
}

function formatDateSv(d: Date): string {
  return d
    .toLocaleDateString("sv-SE", { weekday: "short", day: "2-digit", month: "short" })
    .toUpperCase()
    .replace(".", "");
}

function relativeTime(iso: string | null | undefined, now: Date): string {
  if (!iso) return "aldrig";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;
  const diff = Math.max(0, now.getTime() - then.getTime());
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "nyss";
  if (mins < 60) return `${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} h`;
  return then.toLocaleDateString("sv-SE", { day: "2-digit", month: "short" });
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [now] = useState(() => new Date());

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [s, a, p] = await Promise.all([api.stats(), api.agentsStatus(), api.listProspects()]);
        if (!mounted) return;
        setStats(s);
        setAgents(a.agents);
        setProspects(p);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "okänt fel");
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const todayIso = now.toISOString().slice(0, 10);
  const newToday = stats?.daily.find((d) => d.day === todayIso)?.n ?? 0;
  const queueCount = stats
    ? stats.total - Math.round((stats.enrichment_rate / 100) * stats.total)
    : 0;
  const enriched = stats ? Math.round((stats.enrichment_rate / 100) * stats.total) : 0;

  const events = agents.slice(0, 6).map((a) => ({
    id: a.name,
    label: a.name,
    time: relativeTime(a.last_run ?? null, now),
    live: a.state !== "idle",
  }));

  const topRows = [...prospects]
    .filter((p) => p.score != null)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 5)
    .map((p, i) => ({
      rank: i + 1,
      label: p.address,
      score: (p.score ?? 0).toFixed(1),
    }));

  return (
    <section style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      <header style={{ marginBottom: 32 }}>
        <h1
          className="display"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "var(--t-display-lg)",
            color: "var(--ink)",
            margin: 0,
            lineHeight: 1.1,
          }}
        >
          {greeting(now)}, <em style={{ color: "var(--amber)", fontStyle: "italic" }}>Edvin</em>
        </h1>
        <div
          className="caps tabular"
          style={{
            marginTop: 8,
            fontSize: "var(--t-micro)",
            letterSpacing: "var(--ls-wider)",
            color: "var(--ink-60)",
          }}
        >
          {formatDateSv(now)} ·{" "}
          {now.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" })} · Falun
        </div>
        <p
          style={{
            maxWidth: "64ch",
            marginTop: 16,
            fontSize: "var(--t-body)",
            color: "var(--ink-80)",
            lineHeight: 1.55,
          }}
        >
          Tre agenter arbetar i bakgrunden. Börja med en sak — klistra in adresser, kör detektion
          eller följ upp toppprospekt.
        </p>
      </header>

      {error && (
        <div
          style={{
            marginBottom: 24,
            padding: 12,
            border: "1px solid var(--barn)",
            background: "var(--paper)",
            borderRadius: "var(--r-2)",
            color: "var(--barn)",
            fontSize: "var(--t-small)",
          }}
        >
          Kunde inte ladda data: {error}
        </div>
      )}

      <section
        aria-label="Dagens nyckeltal"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          border: "1px solid var(--rule)",
          background: "var(--paper)",
          borderRadius: "var(--r-4)",
          marginBottom: 32,
        }}
      >
        <div style={{ borderRight: "1px solid var(--rule)" }}>
          <KpiTile label="Nya idag" value={`+${formatNumber(newToday)}`} />
        </div>
        <div style={{ borderRight: "1px solid var(--rule)" }}>
          <KpiTile
            label="Berikade"
            value={formatNumber(enriched)}
            trend={{ delta: `${stats?.enrichment_rate ?? 0}% total`, direction: "flat" }}
          />
        </div>
        <div style={{ borderRight: "1px solid var(--rule)" }}>
          <KpiTile
            label="Konvertering"
            value={`${stats?.conversion_rate ?? 0}%`}
            trend={{ delta: `snitt ${stats?.avg_score.toFixed(1) ?? "0.0"}`, direction: "flat" }}
          />
        </div>
        <div>
          <KpiTile label="Kö" value={formatNumber(queueCount)} />
        </div>
      </section>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) 360px",
          gap: 32,
          alignItems: "start",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <section
            style={{
              padding: "24px 32px",
              background: "var(--paper)",
              border: "1px solid var(--rule)",
              borderRadius: "var(--r-4)",
              marginBottom: 8,
            }}
          >
            <h3 className="caps mb-6 text-[10px] text-(--ink-60)">Affärstratt // Konvertering</h3>
            <div className="flex flex-col gap-1">
              {[
                {
                  label: "Nya prospekt",
                  value: stats?.total ?? 0,
                  color: "var(--stone)",
                  width: "100%",
                },
                { label: "Berikade", value: enriched, color: "var(--azure)", width: "85%" },
                {
                  label: "Intresserade",
                  value: prospects.filter((p) => p.status === "interested").length,
                  color: "var(--forest)",
                  width: "60%",
                },
                {
                  label: "Bokade möten",
                  value: prospects.filter((p) => p.status === "callback").length,
                  color: "var(--amber)",
                  width: "35%",
                },
              ].map((row, i) => (
                <div key={i} className="group flex items-center gap-4 py-2">
                  <div className="w-32 text-xs text-(--ink-60)">{row.label}</div>
                  <div className="relative h-8 flex-1 bg-(--paper-tint) rounded-sm overflow-hidden">
                    <div
                      className="absolute inset-y-0 left-0 transition-all duration-1000 ease-out"
                      style={{
                        width: row.width,
                        background: row.color,
                        opacity: 0.15,
                      }}
                    />
                    <div
                      className="absolute inset-y-0 left-0 border-l-2 transition-all duration-1000 ease-out"
                      style={{
                        width: row.width,
                        background: `linear-gradient(to right, ${row.color}33, transparent)`,
                        borderColor: row.color,
                      }}
                    />
                    <div className="absolute inset-y-0 left-4 flex items-center text-xs font-medium text-(--ink)">
                      {formatNumber(row.value)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <StepCard
            step={1}
            eyebrow="Vanligaste start"
            title="Klistra in adresser"
            body="Lägg till nya prospekt från CSV eller radbrytning. Berikning startar automatiskt."
            kbdHint={["G", "då", "P"]}
            ctaLabel="Gå till prospekt"
            onCta={() => navigate("/prospekt")}
            tone="amber"
          />
          <StepCard
            step={2}
            eyebrow="Bearbeta kön"
            title="Kör paneldetektion"
            body="Identifiera tak MED solpaneler i den nuvarande kön. Målgrupp: befintliga panelägare. Kör i bakgrunden."
            kbdHint={["G", "då", "D"]}
            ctaLabel="Öppna detektion"
            onCta={() => navigate("/detektion")}
            tone="forest"
          />
          <StepCard
            step={3}
            eyebrow="Följ upp"
            title="Visa toppprospekt"
            body="Granska de högst rankade leads och starta samtal eller anteckna nästa steg."
            kbdHint={["G", "då", "K"]}
            ctaLabel="Öppna karta"
            onCta={() => navigate("/karta")}
            tone="leaf"
          />
        </div>

        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <AgentThoughtStream />
          <EventList
            title="Senaste händelser"
            events={
              events.length > 0
                ? events
                : [{ id: "empty", label: "Inga händelser ännu", time: "—" }]
            }
          />
          <Scoreboard
            title="Dagens topp"
            scoreLabel="score"
            rows={
              topRows.length > 0
                ? topRows
                : [{ rank: 1, label: "Inga poängsatta prospekt", score: "—" }]
            }
          />
        </aside>
      </div>
    </section>
  );
}
