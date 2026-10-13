// The note thread for one quarter, over /api/inbox. Local only: nothing is sent to Slack or anyone.
// Every control posts to the API and shows the reply. Each screen names its data (public or synthetic).
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

type CaseId = "xz" | "tallowdate";
type Head = { label: string; case: CaseId; data_kind: string; synthetic: boolean; sent_to_slack: boolean };
type Draft = { kind: string; text: string; sent_by_owner: boolean; at: number };
type Question = { question: string; answer: string; tool: string; refused: boolean; created_at: number };
type ThreadData = Head & {
  quarter: string;
  decision: string;
  as_of: string;
  note: string;
  finding: { id: string; status: string };
  snooze: { state: string; until: number | null; new_moves: string[] };
  routing: { recipients: string[]; thread: string; reason: string; waiting: boolean; nothing_is_sent: boolean };
  decisions: { text: string; at: number; authority: string; exception_id?: string | null; learning_state?: string | null; learning_reason?: string | null }[];
  drafts: Draft[];
  questions: Question[];
  suggested_questions: string[];
};
type Digest = Head & { headline: string; text: string; quiet: boolean; quarter: string; as_of: string };

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  const body = await r.json();
  if (!r.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `request failed (HTTP ${r.status})`;
    throw new Error(detail);
  }
  return body as T;
}

const post = (url: string, body?: unknown) =>
  call<unknown>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

