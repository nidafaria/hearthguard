import { NOT_COMPUTED, useResult } from "./data";

// Patience curve (spec 13.7): detection rate and lead time against attacker patience, full memory
// against forgetful memory, on one chart. The chart reads eval/results/ablation_memory.json, which
// `eval/ablation_memory.py` writes. Every point is a number from that file; nothing is computed or
// filled in here. A tie, or a forgetful arm that looks better, is drawn as it was measured (spec 10.2).
// If the file is absent the panel says NOT COMPUTED and names the blocker. No curve is drawn from
// anything else.

export const ABLATION_FILE = "ablation_memory.json";

export type ArmRow = {
  patience_days: number;
  n: number;
  detection_rate: number | null;
  median_lead_time_days: number | null;
};
export type Arm = {
  memory_window_days: number | null;
  summary: Omit<ArmRow, "patience_days">;
  by_patience: ArmRow[];
  clean: { n: number; flagged: number; false_flag_rate: number | null };
};
export type AblationDoc = {
  label?: string;
  n: number;
  n_clean?: number;
  seed?: number;
  arms: Record<string, Arm>;
  comparison?: Record<string, { overall: { verdict: string } }>;
  notes?: string[];
};

export type Series = { arm: string; text: string; points: { x: number; rate: number | null; lead: number | null; n: number }[] };

const ORDER = ["full", "forget_90", "forget_30"];
const TEXT: Record<string, string> = {
  full: "Full memory",
  forget_90: "Forgetful: last 90 days",
  forget_30: "Forgetful: last 30 days",
};

// The series to draw, straight from the file's by_patience rows, in the order full, 90, 30.
// Returns null when the file does not have the shape of the memory ablation.
export function seriesOf(doc: AblationDoc | undefined): Series[] | null {
  if (!doc || typeof doc !== "object" || !doc.arms || !doc.arms.full) return null;
  const names = [...ORDER.filter((a) => doc.arms[a]), ...Object.keys(doc.arms).filter((a) => !ORDER.includes(a))];
  return names.map((arm) => ({
    arm,
    text: TEXT[arm] ?? arm,
    points: (doc.arms[arm].by_patience ?? []).map((r) => ({
      x: r.patience_days,
      rate: r.detection_rate,
      lead: r.median_lead_time_days,
      n: r.n,
    })),
  }));
}

const W = 640;
const PAD = { l: 52, r: 16, t: 14, b: 30 };
const PANEL_H = 150;
const COLORS: Record<string, string> = { full: "#1b6ec2", forget_90: "#c27c1b", forget_30: "#b3261e" };

function Panel({
  title,
  series,
  field,
  max,
  top,
  xs,
  fmt,
}: {
  title: string;
  series: Series[];
  field: "rate" | "lead";
  max: number;
  top: number;
  xs: number[];
  fmt: (v: number) => string;
}) {
  const xPos = (x: number) => PAD.l + (xs.length < 2 ? 0 : (xs.indexOf(x) / (xs.length - 1)) * (W - PAD.l - PAD.r));
  const yPos = (v: number) => top + PAD.t + (1 - v / max) * (PANEL_H - PAD.t - PAD.b);
  const ticks = [0, max / 2, max];
  return (
    <g aria-label={title}>
      <text x={PAD.l} y={top + 10} fontSize="12" fontWeight="600">
        {title}
      </text>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={PAD.l} x2={W - PAD.r} y1={yPos(t)} y2={yPos(t)} stroke="currentColor" opacity="0.15" />
          <text x={PAD.l - 6} y={yPos(t) + 4} fontSize="11" textAnchor="end">
            {fmt(t)}
          </text>
        </g>
      ))}
      {series.map((s) => {
        const pts = s.points.filter((p) => p[field] !== null);
        return (
          <g key={s.arm} data-arm={s.arm}>
            <polyline
              fill="none"
              stroke={COLORS[s.arm] ?? "currentColor"}
              strokeWidth="2"
              points={pts.map((p) => `${xPos(p.x)},${yPos(p[field] as number)}`).join(" ")}
            />
            {pts.map((p) => (
              <circle key={p.x} cx={xPos(p.x)} cy={yPos(p[field] as number)} r="3" fill={COLORS[s.arm] ?? "currentColor"}>
                <title>{`${s.text}, patience ${p.x} days: ${fmt(p[field] as number)} (n=${p.n})`}</title>
              </circle>
            ))}
          </g>
        );
      })}
    </g>
  );
}

