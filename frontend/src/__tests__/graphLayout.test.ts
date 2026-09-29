import { describe, expect, it } from 'vitest';

import {
  KIND_LABEL,
  MAX_RENDERED_NODES,
  layoutGraph,
  moduleById,
  neighboursOf,
  rankModules,
} from '../components/architecture/graphLayout';
import { architectureModule, architectureGraph } from '../test/fixtures';

describe('architecture graphLayout', () => {
  it('lays out the same graph identically on every call', () => {
    const graph = architectureGraph();
    const first = layoutGraph(graph);
    const second = layoutGraph(graph);

    expect(second.nodes.map((node) => [node.id, node.x, node.y])).toEqual(
      first.nodes.map((node) => [node.id, node.x, node.y]),
    );
  });

  it('only lays out internal edges between rendered nodes', () => {
    const graph = architectureGraph({
      edges: [
        { source: 'app.services.auth', target: 'app.db.session', kind: 'internal', reference: 'x', resolved: true },
        // External edges point at synthetic ids that are not modules.
        { source: 'app.services.auth', target: 'external:fastapi', kind: 'external', reference: 'fastapi', resolved: true },
      ],
    });

    const layout = layoutGraph(graph);

    expect(layout.edges).toHaveLength(1);
    expect(layout.edges[0].target).toBe('app.db.session');
  });

  it('caps the number of rendered nodes on very large repositories', () => {
    const modules = Array.from({ length: MAX_RENDERED_NODES + 40 }, (_, index) =>
      architectureModule({ id: `pkg.mod_${index}`, path: `pkg/mod_${index}.ts` }),
    );

    const layout = layoutGraph(
      architectureGraph({ modules, nodes: [], edges: [] }),
    );

    expect(layout.nodes).toHaveLength(MAX_RENDERED_NODES);
  });

  it('returns related modules and their direct neighbours for a selection', () => {
    const graph = architectureGraph();
    const related = neighboursOf(graph, 'app.services.auth');

    expect(related.has('app.services.auth')).toBe(true);
    expect(related.has('app.routers.auth')).toBe(true);
    expect(related.has('app.db.session')).toBe(true);
    expect(related.has('unrelated.module')).toBe(false);
    expect(neighboursOf(graph, null).size).toBe(0);
  });

  it('resolves a module by id and ranks the most connected first', () => {
    const graph = architectureGraph();
    expect(moduleById(graph, 'app.db.session')?.name).toBe('session');
    expect(moduleById(graph, null)).toBeNull();

    const ranked = rankModules(graph, { search: 'auth' });
    expect(ranked.map((entry) => entry.module.id)).toContain('app.services.auth');
    expect(ranked.some((entry) => entry.module.id === 'app.db.session')).toBe(false);
  });

  it('exposes a human label for every node kind', () => {
    expect(Object.keys(KIND_LABEL).sort()).toEqual(
      ['controller', 'database', 'external', 'module', 'route', 'service'].sort(),
    );
  });
});
