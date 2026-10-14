import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { Patience, seriesOf, type AblationDoc } from "./Patience";

afterEach(cleanup);

// Hand-written fixture (not a measurement): two arms, two patience levels.
const arm = (rates: [number, number], leads: [number | null, number | null]) => ({
  memory_window_days: null,
  summary: { n: 10, detection_rate: (rates[0] + rates[1]) / 2, median_lead_time_days: 5 },
  by_patience: [
    { patience_days: 7, n: 5, detection_rate: rates[0], median_lead_time_days: leads[0] },
    { patience_days: 90, n: 5, detection_rate: rates[1], median_lead_time_days: leads[1] },
  ],
  clean: { n: 4, flagged: 1, false_flag_rate: 0.25 },
});
const doc: AblationDoc = {
  n: 10,
  arms: { forget_30: arm([0.2, 0.4], [null, 3]), full: arm([0.8, 1], [10, 12]) },
  comparison: { forget_30: { overall: { verdict: "worse than full memory (lower detection rate)" } } },
};

describe("Patience curve", () => {
  it("orders the series full first and keeps the file's numbers", () => {
    const s = seriesOf(doc)!;
    expect(s.map((x) => x.arm)).toEqual(["full", "forget_30"]);
    expect(s[0].points.map((p) => p.rate)).toEqual([0.8, 1]);
    expect(s[1].points.map((p) => p.lead)).toEqual([null, 3]);
  });

  it("returns null for a file that is not the memory ablation", () => {
    expect(seriesOf({} as AblationDoc)).toBeNull();
    expect(seriesOf(undefined)).toBeNull();
  });

  it("draws both arms and the verdict from the file", () => {
    render(<Patience present data={doc} />);
    expect(screen.getByRole("img", { name: /Detection rate and lead time/ })).toBeTruthy();
    expect(document.querySelectorAll("g[data-arm='full']").length).toBe(2);
    expect(document.querySelectorAll("g[data-arm='forget_30']").length).toBe(2);
    expect(screen.getByText(/worse than full memory/)).toBeTruthy();
  });

  it("leaves a missing lead time out of the line instead of drawing a zero", () => {
    render(<Patience present data={doc} />);
    const panels = document.querySelectorAll("g[data-arm='forget_30'] polyline");
    // detection has 2 points, lead time has only the 1 non-null point
    expect(panels[0].getAttribute("points")!.split(" ").length).toBe(2);
    expect(panels[1].getAttribute("points")!.split(" ").length).toBe(1);
  });

  it("is NOT COMPUTED while the file is absent", () => {
    render(<Patience present={false} />);
    expect(screen.getByText(/NOT COMPUTED/)).toBeTruthy();
  });
});
