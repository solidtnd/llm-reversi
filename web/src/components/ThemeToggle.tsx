/**
 * ライト/ダークモードの手動切り替え。初期値は`prefers-color-scheme`(端末設定)に従い、
 * 一度切り替えたらその選択をlocalStorageに保持する(以後は端末設定の変化を追わない)。
 * FOUC対策の早期反映はindex.htmlのインラインスクリプトが担う。
 */

import { useEffect, useState } from "react";
import { MoonIcon, SunIcon } from "./Icons";

type ThemeOverride = "light" | "dark" | null;

const STORAGE_KEY = "llm-reversi-theme";

function readOverride(): ThemeOverride {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : null;
}

function prefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeToggle() {
  const [override, setOverride] = useState<ThemeOverride>(() => readOverride());
  const [systemDark, setSystemDark] = useState(() => prefersDark());

  useEffect(() => {
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (override) document.documentElement.setAttribute("data-theme", override);
    else document.documentElement.removeAttribute("data-theme");
  }, [override]);

  const effectiveDark = override ? override === "dark" : systemDark;

  const toggle = () => {
    const next: ThemeOverride = effectiveDark ? "light" : "dark";
    setOverride(next);
    localStorage.setItem(STORAGE_KEY, next);
  };

  return (
    <button
      type="button"
      className="icon-button"
      onClick={toggle}
      aria-label={effectiveDark ? "ライトモードに切り替え" : "ダークモードに切り替え"}
    >
      {effectiveDark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}
