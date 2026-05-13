import { useEffect, useState } from "react";
import ThemeToggle from "../components/ThemeToggle";
import ExportButton from "../components/ExportButton";
import BulkInput from "../components/BulkInput";

interface BackendFlags {
  allow_external_llm: boolean;
  allow_google_solar_api: boolean;
}

interface FlagRow {
  name: string;
  description: string;
  scope: string;
  state: "on" | "off" | "unknown";
  live: boolean;
}

const STATIC_FLAGS: Array<Omit<FlagRow, "state" | "live">> = [
  {
    name: "ALLOW_METRIA",
    description: "Metria takdata (kommersiell)",
    scope: "backend",
  },
  {
    name: "ALLOW_MRKOLL",
    description: "Mrkoll personuppslag (Electron)",
    scope: "renderer",
  },
  {
    name: "PIIFILTER_STRICT",
    description: "Strikt PII-filter innan loggning",
    scope: "backend",
  },
  {
    name: "COVE_THRESHOLD",
    description: "Chain-of-Verification minsta säkerhet",
    scope: "backend",
  },
  {
    name: "AUTONOMOUS_CYCLE",
    description: "Daglig självförbättringscykel",
    scope: "backend",
  },
  {
    name: "PITCH_USE_PRO",
    description: "Gemini 2.5 Pro för pitchgenerering",
    scope: "backend",
  },
  {
    name: "EXPERIMENTAL_MAP_TILES",
    description: "Experimentella kart-tiles",
    scope: "frontend",
  },
];

const HOTKEYS: Array<{ chord: string[]; desc: string; group: string }> = [
  { chord: ["Ctrl", "V"], desc: "Öppna Prospekt-vyn", group: "Navigation" },
  { chord: ["G", "P"], desc: "Gå till Prospekt", group: "Navigation" },
  { chord: ["G", "K"], desc: "Gå till Karta", group: "Navigation" },
  { chord: ["G", "D"], desc: "Gå till Dashboard", group: "Navigation" },
  { chord: ["G", "H"], desc: "Gå till Historik", group: "Navigation" },
  { chord: ["⌘", "K"], desc: "Kommandopalett", group: "Åtgärder" },
  { chord: ["/"], desc: "Fokusera sökfält", group: "Åtgärder" },
  { chord: ["B"], desc: "Växla sidopanel", group: "Åtgärder" },
  { chord: ["⌘", "⌫"], desc: "Radera markerade", group: "Åtgärder" },
  { chord: ["J"], desc: "Nästa prospekt", group: "Listor" },
  { chord: ["K"], desc: "Föregående prospekt", group: "Listor" },
  { chord: ["S"], desc: "Växla status", group: "Listor" },
];

interface ApiKeyRow {
  name: string;
  service: string;
  masked: string;
  status: "configured" | "missing";
}

const API_KEYS: ApiKeyRow[] = [
  {
    name: "GOOGLE_MAPS_API_KEY",
    service: "Google Maps Platform",
    masked: "AIza••••••••••••••••••••••••••••••••",
    status: "configured",
  },
  {
    name: "GEMINI_API_KEY",
    service: "Gemini · AI Studio",
    masked: "AIza••••••••••••••••••••••••••••••••",
    status: "configured",
  },
  {
    name: "GOOGLE_SOLAR_API_KEY",
    service: "Google Solar API",
    masked: "—",
    status: "missing",
  },
];

