import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { computed, norm, NotComputed, NOT_COMPUTED } from "./data";
import { Timeline } from "./Timeline";
import { Gauge } from "./Gauge";
import { EvidenceCard, quotesForQuarter, type Quote } from "./EvidenceCard";
import { WhoSaw, type EventsDoc, type GapsDoc } from "./WhoSaw";
import { elementsOf, TrustMap, type TrustMapDoc } from "./TrustMap";
import { Hardening, type FixtureHardening, type XzHardening } from "./Hardening";
import { Patience, ABLATION_FILE } from "./Patience";
import { TwoEndings } from "./TwoEndings";
import { Packager } from "./Packager";
import { ConnectRepo } from "./ConnectRepo";
import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

// ---------------------------------------------------------------- fixtures (hand-written, labelled)

const timelineFull = [
  { quarter: "2023-Q1", moves: { pressure: "NOT_FIRED", vouch: "FIRED", rush: "NOT COMPUTED", bypass: "NOT_FIRED" }, takeover_cost: 1, decision: "HOLD" },
  { quarter: "2023-Q2", moves: { pressure: "FIRED", vouch: "NOT_FIRED", rush: "NOT_FIRED", bypass: "NOT_FIRED" }, takeover_cost: 2, decision: "NOTE" },
];
const timelineNotComputed = [
  { quarter: "2023-Q1", moves: {}, takeover_cost: null, decision: "HOLD" },
  { quarter: "2023-Q2", moves: {}, takeover_cost: null, decision: "HOLD" },
];

const gapsFull: GapsDoc = {
  decisions: [
    {
      decision: "debian-upgrade-request-bug1",
      place: "debian-bts",
      decision_at: "2024-03-20T18:00:00Z",
      deciding_role: "Debian package maintainer",
      decision_kind: "upgrade_request",
      status: "COMPUTED",
      gaps: [{ gap: "UNREACHABLE", signal: "ev-1", signal_kind: "pr_opened", signal_place: "xz-git", signal_at: "2024-03-01T00:00:00Z", label_confidence: "absence-of-evidence" }],
    },
    {
      decision: "lkml-entry",
      place: "lkml",
      decision_at: "2024-03-21T00:00:00Z",
      deciding_role: "Linux kernel reviewer",
      status: "NOT COMPUTED",
      reason: "no role watches lkml",
      gaps: [],
    },
  ],
};
const eventsFull: EventsDoc = {
  events: [
    { event_id: "ev-1", place: "xz-git", at: "2024-03-01T00:00:00Z", kind: "commit", actor_role: "contributor" },
    { event_id: "ev-2", place: "debian-bts", at: "2024-03-10T00:00:00Z", kind: "bug_filed", actor_role: "Debian package maintainer" },
  ],
};
const gapsNotComputed: GapsDoc = {
  decisions: [{ decision: "x", place: "lkml", decision_at: "2024-03-21T00:00:00Z", deciding_role: "Linux kernel reviewer", status: "NOT COMPUTED", reason: "no role watches lkml", gaps: [] }],
};

const trustFull: TrustMapDoc = {
  synthetic: true,
  label: "SYNTHETIC: fictional project, fictional people. Hashed actor ids. Not a finding.",
  graph: "org_tallowdate",
  nodes: [
    { id: "actor:aaaaaaaaaaaaaaaa", type: "actor", actions: 4 },
    { id: "release:v1", type: "release" },
  ],
  edges: [{ source: "actor:aaaaaaaaaaaaaaaa", target: "release:v1", type: "DID" }],
  trust_path: ["actor:aaaaaaaaaaaaaaaa", "release:v1"],
};
const trustNoPath: TrustMapDoc = { ...trustFull, trust_path: null, trust_path_note: "No trust path in the saved results." };

