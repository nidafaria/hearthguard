import { useEffect, useState } from "react";

type Cell = {
  status: string;
  reason?: string | null;
  source?: string;
  value?: number | null;
  unit?: string | null;
};
type Query = { name: string; query: string; params: Record<string, unknown>; ms: number; rows: number };
type Check = {
  status: string;
  reason: string;
  query_ms?: number | null;
  queries?: Query[];
  evidence?: Record<string, unknown>;
};
type ReplayRow = {
  quarter: string;
  T_iso: string;
  normal: Record<string, Cell>;
  checks: Record<string, Cell>;
  reader_unread_in_pressure_window: number;
  decision: { type: string; reason: string | null; source: string };
};
type Replay = {
  what: string;
  sources: string[];
  quarters: ReplayRow[];
  reader_coverage: {
    read_so_far: number;
    to_read: number;
    complete: boolean;
    excluded_human_labelled_test_set: number;
  };
};
type PvRow = { quarter: string; pressure: Check; vouch: Check };
type QsRow = { quarter: string; checks: Record<string, Check> };

type Loaded<T> = { state: "loading" } | { state: "missing"; file: string } | { state: "ok"; data: T };

function useResult<T>(file: string): Loaded<T> {
  const [v, setV] = useState<Loaded<T>>({ state: "loading" });
  useEffect(() => {
    fetch(`/results/${file}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("missing"))))
      .then((data) => setV({ state: "ok", data }))
      .catch(() => setV({ state: "missing", file }));
  }, [file]);
  return v;
}

const norm = (s: string) => (s === "NOT_COMPUTED" || s === "NOT COMPUTED" ? "NOT COMPUTED" : s);
const cls = (s: string) => norm(s).replace(" ", "_");

function NotComputed({ file }: { file: string }) {
  return (
    <p className="NOT_COMPUTED tag">
      NOT COMPUTED: {file} not found. Build it first (see README, Commands).
    </p>
  );
}

function Status({ s }: { s: string }) {
  return <span className={`tag ${cls(s)}`}>{norm(s)}</span>;
}

const COLS: Array<[string, string]> = [
  ["rush", "Rush"],
  ["bypass", "Bypass"],
  ["lone_keeper", "Lone keeper"],
  ["takeover_cost", "Takeover cost"],
  ["guardians", "Guardians"],
  ["pressure", "Pressure"],
  ["vouch", "Vouch"],
];

function ReplayTable({ replay, sel, onSel }: { replay: Replay; sel: string; onSel: (q: string) => void }) {
  const cov = replay.reader_coverage;
  return (
    <section>
      <h2>Replay, one row per quarter-end</h2>
      {!cov.complete && (
        <div className="banner">
          Reader coverage is incomplete: {cov.read_so_far} of {cov.to_read} messages read.{" "}
          {cov.excluded_human_labelled_test_set} messages are held back for the human-labelled test set. A
          NOT_FIRED here is a result on the messages read only.
        </div>
      )}
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Quarter</th>
              <th>Cadence (days)</th>
              <th>Active keepers</th>
              {COLS.map(([, label]) => (
                <th key={label}>{label}</th>
              ))}
              <th>Unread msgs (120d)</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {replay.quarters.map((r) => (
              <tr key={r.quarter} className={r.quarter === sel ? "sel" : ""} onClick={() => onSel(r.quarter)}>
                <td>{r.quarter}</td>
                <td>
                  {r.normal.cadence_days?.value == null ? (
                    <Status s="NOT COMPUTED" />
                  ) : (
                    r.normal.cadence_days.value.toFixed(4)
                  )}
                </td>
                <td>
                  {r.normal.active_keepers?.value == null ? (
                    <Status s="NOT COMPUTED" />
                  ) : (
                    r.normal.active_keepers.value
                  )}
                </td>
                {COLS.map(([k]) => (
                  <td key={k}>
                    <Status s={r.checks[k]?.status ?? "NOT COMPUTED"} />
                  </td>
                ))}
                <td>{r.reader_unread_in_pressure_window}</td>
                <td>
                  <Status s={r.decision.type} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">Source files: {replay.sources.join(", ")}. Click a row for the detail below.</p>
    </section>
  );
}

function QueryBox({ q }: { q: Query }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button className="q" onClick={() => setOpen(!open)}>
        {open ? "hide" : "show"} query: {q.name}
      </button>
      <span className="muted">
        {" "}
        {q.ms.toFixed(1)} ms, {q.rows} rows
      </span>
      {open && (
        <pre>
          {q.query}
          {"\n"}params: {JSON.stringify(q.params)}
        </pre>
      )}
    </div>
  );
}

function CheckCard({ name, c }: { name: string; c: Check | undefined }) {
  if (!c) {
    return (
      <div className="card">
        <b>{name}</b>
        <p>
          <Status s="NOT COMPUTED" /> no data for this quarter
        </p>
      </div>
    );
  }
  const queries = c.queries ?? [];
  return (
    <div className="card">
      <b>{name}</b> <Status s={c.status} />
      <p>{c.reason}</p>
      {c.query_ms != null && <p className="muted">Total query time {c.query_ms.toFixed(1)} ms</p>}
      {c.evidence && Object.keys(c.evidence).length > 0 && (
        <pre>{JSON.stringify(c.evidence, null, 1).replace(/\n\s*/g, " ")}</pre>
      )}
      {queries.map((q, i) => (
        <QueryBox key={i} q={q} />
      ))}
      {queries.length === 0 && <p className="muted">No query ran for this check.</p>}
    </div>
  );
}

export default function App() {
  const replay = useResult<Replay>("xz_replay.json");
  const pv = useResult<{ quarters: PvRow[] }>("pressure_vouch_status.json");
  const qs = useResult<{ quarters: QsRow[] }>("xz_quarterly_status.json");
  const grant = useResult<{ status: string; reason: string; sources: unknown[] }>("xz_grant_search.json");
  const [sel, setSel] = useState("2024-Q1");

  const pvRow = pv.state === "ok" ? pv.data.quarters.find((q) => q.quarter === sel) : undefined;
  const qsRow = qs.state === "ok" ? qs.data.quarters.find((q) => q.quarter === sel) : undefined;
  const row = replay.state === "ok" ? replay.data.quarters.find((r) => r.quarter === sel) : undefined;

  return (
    <main>
      <h1>Hearthguard: xz replay</h1>
      <p className="sub">
        Read-only view of eval/results/*.json. Provisional. Nothing here is a finding about a person.
      </p>
      <div className="banner">
        Data on this page: the public xz git history and the public xz-devel mailing list, hashed on
        ingest. No synthetic or fixture data is shown on this page. Hand-built fixtures exist only in the
        tests.
      </div>

      {replay.state === "loading" && <p>Loading…</p>}
      {replay.state === "missing" && (
        <section>
          <NotComputed file={replay.file} />
        </section>
      )}
      {replay.state === "ok" && <ReplayTable replay={replay.data} sel={sel} onSel={setSel} />}

      <section>
        <h2>Detail for {sel}</h2>
        {row && (
          <p>
            Decision: <Status s={row.decision.type} /> {row.decision.reason ?? ""}
          </p>
        )}
        {pv.state === "missing" && <NotComputed file={pv.file} />}
        {qs.state === "missing" && <NotComputed file={qs.file} />}
        <div className="grid">
          <CheckCard name="Pressure" c={pvRow?.pressure} />
          <CheckCard name="Vouch" c={pvRow?.vouch} />
          {["rush", "bypass", "lone_keeper", "takeover_cost", "guardians"].map((k) => (
            <CheckCard key={k} name={k.replace("_", " ")} c={qsRow?.checks[k]} />
          ))}
        </div>
      </section>

      <section>
        <h2>Who was given commit or release rights</h2>
        {grant.state === "missing" && <NotComputed file={grant.file} />}
        {grant.state === "ok" && (
          <p>
            <Status s={grant.data.status} /> {grant.data.reason}. Sources searched: {grant.data.sources.length}.
          </p>
        )}
      </section>
    </main>
  );
}