export default function Settings() {
  const [flags, setFlags] = useState<BackendFlags | null>(null);
  const [flagsError, setFlagsError] = useState(false);
  const [revealKey, setRevealKey] = useState<string | null>(null);
  const [copyToast, setCopyToast] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const base = import.meta.env.VITE_API_URL ?? "";
        const res = await fetch(`${base}/api/settings/flags`);
        if (!res.ok) throw new Error("bad status");
        const data = (await res.json()) as BackendFlags;
        if (!cancelled) {
          setFlags(data);
          setFlagsError(false);
        }
      } catch {
        if (!cancelled) setFlagsError(true);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const flagRows: FlagRow[] = [
    {
      name: "ALLOW_EXTERNAL_LLM",
      description: "Gemini · AI Studio (gratis)",
      scope: "backend",
      state: flags ? (flags.allow_external_llm ? "on" : "off") : "unknown",
      live: true,
    },
    {
      name: "ALLOW_GOOGLE_SOLAR_API",
      description: "Google Solar (kostar — default OFF)",
      scope: "backend",
      state: flags ? (flags.allow_google_solar_api ? "on" : "off") : "unknown",
      live: true,
    },
    ...STATIC_FLAGS.map((f) => ({ ...f, state: "unknown" as const, live: false })),
  ];

  const handleCopy = async (text: string, name: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyToast(`Kopierad: ${name}`);
      setTimeout(() => setCopyToast(null), 1800);
    } catch {
      setCopyToast("Kopiering misslyckades");
      setTimeout(() => setCopyToast(null), 1800);
    }
  };

  return (
    <section className="p-6">
      <h2 className="display text-3xl text-(--ink)">Inställningar</h2>

      {copyToast && (
        <div className="mt-3 rounded border border-(--rule) bg-(--paper-tint) px-3 py-2 text-sm text-(--ink-60)">
          {copyToast}
        </div>
      )}

      <section className="mt-8">
        <h3 className="caps text-(--ink-60)">Tema</h3>
        <div className="mt-2 flex items-center gap-3">
          <ThemeToggle />
          <span className="caps text-(--ink-60)" style={{ fontSize: "var(--t-micro)" }}>
            Klicka för att växla Papper / Kväll / System
          </span>
        </div>
      </section>

      <section className="mt-8">
        <h3 className="caps text-(--ink-60)">API-nycklar</h3>
        <div
          className="mt-2 overflow-hidden rounded border"
          style={{ borderColor: "var(--rule)", background: "var(--paper)" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr
                className="text-left"
                style={{
                  borderBottom: "1px solid var(--rule)",
                  background: "var(--paper-tint)",
                }}
              >
                <th className="caps px-3 py-2 text-(--ink-60)">Tjänst</th>
                <th className="caps px-3 py-2 text-(--ink-60)">Nyckel</th>
                <th className="caps px-3 py-2 text-(--ink-60)">Status</th>
                <th className="caps px-3 py-2 text-right text-(--ink-60)">Åtgärd</th>
              </tr>
            </thead>
            <tbody>
              {API_KEYS.map((k) => {
                const revealed = revealKey === k.name;
                return (
                  <tr key={k.name} style={{ borderBottom: "1px solid var(--rule)" }}>
                    <td className="px-3 py-2 text-(--ink)">
                      <div>{k.service}</div>
                      <div
                        className="tabular"
                        style={{ fontSize: "var(--t-micro)", color: "var(--ink-60)" }}
                      >
                        {k.name}
                      </div>
                    </td>
                    <td
                      className="tabular px-3 py-2 text-(--ink)"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {k.status === "missing" ? "—" : revealed ? "(dold — serverside)" : k.masked}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className="caps"
                        style={{
                          fontSize: 10,
                          padding: "1px 6px",
                          borderRadius: "var(--r-1)",
                          background:
                            k.status === "configured"
                              ? "color-mix(in srgb, var(--forest) 18%, transparent)"
                              : "color-mix(in srgb, var(--stone) 24%, transparent)",
                          color: k.status === "configured" ? "var(--forest)" : "var(--ink-60)",
                        }}
                      >
                        {k.status === "configured" ? "konfigurerad" : "saknas"}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="inline-flex gap-2">
                        <button
                          disabled={k.status !== "configured"}
                          onClick={() => setRevealKey(revealed ? null : k.name)}
                          className="caps rounded border border-(--rule) bg-(--paper) px-2 py-0.5 text-(--ink-60) hover:text-(--ink) disabled:opacity-40"
                          style={{ fontSize: "var(--t-micro)" }}
                        >
                          {revealed ? "dölj" : "visa"}
                        </button>
                        <button
                          disabled={k.status !== "configured"}
                          onClick={() => handleCopy(k.masked, k.name)}
                          className="caps rounded border border-(--rule) bg-(--paper) px-2 py-0.5 text-(--ink-60) hover:text-(--ink) disabled:opacity-40"
                          style={{ fontSize: "var(--t-micro)" }}
                          aria-label={`Kopiera ${k.name}`}
                        >
                          kopiera
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div
            className="caps px-3 py-2"
            style={{
              borderTop: "1px solid var(--rule)",
              background: "var(--paper-tint)",
              fontSize: "var(--t-micro)",
              color: "var(--ink-60)",
            }}
          >
            Nycklar lagras endast server-side · visa-knappen läser ej klartext
          </div>
        </div>
      </section>

      <section className="mt-8">
        <h3 className="caps text-(--ink-60)">Kortkommandon</h3>
        <div className="mt-2 grid gap-4 md:grid-cols-2">
          {["Navigation", "Åtgärder", "Listor"].map((group) => {
            const rows = HOTKEYS.filter((h) => h.group === group);
            if (rows.length === 0) return null;
            return (
              <div
                key={group}
                className="rounded border"
                style={{ borderColor: "var(--rule)", background: "var(--paper)" }}
              >
                <div
                  className="caps px-3 py-2"
                  style={{
                    borderBottom: "1px solid var(--rule)",
                    background: "var(--paper-tint)",
                    color: "var(--ink-60)",
                    fontSize: "var(--t-micro)",
                  }}
                >
                  {group}
                </div>
                <table className="w-full text-sm">
                  <tbody>
                    {rows.map((h) => (
                      <tr key={h.desc} style={{ borderBottom: "1px solid var(--rule)" }}>
                        <td className="px-3 py-2">
                          <span className="inline-flex items-center gap-1">
                            {h.chord.map((k, i) => (
                              <span key={i} className="inline-flex items-center gap-1">
                                {i > 0 && (
                                  <span
                                    style={{
                                      color: "var(--ink-60)",
                                      fontSize: "var(--t-micro)",
                                    }}
                                  >
                                    +
                                  </span>
                                )}
                                <kbd
                                  className="tabular"
                                  style={{
                                    fontFamily: "var(--font-mono)",
                                    fontSize: "var(--t-micro)",
                                    padding: "2px 6px",
                                    border: "1px solid var(--rule)",
                                    borderRadius: "var(--r-1)",
                                    background: "var(--paper-tint)",
                                    color: "var(--ink)",
                                    boxShadow: "0 1px 0 var(--rule)",
                                  }}
                                >
                                  {k}
                                </kbd>
                              </span>
                            ))}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-(--ink-60)">{h.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      </section>

      <section className="mt-8">
        <h3 className="caps text-(--ink-60)">Funktionsflaggor</h3>
        <div
          className="mt-2 overflow-hidden rounded border"
          style={{ borderColor: "var(--rule)", background: "var(--paper)" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr
                className="text-left"
                style={{
                  borderBottom: "1px solid var(--rule)",
                  background: "var(--paper-tint)",
                }}
              >
                <th className="caps px-3 py-2 text-(--ink-60)">Flagga</th>
                <th className="caps px-3 py-2 text-(--ink-60)">Beskrivning</th>
                <th className="caps px-3 py-2 text-(--ink-60)">Omfattning</th>
                <th className="caps px-3 py-2 text-right text-(--ink-60)">Tillstånd</th>
              </tr>
            </thead>
            <tbody>
              {flagRows.map((f) => {
                const dim = !f.live;
                return (
                  <tr
                    key={f.name}
                    style={{
                      borderBottom: "1px solid var(--rule)",
                      opacity: dim ? 0.55 : 1,
                    }}
                  >
                    <td
                      className="px-3 py-2 text-(--ink)"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {f.name}
                    </td>
                    <td className="px-3 py-2 text-(--ink-60)">{f.description}</td>
                    <td
                      className="caps px-3 py-2 text-(--ink-60)"
                      style={{ fontSize: "var(--t-micro)" }}
                    >
                      {f.scope}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {f.state === "on" && (
                        <span
                          className="caps"
                          style={{
                            fontSize: 10,
                            padding: "1px 6px",
                            borderRadius: "var(--r-1)",
                            background: "color-mix(in srgb, var(--forest) 18%, transparent)",
                            color: "var(--forest)",
                          }}
                        >
                          på
                        </span>
                      )}
                      {f.state === "off" && (
                        <span
                          className="caps"
                          style={{
                            fontSize: 10,
                            padding: "1px 6px",
                            borderRadius: "var(--r-1)",
                            background: "var(--paper-tint)",
                            color: "var(--ink-60)",
                            border: "1px solid var(--rule)",
                          }}
                        >
                          av
                        </span>
                      )}
                      {f.state === "unknown" && (
                        <span
                          className="caps tabular"
                          style={{
                            fontSize: 10,
                            color: "var(--ink-60)",
                            fontStyle: "italic",
                          }}
                        >
                          ej tillgängligt ännu
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {flagsError && (
            <div
              className="caps px-3 py-2"
              style={{
                borderTop: "1px solid var(--rule)",
                background: "var(--paper-tint)",
                fontSize: "var(--t-micro)",
                color: "var(--barn)",
              }}
            >
              Kunde ej läsa /api/settings/flags — visar senast kända värden
            </div>
          )}
        </div>
      </section>

      <section className="mt-8">
        <h3 className="caps text-(--ink-60)">Import / Export</h3>
        <div className="mt-2 flex gap-2">
          <BulkInput onAdded={() => {}} />
          <ExportButton />
        </div>
      </section>

      <section className="mt-8">
        <h3 className="caps text-(--ink-60)">Om</h3>
        <p className="mt-1 text-sm text-(--ink-60)">
          Solar Unified v0.1.0 · build {import.meta.env.DEV ? "dev" : "prod"}
        </p>
      </section>
    </section>
  );
}