export function Curve({ doc }: { doc: AblationDoc }) {
  const series = seriesOf(doc);
  if (!series) return null;
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b);
  const leadMax = Math.max(1, ...series.flatMap((s) => s.points.map((p) => p.lead ?? 0)));
  const H = PANEL_H * 2 + 8;
  return (
    <>
      <svg role="img" aria-label="Detection rate and lead time against attacker patience" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }}>
        <Panel title="Detection rate" series={series} field="rate" max={1} top={0} xs={xs} fmt={(v) => `${Math.round(v * 100)}%`} />
        <Panel title="Median lead time (days)" series={series} field="lead" max={leadMax} top={PANEL_H + 8} xs={xs} fmt={(v) => String(Math.round(v * 10) / 10)} />
        {xs.map((x) => (
          <text key={x} x={PAD.l + (xs.length < 2 ? 0 : (xs.indexOf(x) / (xs.length - 1)) * (W - PAD.l - PAD.r))} y={H - 8} fontSize="11" textAnchor="middle">
            {x}
          </text>
        ))}
      </svg>
      <p className="muted">Attacker patience in days (days from first action to the privilege grant).</p>
      <ul aria-label="Legend" style={{ listStyle: "none", padding: 0, display: "flex", gap: 16, flexWrap: "wrap" }}>
        {series.map((s) => (
          <li key={s.arm}>
            <span style={{ color: COLORS[s.arm] ?? "currentColor" }}>●</span> {s.text}
          </li>
        ))}
      </ul>
      <table aria-label="Patience curve values">
        <thead>
          <tr>
            <th>Arm</th>
            <th>Detected / n (all patience)</th>
            <th>Median lead (days)</th>
            <th>Clean campaigns flagged</th>
            <th>Versus full</th>
          </tr>
        </thead>
        <tbody>
          {series.map((s) => {
            const a = doc.arms[s.arm];
            const sum = a.summary;
            return (
              <tr key={s.arm}>
                <td>{s.text}</td>
                <td>
                  {sum.detection_rate === null ? NOT_COMPUTED : `${Math.round(sum.detection_rate * sum.n)} / ${sum.n}`}
                </td>
                <td>{sum.median_lead_time_days === null ? NOT_COMPUTED : Math.round(sum.median_lead_time_days * 10) / 10}</td>
                <td>{a.clean ? `${a.clean.flagged} / ${a.clean.n}` : NOT_COMPUTED}</td>
                <td>{s.arm === "full" ? "baseline" : doc.comparison?.[s.arm]?.overall.verdict ?? NOT_COMPUTED}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted">
        {doc.label ?? "Synthetic campaigns."} N={doc.n} attack campaigns
        {doc.n_clean !== undefined ? `, ${doc.n_clean} clean` : ""}. Published as measured: a tie is a tie. Three real attacks are
        too few to claim precision.
      </p>
    </>
  );
}

export function Patience({ present, data }: { present: boolean; data?: AblationDoc }) {
  const loaded = useResult<AblationDoc>(ABLATION_FILE);
  const doc = data ?? (present && loaded.state === "ok" ? loaded.data : undefined);
  return (
    <section aria-label="Patience curve">
      <h2>Patience curve</h2>
      {!present && !data ? (
        <p className="NOT_COMPUTED tag">
          {NOT_COMPUTED}: {ABLATION_FILE} is not on this branch. Blocker: the memory ablation (`make
          ablation-memory`) writes it. See eval/results/blockers_b.md.
        </p>
      ) : doc && seriesOf(doc) ? (
        <Curve doc={doc} />
      ) : (
        <p className="muted">
          The chart is not drawn: {ABLATION_FILE} is present but{" "}
          {loaded.state === "loading" ? "is still being read." : "could not be read in the expected shape."}
        </p>
      )}
    </section>
  );
}
