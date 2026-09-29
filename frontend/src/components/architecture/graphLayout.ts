import { useMemo } from 'react';

import type {
  ArchitectureEdge,
  ArchitectureGraph,
  ArchitectureIssue,
  ArchitectureModule,
  ArchitectureNode,
  ArchitectureNodeKind,
} from '../../types';

export interface LaidOutNode {
  id: string;
  x: number;
  y: number;
  /** 0..1, relative size. */
  weight: number;
  node: ArchitectureModule;
}

export interface LaidOutEdge {
  source: string;
  target: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  edge: ArchitectureEdge;
}

export interface GraphLayout {
  nodes: LaidOutNode[];
  edges: LaidOutEdge[];
  width: number;
  height: number;
}

const WIDTH = 900;
const HEIGHT = 560;

/** Nodes beyond this are not laid out, because the graph stops being readable. */
export const MAX_RENDERED_NODES = 220;

export const KIND_COLOR: Record<ArchitectureNodeKind, string> = {
  service: '#8B5CF6',
  route: '#22D3EE',
  controller: '#38BDF8',
  database: '#F59E0B',
  module: '#64748B',
  external: '#475569',
};

export const KIND_LABEL: Record<ArchitectureNodeKind, string> = {
  service: 'Service',
  route: 'Route',
  controller: 'Controller',
  database: 'Data layer',
  module: 'Module',
  external: 'External',
};

/**
 * Deterministic force-directed layout.
 *
 * This is seeded, not random. Each node's initial position is derived from a
 * hash of its id, so the same repository always lays out the same way and a
 * reviewer can compare two graphs visually. A random seed would reshuffle the
 * layout on every render and make the view impossible to reason about.
 *
 * The simulation is a bounded fixed number of iterations rather than a
 * convergence check, so layout time is predictable and cannot blow up on a
 * pathological graph.
 */