function Box({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function ErrorLine({ error }: { error: string | null }) {
  return error ? <p className="NOT_COMPUTED tag">{error}</p> : null;
}

export function Thread({ caseId, quarter, onChange }: { caseId: CaseId; quarter: string; onChange?: () => void }) {
  const [data, setData] = useState<ThreadData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [out, setOut] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [question, setQuestion] = useState("");
  const [draftText, setDraftText] = useState("");
  const [learned, setLearned] = useState<string | null>(null);
  const base = `/api/inbox/${caseId}/notes/${quarter}`;

  async function load() {
    try {
      const t = await call<ThreadData>(base);
      setData(t);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    setData(null);
    setOut(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, quarter]);

  // Runs one control. A second press while the first is running does nothing.
  async function act(label: string, fn: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      setOut(`${label}: ${JSON.stringify(r, null, 2)}`);
      await load();
      onChange?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function submitDismiss(e: FormEvent) {
    e.preventDefault();
    await act("Dismiss with reason", async () => {
      const r = (await post(`${base}/dismiss`, { reason })) as {
        learning?: { state?: string; result_line?: string };
      };
      // The learning result goes in the thread, with its proof (spec 12.2).
      setLearned(r.learning?.result_line ? `${r.learning.state}: ${r.learning.result_line}` : null);
      return r;
    });
  }
  async function submitQuestion(e: FormEvent) {
    e.preventDefault();
    await act("Thread question", () => post(`${base}/ask`, { question }));
    setQuestion("");
  }

  if (error && !data) return <Box title="Thread"><ErrorLine error={error} /></Box>;
  if (!data) return <Box title="Thread"><p className="sub">Loading the thread…</p></Box>;

  const draft = data.drafts.find((d) => d.kind === "boundary_reply");
  return (
    <>
      <p className="banner">
        <strong>{data.synthetic ? "Synthetic demo" : "Public record"}.</strong> Local thread. Nothing is sent to
        Slack or anyone. <br />
        <span className="sub">{data.label}</span>
      </p>

      <Box title={`Note ${data.quarter} (${data.decision})`}>
        <pre>{data.note}</pre>
        <p className="sub">
          Routed to: {data.routing.recipients.join(", ")} ({data.routing.thread}). {data.routing.reason}
        </p>
        <p className="sub">
          Snooze: {data.snooze.state}
          {data.snooze.until ? ` until ${new Date(data.snooze.until * 1000).toISOString()}` : ""}
          {data.snooze.new_moves.length ? `, raised early for ${data.snooze.new_moves.join(", ")}` : ""}
        </p>
        <div className="controls">
          <button type="button" disabled={busy} onClick={() => act("Show me why", () => call(`${base}/why`))}>
            Show me why
          </button>{" "}
          <button type="button" disabled={busy} onClick={() => act("Simulate a fix", () => post(`${base}/simulate`))}>
            Simulate a fix
          </button>{" "}
          <button type="button" disabled={busy} onClick={() => act("Draft a reply", () => post(`${base}/draft`, { kind: "boundary_reply" }))}>
            Draft a reply
          </button>{" "}
          <button type="button" disabled={busy} onClick={() => act("Remind me in a week", () => post(`${base}/snooze`))}>
            Remind me in a week
          </button>
        </div>
      </Box>

      <Box title="Draft a reply">
        {draft ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act("Edit draft", () => fetch(`${base}/draft`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: "boundary_reply", text: draftText || draft.text }) }).then((r) => r.json()));
            }}
          >
            <textarea
              aria-label="Draft reply text"
              rows={4}
              cols={60}
              defaultValue={draft.text}
              onChange={(e) => setDraftText(e.target.value)}
              disabled={draft.sent_by_owner}
            />
            <br />
            <button type="submit" disabled={busy || draft.sent_by_owner}>Save edit</button>{" "}
            <button type="button" disabled={busy || draft.sent_by_owner} onClick={() => act("I sent it myself", () => post(`${base}/draft/sent`, { kind: "boundary_reply" }))}>
              I sent it myself
            </button>
            <p className="sub">{draft.sent_by_owner ? "Marked sent by you. The code sent nothing." : "Not sent. You send it yourself; the code contacts no one."}</p>
          </form>
        ) : (
          <p className="sub">No draft yet. Use Draft a reply above.</p>
        )}
      </Box>

      <Box title="Dismiss with reason">
        {data.finding.status === "dismissed" ? (
          <p>Dismissed. {data.decisions.map((d) => d.text).join(" / ")}</p>
        ) : (
          <form onSubmit={submitDismiss}>
            <textarea aria-label="Dismiss reason" rows={2} cols={60} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
            <br />
            <button type="submit" disabled={busy || reason.trim().length < 3}>Dismiss with reason</button>
          </form>
        )}
        {data.decisions.some((d) => d.learning_state) ? (
          <p className="sub">Learning: {data.decisions.map((d) => d.learning_state).filter(Boolean).join(" / ")}. Nothing is applied to a live decision.</p>
        ) : null}
        {learned ? <p>{learned}</p> : null}
      </Box>

      <Box title="Thread">
        {data.questions.length === 0 && <p className="sub">No questions yet.</p>}
        {data.questions.map((q, i) => (
          <div key={i} className="card">
            <p><strong>You:</strong> {q.question}</p>
            <pre>{q.answer}</pre>
            <p className="sub">Tool: {q.tool}{q.refused ? " (refused: no judgement of people)" : ""}</p>
          </div>
        ))}
        <form onSubmit={submitQuestion}>
          <input aria-label="Thread question" value={question} onChange={(e) => setQuestion(e.target.value)} size={60} maxLength={500} />{" "}
          <button type="submit" disabled={busy || question.trim().length < 3}>Ask</button>
        </form>
        <p className="sub">Try: {data.suggested_questions.join(" · ")}</p>
      </Box>

      {out && (
        <Box title="Last reply">
          <pre>{out}</pre>
        </Box>
      )}
      <ErrorLine error={error} />
      <DigestPanel caseId={caseId} />
    </>
  );
}

export function DigestPanel({ caseId }: { caseId: CaseId }) {
  const [d, setD] = useState<Digest | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function load() {
    try {
      setD(await call<Digest>(`/api/inbox/${caseId}/digest`));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <Box title="Weekly digest">
      <button type="button" onClick={load}>Show the digest</button>
      <ErrorLine error={error} />
      {d && (
        <>
          <p className="banner"><strong>{d.synthetic ? "Synthetic" : "Public record"}.</strong> {d.label}</p>
          <pre>{d.text}</pre>
          <p className="sub">{d.quiet ? "Quiet week." : "Not a quiet week."} Source: saved results. Nothing was sent.</p>
        </>
      )}
    </Box>
  );
}
