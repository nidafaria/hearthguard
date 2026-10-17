import { useState } from "react";
import { NOT_COMPUTED, Status } from "./data";
import type { GapDecision, GapsDoc } from "./WhoSaw";

// Downstream packager question (spec 4.3). Pick a decision in the saved gaps file (for example the
// Debian upgrade request) and see the visibility-gap question it raises, with roles only. Read-only,
// public record, nothing is sent to anyone.

export function questionFor(d: GapDecision): string {
  return `Before ${d.deciding_role} decided at ${d.place} on ${d.decision_at}, did that role see the earlier signals about the same identity in the places it watches?`;
}

export function Packager({ gaps, file }: { gaps?: GapsDoc; file: string }) {
  const decisions = gaps?.decisions ?? [];
  const [pick, setPick] = useState<string>(decisions[0]?.decision ?? "");
  const d = decisions.find((x) => x.decision === pick) ?? decisions[0];
  return (
    <section aria-label="Downstream packager question">
      <h2>Downstream packager question</h2>
      <p className="muted">Public record, xz. Roles, not names. Read-only; nothing is sent.</p>
      {!gaps && <p className="NOT_COMPUTED tag">NOT COMPUTED: {file} not found. Run `make ecosystem-xz` first.</p>}
      {gaps && decisions.length > 0 && (
        <>
          <label>
            Decision{" "}
            <select value={d?.decision} onChange={(e) => setPick(e.target.value)} aria-label="Decision">
              {decisions.map((x) => (
                <option key={x.decision} value={x.decision}>
                  {x.decision}
                </option>
              ))}
            </select>
          </label>
          {d && (
            <>
              <p>
                <b className="question">{questionFor(d)}</b>
              </p>
              {d.status !== "COMPUTED" ? (
                <p>
                  <Status s={NOT_COMPUTED} /> {d.reason ?? "no reason saved"}
                </p>
              ) : d.gaps.length === 0 ? (
                <p>No gap: every signal the saved file checked was covered or referenced.</p>
              ) : (
                <ul>
                  {d.gaps.map((g, i) => (
                    <li key={i}>
                      <Status s={g.gap} /> a {g.signal_kind ?? "signal"} in {g.signal_place} at {g.signal_at}
                      {g.label_confidence && <span className="muted"> (label: {g.label_confidence})</span>}
                    </li>
                  ))}
                </ul>
              )}
              <p className="muted">
                A gap is a lower bound: the cached records are the only signals. UNREACHABLE means no loaded
                record shows the role acting in that place before the signal; it is not proof the role was not
                watching.
              </p>
            </>
          )}
        </>
      )}
    </section>
  );
}
