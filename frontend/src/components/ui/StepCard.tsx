import { Fragment } from "react";

interface StepCardProps {
  step: number;
  eyebrow: string;
  title: string;
  body: string;
  kbdHint?: string[];
  onCta: () => void;
  ctaLabel: string;
  tone?: "amber" | "forest" | "leaf";
}

const TONE_COLOR: Record<NonNullable<StepCardProps["tone"]>, string> = {
  amber: "var(--amber)",
  forest: "var(--forest)",
  leaf: "var(--leaf)",
};

export function StepCard({
  step,
  eyebrow,
  title,
  body,
  kbdHint,
  onCta,
  ctaLabel,
  tone = "amber",
}: StepCardProps) {
  const accent = TONE_COLOR[tone];
  const stepLabel = step.toString().padStart(2, "0");

  return (
    <button
      type="button"
      onClick={onCta}
      aria-label={ctaLabel}
      className="group grid w-full cursor-pointer items-center gap-6 text-left transition-colors"
      style={{
        background: "var(--paper)",
        border: "1px solid var(--rule)",
        borderLeft: `3px solid ${accent}`,
        borderRadius: "var(--r-2)",
        padding: "28px 32px",
        gridTemplateColumns: "1fr auto",
        transitionDuration: "var(--dur-snap)",
        transitionTimingFunction: "var(--ease-paper)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--paper-tint)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "var(--paper)";
      }}
    >
      <div>
        <div
          style={{
            textTransform: "uppercase",
            letterSpacing: "var(--ls-wider)",
            fontSize: "var(--t-micro)",
            color: accent,
            marginBottom: 8,
          }}
        >
          {stepLabel} · {eyebrow}
        </div>
        <h3
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "var(--t-h2)",
            fontWeight: 400,
            letterSpacing: "var(--ls-tight)",
            marginBottom: 8,
            lineHeight: 1.2,
          }}
        >
          {title}
        </h3>
        <p
          style={{
            color: "var(--ink-80)",
            fontSize: "var(--t-body)",
            lineHeight: 1.55,
            maxWidth: "60ch",
          }}
        >
          {body}
        </p>
        {kbdHint && kbdHint.length > 0 && (
          <div
            className="flex flex-wrap items-center"
            style={{
              marginTop: 12,
              fontSize: 11,
              color: "var(--ink-60)",
              gap: 4,
            }}
          >
            {kbdHint.map((chip, i) => {
              const isKey = /^[A-Za-z0-9+_-]+$/.test(chip) && chip.length <= 24;
              return (
                <Fragment key={`${chip}-${i}`}>
                  {isKey ? (
                    <kbd
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        padding: "2px 6px",
                        border: "1px solid var(--rule)",
                        background: "var(--paper-tint)",
                        borderRadius: "var(--r-2)",
                        color: "var(--ink)",
                        lineHeight: 1.2,
                      }}
                    >
                      {chip}
                    </kbd>
                  ) : (
                    <span>{chip}</span>
                  )}
                </Fragment>
              );
            })}
          </div>
        )}
      </div>
      <div
        aria-hidden="true"
        className="flex items-center justify-center"
        style={{ width: 32, height: 32, color: accent }}
      >
        <svg
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="transition-transform group-hover:translate-x-1"
          style={{
            transitionDuration: "var(--dur-snap)",
            transitionTimingFunction: "var(--ease-paper)",
          }}
        >
          <path d="M5 12h14" />
          <path d="M13 5l7 7-7 7" />
        </svg>
      </div>
    </button>
  );
}
