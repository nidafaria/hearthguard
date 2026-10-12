import { NOT_COMPUTED, Status } from "./data";

// Hardening simulator (spec 13.6). Up to three steps, each with before and after takeover cost and
// guardians. Caught and lead time are NOT COMPUTED unless a saved red-team result holds them; the xz
// hardening file says the red team was not run.

export type HardStepCell = { status: string; value?: number | null; reason?: string | null };
export type XzHardening = {
  org: string;
  provisional: boolean;
  red_team?: string;
  results: Array<{
    quarter: string;
    steps: Array<{
      step: string;
      applied: boolean;
      before: { takeover_cost: HardStepCell; guardians: HardStepCell };
      after: { takeover_cost: HardStepCell; guardians: HardStepCell };
      note?: string | null;
    }>;
  }>;
};
export type FixtureHardening = {
  rule?: string;
  results: Array<{
    fixture: string;
    step: string;
    before: { cost: number; cost_status: string; guardians: number | null; guardians_status: string };
    after: { cost: number; cost_status: string; guardians: number | null; guardians_status: string };
  }>;
};

const MAX_STEPS = 3;

function cell(c: HardStepCell | undefined): string {
  if (!c) return NOT_COMPUTED;
  if (c.status === "COMPUTED" && c.value != null) return String(c.value);
  return NOT_COMPUTED;
}

export function Hardening({ xz, fixture }: { xz?: XzHardening; fixture?: FixtureHardening }) {
  const latest = xz?.results[xz.results.length - 1];
  const steps = (latest?.steps ?? []).slice(0, MAX_STEPS);
  return (
    <section aria-label="Hardening simulator">
      <h2>Hardening simulator</h2>
      <p className="muted">
        Up to three steps per graph. Before and after values come from saved results only. Rule:{" "}
        {fixture?.rule ?? "docs/decisions/0001-outsider-edges (PROPOSED), as named in the saved file"}.
      </p>
      <h3>xz, latest quarter-end {latest ? `(${latest.quarter})` : ""}</h3>
      {!xz && <p className="NOT_COMPUTED tag">NOT COMPUTED: xz_hardening.json not found.</p>}
      {xz && steps.length > 0 && (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Step</th>
                <th>Applied</th>
                <th>Takeover cost before</th>
                <th>Takeover cost after</th>
                <th>Guardians before</th>
                <th>Guardians after</th>
                <th>Caught</th>
                <th>Lead time</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((s) => (
                <tr key={s.step}>
                  <td>{s.step}</td>
                  <td>{s.applied ? "yes" : "no"}</td>
                  <td>{cell(s.before.takeover_cost)}</td>
                  <td>{cell(s.after.takeover_cost)}</td>
                  <td>{cell(s.before.guardians)}</td>
                  <td>{cell(s.after.guardians)}</td>
                  <td>
                    <Status s={NOT_COMPUTED} />
                  </td>
                  <td>
                    <Status s={NOT_COMPUTED} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {xz && (
        <p className="muted">
          {xz.red_team ?? "Red-team result: not in this file."} Caught and lead time need that result.
        </p>
      )}
      <h3>Fixture graphs (hand-built, in tests)</h3>
      {!fixture && <p className="NOT_COMPUTED tag">NOT COMPUTED: hardening_fixture.json not found.</p>}
      {fixture && (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Fixture</th>
                <th>Step</th>
                <th>Cost before → after</th>
                <th>Guardians before → after</th>
              </tr>
            </thead>
            <tbody>
              {fixture.results.map((r) => (
                <tr key={`${r.fixture}-${r.step}`}>
                  <td>{r.fixture}</td>
                  <td>{r.step}</td>
                  <td>
                    {r.before.cost} → {r.after.cost}
                  </td>
                  <td>
                    {r.before.guardians ?? NOT_COMPUTED} → {r.after.guardians ?? NOT_COMPUTED}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