const hardeningXz: XzHardening = {
  org: "xz",
  provisional: true,
  red_team: "not run",
  results: [
    {
      quarter: "2024-Q1",
      steps: [
        { step: "add_second_keeper", applied: false, before: { takeover_cost: { status: "NOT COMPUTED", value: null }, guardians: { status: "NOT COMPUTED", value: null } }, after: { takeover_cost: { status: "NOT COMPUTED", value: null }, guardians: { status: "NOT COMPUTED", value: null } } },
      ],
    },
  ],
};
const hardeningFixture: FixtureHardening = {
  results: [{ fixture: "a_single_chain", step: "add_second_keeper", before: { cost: 1, cost_status: "COMPUTED", guardians: 1, guardians_status: "COMPUTED" }, after: { cost: 1, cost_status: "COMPUTED", guardians: 2, guardians_status: "COMPUTED" } }],
};

const quotesFull: Quote[] = [
  { text: "my resources are too limited", message_date_utc: "2024-01-15T10:00:00Z", file: "data/raw/mail/xz-devel/msg1.html", status: "FOUND" },
  { text: "from another quarter", message_date_utc: "2022-05-19T20:41:31Z", file: "data/raw/mail/xz-devel/msg2.html", status: "FOUND" },
];

const checksFull = {
  pressure: { status: "NOT_FIRED", reason: "0 claims", queries: [{ name: "read_claims", query: "MATCH (a) RETURN a", params: {}, ms: 2.1, rows: 0 }] },
  vouch: { status: "NOT_FIRED", reason: "no vouch" },
  rush: { status: "FIRED", reason: "rush fired" },
  bypass: { status: "NOT_FIRED", reason: "no bypass" },
  lone_keeper: { status: "NOT_COMPUTED", reason: "no grant" },
};
const checksNotComputed = {
  pressure: { status: "NOT COMPUTED", reason: "no data" },
  vouch: { status: "NOT COMPUTED", reason: "no data" },
  rush: { status: "NOT COMPUTED", reason: "no grant" },
  bypass: { status: "NOT COMPUTED", reason: "no grant" },
  lone_keeper: { status: "NOT COMPUTED", reason: "no grant" },
};

// ---------------------------------------------------------------- shared helpers

