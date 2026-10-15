import { NOT_COMPUTED, useResult } from "./data";

// Census (spec 13.9, 11.2): the distribution of takeover cost across N public packages, as
// aggregates only. No package names, no per-package rows, no list of anyone. The screen reads
// eval/results/census.json, which `make census` will write. That command and the npm ingest
// behind it are not built, so today the screen says NOT COMPUTED and names why. It draws nothing
// from any other source.

export const CENSUS_FILE = "census.json";

export type CensusDoc = {
  n: number;
  label?: string;
  cost_distribution: Record<string, number>;
  generated_at_utc?: string;
};

export function Census({ present, data }: { present: boolean; data?: CensusDoc }) {
  const loaded = useResult<CensusDoc>(CENSUS_FILE);
  const doc = data ?? (present && loaded.state === "ok" ? loaded.data : undefined);
  return (
    <section aria-label="Census">
      <h2>Takeover Cost Census</h2>
      <p>
        Aggregates only: how many packages have each takeover cost. No package names and no
        per-package results are shown or stored here. A high share at cost 1 describes how the
        ecosystem is structured. It is not a statement about any person or project.
      </p>
      {!doc ? (
        <p className="NOT_COMPUTED tag">
          {NOT_COMPUTED}: {CENSUS_FILE} is not on this branch. The census (`make census`) and its
          npm ingest are not built, and no registry records for N packages are cached. See
          eval/results/blockers_census.md.
        </p>
      ) : (
        <>
          <table aria-label="Cost distribution">
            <thead>
              <tr>
                <th>Takeover cost</th>
                <th>Packages</th>
                <th>Share</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(doc.cost_distribution).map(([cost, count]) => (
                <tr key={cost}>
                  <td>{cost}</td>
                  <td>{count}</td>
                  <td>{doc.n ? `${Math.round((count / doc.n) * 100)}%` : NOT_COMPUTED}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            {doc.label ?? "Public npm packages, structure only."} N={doc.n}. Provenance absence is
            not compromise.
          </p>
        </>
      )}
    </section>
  );
}
