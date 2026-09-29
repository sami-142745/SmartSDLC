import { useCallback, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent, WheelEvent } from 'react';

import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { cn } from '../../lib/cn';
import {
  KIND_COLOR,
  KIND_LABEL,
  neighboursOf,
} from './graphLayout';
import type { GraphLayout } from './graphLayout';
import type { ArchitectureGraph, ArchitectureIssue, ArchitectureNode } from '../../types';

const MIN_ZOOM = 0.4;
const MAX_ZOOM = 3;

export interface ArchitectureGraphViewProps {
  graph: ArchitectureGraph;
  layout: GraphLayout;
  selected: string | null;
  onSelect: (id: string | null) => void;
  issues: ArchitectureIssue[];
  className?: string;
}

/**
 * Interactive dependency graph: zoom, pan, node selection and dependency
 * highlighting.
 *
 * Rendered as inline SVG rather than a canvas library. The graphs this shows are
 * a few hundred nodes, SVG handles that comfortably, and it keeps the route's
 * bundle free of a graph dependency while staying crisp and keyboard-reachable.
 *
 * Determinism matters here: the layout is seeded (see `graphLayout`), so the
 * picture does not reshuffle between renders and two repositories can be compared
 * by eye.
 */
export function ArchitectureGraphView({
  graph,
  layout,
  selected,
  onSelect,
  issues,
  className,
}: ArchitectureGraphViewProps) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragState = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number } | null>(null);

  const highlighted = useMemo(() => neighboursOf(graph, selected), [graph, selected]);
  const hasSelection = selected !== null;

  const moduleIdsInCycles = useMemo(() => {
    const ids = new Set<string>();
    for (const issue of issues) {
      if (issue.kind === 'circular_dependency') issue.nodes.forEach((id) => ids.add(id));
    }
    return ids;
  }, [issues]);

  const clampZoom = useCallback((value: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value)), []);

  const handleWheel = useCallback(
    (event: WheelEvent<SVGSVGElement>) => {
      event.preventDefault();
      // Trackpads report small deltas; a plain mouse wheel reports ~100 per notch.
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      setZoom((current) => clampZoom(current * factor));
    },
    [clampZoom],
  );

  const handlePointerDown = useCallback((event: PointerEvent<SVGSVGElement>) => {
    // Ignore secondary buttons so a context menu does not start a pan.
    if (event.button !== 0) return;
    dragState.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: pan.x,
      originY: pan.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }, [pan.x, pan.y]);

  const handlePointerMove = useCallback((event: PointerEvent<SVGSVGElement>) => {
    const state = dragState.current;
    if (!state || state.pointerId !== event.pointerId) return;
    setPan({
      x: state.originX + (event.clientX - state.startX),
      y: state.originY + (event.clientY - state.startY),
    });
  }, []);

  const endDrag = useCallback((event: PointerEvent<SVGSVGElement>) => {
    const state = dragState.current;
    if (!state || state.pointerId !== event.pointerId) return;
    dragState.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  /**
   * Arrow keys walk the laid-out nodes in id order and Enter selects. Without
   * this a keyboard user could not reach any node, since SVG nodes are not
   * naturally focusable in a useful order.
   */
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Escape') {
        onSelect(null);
        return;
      }
      if (event.key === '+' || event.key === '=') {
        event.preventDefault();
        setZoom((current) => clampZoom(current * 1.2));
        return;
      }
      if (event.key === '-') {
        event.preventDefault();
        setZoom((current) => clampZoom(current / 1.2));
        return;
      }
      if (event.key === '0') {
        event.preventDefault();
        resetView();
        return;
      }
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      if (layout.nodes.length === 0) return;
      event.preventDefault();
      const index = layout.nodes.findIndex((node) => node.id === selected);
      const step = event.key === 'ArrowRight' ? 1 : -1;
      const nextIndex = index === -1 ? 0 : (index + step + layout.nodes.length) % layout.nodes.length;
      onSelect(layout.nodes[nextIndex].id);
    },
    [clampZoom, layout.nodes, onSelect, resetView, selected],
  );

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      <div
        className="flex flex-wrap items-center gap-2"
        role="toolbar"
        aria-label="Graph view controls"
      >
        <Button variant="ghost" size="sm" onClick={() => setZoom((z) => clampZoom(z * 1.2))} aria-label="Zoom in">
          +
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setZoom((z) => clampZoom(z / 1.2))} aria-label="Zoom out">
          &minus;
        </Button>
        <Button variant="ghost" size="sm" onClick={resetView} aria-label="Reset view">
          Reset
        </Button>
        <span className="font-mono text-[11px] tabular-nums text-ink-subtle">
          {Math.round(zoom * 100)}%
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2 text-[11px] text-ink-subtle">
          {(['service', 'route', 'controller', 'database', 'module'] as const).map((kind) => (
            <span key={kind} className="inline-flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="size-2 rounded-full"
                style={{ backgroundColor: KIND_COLOR[kind] }}
              />
              {KIND_LABEL[kind]}
            </span>
          ))}
        </div>
      </div>

      <div
        className="relative overflow-hidden rounded-xl border border-white/[0.07] bg-surface-1"
        tabIndex={0}
        onKeyDown={handleKeyDown}
        role="application"
        aria-label={`Dependency graph with ${layout.nodes.length} modules. Use arrow keys to move between modules, Escape to clear the selection.`}
      >
        <svg
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          className="h-[560px] w-full touch-none select-none"
          role="img"
          aria-label={`${layout.nodes.length} modules and ${layout.edges.length} dependencies`}
          onWheel={handleWheel}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
            {layout.edges.map((edge) => {
              const active = selected !== null && (edge.source === selected || edge.target === selected);
              const dimmed = hasSelection && !active;
              return (
                <line
                  key={`${edge.source}->${edge.target}`}
                  x1={edge.x1}
                  y1={edge.y1}
                  x2={edge.x2}
                  y2={edge.y2}
                  stroke={active ? '#8B5CF6' : '#334155'}
                  strokeWidth={active ? 1.8 : 1}
                  strokeOpacity={dimmed ? 0.15 : 0.75}
                />
              );
            })}

            {layout.nodes.map((item) => {
              const isSelected = item.id === selected;
              const isRelated = highlighted.has(item.id);
              const dimmed = hasSelection && !isRelated;
              const radius = 5 + item.weight * 9;
              const inCycle = moduleIdsInCycles.has(item.id);
              return (
                <g
                  key={item.id}
                  transform={`translate(${item.x} ${item.y})`}
                  opacity={dimmed ? 0.25 : 1}
                >
                  <circle
                    r={radius}
                    fill={KIND_COLOR[item.node.kind]}
                    fillOpacity={isSelected ? 1 : 0.7}
                    stroke={isSelected ? '#E2E8F0' : inCycle ? '#F87171' : 'transparent'}
                    strokeWidth={isSelected ? 2 : inCycle ? 1.5 : 0}
                    className="cursor-pointer"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(isSelected ? null : item.id);
                    }}
                  />
                  <title>{`${item.node.id} (${KIND_LABEL[item.node.kind]}) — imports ${item.node.fan_out}, imported by ${item.node.fan_in}`}</title>
                </g>
              );
            })}
          </g>
        </svg>

        {layout.nodes.length === 0 ? (
          <p className="px-4 py-10 text-center text-[13px] text-ink-subtle">
            No modules to lay out.
          </p>
        ) : null}
      </div>

      <p className="text-[11px] text-ink-faint">
        Drag to pan, scroll to zoom. Node size reflects how many modules it imports
        or is imported by.
      </p>
    </div>
  );
}