describe("status helpers", () => {
  it("treat NOT_COMPUTED and NOT COMPUTED as one value, and only computed statuses as computed", () => {
    expect(norm("NOT_COMPUTED")).toBe(NOT_COMPUTED);
    expect(norm(undefined)).toBe(NOT_COMPUTED);
    expect(computed("FIRED")).toBe(true);
    expect(computed("NOT_FIRED")).toBe(true);
    expect(computed("NOT_COMPUTED")).toBe(false);
    expect(computed(undefined)).toBe(false);
  });

  it("says the file name when a file is missing", () => {
    render(<NotComputed file="xz_replay.json" />);
    expect(screen.getByText(/xz_replay\.json not found/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------- Timeline (13.1)

describe("Timeline", () => {
  it("draws a takeover line only between quarters with a saved value, and labels the synthetic note", () => {
    const { container } = render(<Timeline quarters={timelineFull} source="fixture" noteSent={null} />);
    expect(container.querySelectorAll("circle").length).toBe(8);
    expect(container.querySelectorAll("polyline").length).toBe(1);
    expect(screen.getByText(/no saved file measures a send date/)).toBeTruthy();
  });

  it("draws the note-sent marker only when a saved file gives a date", () => {
    const { container } = render(
      <Timeline quarters={timelineFull} source="fixture" noteSent={{ at_utc: "2023-06-01T00:00:00Z", source: "file" }} />,
    );
    expect(container.querySelector("line[stroke-dasharray]")).toBeTruthy();
    expect(screen.getByText(/marker at 2023-06-01/)).toBeTruthy();
  });

  it("draws no line and says NOT COMPUTED when no quarter has a takeover value", () => {
    const { container } = render(<Timeline quarters={timelineNotComputed} source="fixture" />);
    expect(container.querySelectorAll("polyline").length).toBe(0);
    expect(screen.getByText(/NOT COMPUTED in every quarter/)).toBeTruthy();
    expect(screen.getByText(/this file carries no counts per quarter/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------- Gauge (13.3)

describe("Gauge", () => {
  it("shows the saved number, the guardians and the path when computed", () => {
    render(
      <Gauge cost={{ status: "COMPUTED", value: 2 }} guardians={{ status: "COMPUTED", value: 1 }} path={["a", "b"]} source="fixture" synthetic />,
    );
    expect(screen.getByLabelText("takeover cost value").textContent).toBe("2");
    expect(screen.getByText("a")).toBeTruthy();
    expect(screen.getByText("drawn on the trust map")).toBeTruthy();
  });

  it("shows NOT COMPUTED with the saved reason for real xz (no grant record)", () => {
    render(
      <Gauge
        cost={{ status: "NOT COMPUTED", value: null, reason: "no CAN_GRANT or Privilege data in org_xz" }}
        guardians={{ status: "NOT COMPUTED", value: null, reason: null }}
        path={null}
        source="fixture"
      />,
    );
    expect(screen.queryByLabelText("takeover cost value")).toBeNull();
    expect(screen.getByText(/no CAN_GRANT or Privilege data in org_xz/)).toBeTruthy();
    expect(screen.getAllByText(/NOT COMPUTED/).length).toBeGreaterThan(0);
  });

  it("says no saved result when the file is missing (no cost given)", () => {
    render(<Gauge cost={undefined} guardians={undefined} source="fixture" />);
    expect(screen.getByText("no saved takeover-cost result for this org")).toBeTruthy();
  });
});

// ---------------------------------------------------------------- EvidenceCard (13.5)

describe("EvidenceCard", () => {
  it("turns an item green only when a saved result computed it, and shows the query and time", () => {
    const { container } = render(<EvidenceCard quarter="2024-Q1" checks={checksFull} quotes={quotesFull} />);
    // pressure, vouch, rush and bypass have a computed status; lone keeper does not.
    expect(container.querySelectorAll('[data-computed="yes"]').length).toBe(4);
    expect(screen.getByText(/query read_claims, 2\.1 ms, 0 rows/)).toBeTruthy();
  });

  it("shows only quotes dated in the quarter, with the matched file and no invented link", () => {
    render(<EvidenceCard quarter="2024-Q1" checks={checksFull} quotes={quotesFull} />);
    expect(screen.getByText(/my resources are too limited/)).toBeTruthy();
    expect(screen.queryByText(/from another quarter/)).toBeNull();
    expect(screen.getByText(/no link: the saved record carries a file path/)).toBeTruthy();
    expect(quotesForQuarter(quotesFull, "2024-Q1").length).toBe(1);
  });

  it("says NOT COMPUTED for quotes when the quote file is missing, and for objections always", () => {
    render(<EvidenceCard quarter="2024-Q1" checks={checksFull} quotes={undefined} />);
    expect(screen.getByText(/no saved quote file was found/)).toBeTruthy();
    expect(screen.getByText(/the Skeptic is not built/)).toBeTruthy();
  });

  it("is all NOT COMPUTED when no check computed", () => {
    const { container } = render(<EvidenceCard quarter="2024-Q1" checks={checksNotComputed} quotes={[]} />);
    expect(container.querySelectorAll('[data-computed="yes"]').length).toBe(0);
    expect(screen.getByText(/no saved quote is dated in 2024-Q1/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------- WhoSaw (13.2)

describe("WhoSaw", () => {
  it("draws a dot per event, rings the computed gap, and names roles only", () => {
    const { container } = render(<WhoSaw gaps={gapsFull} events={eventsFull} />);
    expect(container.querySelectorAll("circle").length).toBe(2);
    expect(container.querySelector('circle[data-gap="yes"]')).toBeTruthy();
    expect(screen.getByText(/1 gap row\(s\) computed across 1 decision/)).toBeTruthy();
    expect(document.body.textContent).toContain("Debian package maintainer");
    expect(document.body.textContent).not.toMatch(/persona|public_handle|Jia/);
  });

  it("shows NOT COMPUTED decisions with their reason and draws no gap", () => {
    const { container } = render(<WhoSaw gaps={gapsNotComputed} events={eventsFull} />);
    expect(container.querySelector('circle[data-gap="yes"]')).toBeNull();
    expect(screen.getByText(/no role watches lkml/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------- TrustMap (13.4)

describe("TrustMap", () => {
  it("builds Cytoscape elements from hashed ids and highlights the saved path", () => {
    const els = elementsOf(trustFull);
    const onPath = els.filter((e) => (e.classes ?? "").includes("onpath"));
    expect(onPath.length).toBe(3); // both nodes and the edge between them
    expect(JSON.stringify(els)).not.toMatch(/@|persona|Mira|Tom|Rowan/);
  });

  it("says NOT COMPUTED and highlights nothing when the file holds no path", () => {
    const els = elementsOf(trustNoPath);
    expect(els.filter((e) => (e.classes ?? "").includes("onpath")).length).toBe(0);
    render(<TrustMap doc={trustNoPath} />);
    expect(screen.getByText(/no trust path in the saved file/)).toBeTruthy();
    expect(screen.getAllByText(/SYNTHETIC/).length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------- Hardening (13.6)

describe("Hardening", () => {
  it("shows the xz step with before and after, and the fixture rows", () => {
    render(<Hardening xz={hardeningXz} fixture={hardeningFixture} />);
    expect(screen.getAllByText("add_second_keeper").length).toBe(2); // xz row and fixture row
    expect(screen.getByText("a_single_chain")).toBeTruthy();
    expect(screen.getByText("1 → 1")).toBeTruthy();
  });

  it("names the missing files and leaves caught and lead time NOT COMPUTED", () => {
    render(<Hardening />);
    expect(screen.getByText(/xz_hardening\.json not found/)).toBeTruthy();
    expect(screen.getByText(/hardening_fixture\.json not found/)).toBeTruthy();
  });

  it("shows NOT COMPUTED for every xz cost, caught and lead time when the file says so", () => {
    render(<Hardening xz={hardeningXz} />);
    const row = screen.getAllByText("add_second_keeper")[0].closest("tr")!;
    expect(within(row).getAllByText(NOT_COMPUTED).length).toBeGreaterThanOrEqual(4);
  });
});

// ---------------------------------------------------------------- Patience (13.7)

describe("Patience", () => {
  it("is NOT COMPUTED with the blocker while ablation_memory.json is absent", () => {
    render(<Patience present={false} />);
    expect(screen.getByText(new RegExp(ABLATION_FILE.replace(".", "\\.")))).toBeTruthy();
    expect(screen.getByText(/Blocker: the memory ablation/)).toBeTruthy();
  });

  it("does not draw a curve from anything else when the file is present", () => {
    render(<Patience present />);
    expect(screen.getByText(/The chart is not drawn/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------- TwoEndings (13.12)

describe("TwoEndings", () => {
  it("puts both timelines on one quarter axis and labels the tallowdate lane SYNTHETIC", () => {
    render(
      <TwoEndings
        xz={[{ quarter: "2024-Q1", decision: "HOLD", takeover_cost: null }]}
        tallowdate={[{ quarter: "2023-Q4", decision: "HOLD" }, { quarter: "2024-Q1", decision: "NOTE" }]}
      />,
    );
    expect(screen.getAllByText("2024-Q1").length).toBe(2); // one row per lane on the shared axis
    expect(screen.getAllByText("2023-Q4").length).toBe(2);
    expect(screen.getByText("tallowdate")).toBeTruthy();
    expect(screen.getAllByText(NOT_COMPUTED).length).toBeGreaterThan(0);
  });

  it("says each missing lane is NOT COMPUTED", () => {
    render(<TwoEndings xz={undefined} tallowdate={undefined} />);
    expect(screen.getByText(/xz replay file was not found/)).toBeTruthy();
    expect(screen.getByText(/tallowdate decision file was not found/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------- Packager (23)

describe("Packager", () => {
  it("asks the visibility-gap question for the chosen decision, roles only", () => {
    render(<Packager gaps={gapsFull} file="ecosystem_gaps.json" />);
    expect(screen.getByText(/Debian package maintainer decided at debian-bts/)).toBeTruthy();
    expect(screen.getAllByText(/UNREACHABLE/).length).toBeGreaterThan(0);
  });

  it("switches decisions from the dropdown", () => {
    render(<Packager gaps={gapsFull} file="ecosystem_gaps.json" />);
    fireEvent.change(screen.getByLabelText("Decision"), { target: { value: "lkml-entry" } });
    expect(screen.getByText(/no role watches lkml/)).toBeTruthy();
  });

  it("says NOT COMPUTED when the gaps file is missing", () => {
    render(<Packager gaps={undefined} file="ecosystem_gaps.json" />);
    expect(screen.getByText(/ecosystem_gaps\.json not found/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------- Connect your repo (13.8)

describe("ConnectRepo", () => {
  it("posts owner/name, polls the job, and shows the steps and the NOT COMPUTED cost", async () => {
    const job = {
      id: "j1",
      repo: "octo/demo",
      state: "done",
      steps: [{ name: "read repository", status: "done", detail: "octo/demo" }],
      result: {
        repo: "octo/demo",
        org: "org_octo_demo",
        status: "DONE",
        wall_clock_s: 1.5,
        requests: { network: 4, from_cache: 0 },
        counts: { commits_read: 3, actors: 2 },
        metrics: { cadence_days: { status: "COMPUTED", value: 30, unit: "days" } },
        takeover_cost: { status: "NOT COMPUTED", reason: "no grant record" },
        guardians: { status: "NOT COMPUTED", reason: "no grant record" },
        best_hardening_step: { status: "NOT COMPUTED", reason: "no grant record" },
      },
    };
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") return new Response(JSON.stringify({ job: "j1" }), { status: 200 });
      return new Response(JSON.stringify(job), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ConnectRepo />);
    fireEvent.change(screen.getByLabelText("Repository owner/name"), { target: { value: "octo/demo" } });
    fireEvent.click(screen.getByText("Connect"));
    await waitFor(() => expect(screen.getByText("org_octo_demo")).toBeTruthy());
    expect(screen.getByText("Measured wall clock: 1.5 s. Requests to GitHub: 4, from cache: 0.")).toBeTruthy();
    expect(screen.getAllByText(/no grant record/).length).toBe(3);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/connect");
  });

  it("shows a refusal from the API as NOT COMPUTED, not as a result", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "expected owner/name" }), { status: 422 })));
    render(<ConnectRepo />);
    fireEvent.change(screen.getByLabelText("Repository owner/name"), { target: { value: "nope" } });
    fireEvent.click(screen.getByText("Connect"));
    await waitFor(() => expect(screen.getByText(/NOT COMPUTED: expected owner\/name/)).toBeTruthy());
  });

  it("says the API is not running when the request cannot be made", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }));
    render(<ConnectRepo />);
    fireEvent.change(screen.getByLabelText("Repository owner/name"), { target: { value: "octo/demo" } });
    fireEvent.click(screen.getByText("Connect"));
    await waitFor(() => expect(screen.getByText(/make inbox/)).toBeTruthy());
  });
});

// ---------------------------------------------------------------- the page, with files missing and present

describe("results page", () => {
  it("shows NOT COMPUTED for every missing file and invents no value", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("not found", { status: 404 })));
    window.location.hash = "#/";
    render(<App />);
    await waitFor(() => expect(screen.getAllByText(/not found/).length).toBeGreaterThan(3));
    expect(screen.getByText(/xz_replay\.json not found/)).toBeTruthy();
    expect(screen.getByText(/trust_map_tallowdate\.json/)).toBeTruthy();
    expect(screen.getByText(/Pack: /)).toBeTruthy();
  });

  it("opens the connect screen from its hash", () => {
    window.location.hash = "#/connect";
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
    render(<App />);
    expect(screen.getByLabelText("Repository owner/name")).toBeTruthy();
  });
});