function hashToUnit(id: string): number {
  let hash = 2166136261;
  for (let index = 0; index < id.length; index += 1) {
    hash ^= id.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  // Map into [0, 1) using the top bits, which are the best mixed.
  return ((hash >>> 0) % 100000) / 100000;
}

export function layoutGraph(graph: ArchitectureGraph): GraphLayout {
  const modules = graph.modules.slice(0, MAX_RENDERED_NODES);
  const ids = new Set(modules.map((module) => module.id));

  // Only edges between two laid-out nodes; an edge to a dropped node would
  // otherwise be drawn to a position that does not exist.
  const usableEdges = graph.edges.filter(
    (edge) => edge.kind === 'internal' && ids.has(edge.source) && ids.has(edge.target),
  );

  if (modules.length === 0) {
    return { nodes: [], edges: [], width: WIDTH, height: HEIGHT };
  }

  // Highly connected modules sit near the centre, so the dense core of a
  // repository is legible instead of being scattered.
  const degree = new Map<string, number>(modules.map((module) => [module.id, 0]));
  for (const edge of usableEdges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }
  const maxDegree = Math.max(...degree.values(), 1);

  const centre = { x: WIDTH / 2, y: HEIGHT / 2 };
  const spread = Math.min(WIDTH, HEIGHT) * 0.38;

  const positions = new Map<string, { x: number; y: number }>();
  modules.forEach((module, index) => {
    // Deterministic golden-angle placement: even angular coverage, and the
    // angle depends only on the index so it never varies between renders.
    const angle = index * 2.39996323;
    const unit = hashToUnit(module.id);
    const radius = spread * (0.45 + unit * 0.55);
    const centrePull = 1 - Math.min((degree.get(module.id) ?? 0) / (maxDegree * 1.6), 0.55);
    positions.set(module.id, {
      x: centre.x + Math.cos(angle) * radius * centrePull,
      y: centre.y + Math.sin(angle) * radius * centrePull,
    });
  });

  // A few relaxation passes. Enough to untangle the dense middle without making
  // layout a perceptible cost.
  const ITERATIONS = 90;
  const idealLength = 92;
  for (let step = 0; step < ITERATIONS; step += 1) {
    const cooling = 1 - step / ITERATIONS;
    const displacement = new Map<string, { x: number; y: number }>();

    // Repulsion, computed against every other node.
    for (const a of modules) {
      const pa = positions.get(a.id)!;
      let fx = 0;
      let fy = 0;
      for (const b of modules) {
        if (a.id === b.id) continue;
        const pb = positions.get(b.id)!;
        let dx = pa.x - pb.x;
        let dy = pa.y - pb.y;
        let distanceSq = dx * dx + dy * dy;
        if (distanceSq < 0.01) {
          // Coincident nodes: nudge deterministically by id so they separate
          // instead of dividing by zero.
          dx = (hashToUnit(`${a.id}:x`) - 0.5) * 2;
          dy = (hashToUnit(`${a.id}:y`) - 0.5) * 2;
          distanceSq = dx * dx + dy * dy;
        }
        const distance = Math.sqrt(distanceSq);
        const force = (idealLength * idealLength) / distance / 12;
        fx += (dx / distance) * force;
        fy += (dy / distance) * force;
      }
      displacement.set(a.id, { x: fx, y: fy });
    }

    // Attraction along edges.
    for (const edge of usableEdges) {
      const ps = positions.get(edge.source);
      const pt = positions.get(edge.target);
      if (!ps || !pt) continue;
      const dx = pt.x - ps.x;
      const dy = pt.y - ps.y;
      const distance = Math.max(Math.sqrt(dx * dx + dy * dy), 0.01);
      const force = (distance - idealLength) / 8;
      const ux = (dx / distance) * force;
      const uy = (dy / distance) * force;
      const ds = displacement.get(edge.source);
      const dt = displacement.get(edge.target);
      if (ds) {
        ds.x += ux;
        ds.y += uy;
      }
      if (dt) {
        dt.x -= ux;
        dt.y -= uy;
      }
    }

    for (const module of modules) {
      const p = positions.get(module.id)!;
      const d = displacement.get(module.id)!;
      const step2 = 6 * cooling;
      p.x += Math.max(-step2, Math.min(step2, d.x));
      p.y += Math.max(-step2, Math.min(step2, d.y));
      // Keep nodes inside the viewport so nothing is clipped away.
      p.x = Math.max(30, Math.min(WIDTH - 30, p.x));
      p.y = Math.max(24, Math.min(HEIGHT - 24, p.y));
    }
  }

  const maxFan = Math.max(...modules.map((module) => module.fan_in + module.fan_out), 1);

  return {
    nodes: modules.map((module) => {
      const p = positions.get(module.id)!;
      return {
        id: module.id,
        x: p.x,
        y: p.y,
        weight: (module.fan_in + module.fan_out) / maxFan,
        node: module,
      };
    }),
    edges: usableEdges.map((edge) => {
      const from = positions.get(edge.source)!;
      const to = positions.get(edge.target)!;
      return {
        source: edge.source,
        target: edge.target,
        x1: from.x,
        y1: from.y,
        x2: to.x,
        y2: to.y,
        edge,
      };
    }),
    width: WIDTH,
    height: HEIGHT,
  };
}

/** The module a selection resolves to, preferring the graph's own node record. */
export function moduleById(graph: ArchitectureGraph, id: string | null): ArchitectureNode | null {
  if (!id) return null;
  return graph.nodes.find((node) => node.id === id) ?? null;
}

/** Issues touching a module, so selecting one surfaces its known problems. */
export function issuesForModule(issues: ArchitectureIssue[], moduleId: string): ArchitectureIssue[] {
  return issues.filter((issue) => issue.nodes.includes(moduleId));
}

/** Modules importing or imported by the selection, for dependency highlighting. */
export function neighboursOf(
  graph: ArchitectureGraph,
  moduleId: string | null,
): Set<string> {
  if (!moduleId) return new Set();
  const related = new Set<string>([moduleId]);
  for (const edge of graph.edges) {
    if (edge.kind !== 'internal') continue;
    if (edge.source === moduleId) related.add(edge.target);
    if (edge.target === moduleId) related.add(edge.source);
  }
  return related;
}

export interface RankedModule {
  module: ArchitectureModule;
  score: number;
}

export function rankModules(
  graph: ArchitectureGraph,
  options: { search?: string; kinds?: ArchitectureNodeKind[] } = {},
): RankedModule[] {
  const { search = '', kinds = [] } = options;
  const needle = search.trim().toLowerCase();
  return graph.modules
    .filter((module) => (kinds.length ? kinds.includes(module.kind) : true))
    .filter((module) => {
      if (!needle) return true;
      return (
        module.id.toLowerCase().includes(needle) || module.path.toLowerCase().includes(needle)
      );
    })
    .map((module) => ({
      module,
      // Ordering is by connectivity then size then id, so the list is stable for
      // modules that tie.
      score: module.fan_in * 2 + module.fan_out + (module.line_count ?? 0) / 1000,
    }))
    .sort((a, b) => b.score - a.score || a.module.id.localeCompare(b.module.id))
    .slice(0, 300);
}

export function useGraphLayout(graph: ArchitectureGraph | null): GraphLayout | null {
  return useMemo(() => (graph ? layoutGraph(graph) : null), [graph]);
}