export interface ModuleDetailProps {
  node: ArchitectureNode | null;
  graph: ArchitectureGraph;
  issues: ArchitectureIssue[];
  className?: string;
}

/** Detail panel for the selected module, including the evidence for its label. */
export function ModuleDetail({ node, graph, issues, className }: ModuleDetailProps) {
  if (!node) {
    return (
      <p className={cn('text-[13px] text-ink-subtle', className)}>
        Select a module in the graph to see its details.
      </p>
    );
  }

  const own = issues.filter((issue) => issue.nodes.includes(node.id));
  const dependsOn = graph.edges.filter((edge) => edge.kind === 'internal' && edge.source === node.id);
  const dependedOnBy = graph.edges.filter((edge) => edge.kind === 'internal' && edge.target === node.id);
  const externals = graph.edges.filter((edge) => edge.kind === 'external' && edge.source === node.id);

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <div>
        <div className="flex items-center gap-2">
          <h3 className="truncate font-mono text-[13px] font-medium text-ink">{node.name}</h3>
          <Badge tone="neutral">{KIND_LABEL[node.kind]}</Badge>
        </div>
        <p className="mt-1 break-all font-mono text-[11px] text-ink-subtle">{node.path || node.id}</p>
      </div>

      {/*
        The evidence string is shown rather than hidden. A classification the
        reviewer cannot check is a classification they have to trust.
      */}
      {node.evidence ? (
        <p className="text-[12px] text-ink-muted">
          <span className="text-ink-subtle">Classified because it</span> {node.evidence}.
        </p>
      ) : (
        <p className="text-[12px] text-ink-subtle">
          No structural role was detected for this module.
        </p>
      )}

      {!node.parsed ? (
        <p className="rounded-lg border border-amber-500/25 bg-amber-500/[0.06] px-3 py-2 text-[12px] text-amber-300">
          This file could not be parsed, so its own imports are unknown. It is still
          listed because it exists.
        </p>
      ) : null}

      <dl className="grid grid-cols-2 gap-3 text-[12px]">
        <div>
          <dt className="text-ink-subtle">Imports</dt>
          <dd className="font-mono tabular-nums text-ink">{node.fan_out}</dd>
        </div>
        <div>
          <dt className="text-ink-subtle">Imported by</dt>
          <dd className="font-mono tabular-nums text-ink">{node.fan_in}</dd>
        </div>
        <div>
          <dt className="text-ink-subtle">Lines</dt>
          <dd className="font-mono tabular-nums text-ink">{node.line_count ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-ink-subtle">Language</dt>
          <dd className="text-ink">{node.language ?? '—'}</dd>
        </div>
      </dl>

      {[
        { label: 'Imports', ids: dependsOn.map((edge) => edge.target) },
        { label: 'Imported by', ids: dependedOnBy.map((edge) => edge.source) },
      ]
        .filter((section) => section.ids.length > 0)
        .map((section) => (
          <div key={section.label}>
            <h4 className="text-[11px] font-medium uppercase tracking-wide text-ink-subtle">
              {section.label} ({section.ids.length})
            </h4>
            <ul className="mt-1 space-y-0.5">
              {section.ids.slice(0, 12).map((id) => (
                <li key={id} className="truncate font-mono text-[11px] text-ink-muted">
                  {id}
                </li>
              ))}
              {section.ids.length > 12 ? (
                <li className="text-[11px] text-ink-faint">+{section.ids.length - 12} more</li>
              ) : null}
            </ul>
          </div>
        ))}

      {externals.length > 0 ? (
        <div>
          <h4 className="text-[11px] font-medium uppercase tracking-wide text-ink-subtle">
            Third-party packages ({externals.length})
          </h4>
          <ul className="mt-1 flex flex-wrap gap-1">
            {externals.slice(0, 20).map((edge) => (
              <li key={edge.target}>
                <Badge tone="neutral">{edge.reference}</Badge>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {own.length > 0 ? (
        <div>
          <h4 className="text-[11px] font-medium uppercase tracking-wide text-ink-subtle">
            Structural signals ({own.length})
          </h4>
          <ul className="mt-1 space-y-2">
            {own.map((issue) => (
              <li key={`${issue.kind}-${issue.title}`} className="text-[12px]">
                <span className="text-ink-muted">{issue.title}</span>
                <p className="text-ink-subtle">{issue.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
