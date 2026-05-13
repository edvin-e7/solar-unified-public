import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "solar.theme";

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

function loadTheme(): Theme {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === "light" || raw === "dark" || raw === "system") return raw;
  return "system";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => loadTheme());

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const next: Record<Theme, Theme> = {
    light: "dark",
    dark: "system",
    system: "light",
  };

  const label: Record<Theme, string> = {
    light: "☼",
    dark: "☾",
    system: "◐",
  };

  const themeName: Record<Theme, string> = {
    light: "Ljus",
    dark: "Mörk",
    system: "System",
  };

  return (
    <button
      onClick={() => setTheme(next[theme])}
      title={`Tema: ${themeName[theme]}`}
      className="rounded bg-(--paper-tint) px-3 py-1 text-xs text-(--ink) hover:bg-(--rule)"
    >
      {label[theme]}
    </button>
  );
}
