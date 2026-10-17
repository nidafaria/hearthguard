import { useEffect, useState } from "react";

// The playbook (spec 13.10): learned exceptions in their four states, with their regression
// results. Read from /api/inbox/playbook. Holds no organisation data. Nothing here is applied to
// a live decision yet; the owner can approve a Shadow exception, and that is all.

type Gate = {
  passed: boolean;
  reason: string;
  planted_total: number;
  planted_caught_before: number;
  planted_caught_after: number;
  planted_lost: number;
  planted_points_changed: number;
  real_total: number;
  real_lost: number;
};
type Exception = {
  id: string;
  exception: string;
  applies_to: string;
  when: string;
  effect: string;
  state: string;
  state_reason: string;
  agreements: number;
  gate: Gate | null;
  owner_approved_at?: number;
};
type PlaybookDoc = {
  graph: string;
  spec_hashes: string[];
  exceptions: Exception[];
  states: string[];
  data_kind: string;
};

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  const body = await r.json();
  if (!r.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `request failed (HTTP ${r.status})`;
    throw new Error(detail);
  }
  return body as T;
}

export function Playbook() {
  const [doc, setDoc] = useState<PlaybookDoc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setDoc(await call<PlaybookDoc>("/api/inbox/playbook"));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function approve(id: string) {
    if (busy) return;
    setBusy(true);
    try {
      await call(`/api/inbox/playbook/${id}/approve`, { method: "POST" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !doc) return <section><h2>Playbook</h2><p className="NOT_COMPUTED tag">{error}</p></section>;
  if (!doc) return <section><h2>Playbook</h2><p>Loading the playbook…</p></section>;

  return (
    <section>
      <h2>Playbook</h2>
      <p>
        Learned exceptions, in four states. Shadow records what it would have suppressed and acts on
        nothing. Nothing is applied to a live decision yet. The playbook holds no organisation data.
      </p>
      <p className="sub">
        Detector spec: {doc.spec_hashes.length ? doc.spec_hashes.map((h) => h.slice(0, 12)).join(", ") : "not recorded yet"}
      </p>
      {error ? <p className="NOT_COMPUTED tag">{error}</p> : null}
      {doc.exceptions.length === 0 ? (
        <p>No learned exceptions yet. Dismiss a note with a reason in the Inbox to propose one.</p>
      ) : (
        <div className="steps">
          {doc.exceptions.map((x) => (
            <div className="step" key={x.id}>
              <div className="step-head">
                <span className="step-name">{x.exception}</span>
                <b>{x.state}</b>
                <small>{x.state_reason}</small>
              </div>
              <div className="step-body">
                <p>
                  <span className="lab">Narrows</span> {x.applies_to}
                </p>
                <p>
                  <span className="lab">When</span> <code>{x.when}</code>
                </p>
                <p>
                  <span className="lab">Regression gate</span>{" "}
                  {x.gate ? (
                    <small>
                      {x.gate.planted_total} planted attacks: {x.gate.planted_caught_before} caught before, {" "}
                      {x.gate.planted_caught_after} after, {x.gate.planted_lost} lost. Real cases: {x.gate.real_lost} lost
                      of {x.gate.real_total}. Would change {x.gate.planted_points_changed} planted decision points.
                    </small>
                  ) : (
                    <small>not run</small>
                  )}
                </p>
                <p>
                  <span className="lab">Agreements</span> {x.agreements}
                </p>
                {x.state === "Shadow" ? (
                  <button type="button" disabled={busy} onClick={() => approve(x.id)}>
                    Approve
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="sub">States: {doc.states.join(" · ")}. Data: {doc.data_kind}.</p>
    </section>
  );
}
