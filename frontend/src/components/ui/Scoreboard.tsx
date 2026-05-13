interface ScoreRow {
  rank: number;
  label: string;
  score: string;
}

interface ScoreboardProps {
  title: string;
  scoreLabel: string;
  rows: ScoreRow[];
}

export function Scoreboard({ title, scoreLabel, rows }: ScoreboardProps) {
  return (
    <div
      style={{
        border: "1px solid var(--rule)",
        background: "var(--paper)",
        borderRadius: "var(--r-4)",
        padding: 20,
      }}
    >
      <div
        className="flex items-center justify-between"
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "var(--t-h3)",
          fontWeight: 500,
          letterSpacing: "-0.005em",
          marginBottom: 12,
          paddingBottom: 12,
          borderBottom: "1px solid var(--rule)",
        }}
      >
        <h4 style={{ font: "inherit" }}>{title}</h4>
        <span
          style={{
            fontFamily: "var(--font-body)",
            fontSize: 9,
            letterSpacing: "var(--ls-wide)",
            textTransform: "uppercase",
            color: "var(--ink-60)",
          }}
        >
          {scoreLabel}
        </span>
      </div>
      <ul className="list-none" style={{ margin: 0, padding: 0 }}>
        {rows.map((row, i) => (
          <li
            key={`${row.rank}-${row.label}`}
            className="grid items-center transition-colors"
            style={{
              padding: "10px 0",
              borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--rule)",
              gridTemplateColumns: "1fr auto",
              gap: 12,
              transitionDuration: "120ms",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--paper-tint)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            <span className="flex items-baseline" style={{ gap: 10, minWidth: 0 }}>
              <span
                className="tabular"
                style={{
                  fontSize: 11,
                  color: "var(--ink-60)",
                  width: 16,
                  flex: "0 0 16px",
                }}
              >
                {row.rank}
              </span>
              <span
                style={{
                  fontSize: "var(--t-body)",
                  color: "var(--ink)",
                  letterSpacing: "-0.005em",
                }}
              >
                {row.label}
              </span>
            </span>
            <span
              className="tabular text-right"
              style={{
                fontSize: "var(--t-body)",
                color: "var(--ink)",
                fontWeight: 500,
              }}
            >
              {row.score}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
