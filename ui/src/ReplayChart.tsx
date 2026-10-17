import { computed, norm, Status, NOT_COMPUTED } from "./data";

// Plate 01's main chart: the four moves and one condition, one square per quarter-end. Every mark is a
// saved status from xz_replay.json; nothing is drawn that the file does not hold.

export type ChartQuarter = { quarter: string; checks: Record<string, { status?: string | null } | undefined> };

const LANES: Array<[string, string]> = [
  ["pressure", "Pressure"],
  ["vouch", "Vouch"],
  ["rush", "Rush"],
  ["bypass", "Bypass"],
  ["lone_keeper", "Lone keeper"],
];

const W = 1400;
const PL = 170;
const PR = 30;
const T = 46;
const LH = 54;

export function ReplayChart({ quarters }: { quarters: ChartQuarter[] }) {
  const n = quarters.length;
  const x = (i: number) => PL + (i * (W - PL - PR)) / Math.max(n - 1, 1);
  const height = T + LANES.length * LH + 30;
  const ticks = Math.max(n - 1, 1) * 4;
  return (
    <div className="row">
      <div className="c s12">
        <div className="lab br" style={{ marginBottom: 22 }}>
          The four moves and one condition, by quarter
        </div>
        <svg className="viz" viewBox={`0 0 ${W} ${height}`} role="img" aria-label="Moves by quarter">
          <line className="rule" x1={PL - 20} x2={W - PR + 10} y1={18} y2={18} />
          {Array.from({ length: ticks + 1 }, (_, i) => {
            const X = PL + (i * (W - PL - PR)) / ticks;
            return <line key={i} className="rule" x1={X} x2={X} y1={18} y2={i % 4 ? 23 : 28} />;
          })}
          {quarters.map((q, i) => (
            <text key={q.quarter} x={x(i)} y={11} textAnchor="middle" className="t-ink">
              {q.quarter}
            </text>
          ))}
          {LANES.map(([k, label], li) => {
            const y = T + li * LH + (li === 4 ? 12 : 0);
            return (
              <g key={k}>
                <text className="lane" x={0} y={y + 5}>
                  {label}
                </text>
                <line className="rule" x1={PL - 20} x2={W - PR + 10} y1={y} y2={y} />
                {quarters.map((q, i) => {
                  const s = norm(q.checks[k]?.status);
                  const X = x(i);
                  return (
                    <g key={q.quarter} data-status={s}>
                      <title>
                        {label} {q.quarter}: {s}
                      </title>
                      {s === "FIRED" ? (
                        <rect x={X - 8} y={y - 8} width={16} height={16} fill="var(--signal)" />
                      ) : !computed(s) ? (
                        <>
                          <rect x={X - 8} y={y - 8} width={16} height={16} fill="var(--paper)" stroke="var(--graphite)" />
                          <path
                            d={`M${X - 8} ${y + 4}l12 -12M${X - 4} ${y + 8}l12 -12M${X - 8} ${y - 2}l6 -6M${X + 2} ${y + 8}l6 -6`}
                            stroke="var(--graphite)"
                            strokeWidth={0.8}
                          />
                        </>
                      ) : (
                        <rect x={X - 7} y={y - 7} width={14} height={14} fill="var(--paper)" stroke="var(--ink)" strokeWidth={1.6} />
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}
          <line
            x1={PL - 20}
            x2={W - PR + 10}
            y1={T + 3.5 * LH + 6}
            y2={T + 3.5 * LH + 6}
            stroke="var(--rule-2)"
            strokeDasharray="2 4"
          />
        </svg>
        <div className="legend-row">
          <Status s="FIRED" />
          <span className="tag NOT_FIRED">Did not fire</span>
          <Status s={NOT_COMPUTED} />
        </div>
      </div>
    </div>
  );
}
