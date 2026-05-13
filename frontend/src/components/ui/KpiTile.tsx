interface Trend {
  delta: string;
  direction: "up" | "down" | "flat";
}

interface KpiTileProps {
  label: string;
  value: string;
  trend?: Trend;
}

export function KpiTile({ label, value, trend }: KpiTileProps) {
  return (
    <div className="p-6" style={{ padding: "20px 24px" }}>
      <div
        style={{
          textTransform: "uppercase",
          letterSpacing: "var(--ls-wide)",
          fontSize: "var(--t-micro)",
          color: "var(--ink-60)",
        }}
      >
        {label}
      </div>
      <div
        className="tabular"
        style={{
          fontFamily: "var(--font-body)",
          fontSize: "var(--t-display)",
          fontWeight: 500,
          color: "var(--amber)",
          marginTop: 8,
          lineHeight: 1,
          letterSpacing: "var(--ls-tight)",
        }}
      >
        {value}
      </div>
      {trend && (
        <div
          className="tabular"
          style={{
            marginTop: 8,
            fontSize: 11,
            color: "var(--ink-60)",
          }}
        >
          {trend.delta}
        </div>
      )}
    </div>
  );
}
