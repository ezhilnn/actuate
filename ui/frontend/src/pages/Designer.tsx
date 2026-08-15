import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactFlow, {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  MiniMap,
  Node,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "reactflow";
import "reactflow/dist/style.css";
import { api, Provider } from "../api";
import AgentFlowNode from "../graph/AgentFlowNode";
import AgentGuide, { Agent } from "../graph/AgentGuide";

const nodeTypes = { agent: AgentFlowNode };

type Template = {
  id: string;
  name: string;
  blurb: string;
  nodes: { id: string; agent: string; x: number; y: number; label?: string }[];
  edges: { id: string; source: string; target: string }[];
  target_score: number;
  max_passes: number;
};

function toFlow(template: Template, agents: Agent[]): { nodes: Node[]; edges: Edge[] } {
  const byId = Object.fromEntries(agents.map((a) => [a.id, a]));
  return {
    nodes: template.nodes.map((n) => {
      const spec = byId[n.agent];
      return {
        id: n.id,
        type: "agent",
        position: { x: n.x, y: n.y },
        data: {
          agent: n.agent,
          title: n.label || spec?.title || n.agent,
          kind: spec?.kind || "agent",
          color: spec?.color || "#3d8bfd",
          blurb: spec?.blurb || "",
        },
      };
    }),
    edges: template.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
    })),
  };
}

function fromFlow(nodes: Node[], edges: Edge[], name: string, target: number, passes: number): Template {
  return {
    id: "custom",
    name,
    blurb: "User designed",
    target_score: target,
    max_passes: passes,
    nodes: nodes.map((n) => ({
      id: n.id,
      agent: n.data.agent,
      x: n.position.x,
      y: n.position.y,
      label: n.data.title,
    })),
    edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
  };
}

