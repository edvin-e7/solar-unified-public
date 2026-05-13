import { useRef, type KeyboardEvent, type ReactElement } from "react";

export type SidebarIcon =
  | "layout-dashboard"
  | "users"
  | "search"
  | "scan-eye"
  | "sun"
  | "map"
  | "bot"
  | "sparkles"
  | "settings";

export interface NavItem {
  id: string;
  label: string;
  icon: SidebarIcon;
}

interface SidebarUser {
  name: string;
  email: string;
  initials: string;
}

interface SidebarProps {
  items: NavItem[];
  activeId: string;
  onSelect: (id: string) => void;
  user: SidebarUser;
  brand?: string;
  tagline?: string;
  version?: string;
}

const ICON_PATHS: Record<SidebarIcon, ReactElement> = {
  "layout-dashboard": (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </>
  ),
  users: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </>
  ),
  "scan-eye": (
    <>
      <path d="M3 7V5a2 2 0 0 1 2-2h2" />
      <path d="M17 3h2a2 2 0 0 1 2 2v2" />
      <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
      <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
      <circle cx="12" cy="12" r="1.5" />
      <path d="M18 12a6 6 0 0 1-12 0 6 6 0 0 1 12 0z" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="M4.93 4.93l1.41 1.41" />
      <path d="M17.66 17.66l1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="M4.93 19.07l1.41-1.41" />
      <path d="M17.66 6.34l1.41-1.41" />
    </>
  ),
  map: (
    <>
      <path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3V6z" />
      <path d="M9 3v15" />
      <path d="M15 6v15" />
    </>
  ),
  bot: (
    <>
      <path d="M12 2v4" />
      <rect x="4" y="6" width="16" height="12" rx="2" />
      <path d="M2 14h2" />
      <path d="M20 14h2" />
      <circle cx="9" cy="12" r="1" />
      <circle cx="15" cy="12" r="1" />
      <path d="M9 16h6" />
    </>
  ),
  sparkles: (
    <>
      <path d="M12 3l1.9 4.9L19 10l-5.1 2.1L12 17l-1.9-4.9L5 10l5.1-2.1L12 3z" />
      <path d="M19 17l.9 2.1L22 20l-2.1.9L19 23l-.9-2.1L16 20l2.1-.9L19 17z" />
      <path d="M5 3l.6 1.4L7 5l-1.4.6L5 7l-.6-1.4L3 5l1.4-.6L5 3z" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </>
  ),
};

function NavIcon({ name }: { name: SidebarIcon }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flex: "0 0 16px" }}
    >
      {ICON_PATHS[name]}
    </svg>
  );
}

export function Sidebar({
  items,
  activeId,
  onSelect,
  user,
  brand = "Edvin Solar",
  tagline = "Prospekteringssystem",
  version = "v0.1.0",
}: SidebarProps) {
  const refs = useRef<Array<HTMLAnchorElement | null>>([]);

  function handleKey(e: KeyboardEvent<HTMLAnchorElement>, index: number) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = (index + 1) % items.length;
      refs.current[next]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const prev = (index - 1 + items.length) % items.length;
      refs.current[prev]?.focus();
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(items[index].id);
    }
  }

  return (
    <aside
      aria-label="Primär navigation"
      className="sticky top-0 flex h-screen flex-col"
      style={{
        width: 248,
        background: "var(--warm-dark)",
        color: "var(--ondark-72)",
        borderRight: "1px solid var(--ondark-rule)",
      }}
    >
      <div className="px-4 pt-5 pb-4" style={{ borderBottom: "1px solid var(--ondark-rule)" }}>
        <div className="flex items-center gap-2.5">
          <svg viewBox="0 0 20 20" aria-hidden="true" width="20" height="20">
            <circle cx="10" cy="7" r="2.6" fill="var(--amber)" />
            <path d="M1.5 15.5 L10 8.5 L18.5 15.5 Z" fill="var(--amber)" opacity="0.9" />
            <path d="M4 15.5 L10 10.5 L16 15.5 Z" fill="var(--warm-dark)" />
          </svg>
          <span
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 16,
              fontWeight: 500,
              letterSpacing: "var(--ls-tight)",
              color: "var(--ondark-strong)",
            }}
          >
            {brand}
          </span>
        </div>
        <div
          className="mt-2"
          style={{
            fontSize: "var(--t-micro)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--ondark-40)",
          }}
        >
          {tagline}
        </div>
      </div>

      <div
        className="px-4 pt-3 pb-1.5"
        style={{
          fontSize: "var(--t-micro)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--ondark-40)",
        }}
      >
        Arbetsyta
      </div>

      <ul role="list" className="m-0 flex-1 list-none overflow-y-auto px-2">
        {items.map((item, i) => {
          const isActive = item.id === activeId;
          return (
            <li key={item.id}>
              <a
                ref={(el) => {
                  refs.current[i] = el;
                }}
                href={`#${item.id}`}
                aria-current={isActive ? "page" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  onSelect(item.id);
                }}
                onKeyDown={(e) => handleKey(e, i)}
                className="flex items-center gap-2.5 rounded-[2px] px-3 transition-colors"
                style={{
                  height: 36,
                  fontSize: "var(--t-body)",
                  fontWeight: 450,
                  borderLeft: `2px solid ${isActive ? "var(--amber)" : "transparent"}`,
                  background: isActive ? "var(--ondark-active-bg)" : "transparent",
                  color: isActive ? "var(--ondark-strong)" : "var(--ondark-72)",
                  transitionDuration: "120ms",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = "var(--ondark-hover-bg)";
                    e.currentTarget.style.color = "var(--ondark-strong)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--ondark-72)";
                  }
                }}
              >
                <span style={{ color: isActive ? "var(--amber)" : "var(--ondark-55)" }}>
                  <NavIcon name={item.icon} />
                </span>
                <span>{item.label}</span>
              </a>
            </li>
          );
        })}
      </ul>

      <div
        className="flex items-center gap-2.5 px-4 pt-3 pb-2"
        style={{ borderTop: "1px solid var(--ondark-rule)" }}
        role="button"
        tabIndex={0}
        aria-label={`Konto: ${user.name}`}
      >
        <div
          aria-hidden="true"
          className="flex items-center justify-center rounded-full"
          style={{
            width: 32,
            height: 32,
            flex: "0 0 32px",
            background: "var(--amber)",
            color: "var(--ink)",
            fontSize: "var(--t-small)",
            fontWeight: 600,
            letterSpacing: "0.02em",
          }}
        >
          {user.initials}
        </div>
        <div className="min-w-0 flex-1">
          <div
            style={{
              fontSize: "var(--t-body)",
              color: "var(--ondark-strong)",
              lineHeight: 1.2,
            }}
          >
            {user.name}
          </div>
          <div
            className="overflow-hidden text-ellipsis whitespace-nowrap"
            style={{
              fontSize: 11,
              color: "var(--ondark-40)",
              lineHeight: 1.2,
              marginTop: 2,
            }}
          >
            {user.email}
          </div>
        </div>
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: "var(--ondark-40)" }}
        >
          <path d="M18 15l-6-6-6 6" />
        </svg>
      </div>

      <div
        className="pb-3 text-center"
        style={{
          padding: "4px 16px 12px",
          fontFamily: "var(--font-mono)",
          fontSize: "var(--t-micro)",
          color: "var(--ondark-25)",
          letterSpacing: "0.04em",
        }}
      >
        {version}
      </div>
    </aside>
  );
}
