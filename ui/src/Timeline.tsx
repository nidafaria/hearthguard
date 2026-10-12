import { computed, NOT_COMPUTED, norm, quarterOf, Status, SyntheticTag } from "./data";

// Replay timeline (spec 13.1). One column per quarter-end. A marker per move with its saved status,
// takeover cost as a line only where a saved value exists, and the note-sent marker only when a saved
// file measured a send date. Nothing is plotted that a file does not hold.

export type TimelineQuarter = {
  quarter: string;
  moves: Record<string, string | null | undefined>; // pressure, vouch, rush, bypass, lone_keeper
  takeover_cost?: number | null;
  decision?: string | null;
};

export type NoteSent = { at_utc: string; source: string } | null | undefined;

const MOVES: Array<[string, string]> = [
  ["pressure", "Pressure"],
  ["vouch", "Vouch"],
  ["rush", "Rush"],
  ["bypass", "Bypass"],
];

const W = 760;
const H = 230;
const PAD = { l: 60, r: 16, t: 14, b: 40 };

export function Timeline({
  quarters,
  synthetic = false,
  noteSent,
  counts,
  source,
}: {
  quarters: TimelineQuarter[];
  synthetic?: boolean;
  noteSent?: NoteSent;
  counts?: { claims?: number; grants?: number; actions?: number } | null;
  source: string;
}) {
  const n = Math.max(quarters.length, 1);
  const x = (i: number) => PAD.l + (i * (W - PAD.l - PAD.r)) / Math.max(n - 1, 1);
  const costs = quarters.map((q) => q.takeover_cost);
  const costVals = costs.filter((c): c is number => typeof c === "number");
  const maxCost = Math.max(1, ...costVals);
  const y = (v: number) => H - PAD.b - (v / maxCost) * (H - PAD.t - PAD.b);
  const laneY = (k: number) => PAD.t + 14 + k * 26;

  // The line runs only between quarters that have a number; a gap breaks it.
  const segments: string[] = [];
  let cur: string[] = [];
  quarters.forEach((q, i) => {
    if (typeof q.takeover_cost === "number") cur.push(`${x(i)},${y(q.takeover_cost)}`);
    else if (cur.length) {
      segments.push(cur.join(" "));
      cur = [];
    }
  });
  if (cur.length) segments.push(cur.join(" "));

  const noteIndex = noteSent ? quarters.findIndex((q) => q.quarter === quarterOf(noteSent.at_utc)) : -1;

  return (
    <section aria-label="Replay timeline">
      <h2>
        Replay timeline {synthetic && <SyntheticTag />}
      </h2>
      <p className="muted">Source: {source}. Quarter-ends on one axis.</p>
      <div className="scroll">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Replay timeline chart">
          {MOVES.map(([k, label], lane) => (
            <g key={k}>
              <text x={4} y={laneY(lane) + 4} fontSize="11" className="muted">
                {label}
              </text>
              <line x1={PAD.l} x2={W - PAD.r} y1={laneY(lane)} y2={laneY(lane)} stroke="var(--line)" />
              {quarters.map((q, i) => {
                const s = norm(q.moves[k]);
                const fill = !computed(s) ? "var(--na)" : s === "FIRED" ? "var(--bad)" : "var(--ok)";
                return (
                  <circle key={q.quarter} cx={x(i)} cy={laneY(lane)} r={5} fill={fill} data-status={s}>
                    <title>
                      {label} {q.quarter}: {s}
                    </title>
                  </circle>
                );
              })}
            </g>
          ))}
          {quarters.map((q, i) => (
            <text key={q.quarter} x={x(i)} y={H - 18} fontSize="10" textAnchor="middle" className="muted">
              {q.quarter}
            </text>
          ))}
          {segments.map((pts, i) => (
            <polyline key={i} points={pts} fill="none" stroke="var(--warn)" strokeWidth={2} />
          ))}
          {noteIndex >= 0 && (
            <line x1={x(noteIndex)} x2={x(noteIndex)} y1={PAD.t} y2={H - PAD.b} stroke="var(--fg)" strokeDasharray="4 3">
              <title>Note sent {noteSent?.at_utc}</title>
            </line>
          )}
        </svg>
      </div>
      <ul className="legend">
        <li>
          Takeover cost:{" "}
          {costVals.length === 0 ? (
            <span className="NOT_COMPUTED">{NOT_COMPUTED} in every quarter of this file, so no line is drawn</span>
          ) : (
            <span>line drawn only at {costVals.length} quarter(s) with a saved value</span>
          )}
        </li>
        <li>
          Note sent:{" "}
          {noteSent ? (
            <span>
              marker at {noteSent.at_utc} (from {noteSent.source})
            </span>
          ) : (
            <span className="NOT_COMPUTED">{NOT_COMPUTED}: no saved file measures a send date</span>
          )}
        </li>
        <li>
          Claims, grants, actions:{" "}
          {counts && (counts.claims != null || counts.grants != null || counts.actions != null) ? (
            <span>
              claims {counts.claims ?? NOT_COMPUTED}, grants {counts.grants ?? NOT_COMPUTED}, actions{" "}
              {counts.actions ?? NOT_COMPUTED}
            </span>
          ) : (
            <span className="NOT_COMPUTED">{NOT_COMPUTED}: this file carries no counts per quarter</span>
          )}
        </li>
      </ul>
      <p className="muted">
        Decisions by quarter:{" "}
        {quarters.map((q) => (
          <span key={q.quarter} style={{ marginRight: 10 }}>
            {q.quarter} <Status s={q.decision ?? null} />
          </span>
        ))}
      </p>
    </section>
  );
}
