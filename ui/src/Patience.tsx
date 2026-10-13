import { NOT_COMPUTED } from "./data";

// Patience curve (spec 13.7): detection rate and lead time against attacker patience, full memory
// against forgetful memory, on one chart. The chart reads eval/results/ablation_memory.json, which
// block C writes. Until that file is on this branch, the panel says NOT COMPUTED and names the blocker.
// No curve is drawn from anything else.

export const ABLATION_FILE = "ablation_memory.json";

export function Patience({ present }: { present: boolean }) {
  return (
    <section aria-label="Patience curve">
      <h2>Patience curve</h2>
      {present ? (
        <p className="muted">
          {ABLATION_FILE} is present. The chart is not drawn: its schema is set by the ablation that writes
          it, and this branch does not yet read it.
        </p>
      ) : (
        <p className="NOT_COMPUTED tag">
          {NOT_COMPUTED}: {ABLATION_FILE} is not on this branch. Blocker: the memory ablation (`make
          ablation-memory`) writes it. See eval/results/blockers_b.md.
        </p>
      )}
    </section>
  );
}
