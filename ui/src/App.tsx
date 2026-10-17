import { useState } from "react";
import { ConnectRepo, type ConnectResult } from "./ConnectRepo";
import { Gauge, type CostCell } from "./Gauge";
import { Hardening, type FixtureHardening, type XzHardening } from "./Hardening";
import { Blank, Fig, NotComputed, NOT_COMPUTED, PlateHead, Status, SyntheticTag, WORD, norm, useResult } from "./data";
import { EvidenceCard, type Check, type Query, type Quote } from "./EvidenceCard";
import { Packager } from "./Packager";
import { Playbook } from "./Playbook";
import { Census } from "./Census";
import { Patience, ABLATION_FILE } from "./Patience";
import { ReplayChart } from "./ReplayChart";
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
type PvRow = {
  quarter: string;
  pressure: Check;
  vouch: Check;
  window_coverage?: { pressure?: { read: number; messages_in_window: number } };
};
type QsRow = { quarter: string; checks: Record<string, Check & { value?: number | null }> };
type TallowDetector = { quarters: Array<{ quarter: string; checks: Record<string, CostCell> }> };
type TallowDecision = { quarters: Array<{ quarter: string; decision: string; hold_reason?: string | null }> };
type VideoQuotes = { quotes: Record<string, Quote> };

const SCREENS = ["#/connect", "#/packager", "#/playbook", "#/census"];

// Paper / Night, as in the demo header. The choice is kept in this browser only.
function ThemeSwitch() {
  const toggle = () => {
    const r = document.documentElement;
    r.dataset.theme = r.dataset.theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("hg-theme", r.dataset.theme);
    } catch (_) {
      /* not kept: the switch still works for this page */
    }
  };
  return (
    <button type="button" className="theme" onClick={toggle} aria-label="Switch paper or night">
      Paper / Night
    </button>
  );
}

export function Header({ hash }: { hash: string }) {
  const nav: Array<[string, string]> = [
    ["#/", "Results"],
    ["#/connect", "Connect your repo"],
    ["#/packager", "Packager question"],
    ["#/inbox", "Inbox (local)"],
    ["#/playbook", "Playbook"],
    ["#/census", "Census"],
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
        <ThemeSwitch />
      </nav>
    </header>
  );
}

const COLS: Array<[string, string]> = [
  ["pressure", "Pressure"],
  ["vouch", "Vouch"],
  ["rush", "Rush"],
  ["bypass", "Bypass"],
  ["lone_keeper", "Lone keeper"],
];

// The replay as a quarter strip: one cell per quarter-end, the five checks as marks, the Pressure window as
// a field of message squares (filled if read), and the decision stamp. Click a cell for its detail below.
function QuarterStrip({
  replay,
  pressure,
  sel,
  onSel,
}: {
  replay: Replay;
  pressure: { quarters: PvRow[] } | undefined;
  sel: string;
  onSel: (q: string) => void;
}) {
  const windowOf = (q: string) => pressure?.quarters.find((p) => p.quarter === q)?.window_coverage?.pressure;
  return (
    <div
      className="qrow"
      role="group"
      aria-label="Replay quarter strip"
      style={{ gridTemplateColumns: `repeat(${replay.quarters.length}, minmax(0, 1fr))` }}
    >
      {replay.quarters.map((r) => {
        const w = windowOf(r.quarter);
        const n = Math.min(w?.messages_in_window ?? 0, 300);
        return (
          <button
            type="button"
            key={r.quarter}
            className="qc"
            aria-pressed={r.quarter === sel}
            onClick={() => onSel(r.quarter)}
          >
            <span className="qq">{r.quarter}</span>
            <span className="mk">
              {COLS.map(([k, label]) => (
                <span key={k} style={{ display: "contents" }}>
                  <span className="lab">{label}</span>
                  <Status s={r.checks[k]?.status ?? NOT_COMPUTED} />
                </span>
              ))}
            </span>
            {w && (
              <>
                <span className="lab">
                  Pressure window · {w.read}/{w.messages_in_window} read
                </span>
                <span className="dots" title={`${w.read} of ${w.messages_in_window} read`}>
                  {Array.from({ length: n }, (_, k) => (
                    <i key={k} className={k < w.read ? "r" : ""} />
                  ))}
                </span>
              </>
            )}
            <span className="stamp">{WORD[r.decision.type] ?? r.decision.type}</span>
          </button>
        );
      })}
    </div>
  );
}

// The three stat cells under the plate head. Counts and sums are over the saved rows; nothing else is derived.
function ReplayFigures({ replay, pressure }: { replay: Replay; pressure: { quarters: PvRow[] } | undefined }) {
  const cov = replay.reader_coverage;
  const held = replay.quarters.filter((q) => q.decision.type === "HOLD").length;
  const win = pressure?.quarters.map((q) => q.window_coverage?.pressure);
  const read = win?.reduce((a, w) => a + (w?.read ?? 0), 0);
  const total = win?.reduce((a, w) => a + (w?.messages_in_window ?? 0), 0);
  return (
    <div className="row">
      <Fig cls="s4" label="Quarters held" value={held} of={replay.quarters.length} src="xz_replay.json" />
      {pressure ? (
        <Fig
          cls="s4"
          label="Pressure-window messages read"
          signal
          value={read}
          of={total}
          caption={`Summed over all ${replay.quarters.length} quarters. Pressure "did not fire" every time, without reading a single message in its window.`}
          src="pressure_vouch_status.json"
        />
      ) : (
        <Blank cls="s4" name="Pressure-window messages read" reason="pressure_vouch_status.json not found" />
      )}
      <Fig
        cls="s4"
        label="Messages the Reader has read"
        value={cov.read_so_far}
        of={cov.to_read}
        caption={`${cov.excluded_human_labelled_test_set} more are held back for the human-labelled test set.`}
        src="xz_replay.json"
      />
    </div>
  );
}

