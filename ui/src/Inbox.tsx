// The local inbox: a list of notes, the note itself, and its "Show me why" page. Reads /api only.
// Not connected to Slack. Nothing is sent. Every screen shows its data label.
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Thread } from "./Thread";

const LABEL = "Public record: xz project git history (org_xz). Synthetic data: none on this screen.";

type NoteItem = { quarter: string; decision: string; headline: string; dismissed: boolean };
type NotesList = { label: string; provisional: boolean; notes: NoteItem[] };
type Dismissal = { quarter: string; decision: string; reason: string; at_utc: string };
type NoteDetail = { label: string; quarter: string; decision: string; note: string; dismissal: Dismissal | null };
type Query = { name: string; query: string; rows: number; ms: number };
type Fact = { fact: string; status: string; reason: string; file: string; queries: Query[] };
type Why = { label: string; quarter: string; decision: string; rule: string; facts: Fact[]; text: string };
type Simulate = { available: boolean; reason: string; source: string; result: unknown };

type Route = { name: "list" } | { name: "note"; quarter: string } | { name: "why"; quarter: string };

export function parseRoute(hash: string): Route {
  const m = hash.match(/^#\/inbox(?:\/(\d{4}-Q[1-4])(\/why)?)?$/);
  if (!m || !m[1]) return { name: "list" };
  return m[2] ? { name: "why", quarter: m[1] } : { name: "note", quarter: m[1] };
}

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  const body = await r.json();
  if (!r.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `request failed (HTTP ${r.status})`;
    throw new Error(detail);
  }
  return body as T;
}

function useLoad<T>(url: string | null): { data: T | null; error: string | null } {
  const [state, setState] = useState<{ data: T | null; error: string | null }>({ data: null, error: null });
  useEffect(() => {
    if (url === null) return;
    let live = true;
    setState({ data: null, error: null });
    getJson<T>(url)
      .then((data) => live && setState({ data, error: null }))
      .catch((e: Error) => live && setState({ data: null, error: e.message }));
    return () => {
      live = false;
    };
  }, [url]);
  return state;
}

// Shows **bold** and `code` from the note text. Anything else is plain text.
function Rich({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((p, i) => {
        if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
        if (p.startsWith("`") && p.endsWith("`")) return <code key={i}>{p.slice(1, -1)}</code>;
        return <span key={i}>{p}</span>;
      })}
    </>
  );
}

function Frame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main>
      <p className="banner">
        <strong>Local inbox.</strong> Not connected to Slack. Nothing is sent. <br />
        <span className="sub">{LABEL}</span>
      </p>
      <h1>{title}</h1>
      {children}
      <p className="sub">
        <a href="#/inbox">Back to the inbox</a>
      </p>
    </main>
  );
}

