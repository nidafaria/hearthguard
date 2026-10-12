import { computed, NOT_COMPUTED, norm, Status, SyntheticTag } from "./data";

// Takeover cost gauge (spec 13.3): the number, the guardians, and the path. A value is shown only
// when the saved check computed it. There is no scale: the file holds a number, not a bound. Real xz has no grant record, so its gauge reads NOT COMPUTED with
// the saved reason.

export type CostCell = { status: string; value?: number | null; reason?: string | null } | null | undefined;

export function Gauge({
  cost,
  guardians,
  path,
  synthetic = false,
  source,
}: {
  cost: CostCell;
  guardians: CostCell;
  path?: string[] | null;
  synthetic?: boolean;
  source: string;
}) {
  const costOk = !!cost && computed(cost.status) && typeof cost.value === "number";
  const guardOk = !!guardians && computed(guardians.status) && typeof guardians.value === "number";
  return (
    <section aria-label="Takeover cost gauge">
      <h2>
        Takeover cost {synthetic && <SyntheticTag />}
      </h2>
      <p className="muted">Source: {source}</p>
      <div className="grid">
        <div className="card">
          {costOk ? (
            <>
              <p className="gauge-number" aria-label="takeover cost value">
                {cost!.value}
              </p>
            </>
          ) : (
            <p>
              <Status s={cost?.status ?? NOT_COMPUTED} /> <span className="muted">{norm(cost?.status) === NOT_COMPUTED ? "no number to show" : ""}</span>
            </p>
          )}
          <p className="muted">{cost?.reason ?? "no saved takeover-cost result for this org"}</p>
        </div>
        <div className="card">
          <b>Guardians</b>
          <p>
            {guardOk ? (
              <span className="gauge-number">{guardians!.value as number}</span>
            ) : (
              <>
                <Status s={guardians?.status ?? NOT_COMPUTED} />
              </>
            )}
          </p>
          <p className="muted">{guardians?.reason ?? "no saved guardians result"}</p>
        </div>
        <div className="card">
          <b>Path that achieves it</b>
          {path && path.length > 0 ? (
            <ol>
              {path.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ol>
          ) : (
            <p>
              <Status s={NOT_COMPUTED} />
            </p>
          )}
          <p className="muted">
            {path && path.length > 0
              ? "drawn on the trust map"
              : "no saved path: a path exists only where a takeover cost is computed"}
          </p>
        </div>
      </div>
    </section>
  );
}
