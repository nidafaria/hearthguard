import { useState } from "react";
import { ConnectRepo } from "./ConnectRepo";
import { Gauge, type CostCell } from "./Gauge";
import { Hardening, type FixtureHardening, type XzHardening } from "./Hardening";
import { NotComputed, NOT_COMPUTED, Status, SyntheticTag, useResult } from "./data";
import { EvidenceCard, type Check, type Query, type Quote } from "./EvidenceCard";
import { Packager } from "./Packager";
import { Playbook } from "./Playbook";
import { Patience, ABLATION_FILE } from "./Patience";
import { Timeline, type TimelineQuarter } from "./Timeline";
import { TrustMap, type TrustMapDoc } from "./TrustMap";
import { TwoEndings, type LaneQuarter } from "./TwoEndings";
import { WhoSaw, type EventsDoc, type GapsDoc } from "./WhoSaw";

// The results page: every number here is read from eval/results/*.json. Nothing is computed in the
// browser. The pack header is on every screen; synthetic data is labelled where it appears.

type Cell = { status: string; reason?: string | null; source?: string; value?: number | null; unit?: string | null };
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
  reader_coverage: { read_so_far: number; to_read: number; complete: boolean; excluded_human_labelled_test_set: number };
};
type PvRow = { quarter: string; pressure: Check; vouch: Check };
type QsRow = { quarter: string; checks: Record<string, Check & { value?: number | null }> };
type TallowDetector = { quarters: Array<{ quarter: string; checks: Record<string, CostCell> }> };
type TallowDecision = { quarters: Array<{ quarter: string; decision: string; hold_reason?: string | null }> };
type VideoQuotes = { quotes: Record<string, Quote> };

const SCREENS = ["#/connect", "#/packager", "#/playbook"];

