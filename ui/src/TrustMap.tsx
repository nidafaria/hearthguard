import { useEffect, useRef, useState } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { SyntheticTag, token } from "./data";

// Trust map (spec 13.4), drawn with Cytoscape. Reads eval/results/trust_map_tallowdate.json, written by
// eval/trust_map_export.py from the synthetic graph. Hashed actor ids only. The trust path is
// highlighted only when the file holds one; a null path is said, not drawn.

export type TrustNode = { id: string; type: string; actions?: number; synthetic?: boolean };
export type TrustEdge = { source: string; target: string; type: string; synthetic?: boolean };
export type TrustMapDoc = {
  synthetic: boolean;
  label: string;
  graph: string;
  nodes: TrustNode[];
  edges: TrustEdge[];
  trust_path: string[] | null;
  trust_path_note?: string;
};

// Node colours come from the design tokens: actors are ultramarine (synthetic), release and path are ink.
function colorOf(): Record<string, string> {
  const ink = token("--ink", "#161513");
  return { actor: token("--ultra", "#2F43C8"), release: ink, path: ink };
}

export function elementsOf(doc: TrustMapDoc): ElementDefinition[] {
  const onPath = new Set(doc.trust_path ?? []);
  const nodes = doc.nodes.map((n) => ({
    data: { id: n.id, label: n.type === "actor" ? `actor ${n.id.slice(6, 14)}` : n.id, type: n.type },
    classes: onPath.has(n.id) ? "onpath" : "",
  }));
  const edges = doc.edges.map((e, i) => ({
    data: { id: `e${i}`, source: e.source, target: e.target, label: e.type },
    classes: doc.trust_path && onPath.has(e.source) && onPath.has(e.target) ? "onpath" : "",
  }));
  return [...nodes, ...edges];
}

export function TrustMap({ doc }: { doc: TrustMapDoc }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    let cy: Core | null = null;
    try {
      cy = cytoscape({
        container: ref.current,
        elements: elementsOf(doc),
        style: [
          { selector: "node", style: { label: "data(label)", "font-size": 9, color: token("--ink", "#161513"), "background-color": token("--graphite", "#625E57"), width: 26, height: 26 } },
          ...Object.entries(colorOf()).map(([t, c]) => ({
            selector: `node[type = "${t}"]`,
            style: { "background-color": c },
          })),
          { selector: "edge", style: { width: 1.5, "line-color": token("--graphite", "#625E57"), "target-arrow-shape": "triangle", "target-arrow-color": token("--graphite", "#625E57"), "curve-style": "bezier", label: "data(label)", "font-size": 7 } },
          { selector: ".onpath", style: { "line-color": token("--signal", "#B8340A"), "background-color": token("--signal", "#B8340A"), width: 4 } },
        ],
        layout: { name: "cose", animate: false, padding: 12 },
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
    return () => {
      cy?.destroy();
    };
  }, [doc]);

  return (
    <section aria-label="Trust map">
      <h2>
        Trust map <SyntheticTag />
      </h2>
      <p className="muted">{doc.label}</p>
      <div ref={ref} style={{ width: "100%", height: 340, border: "1px solid var(--rule-2)" }} />
      {err && <p className="NOT_COMPUTED tag">NOT COMPUTED: the graph view failed to draw: {err}</p>}
      <p>
        {doc.trust_path && doc.trust_path.length > 0 ? (
          <>Trust path highlighted: {doc.trust_path.length} node(s).</>
        ) : (
          <span className="NOT_COMPUTED tag">NOT COMPUTED: no trust path in the saved file.</span>
        )}{" "}
        <span className="muted">{doc.trust_path_note ?? ""}</span>
      </p>
    </section>
  );
}
