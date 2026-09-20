"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";

type Theme = "light" | "dark" | "system";

const NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<Theme, string> = {
  system: "Theme: system",
  light: "Theme: light",
  dark: "Theme: dark",
};
const GLYPH: Record<Theme, string> = { system: "◐", light: "☀", dark: "☾" };

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    const stored = window.localStorage.getItem("finpilot-theme") as Theme | null;
    if (stored === "light" || stored === "dark") setTheme(stored);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") {
      root.removeAttribute("data-theme");
      window.localStorage.removeItem("finpilot-theme");
    } else {
      root.setAttribute("data-theme", theme);
      window.localStorage.setItem("finpilot-theme", theme);
    }
  }, [theme]);

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setTheme((t) => NEXT[t])}
      aria-label={`${LABEL[theme]}. Activate to switch to ${NEXT[theme]}.`}
    >
      <span aria-hidden="true">{GLYPH[theme]}</span>
      <span className="hidden sm:inline">{LABEL[theme].replace("Theme: ", "")}</span>
    </Button>
  );
}