function ListScreen() {
  const { data, error } = useLoad<NotesList>("/api/notes");
  return (
    <Frame title="Inbox">
      <section>
        {error && <p className="NOT_COMPUTED tag">Could not load notes: {error}</p>}
        {data && (
          <>
            {data.provisional && <p className="sub">Provisional: the decision policy is not final.</p>}
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>Quarter</th>
                    <th>Decision</th>
                    <th>Note</th>
                    <th>Dismissed</th>
                  </tr>
                </thead>
                <tbody>
                  {data.notes.map((n) => (
                    <tr key={n.quarter}>
                      <td>
                        <a href={`#/inbox/${n.quarter}`}>{n.quarter}</a>
                      </td>
                      <td>
                        <span className={`tag ${n.decision}`}>{n.decision === "HOLD" ? "Held" : n.decision}</span>
                      </td>
                      <td style={{ whiteSpace: "normal" }}>
                        <Rich text={n.headline} />
                      </td>
                      <td>{n.dismissed ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </Frame>
  );
}

function SimulatePanel({ quarter }: { quarter: string }) {
  const [sim, setSim] = useState<Simulate | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function run() {
    setError(null);
    try {
      setSim(await getJson<Simulate>(`/api/notes/${quarter}/simulate`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div>
      <button type="button" onClick={run}>
        Simulate a fix
      </button>
      {error && <p className="NOT_COMPUTED tag">{error}</p>}
      {sim && !sim.available && (
        <p>
          <span className="tag NOT_COMPUTED">NOT COMPUTED</span> {sim.reason}
        </p>
      )}
      {sim && sim.available && (
        <>
          <p className="sub">{sim.reason}</p>
          <pre>{JSON.stringify(sim.result, null, 2)}</pre>
        </>
      )}
    </div>
  );
}

function DismissForm({ quarter, onDone }: { quarter: string; onDone: (d: Dismissal) => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await getJson<{ dismissal: Dismissal }>(`/api/notes/${quarter}/dismiss`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      onDone(r.dismissal);
    } catch (err) {
      setError((err as Error).message || "The reason must be 3 to 500 characters.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <label>
        Reason (saved to a local file only)
        <br />
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} cols={60} maxLength={500} />
      </label>
      <br />
      <button type="submit" disabled={busy}>
        Dismiss with reason
      </button>
      {error && <p className="NOT_COMPUTED tag">{error}</p>}
    </form>
  );
}

function NoteScreen({ quarter }: { quarter: string }) {
  const { data, error } = useLoad<NoteDetail>(`/api/notes/${quarter}`);
  const [dismissal, setDismissal] = useState<Dismissal | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (data) {
      setDismissal(data.dismissal);
      setLoaded(true);
    }
  }, [data]);
  return (
    <Frame title={`Note: ${quarter}`}>
      {error && <p className="NOT_COMPUTED tag">Could not load this note: {error}</p>}
      {data && loaded && (
        <>
          <section>
            <p>
              <span className={`tag ${data.decision}`}>{data.decision === "HOLD" ? "Held" : data.decision}</span>
            </p>
            {data.note.split("\n").map((line, i) => (
              <p key={i} style={{ margin: "0 0 6px" }}>
                <Rich text={line} />
              </p>
            ))}
            <p>
              <a className="button" href={`#/inbox/${quarter}/why`}>
                Show me why
              </a>
            </p>
          </section>
          <section>
            <h2>Simulate a fix</h2>
            <SimulatePanel quarter={quarter} />
          </section>
          <section>
            <h2>Dismiss with reason</h2>
            {dismissal ? (
              <p>
                Dismissed {dismissal.at_utc}: {dismissal.reason}
              </p>
            ) : (
              <DismissForm quarter={quarter} onDone={setDismissal} />
            )}
          </section>
          <Thread caseId="xz" quarter={quarter} />
        </>
      )}
    </Frame>
  );
}

function WhyScreen({ quarter }: { quarter: string }) {
  const { data, error } = useLoad<Why>(`/api/notes/${quarter}/why`);
  return (
    <Frame title={`Show me why: ${quarter}`}>
      {error && <p className="NOT_COMPUTED tag">Could not load: {error}</p>}
      {data && (
        <>
          <section>
            <p>
              Decision <strong>{data.decision}</strong>. Rule: <code>{data.rule}</code>
            </p>
            <p className="sub">Every fact below is read from a saved status file. Nothing is re-run.</p>
          </section>
          {data.facts.map((f, i) => (
            <section key={f.fact}>
              <h2>
                {i + 1}. {f.fact.replace("_", " ")}: <span className={`tag ${f.status.replace(" ", "_")}`}>{f.status}</span>
              </h2>
              <p>{f.reason}</p>
              <p className="sub">File: {f.file}</p>
              {f.queries.length === 0 && <p className="sub">No query recorded in the saved file.</p>}
              {f.queries.map((q) => (
                <div key={q.name}>
                  <p className="sub">
                    Query {q.name}: {q.rows} rows, {q.ms.toFixed(1)} ms
                  </p>
                  <pre>{q.query}</pre>
                </div>
              ))}
            </section>
          ))}
          <p className="sub">Only the saved wording is shown. Nothing here judges a person.</p>
          <p>
            <a href={`#/inbox/${quarter}`}>Back to the note</a>
          </p>
        </>
      )}
    </Frame>
  );
}

export default function Inbox({ hash }: { hash: string }) {
  const route = parseRoute(hash);
  if (route.name === "why") return <WhyScreen quarter={route.quarter} />;
  if (route.name === "note") return <NoteScreen quarter={route.quarter} />;
  return <ListScreen />;
}
