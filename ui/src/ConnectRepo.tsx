import { useEffect, useRef, useState } from "react";
import { NOT_COMPUTED, PlateTitle, PublicTag, Status } from "./data";

// Connect your repo (spec 13.8). A public GitHub repo as owner/name. The local API reads it with
// read-only GETs, builds org_<id> with hashed identifiers, and reports live progress. No login: a
// token, if one is in .env, is used by the server and never shown here.

export type Metric = { status: string; value?: unknown; unit?: string | null; n?: number | null; reason?: string | null };
export type Step = { name: string; status: string; detail?: string | null };
export type ConnectResult = {
  repo: string;
  org: string;
  status: string;
  reason?: string | null;
  wall_clock_s?: number;
  requests?: { network: number; from_cache: number };
  counts?: Record<string, number>;
  metrics?: Partial<Record<"cadence_days" | "active_keepers" | "usual_path", Metric>>;
  takeover_cost?: Metric;
  guardians?: Metric;
  best_hardening_step?: Metric;
  steps?: Step[];
};
type Job = { id: string; repo: string; state: string; steps: Step[]; result: ConnectResult | null };

export const POLL_MS = 500;

// One metric as a table row: the label, then the saved value, or its NOT COMPUTED mark and reason.
function MetricRow({ label, m }: { label: string; m?: Metric }) {
  if (!m)
    return (
      <tr>
        <th>{label}</th>
        <td>
          <Status s={NOT_COMPUTED} />
        </td>
      </tr>
    );
  const ok = m.status !== NOT_COMPUTED && m.status !== "NOT_COMPUTED" && m.value != null;
  return (
    <tr>
      <th>{label}</th>
      <td>
        {ok ? <b>{String(m.value)}{m.unit ? ` ${m.unit}` : ""}</b> : <Status s={m.status} />}
        {!ok && m.reason && <span className="muted"> ({m.reason})</span>}
      </td>
    </tr>
  );
}

export function ConnectResultView({ r }: { r: ConnectResult }) {
  return (
    <div>
      <p>
        <b>{r.repo}</b> → <code>{r.org}</code> <Status s={r.status} /> {r.reason && <span className="muted">{r.reason}</span>}
      </p>
      {r.wall_clock_s != null && (
        <p className="muted">
          Measured wall clock: {r.wall_clock_s} s. Requests to GitHub: {r.requests?.network ?? NOT_COMPUTED}, from
          cache: {r.requests?.from_cache ?? NOT_COMPUTED}.
        </p>
      )}
      {r.counts && (
        <p>
          Commits read {r.counts.commits_read ?? NOT_COMPUTED}, loaded {r.counts.commits_loaded ?? NOT_COMPUTED},
          actors {r.counts.actors ?? NOT_COMPUTED}, releases {r.counts.releases_loaded ?? NOT_COMPUTED}.
        </p>
      )}
      <h3>The project&apos;s normal</h3>
      <table className="metrics">
        <tbody>
          <MetricRow label="Commit cadence (median gap)" m={r.metrics?.cadence_days} />
          <MetricRow label="Active keepers, last 90 days" m={r.metrics?.active_keepers} />
          <MetricRow label="Usual release path" m={r.metrics?.usual_path} />
        </tbody>
      </table>
      <h3>Takeover cost</h3>
      <table className="metrics">
        <tbody>
          <MetricRow label="Takeover cost" m={r.takeover_cost} />
          <MetricRow label="Guardians" m={r.guardians} />
        </tbody>
      </table>
      <h3>Best hardening step</h3>
      <table className="metrics">
        <tbody>
          <MetricRow label="Best hardening step" m={r.best_hardening_step} />
        </tbody>
      </table>
    </div>
  );
}

export function ConnectRepo() {
  const [repo, setRepo] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current);
  }, []);

  function poll(id: string) {
    fetch(`/api/connect/${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j: Job) => {
        setJob(j);
        if (j.state === "running") timer.current = window.setTimeout(() => poll(id), POLL_MS);
      })
      .catch((e) => setError(`NOT COMPUTED: could not read the job (${e.message}).`));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setJob(null);
    fetch("/api/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo: repo.trim() }),
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          const d = body.detail;
          const msg = typeof d === "string" ? d : Array.isArray(d) && d[0]?.msg ? d[0].msg : `HTTP ${r.status}`;
          throw new Error(msg);
        }
        return r.json();
      })
      .then((j: { job: string }) => poll(j.job))
      .catch((err) =>
        setError(
          `NOT COMPUTED: ${err.message}. The connect API runs with the local server (make inbox, port 8765); the dev server proxies /api to it.`,
        ),
      );
  }

  return (
    <section aria-label="Connect your repo">
      <div className="plate-head">
        <h2 className="headline">
          Connect your repo <PublicTag />
        </h2>
        <PlateTitle
          plate="15 · Connect a repository"
          data="Public GitHub repo, read live through the local API"
          sources={["the local API, /api/connect"]}
        />
      </div>
      <p className="muted">
        Public GitHub repos only, as owner/name. Read-only GET requests. Identifiers are hashed. No sign-in.
      </p>
      <form onSubmit={submit}>
        <label>
          Repository{" "}
          <input
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="octocat/Hello-World"
            aria-label="Repository owner/name"
            required
          />
        </label>{" "}
        <button type="submit">Connect</button>
      </form>
      {error && <p className="NOT_COMPUTED tag">{error}</p>}
      {job && (
        <>
          <h3>Progress ({job.state})</h3>
          <ol>
            {job.steps.map((s) => (
              <li key={s.name}>
                {s.name}: <Status s={s.status === "done" ? "DONE" : s.status === "failed" ? "FAILED" : s.status} />{" "}
                {s.detail && <span className="muted">{s.detail}</span>}
              </li>
            ))}
          </ol>
          {job.result && <ConnectResultView r={job.result} />}
        </>
      )}
    </section>
  );
}
