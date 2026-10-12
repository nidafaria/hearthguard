import { computed, NOT_COMPUTED, quarterOf, Status } from "./data";

// Evidence card (spec 13.5). The four moves plus Lone keeper, as a checklist. An item turns green only
// when a saved result computed it. Quotes appear only when a saved file holds one for this quarter,
// with the file it was matched in. Skeptic objections and requests have no saved result, so they are
// NOT COMPUTED here.

export type Query = { name: string; query: string; params?: Record<string, unknown>; ms?: number; rows?: number };
export type Check = { status: string; reason?: string | null; queries?: Query[]; query_ms?: number | null };
export type Quote = { text: string; message_date_utc: string | null; file: string; status: string };

const ITEMS: Array<[string, string]> = [
  ["pressure", "Pressure"],
  ["vouch", "Vouch"],
  ["rush", "Rush"],
  ["bypass", "Bypass"],
  ["lone_keeper", "Lone keeper"],
];

export function quotesForQuarter(quotes: Quote[], quarter: string): Quote[] {
  return quotes.filter((q) => q.message_date_utc != null && quarterOf(q.message_date_utc) === quarter && q.status === "FOUND");
}

export function EvidenceCard({
  quarter,
  checks,
  quotes,
  quotesSource,
}: {
  quarter: string;
  checks: Partial<Record<string, Check | undefined>>;
  quotes?: Quote[];
  quotesSource?: string;
}) {
  const inQuarter = quotes ? quotesForQuarter(quotes, quarter) : [];
  return (
    <section aria-label="Evidence card">
      <h2>Evidence card, {quarter}</h2>
      <ol className="checklist">
        {ITEMS.map(([k, label]) => {
          const c = checks[k];
          const ok = !!c && computed(c.status);
          return (
            <li key={k} className={ok ? "done" : "todo"} data-computed={ok ? "yes" : "no"}>
              <span className={ok ? "tick ok" : "tick"} aria-hidden="true">
                {ok ? "✓" : "○"}
              </span>{" "}
              <b>{label}</b> <Status s={c ? c.status : NOT_COMPUTED} />
              <div className="muted">{c?.reason ?? "no saved result for this quarter"}</div>
              {c?.queries?.map((q, i) => (
                <details key={i}>
                  <summary>
                    query {q.name}
                    {q.ms != null ? `, ${q.ms.toFixed(1)} ms` : ""}
                    {q.rows != null ? `, ${q.rows} rows` : ""}
                  </summary>
                  <pre>{q.query}</pre>
                </details>
              ))}
            </li>
          );
        })}
      </ol>
      <h3>Quotes</h3>
      {quotes === undefined ? (
        <p className="NOT_COMPUTED tag">NOT COMPUTED: no saved quote file was found.</p>
      ) : inQuarter.length === 0 ? (
        <p className="NOT_COMPUTED tag">NOT COMPUTED: no saved quote is dated in {quarter}.</p>
      ) : (
        <ul>
          {inQuarter.map((q, i) => (
            <li key={i}>
              <q>{q.text}</q> <span className="muted">{q.message_date_utc}</span>
              <div className="muted">
                matched in {q.file} (no link: the saved record carries a file path, not a URL)
              </div>
            </li>
          ))}
        </ul>
      )}
      {quotesSource && <p className="muted">Quotes source: {quotesSource}</p>}
      <h3>Skeptic objections and requests</h3>
      <p className="NOT_COMPUTED tag">{NOT_COMPUTED}: the Skeptic is not built; no saved result holds one.</p>
      <p className="muted">Checklist items computed: {ITEMS.filter(([k]) => computed(checks[k]?.status)).length} of {ITEMS.length}.</p>
    </section>
  );
}
