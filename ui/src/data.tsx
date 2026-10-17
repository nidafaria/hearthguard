import { useEffect, useState, type ReactNode } from "react";

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
  return <span className={`tag ${v.replace(/ /g, "_")}`}>{WORD[v] ?? v}</span>;
}

declare const __COMMIT__: string;
export const COMMIT: string = typeof __COMMIT__ === "undefined" ? "unknown" : __COMMIT__;

// The words the plates use for a saved status.
export const WORD: Record<string, string> = { HOLD: "Held", NOT_FIRED: "Did not fire", FIRED: "Fired" };

// The title block in a plate's corner: the plate, its data kind, the files it reads, and the build.
export function PlateTitle({ plate, data, sources }: { plate: string; data: string; sources: string[] }) {
  return (
    <div className="tb" aria-label="Title block">
      <span>Plate</span>
      <span>{plate}</span>
      <span>Data</span>
      <span>{data}</span>
      <span>Source</span>
      <span>
        {sources.map((f, i) => (
          <span key={f}>
            {i > 0 && <br />}
            {f}
          </span>
        ))}
      </span>
      <span>Built</span>
      <span>commit {COMMIT}</span>
    </div>
  );
}

// The plate headline: each word rises from a mask, 40 ms apart, unless reduced motion is on (then it shows at once).
// The words of `italic` follow `text`, set in the serif turn the plates use.
export function RisingTitle({ text, italic }: { text: string; italic?: string }) {
  const words = [
    ...text.split(" ").map((w) => [w, false] as const),
    ...(italic ? italic.split(" ").map((w) => [w, true] as const) : []),
  ];
  return (
    <h1 className="H">
      {words.map(([w, it], i) => (
        <span key={i}>
          <span className="w">
            <span style={{ animationDelay: `${i * 40}ms` }}>{it ? <i>{w}</i> : w}</span>
          </span>{" "}
        </span>
      ))}
    </h1>
  );
}

export type DataKind = "pub" | "syn" | "gh";

export function DataTag({ kind, label }: { kind: DataKind; label: string }) {
  const cls = kind === "syn" ? "tag synthetic" : kind === "gh" ? "tag public" : "tag pub";
  return <span className={cls}>{label}</span>;
}

// The head of a plate: kicker, headline, lede, and the title block in the corner.
export function PlateHead({
  n,
  of = 15,
  title,
  italic,
  lede,
  kind,
  tagLabel,
  plate,
  data,
  sources,
  extra,
}: {
  n: string;
  of?: number;
  title: string;
  italic?: string;
  lede: ReactNode;
  kind: DataKind;
  tagLabel: string;
  plate: string;
  data: string;
  sources: string[];
  extra?: ReactNode;
}) {
  return (
    <div className="row head">
      <div className="c s8 head-l">
        <div className="lab br">
          Plate {n} / {of}
        </div>
        <RisingTitle text={title} italic={italic} />
        <p className="lede">{lede}</p>
        {extra}
      </div>
      <div className="c s4 head-r">
        <div className="tags">
          <DataTag kind={kind} label={tagLabel} />
        </div>
        <PlateTitle plate={`${n} · ${plate}`} data={data} sources={sources} />
      </div>
    </div>
  );
}

// The foot of a plate: a serif line, the next screen, and the provenance line.
export function PlateNext({ line, href, n, title }: { line: string; href: string; n: string; title: string }) {
  return (
    <>
      <div className="nx">
        <div className="q">
          <p>{line}</p>
        </div>
        <a href={href}>
          <span className="lab">Next plate · {n}</span>
          <span className="t">{title} →</span>
        </a>
      </div>
      <PlateFoot />
    </>
  );
}

export function PlateFoot() {
  return (
    <div className="foot">
      <span>Every value on this page is read from eval/results/*.json or the local API · commit {COMMIT}</span>
      <span>Nothing here is a finding about a person</span>
    </div>
  );
}

// A big figure with its caption and source, as in the plates' stat cells.
export function Fig({
  label,
  value,
  of,
  unit,
  signal,
  caption,
  src,
  syn,
  cls = "",
}: {
  label: string;
  value: ReactNode;
  of?: ReactNode;
  unit?: string;
  signal?: boolean;
  caption?: ReactNode;
  src: string;
  syn?: boolean;
  cls?: string;
}) {
  return (
    <div className={`c figcol ${syn ? "syn" : ""} ${cls}`}>
      <div>
        <div className="lab">{label}</div>
        <span className={`fig xl ${signal ? "sig" : ""}`}>
          {signal && <span className="sq" />}
          {value}
          {(of != null || unit) && <small>{of != null ? `/ ${of}` : unit}</small>}
        </span>
        {caption && <p className="figcap">{caption}</p>}
      </div>
      <span className="src">{src}</span>
    </div>
  );
}

// A hatched tile naming what a saved file could not compute, and why.
export function Blank({
  name,
  reason,
  src,
  cls = "",
  children,
}: {
  name?: string;
  reason?: string | null;
  src?: string | null;
  cls?: string;
  children?: ReactNode;
}) {
  return (
    <div className={`c blank ${cls}`}>
      <span className="bt">{NOT_COMPUTED}</span>
      {name && <span className="bn">{name}</span>}
      <span className="bw">{reason || "no reason saved in the file"}</span>
      {children}
      {src && <span className="src">{src}</span>}
    </div>
  );
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
