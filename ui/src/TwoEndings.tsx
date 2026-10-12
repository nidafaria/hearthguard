import { NOT_COMPUTED, norm, Status, SyntheticTag } from "./data";

// Two endings (spec 13.12): the xz timeline beside the tallowdate timeline on one quarter axis. The
// tallowdate lane is SYNTHETIC. Each lane shows its saved decision per quarter and its saved takeover
// cost. A lane with no saved value says NOT COMPUTED; the spec's story is not drawn in its place.

export type LaneQuarter = { quarter: string; decision?: string | null; takeover_cost?: string | number | null };

export function quarterAxis(a: LaneQuarter[], b: LaneQuarter[]): string[] {
  return Array.from(new Set([...a, ...b].map((q) => q.quarter))).sort();
}

function Lane({ title, quarters, axis, synthetic }: { title: string; quarters: LaneQuarter[]; axis: string[]; synthetic?: boolean }) {
  const by = new Map(quarters.map((q) => [q.quarter, q]));
  return (
    <div>
      <h3>
        {title} {synthetic && <SyntheticTag />}
      </h3>
      <table>
        <thead>
          <tr>
            <th>Quarter</th>
            <th>Decision</th>
            <th>Takeover cost</th>
          </tr>
        </thead>
        <tbody>
          {axis.map((qt) => {
            const q = by.get(qt);
            const cost = q?.takeover_cost;
            return (
              <tr key={qt}>
                <td>{qt}</td>
                <td>{q ? <Status s={q.decision ?? null} /> : <span className="muted">no quarter in this file</span>}</td>
                <td>
                  {cost != null && norm(String(cost)) !== NOT_COMPUTED ? (
                    String(cost)
                  ) : (
                    <Status s={NOT_COMPUTED} />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function TwoEndings({
  xz,
  tallowdate,
}: {
  xz: LaneQuarter[] | undefined;
  tallowdate: LaneQuarter[] | undefined;
}) {
  const axis = quarterAxis(xz ?? [], tallowdate ?? []);
  return (
    <section aria-label="Two endings">
      <h2>Two endings, one time axis</h2>
      <p className="muted">
        xz is the public record. The tallowdate timeline is synthetic: fictional project, fictional people.
      </p>
      <div className="grid">
        {xz ? (
          <Lane title="xz (public record)" quarters={xz} axis={axis} />
        ) : (
          <p className="NOT_COMPUTED tag">NOT COMPUTED: the xz replay file was not found.</p>
        )}
        {tallowdate ? (
          <Lane title="tallowdate" quarters={tallowdate} axis={axis} synthetic />
        ) : (
          <p className="NOT_COMPUTED tag">NOT COMPUTED: the tallowdate decision file was not found.</p>
        )}
      </div>
    </section>
  );
}
