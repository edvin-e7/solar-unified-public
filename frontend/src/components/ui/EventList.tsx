interface EventItem {
  id: string;
  label: string;
  time: string;
  live?: boolean;
}

interface EventListProps {
  events: EventItem[];
  title: string;
}

export function EventList({ events, title }: EventListProps) {
  const isLive = events.some((e) => e.live);

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
        {isLive && (
          <span
            className="inline-flex items-center"
            style={{
              fontFamily: "var(--font-body)",
              fontSize: 9,
              letterSpacing: "var(--ls-wide)",
              textTransform: "uppercase",
              color: "var(--forest)",
              gap: 6,
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 6,
                height: 6,
                background: "var(--forest)",
                borderRadius: "50%",
                display: "inline-block",
              }}
            />
            live
          </span>
        )}
      </div>
      <ul className="list-none" style={{ margin: 0, padding: 0 }}>
        {events.map((event, i) => (
          <li
            key={event.id}
            className="grid items-center transition-colors"
            style={{
              padding: "10px 0",
              borderBottom: i === events.length - 1 ? "none" : "1px solid var(--rule)",
              fontSize: 13,
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
            <span style={{ color: "var(--ink)", letterSpacing: "-0.005em" }}>{event.label}</span>
            <span
              className="tabular text-right"
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "var(--t-small)",
                color: "var(--ink-60)",
              }}
            >
              {event.time}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