function Header({ hash }: { hash: string }) {
  const nav: Array<[string, string]> = [
    ["#/", "Results"],
    ["#/connect", "Connect your repo"],
    ["#/packager", "Packager question"],
    ["#/inbox", "Inbox (local)"],
    ["#/playbook", "Playbook"],
  ];
  const current = (href: string) => (href === "#/" ? !SCREENS.some((s) => hash.startsWith(s)) : hash.startsWith(href));
  return (
    <header>
      <div className="pack">
        Pack: <b>OSS</b> (xz, public record). Finance pack: not built. Read-only; nothing is sent.
      </div>
      <nav>
        {nav.map(([href, label]) => (
          <a key={href} href={href} className={current(href) ? "current" : ""}>
            {label}
          </a>
        ))}
      </nav>
    </header>
  );
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
          {cov.excluded_human_labelled_test_set} messages are held back for the human-labelled test set. A NOT_FIRED
          here is a result on the messages read only.
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
                  {r.normal.cadence_days?.value == null ? <Status s={NOT_COMPUTED} /> : r.normal.cadence_days.value.toFixed(4)}
                </td>
                <td>{r.normal.active_keepers?.value == null ? <Status s={NOT_COMPUTED} /> : r.normal.active_keepers.value}</td>
                {COLS.map(([k]) => (
                  <td key={k}>
                    <Status s={r.checks[k]?.status ?? NOT_COMPUTED} />
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
        {q.ms != null ? `${q.ms.toFixed(1)} ms` : "time not saved"}, {q.rows ?? "?"} rows
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
          <Status s={NOT_COMPUTED} /> no data for this quarter
        </p>
      </div>
    );
  }
  const queries = c.queries ?? [];
  return (
    <div className="card">
      <b>{name}</b> <Status s={c.status} />
      <p>{c.reason}</p>
      {c.query_ms != null && <p className="muted">Total query time {Number(c.query_ms).toFixed(1)} ms</p>}
      {queries.map((q, i) => (
        <QueryBox key={i} q={q} />
      ))}
      {queries.length === 0 && <p className="muted">No query ran for this check.</p>}
    </div>
  );
}

function ResultsPage() {
  const replay = useResult<Replay>("xz_replay.json");
  const pv = useResult<{ quarters: PvRow[] }>("pressure_vouch_status.json");
  const qs = useResult<{ quarters: QsRow[] }>("xz_quarterly_status.json");
  const grant = useResult<{ status: string; reason: string; sources: unknown[] }>("xz_grant_search.json");
  const takeover = useResult<{ takeover_cost: CostCell; guardians: CostCell }>("xz_takeover_status.json");
  const tallowDetector = useResult<TallowDetector>("tallowdate_detector_status.json");
  const tallowDecision = useResult<TallowDecision>("tallowdate_decision.json");
  const trust = useResult<TrustMapDoc>("trust_map_tallowdate.json");
  const hardening = useResult<XzHardening>("xz_hardening.json");
  const fixture = useResult<FixtureHardening>("hardening_fixture.json");
  const ablation = useResult<unknown>(ABLATION_FILE);
  const gaps = useResult<GapsDoc>("ecosystem_gaps.json");
  const events = useResult<EventsDoc>("ecosystem_events.json");
  const quotes = useResult<VideoQuotes>("video_quotes.json");
  const [sel, setSel] = useState("2024-Q1");

  const pvRow = pv.state === "ok" ? pv.data.quarters.find((q) => q.quarter === sel) : undefined;
  const qsRow = qs.state === "ok" ? qs.data.quarters.find((q) => q.quarter === sel) : undefined;
  const row = replay.state === "ok" ? replay.data.quarters.find((r) => r.quarter === sel) : undefined;

  const timeline: TimelineQuarter[] | null =
    replay.state === "ok"
      ? replay.data.quarters.map((r) => ({
          quarter: r.quarter,
          moves: Object.fromEntries(Object.entries(r.checks).map(([k, c]) => [k, c.status])),
          takeover_cost: r.checks.takeover_cost?.value ?? null,
          decision: r.decision.type,
        }))
      : null;

  const lanesXz: LaneQuarter[] | undefined =
    replay.state === "ok"
      ? replay.data.quarters.map((r) => ({
          quarter: r.quarter,
          decision: r.decision.type,
          takeover_cost: r.checks.takeover_cost?.value ?? null,
        }))
      : undefined;
  const lanesTallow: LaneQuarter[] | undefined =
    tallowDecision.state === "ok"
      ? tallowDecision.data.quarters.map((q) => ({ quarter: q.quarter, decision: q.decision }))
      : undefined;

  const tallowLast =
    tallowDetector.state === "ok" ? tallowDetector.data.quarters[tallowDetector.data.quarters.length - 1] : undefined;

  // Quotes are shown only from the saved file; a missing file leaves the card's quote section NOT COMPUTED.
  const quoteList: Quote[] | undefined = quotes.state === "ok" ? Object.values(quotes.data.quotes) : undefined;

  return (
    <main>
      <h1>Hearthguard: xz replay</h1>
      <p className="sub">Read-only view of eval/results/*.json. Provisional. Nothing here is a finding about a person.</p>
      <div className="banner">
        Data on this page: the public xz git history and the public xz-devel mailing list, hashed on ingest. The
        tallowdate panels are labelled SYNTHETIC. Hand-built fixtures appear only where labelled.
      </div>

      {replay.state === "loading" && <p>Loading…</p>}
      {replay.state === "missing" && (
        <section>
          <NotComputed file={replay.file} />
        </section>
      )}
      {replay.state === "ok" && <ReplayTable replay={replay.data} sel={sel} onSel={setSel} />}

      {timeline && (
        <Timeline
          quarters={timeline}
          source="xz_replay.json (moves and takeover cost per quarter-end)"
          counts={null}
          noteSent={null}
        />
      )}

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
        <EvidenceCard
          quarter={sel}
          checks={{
            pressure: pvRow?.pressure,
            vouch: pvRow?.vouch,
            rush: qsRow?.checks.rush,
            bypass: qsRow?.checks.bypass,
            lone_keeper: qsRow?.checks.lone_keeper,
          }}
          quotes={quoteList}
          quotesSource={quotes.state === "ok" ? "video_quotes.json (matched text and dates)" : undefined}
        />
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

      {takeover.state === "missing" ? (
        <section>
          <NotComputed file={takeover.file} />
        </section>
      ) : (
        <Gauge
          cost={takeover.state === "ok" ? takeover.data.takeover_cost : undefined}
          guardians={takeover.state === "ok" ? takeover.data.guardians : undefined}
          path={null}
          source="xz_takeover_status.json (org xz; the public history has no grant record)"
        />
      )}
      <Gauge
        cost={tallowLast?.checks.takeover_cost}
        guardians={tallowLast?.checks.guardians}
        path={null}
        synthetic
        source={`tallowdate_detector_status.json, latest quarter ${tallowLast?.quarter ?? "(file missing)"}`}
      />

      <TwoEndings xz={lanesXz} tallowdate={lanesTallow} />

      {gaps.state === "ok" && events.state === "ok" ? (
        <WhoSaw gaps={gaps.data} events={events.data} />
      ) : (
        <section aria-label="Who saw what">
          <h2>Who saw what</h2>
          <NotComputed file={gaps.state === "missing" ? gaps.file : events.state === "missing" ? events.file : "ecosystem files"} />
        </section>
      )}

      {trust.state === "ok" ? (
        <TrustMap doc={trust.data} />
      ) : (
        <section aria-label="Trust map">
          <h2>
            Trust map <SyntheticTag />
          </h2>
          <NotComputed file="trust_map_tallowdate.json" what="run eval.trust_map_export" />
        </section>
      )}

      <Hardening
        xz={hardening.state === "ok" ? hardening.data : undefined}
        fixture={fixture.state === "ok" ? fixture.data : undefined}
      />

      <Patience present={ablation.state === "ok"} />
    </main>
  );
}

function PackagerPage() {
  const gaps = useResult<GapsDoc>("ecosystem_gaps.json");
  return (
    <>
      <Header hash="#/packager" />
      <main>
        <Packager gaps={gaps.state === "ok" ? gaps.data : undefined} file="ecosystem_gaps.json" />
      </main>
    </>
  );
}

export default function App() {
  const hash = window.location.hash || "#/";
  if (hash.startsWith("#/connect")) {
    return (
      <>
        <Header hash="#/connect" />
        <main>
          <ConnectRepo />
        </main>
      </>
    );
  }
  if (hash.startsWith("#/packager")) return <PackagerPage />;
  if (hash.startsWith("#/playbook")) {
    return (
      <>
        <Header hash="#/playbook" />
        <main>
          <Playbook />
        </main>
      </>
    );
  }
  return (
    <>
      <Header hash={hash} />
      <ResultsPage />
    </>
  );
}
