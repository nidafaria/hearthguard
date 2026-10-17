import { NOT_COMPUTED, Status } from "./data";

// Who saw what (spec 13.2). One row per place, time across, a dot per signal, a dashed line at each
// downstream decision, and the signals the saved gaps file computed as gaps ringed in red. Roles, not
// names: only event kind, place, time and actor role are drawn. Persona and handle fields in the saved
// events file are never read here.

export type GapEvent = { event_id: string; place: string; at: string; kind: string; actor_role: string };
export type GapRow = {
  gap: string;
  signal: string;
  signal_kind?: string;
  signal_place: string;
  signal_at: string;
  label_confidence?: string;
};
export type GapDecision = {
  decision: string;
  place: string;
  decision_at: string;
  deciding_role: string;
  decision_kind?: string;
  status: string;
  reason?: string | null;
  signals_checked?: number;
  covered_watched_and_referenced?: number;
  gaps: GapRow[];
};
export type GapsDoc = { decisions: GapDecision[] };
export type EventsDoc = { events: GapEvent[] };

const W = 860;
const ROW_H = 46;
const PAD = { l: 120, r: 16, t: 26, b: 34 };

const ms = (iso: string) => Date.parse(iso);

export function WhoSaw({ gaps, events }: { gaps: GapsDoc; events: EventsDoc }) {
  const places = Array.from(new Set(events.events.map((e) => e.place))).sort();
  const decisions = gaps.decisions;
  const gapSignals = new Map<string, GapRow[]>();
  for (const d of decisions) {
    if (d.status !== "COMPUTED") continue;
    for (const g of d.gaps) gapSignals.set(g.signal, [...(gapSignals.get(g.signal) ?? []), g]);
  }
  const times = [
    ...events.events.map((e) => ms(e.at)),
    ...decisions.map((d) => ms(d.decision_at)),
  ].filter((t) => !Number.isNaN(t));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const x = (t: number) => PAD.l + ((t - t0) / Math.max(t1 - t0, 1)) * (W - PAD.l - PAD.r);
  const H = PAD.t + places.length * ROW_H + PAD.b;
  const rowY = (p: string) => PAD.t + places.indexOf(p) * ROW_H + ROW_H / 2;
  const computedDecisions = decisions.filter((d) => d.status === "COMPUTED");
  const notComputed = decisions.filter((d) => d.status !== "COMPUTED");
  const gapCount = computedDecisions.reduce((n, d) => n + d.gaps.length, 0);

  return (
    <section aria-label="Who saw what">
      <h2>Who saw what</h2>
      <p className="muted">
        Public record, xz. Roles, not names. Red rings are gaps the saved file computed; a gap is a lower bound,
        because the cached records are the only signals.
      </p>
      <div className="scroll">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Signals by place and time">
          {places.map((p) => (
            <g key={p}>
              <text x={6} y={rowY(p) + 4} fontSize="12">
                {p}
              </text>
              <line x1={PAD.l} x2={W - PAD.r} y1={rowY(p)} y2={rowY(p)} style={{ stroke: "var(--rule-2)" }} />
            </g>
          ))}
          {computedDecisions.map((d) => (
            <g key={d.decision}>
              <line
                x1={x(ms(d.decision_at))}
                x2={x(ms(d.decision_at))}
                y1={PAD.t}
                y2={H - PAD.b}
                style={{ stroke: "var(--ink)" }}
                strokeDasharray="4 3"
              >
                <title>
                  {d.deciding_role} decided ({d.decision_kind ?? "decision"}) at {d.decision_at}
                </title>
              </line>
            </g>
          ))}
          {events.events.map((e) => {
            const gapped = gapSignals.has(e.event_id);
            return (
              <circle
                key={e.event_id}
                cx={x(ms(e.at))}
                cy={rowY(e.place)}
                r={gapped ? 6 : 4}
                style={{ fill: "var(--ink)", stroke: gapped ? "var(--signal)" : "none" }}
                strokeWidth={gapped ? 3 : 0}
                data-gap={gapped ? "yes" : "no"}
              >
                <title>
                  {e.kind} by {e.actor_role} in {e.place} at {e.at}
                  {gapped ? ` (gap: ${gapSignals.get(e.event_id)!.map((g) => g.gap).join(", ")})` : ""}
                </title>
              </circle>
            );
          })}
        </svg>
      </div>
      <p>
        {gapCount} gap row(s) computed across {computedDecisions.length} decision(s).
      </p>
      <ul>
        {computedDecisions.map((d) => (
          <li key={d.decision}>
            <b>{d.deciding_role}</b> at {d.place}, {d.decision_at}:{" "}
            {d.gaps.length === 0 ? "no gap" : d.gaps.map((g) => g.gap).join(", ")}
          </li>
        ))}
        {notComputed.map((d) => (
          <li key={d.decision}>
            <Status s={NOT_COMPUTED} /> {d.deciding_role} at {d.place}: {d.reason ?? "no reason saved"}
          </li>
        ))}
      </ul>
    </section>
  );
}