function DesignerInner() {
  const nav = useNavigate();
  const { screenToFlowPosition } = useReactFlow();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [provider, setProvider] = useState("nvidia");
  const [model, setModel] = useState("meta/llama-3.1-8b-instruct");
  const [prompt, setPrompt] = useState(
    "Explain how a community can improve access to clean drinking water. Be practical and cautious.",
  );
  const [target, setTarget] = useState(0.85);
  const [passes, setPasses] = useState(4);
  const [maxTokens, setMaxTokens] = useState(250000);
  const [name, setName] = useState("Accurate explainer");
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [guideId, setGuideId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    Promise.all([
      api<{ agents: Agent[] }>("/api/agents"),
      api<{ templates: Template[] }>("/api/graph-templates"),
      api<{ providers: Provider[] }>("/api/models"),
    ]).then(([a, t, m]) => {
      setAgents(a.agents);
      setTemplates(t.templates);
      setProviders(m.providers);
      const first = m.providers.find((p) => p.configured) || m.providers[0];
      if (first) {
        setProvider(first.id);
        setModel(first.default);
      }
      const starter = t.templates[0];
      if (starter) {
        const flow = toFlow(starter, a.agents);
        setNodes(flow.nodes);
        setEdges(flow.edges);
        setName(starter.name);
        setTarget(starter.target_score);
        setPasses(starter.max_passes);
      }
    }).finally(() => setLoading(false));
  }, [setEdges, setNodes]);

  const onConnect = useCallback(
    (c: Connection) => {
      const id = `e-${Date.now()}`;
      setEdges((eds) => addEdge({ ...c, id, animated: true, className: "edge-new" }, eds));
      window.setTimeout(() => {
        setEdges((eds) => eds.map((e) => (e.id === id || (e.source === c.source && e.target === c.target) ? { ...e, animated: false, className: "" } : e)));
      }, 420);
    },
    [setEdges],
  );

  const applyTemplate = (tpl: Template) => {
    const flow = toFlow(tpl, agents);
    setNodes(flow.nodes);
    setEdges(flow.edges);
    setName(tpl.name);
    setTarget(tpl.target_score);
    setPasses(tpl.max_passes);
  };

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const raw = event.dataTransfer.getData("application/actuate-agent");
      if (!raw) return;
      const spec: Agent = JSON.parse(raw);
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      const id = `${spec.id}-${Math.random().toString(36).slice(2, 7)}`;
      setNodes((nds) => [
        ...nds,
        {
          id,
          type: "agent",
          position,
          data: {
            agent: spec.id,
            title: spec.title,
            kind: spec.kind,
            color: spec.color,
            blurb: spec.blurb,
            system: spec.system,
          },
        },
      ]);
    },
    [screenToFlowPosition, setNodes],
  );

  const selectedNode = nodes.find((n) => n.id === selected);
  const guideAgent =
    agents.find((a) => a.id === guideId) ||
    agents.find((a) => a.id === selectedNode?.data.agent);

  const start = async () => {
    setError("");
    try {
      const graph = fromFlow(nodes, edges, name, target, passes);
      const created = await api<{ run_id: string }>("/api/graphs/run", {
        method: "POST",
        body: JSON.stringify({ prompt, name, graph, provider, model, max_tokens: maxTokens }),
      });
      nav(`/graph/${created.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    }
  };

  const grouped = useMemo(() => {
    const groups: Record<string, Agent[]> = { io: [], agent: [], judge: [] };
    for (const a of agents) {
      if (q && !`${a.title} ${a.blurb} ${a.id}`.toLowerCase().includes(q.toLowerCase())) continue;
      (groups[a.kind] || (groups[a.kind] = [])).push(a);
    }
    return groups;
  }, [agents, q]);

  const current = providers.find((p) => p.id === provider);
  const shownTemplates = templates.filter(
    (t) => !filter || t.name.toLowerCase().includes(filter.toLowerCase()) || t.blurb.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="designer-page">
      <header className="designer-head">
        <div>
          <h1>Loop / graph designer</h1>
          <p className="sub">
            Drag specialized agents, connect them, or load a template. Judges keep the graph running until the output is accurate enough.
          </p>
        </div>
        <button className="primary" type="button" onClick={start} style={{ marginTop: 0 }}>
          Run graph
        </button>
      </header>
      {error && <p className="sub" style={{ color: "var(--red)" }}>{error}</p>}
      <div className="designer-shell">
        <aside className="palette">
          <h3>Agents</h3>
          <input placeholder="Search agents" value={q} onChange={(e) => setQ(e.target.value)} />
          {loading && (
            <div className="boot">
              <div className="boot-orb" />
              <p>Loading agents and templates…</p>
            </div>
          )}
          {(["io", "judge", "agent"] as const).map((kind) => (
            <div key={kind}>
              <p className="palette-k">{kind}</p>
              {(grouped[kind] || []).map((a) => (
                <div
                  key={a.id}
                  className={`palette-item ${guideId === a.id ? "on" : ""}`}
                  draggable
                  onClick={() => setGuideId(a.id)}
                  onDragStart={(e) => e.dataTransfer.setData("application/actuate-agent", JSON.stringify(a))}
                >
                  <i style={{ background: a.color }} />
                  {a.title}
                </div>
              ))}
            </div>
          ))}
        </aside>
        <div
          className="rf canvas"
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            isValidConnection={(c) => Boolean(c.source && c.target && c.source !== c.target)}
            nodeTypes={nodeTypes}
            onNodeClick={(_, n) => {
              setSelected(n.id);
              setGuideId(n.data.agent);
            }}
            onPaneClick={() => setSelected(null)}
            fitView
            minZoom={0.15}
            maxZoom={1.75}
            zoomOnScroll
            panOnDrag
            deleteKeyCode={["Backspace", "Delete"]}
            defaultEdgeOptions={{ type: "smoothstep" }}
          >
            <Background />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
        </div>
        <aside className="inspector">
          <AgentGuide agent={guideAgent} />
          <h3>Templates</h3>
          <input placeholder="Filter templates" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <div className="tpl-list">
            {shownTemplates.map((t) => (
              <button key={t.id} type="button" className="tpl" onClick={() => applyTemplate(t)}>
                <strong>{t.name}</strong>
                <span>{t.blurb}</span>
              </button>
            ))}
          </div>
          <h3>Run settings</h3>
          <label>Graph name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <label>Prompt</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} style={{ minHeight: 120 }} />
          <label>LLM plant</label>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <label>Model</label>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {(current?.models || [model]).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <label>Target score {target}</label>
          <input type="range" min={0.5} max={1} step={0.01} value={target} onChange={(e) => setTarget(Number(e.target.value))} />
          <label>Max graph passes</label>
          <input type="number" min={1} max={12} value={passes} onChange={(e) => setPasses(Number(e.target.value))} />
          <label>Token budget</label>
          <input type="number" min={2000} value={maxTokens} onChange={(e) => setMaxTokens(Number(e.target.value))} />
          {selectedNode && (
            <>
              <h3>This node on the canvas</h3>
              <p className="sub">Change the specialist or remove the node. Wiring stays until you delete edges.</p>
              <label>Agent type</label>
              <select
                value={selectedNode.data.agent}
                onChange={(e) => {
                  const spec = agents.find((a) => a.id === e.target.value);
                  if (!spec) return;
                  setNodes((nds) =>
                    nds.map((n) =>
                      n.id === selectedNode.id
                        ? {
                            ...n,
                            data: {
                              ...n.data,
                              agent: spec.id,
                              title: spec.title,
                              kind: spec.kind,
                              color: spec.color,
                              blurb: spec.blurb,
                            },
                          }
                        : n,
                    ),
                  );
                }}
              >
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.title}</option>
                ))}
              </select>
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
                  setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
                  setSelected(null);
                }}
              >
                Remove node
              </button>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

export default function Designer() {
  return (
    <ReactFlowProvider>
      <DesignerInner />
    </ReactFlowProvider>
  );
}
