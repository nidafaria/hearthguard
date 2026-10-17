import { useEffect, useState } from "react";
import { Fig, PlateHead, PlateNext, useResult } from "./data";

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

  const head = (
    <PlateHead
      n="14"
      title="It learns from “no”."
      italic="Only after proving it hides nothing."
      lede="An owner dismissed a note on the fictional project. Hearthguard turned that dismissal into a proposed exception, then replayed every planted attack and every real case against it before keeping anything."
      kind="syn"
      tagLabel="Synthetic (tallowdate)"
      plate="The playbook"
      data="Synthetic (tallowdate)"
      sources={["learning_verify.json", "/api/inbox/playbook"]}
    />
  );
  const next = <PlateNext line="And it all starts with any public repository." href="#/connect" n="15" title="Connect a repository" />;

  if (error && !doc)
    return (
      <>
        {head}
        <div className="row">
          <div className="c s12">
            <p className="NOT_COMPUTED tag">{error}</p>
          </div>
        </div>
        {next}
      </>
    );
  if (!doc)
    return (
      <>
        {head}
        <div className="row">
          <div className="c s12">
            <p>Loading the playbook…</p>
          </div>
        </div>
      </>
    );

  const shadow = doc.exceptions.filter((x) => x.state === "Shadow");
  return (
    <>
      {head}
      <LearningSteps file="learning_verify.json" />
      <div className="row">
        <div className="c s12">
          <div className="lab br">Learned exceptions in the playbook</div>
          <p className="lede" style={{ marginTop: 14 }}>
            Learned exceptions, in four states. Shadow records what it would have suppressed and acts on nothing.
            Nothing is applied to a live decision yet. The playbook holds no organisation data.
          </p>
          {error ? <p className="NOT_COMPUTED tag">{error}</p> : null}
          {doc.exceptions.length === 0 && (
            <p style={{ marginTop: 14 }}>No learned exceptions yet. Dismiss a note with a reason in the Inbox to propose one.</p>
          )}
        </div>
      </div>
      {doc.exceptions.length > 0 && (
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
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="row">
        <div className="c s4">
          {shadow.length === 0 ? (
            <button type="button" className="btn" disabled>
              <span>Approve</span>
              <span>·</span>
            </button>
          ) : (
            shadow.map((x) => (
              <button type="button" className="btn solid" key={x.id} disabled={busy} onClick={() => approve(x.id)}>
                <span>Approve</span>
                <span>→</span>
              </button>
            ))
          )}
        </div>
        <div className="c s8" style={{ display: "flex", alignItems: "center" }}>
          <span className="mono" style={{ fontSize: "12.5px" }}>
            Approval runs only against the local server.
          </span>
        </div>
      </div>
      <div className="row">
        <div className="c s12">
          <p className="fine">
            Detector spec: {doc.spec_hashes.length ? doc.spec_hashes.map((h) => h.slice(0, 12)).join(", ") : "not recorded yet"}.
            States: {doc.states.join(" · ")}. Data: {doc.data_kind}.
          </p>
        </div>
      </div>
      {next}
    </>
  );
}

type LearningVerify = {
  not_applied?: string;
  steps?: {
    dismissal?: { case: string; quarter: string; reason: string };
    proposal?: { template: { applies_to: string; effect: string; exception: string; when: string } };
    safety?: { rules: string[]; violations: string[] };
    gate?: {
      planted_total: number;
      planted_caught_before: number;
      planted_caught_after: number;
      planted_lost: number;
      real_total: number;
      real_lost: number;
      reason: string;
    };
    end_state?: { state: string; reason: string };
  };
};

function StepRow({ n, title, signal, lines, dim, on }: { n: string; title: string; signal?: boolean; lines: string[]; dim?: string[]; on?: boolean }) {
  return (
    <div className={`step-row ${on ? "on" : ""}`}>
      <span className="lab">{n}</span>
      <span className="big-t" style={signal ? { color: "var(--signal)" } : undefined}>
        {title}
      </span>
      <span className="detail">
        {lines.map((l, i) => (
          <span key={i}>
            {i > 0 && <br />}
            {l}
          </span>
        ))}
        {dim?.map((l, i) => (
          <span key={i} className="g">
            <br />
            {l}
          </span>
        ))}
      </span>
    </div>
  );
}

// The learning gate as saved by the verification run: the two figures, then the five steps.
function LearningSteps({ file }: { file: string }) {
  const r = useResult<LearningVerify>(file);
  if (r.state !== "ok") return null;
  const L = r.data;
  const s = L.steps;
  const g = s?.gate;
  if (!s || !g) return null;
  return (
    <>
      <div className="row">
        <Fig
          cls="s6"
          syn
          signal
          label="Planted attacks lost to the new rule"
          value={g.planted_lost}
          of={g.planted_total}
          src={file}
        />
        <Fig cls="s6" syn label="Real-case points lost" value={g.real_lost} of={g.real_total} src={file} />
      </div>
      {s.dismissal && (
        <StepRow n="01 · Dismissed" title={`“${s.dismissal.reason}”`} lines={[`${s.dismissal.case}, ${s.dismissal.quarter}`]} />
      )}
      {s.proposal && (
        <StepRow
          n="02 · Proposed"
          title={s.proposal.template.exception.replace(/_/g, " ")}
          lines={[`${s.proposal.template.applies_to} · ${s.proposal.template.effect}`]}
          dim={[s.proposal.template.when]}
        />
      )}
      {s.safety && (
        <StepRow
          n="03 · Safety rules"
          title={`${s.safety.rules.length} rules, ${s.safety.violations.length} broken`}
          lines={s.safety.rules}
        />
      )}
      <StepRow
        n="04 · Regression gate"
        title={`${g.planted_caught_before} caught before. ${g.planted_caught_after} after.`}
        lines={[g.reason]}
      />
      {s.end_state && (
        <StepRow
          n="05 · End state"
          title={s.end_state.state}
          signal
          on
          lines={[s.end_state.reason]}
          dim={[`${L.not_applied ?? ""}${L.not_applied ? ". " : ""}Shadow records what it would have suppressed and acts on nothing.`]}
        />
      )}
    </>
  );
}
