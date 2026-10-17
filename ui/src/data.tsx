import { useEffect, useState } from "react";

// Shared loading and labels for every screen. Screens read saved files from eval/results/ through
// the dev server (vite.config.ts serves them) and never compute a number of their own.

export type Loaded<T> = { state: "loading" } | { state: "missing"; file: string } | { state: "ok"; data: T };

export function useResult<T>(file: string): Loaded<T> {
  const [v, setV] = useState<Loaded<T>>({ state: "loading" });
  useEffect(() => {
    let alive = true;
    fetch(`/results/${file}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("missing"))))
      .then((data) => alive && setV({ state: "ok", data }))
      .catch(() => alive && setV({ state: "missing", file }));
    return () => {
      alive = false;
    };
  }, [file]);
  return v;
}

export const NOT_COMPUTED = "NOT COMPUTED";

// A design token's current value, for code that needs a concrete colour (a canvas, not CSS). The
// fallback is used only where no stylesheet is loaded, such as a test.
export function token(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

// A saved status string, with NOT_COMPUTED and NOT COMPUTED treated as one value.
export function norm(s: string | null | undefined): string {
  if (s == null) return NOT_COMPUTED;
  return s === "NOT_COMPUTED" ? NOT_COMPUTED : s;
}

// True only when a saved result computed the check (FIRED, NOT_FIRED or COMPUTED).
export function computed(s: string | null | undefined): boolean {
  return norm(s) !== NOT_COMPUTED;
}

// The calendar quarter of an ISO timestamp or date, as the saved files label quarter-ends: 2024-Q1.
export function quarterOf(iso: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(iso);
  if (!m) return "";
  return `${m[1]}-Q${Math.floor((Number(m[2]) - 1) / 3) + 1}`;
}

export function Status({ s }: { s: string | null | undefined }) {
  const v = norm(s);
  return <span className={`tag ${v.replace(/ /g, "_")}`}>{v}</span>;
}

// A value the saved files do not hold: a blank tile, hatched, with the reason on a paper label.
export function NotComputed({ file, what }: { file: string; what?: string }) {
  return (
    <div className="blank">
      <p className="NOT_COMPUTED tag">
        NOT COMPUTED{what ? `: ${what}` : ""}: {file} not found. Build it first (see README, Commands).
      </p>
    </div>
  );
}

export function SyntheticTag() {
  return <span className="tag synthetic">SYNTHETIC</span>;
}

export function PublicTag() {
  return <span className="tag public">PUBLIC RECORD</span>;
}
