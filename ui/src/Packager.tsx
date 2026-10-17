import { useState } from "react";
import { Blank, Fig, NOT_COMPUTED, PlateHead, PlateNext, Status } from "./data";
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
    <>
      <PlateHead
        n="07"
        title="The question every downstream maintainer"
        italic="deserves to ask."
        lede="Pick a decision from the public record. Hearthguard turns its gaps into one plain question, with roles only. It sends nothing to anyone."
        kind="pub"
        tagLabel="Public record (xz)"
        plate="The packager question"
        data="Public record (xz)"
        sources={[file]}
      />
      {!gaps && (
        <div className="row">
          <div className="c s12">
            <p className="NOT_COMPUTED tag">NOT COMPUTED: {file} not found. Run `make ecosystem-xz` first.</p>
          </div>
        </div>
      )}
      {gaps && decisions.length > 0 && (
        <>
          {/* The choice is made on the cards. The select stays for keyboard and screen-reader use, visually hidden. */}
          <label className="sr-only">
            Decision{" "}
            <select value={d?.decision} onChange={(e) => setPick(e.target.value)} aria-label="Decision">
              {decisions.map((x) => (
                <option key={x.decision} value={x.decision}>
                  {x.decision}
                </option>
              ))}
            </select>
          </label>
          <div
            className="row choices"
            role="group"
            aria-label="Choose a decision"
            style={{ gridTemplateColumns: `repeat(${decisions.length}, minmax(0, 1fr))` }}
          >
            {decisions.map((x) => (
              <button
                type="button"
                key={x.decision}
                className="c choice"
                aria-pressed={x.decision === d?.decision}
                onClick={() => setPick(x.decision)}
              >
                <span className="lab">
                  {x.place} · {x.decision_at.slice(0, 10)}
                </span>
                <span className="big-t choice-role">{x.deciding_role}</span>
              </button>
            ))}
          </div>
          {d && (
            <>
              <div className="row">
                <div className="c s12 question-cell">
                  <p className="serif-q">“{questionFor(d)}”</p>
                </div>
              </div>
              <div className="row">
                <Fig
                  cls="s4"
                  label="Gaps behind this question"
                  signal
                  value={d.status === "COMPUTED" ? d.gaps.length : NOT_COMPUTED}
                  caption={
                    d.status === "COMPUTED" && d.signals_checked != null
                      ? `of ${d.signals_checked} signals checked. ${d.covered_watched_and_referenced ?? 0} were covered.`
                      : undefined
                  }
                  src={file}
                />
                {d.status !== "COMPUTED" ? (
                  <Blank cls="s8" name="This decision" reason={d.reason ?? "no reason saved"} src={file} />
                ) : d.gaps.length === 0 ? (
                  <div className="c s8">
                    <p>No gap: every signal the saved file checked was covered or referenced.</p>
                  </div>
                ) : (
                  <div className="c s8 flush">
                    <table className="tbl">
                      <thead>
                        <tr>
                          <th>Gap</th>
                          <th>Signal</th>
                          <th>Where</th>
                          <th>When</th>
                          <th>Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {d.gaps.map((g, i) => (
                          <tr key={i}>
                            <td>
                              <Status s={g.gap} />
                            </td>
                            <td className="n">{g.signal_kind ?? "signal"}</td>
                            <td className="n">{g.signal_place}</td>
                            <td className="n">{g.signal_at.slice(0, 10)}</td>
                            <td className="n g">{g.label_confidence ?? ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <div className="row">
                <div className="c s12">
                  <p className="fine">
                    A gap is a lower bound: the cached records are the only signals. UNREACHABLE means no loaded
                    record shows the role acting in that place before the signal; it is not proof the role was not
                    watching. A question, not a verdict.
                  </p>
                </div>
              </div>
            </>
          )}
        </>
      )}
      <PlateNext line="Now set the real record beside an invented one." href="#/" n="08" title="Two timelines" />
    </>
  );
}