// The saved normal per quarter: cadence, active keepers, usual path, unread messages, decision.
function ReplayTable({ replay, onSel }: { replay: Replay; onSel: (q: string) => void }) {
  const num = (c: Cell | undefined, digits?: number) =>
    c && c.value != null ? (typeof c.value === "number" && digits != null ? c.value.toFixed(digits) : String(c.value)) : NOT_COMPUTED;
  return (
    <div className="scroll">
      <table className="tbl">
        <thead>
          <tr>
            <th>Quarter</th>
            <th>Commit cadence, median days</th>
            <th>Active keepers</th>
            <th>Usual path</th>
            <th>Unread, 120 days</th>
            <th>Decision</th>
          </tr>
        </thead>
        <tbody>
          {replay.quarters.map((r) => (
            <tr key={r.quarter} onClick={() => onSel(r.quarter)}>
              <td className="n">{r.quarter}</td>
              <td className="n">{num(r.normal.cadence_days, 4)}</td>
              <td className="n">{num(r.normal.active_keepers)}</td>
              <td className="n">{num(r.normal.usual_path)}</td>
              <td className="n">{r.reader_unread_in_pressure_window}</td>
              <td>
                <span className={`tag ${norm(r.decision.type)}`}>{WORD[r.decision.type] ?? r.decision.type}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
  // The quarter on show: the reader's pick, or the last quarter the replay file holds.
  const [picked, setPicked] = useState<string | null>(null);
  const sel = picked ?? (replay.state === "ok" ? (replay.data.quarters[replay.data.quarters.length - 1]?.quarter ?? "") : "");
  const setSel = setPicked;

  const pvRow = pv.state === "ok" ? pv.data.quarters.find((q) => q.quarter === sel) : undefined;
  const qsRow = qs.state === "ok" ? qs.data.quarters.find((q) => q.quarter === sel) : undefined;
  const row = replay.state === "ok" ? replay.data.quarters.find((r) => r.quarter === sel) : undefined;

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

  const lastQ = replay.state === "ok" ? replay.data.quarters[replay.data.quarters.length - 1] : undefined;

  return (
    <main>
      <PlateHead
        n="01"
        title={
          replay.state === "ok"
            ? `${replay.data.quarters.length} quarters. ${replay.data.quarters.filter((q) => q.decision.type === "HOLD").length} holds.`
            : "The xz replay."
        }
        italic={
          replay.state === "ok"
            ? replay.data.quarters.every((q) => q.decision.type === "HOLD")
              ? "Not one all-clear."
              : undefined
            : "Not computed."
        }
        lede={
          <>
            Each cell is the xz record as it stood at a quarter&apos;s end.{" "}
            <b>Held means a check could not run, not that the quarter was clear.</b> The squares are the messages in
            Pressure&apos;s 120-day window: filled if read, hollow if not.
          </>
        }
        kind="pub"
        tagLabel="Public record (xz)"
        plate="The replay"
        data="Public record (xz)"
        sources={["xz_replay.json", "pressure_vouch_status.json"]}
      />

      {replay.state === "loading" && <p>Loading…</p>}
      {replay.state === "missing" && (
        <section>
          <NotComputed file={replay.file} />
        </section>
      )}
      {replay.state === "ok" && (
        <>
          <ReplayFigures replay={replay.data} pressure={pv.state === "ok" ? pv.data : undefined} />
          <QuarterStrip replay={replay.data} pressure={pv.state === "ok" ? pv.data : undefined} sel={sel} onSel={setSel} />
          <ReplayChart quarters={replay.data.quarters} />
          <div className="row">
            {["rush", "bypass", "lone_keeper", "takeover_cost"]
              .filter((k) => lastQ && norm(lastQ.checks[k]?.status) === NOT_COMPUTED)
              .map((k) => (
                <Blank
                  key={k}
                  cls="s3"
                  name={k === "takeover_cost" ? "Takeover cost" : (COLS.find(([c]) => c === k)?.[1] ?? k)}
                  reason={lastQ?.checks[k]?.reason}
                  src={lastQ?.checks[k]?.source}
                />
              ))}
          </div>
          <ReplayTable replay={replay.data} onSel={setSel} />
          <div className="row">
            <div className="c s12">
              <p className="fine">
                Data on this page: the public xz git history and the public xz-devel mailing list, hashed on ingest.
                The tallowdate panels are labelled SYNTHETIC. Hand-built fixtures appear only where labelled.
                {!replay.data.reader_coverage.complete &&
                  ` Reader coverage is incomplete: ${replay.data.reader_coverage.read_so_far} of ${replay.data.reader_coverage.to_read} messages read. A NOT_FIRED here is a result on the messages read only.`}
              </p>
            </div>
          </div>
        </>
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

// The saved run of the connect flow fills the screen until a live run replaces it.
function ConnectPage() {
  const saved = useResult<ConnectResult>("connect_repo_run.json");
  return <ConnectRepo saved={saved.state === "ok" ? saved.data : undefined} />;
}

export default function App() {
  const hash = window.location.hash || "#/";
  if (hash.startsWith("#/connect")) {
    return (
      <>
        <Header hash="#/connect" />
        <main>
          <ConnectPage />
        </main>
      </>
    );
  }
  if (hash.startsWith("#/packager")) return <PackagerPage />;
  if (hash.startsWith("#/census")) {
    return (
      <>
        <Header hash="#/census" />
        <main>
          <Census present />
        </main>
      </>
    );
  }
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
