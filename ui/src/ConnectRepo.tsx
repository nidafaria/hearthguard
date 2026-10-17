import { useEffect, useRef, useState } from "react";
import { Blank, Fig, NOT_COMPUTED, PlateHead, PlateNext, Status } from "./data";

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

export const DEFAULT_REPO = "octocat/Hello-World";

const isComputed = (m?: Metric) => !!m && m.status !== NOT_COMPUTED && m.status !== "NOT_COMPUTED" && m.value != null;

// A saved number as the plates show it: whole numbers as they are, others to one decimal.
function shown(m: Metric): string {
  const v = typeof m.value === "number" && !Number.isInteger(m.value) ? m.value.toFixed(1) : String(m.value);
  return m.unit && m.unit !== "channel" ? `${v} ${m.unit}` : v;
}

// One metric as a table row: the label, then the saved value, or its NOT COMPUTED mark and reason.
function MetricRow({ label, m }: { label: string; m?: Metric }) {
  return (
    <tr>
      <td>{label}</td>
      <td className="n">
        {isComputed(m) ? (
          shown(m!)
        ) : (
          <>
            <Status s={m?.status ?? NOT_COMPUTED} />
            {m?.reason && <div className="mono g" style={{ fontSize: 12, marginTop: 6 }}>{m.reason}</div>}
          </>
        )}
      </td>
    </tr>
  );
}

const plain = (v: number | undefined) => (v == null ? NOT_COMPUTED : String(v));

// The plate's body: the measured figures, the steps, the project's normal, and what could not be computed.
// `live` adds the run's own summary lines, which the saved-run view does not repeat.
export function ConnectResultView({ r, steps, live = false, file }: { r: ConnectResult; steps?: Step[]; live?: boolean; file: string }) {
  const rows = steps ?? r.steps ?? [];
  const best = r.best_hardening_step;
  return (
    <>
      {live && (
        <div className="row">
          <div className="c s12">
            <p className="fine">
              <b>{r.repo}</b> → <code>{r.org}</code> <Status s={r.status} />{" "}
              {r.reason && <span className="muted">{r.reason}</span>}
            </p>
            {r.wall_clock_s != null && (
              <p className="fine muted">
                Measured wall clock: {r.wall_clock_s} s. Requests to GitHub: {r.requests?.network ?? NOT_COMPUTED}, from
                cache: {r.requests?.from_cache ?? NOT_COMPUTED}.
              </p>
            )}
          </div>
        </div>
      )}
      <div className="row">
        {r.wall_clock_s != null ? (
          <Fig cls="s4" label="Measured wall clock" value={r.wall_clock_s.toFixed(1)} unit="s" src={file} />
        ) : (
          <Blank cls="s4" name="Measured wall clock" reason="not saved in this run" src={file} />
        )}
        <Fig cls="s4" label="Read-only requests to GitHub" value={plain(r.requests?.network)} src={file} />
        <div className="c s4 flush">
          <table className="tbl">
            <tbody>
              {rows.map((st, i) => (
                <tr key={st.name}>
                  <td className="n g">{String(i + 1).padStart(2, "0")}</td>
                  <td>{st.name}</td>
                  <td className="n" style={{ fontSize: 12 }}>
                    {st.detail || (st.status === "done" ? "done" : st.status)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="row">
        <div className="c s6 flush">
          <table className="tbl">
            <tbody>
              <MetricRow label="Commit cadence, median gap" m={r.metrics?.cadence_days} />
              <MetricRow label="Active keepers, last 90 days" m={r.metrics?.active_keepers} />
              <MetricRow label="Usual release path" m={r.metrics?.usual_path} />
              <tr>
                <td>Commits read</td>
                <td className="n">{plain(r.counts?.commits_read)}</td>
              </tr>
              <tr>
                <td>Releases loaded</td>
                <td className="n">{plain(r.counts?.releases_loaded)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Blank cls="s6" name="Takeover cost and best fix" reason={best?.reason ?? r.takeover_cost?.reason} src={file}>
          {live && (
            <>
              <span className="bw">{r.takeover_cost?.reason}</span>
              <span className="bw">{r.guardians?.reason}</span>
            </>
          )}
        </Blank>
      </div>
    </>
  );
}

export function ConnectRepo({ saved }: { saved?: ConnectResult }) {
  const [repo, setRepo] = useState(DEFAULT_REPO);
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

  const shownRun = job?.result ?? (job ? null : (saved ?? null));
  const live = !!job?.result;
  const repoName = shownRun?.repo ?? DEFAULT_REPO;
  return (
    <>
      <PlateHead
        n="15"
        title="Point it at any public repository."
        italic="It reads. It never writes."
        lede={
          <>
            One measured run on <span className="mono">{repoName}</span>: read-only requests, identifiers hashed on the
            way in, no sign-in. What it couldn&apos;t compute, it says.
          </>
        }
        kind="gh"
        tagLabel={`Public record (${repoName})`}
        plate="Connect a repository"
        data={`Public record (${repoName})`}
        sources={[live ? "/api/connect" : "connect_repo_run.json"]}
      />
      <form className="row" onSubmit={submit} aria-label="Connect your repo">
        <div className="c s8" style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <label className="lab" htmlFor="repo-input">
            Repository
          </label>
          <input
            id="repo-input"
            className="repo-input"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder={DEFAULT_REPO}
            aria-label="Repository owner/name"
            required
          />
        </div>
        <div className="c s4">
          <button type="submit" className="btn solid">
            <span>Connect</span>
            <span>→</span>
          </button>
        </div>
      </form>
      {error && (
        <div className="row">
          <div className="c s12">
            <p className="NOT_COMPUTED tag">{error}</p>
          </div>
        </div>
      )}
      {job && !job.result && (
        <div className="row">
          <div className="c s12">
            <div className="lab br">Progress ({job.state})</div>
            <ol>
              {job.steps.map((s) => (
                <li key={s.name}>
                  {s.name}: <Status s={s.status === "done" ? "DONE" : s.status === "failed" ? "FAILED" : s.status} />{" "}
                  {s.detail && <span className="muted">{s.detail}</span>}
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
      {shownRun && (
        <ConnectResultView
          r={shownRun}
          steps={job?.result ? job.steps : undefined}
          live={live}
          file={live ? "/api/connect" : "connect_repo_run.json"}
        />
      )}
      {!shownRun && !job && (
        <div className="row">
          <div className="c s12">
            <p className="fine">
              Public GitHub repos only, as owner/name. Read-only GET requests. Identifiers are hashed. No sign-in.
            </p>
          </div>
        </div>
      )}
      <PlateNext line="That's the whole record. Back to the beginning." href="#/" n="00" title="Hearthguard" />
    </>
  );
}
