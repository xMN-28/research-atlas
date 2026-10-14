'use client';
import { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import type { Network } from '@/lib/types';
export default function NetworkGraph({ data, dark, onSelect }: { data: Network; dark: boolean; onSelect: (id: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<cytoscape.Core | null>(null);
  useEffect(() => {
    if (!container.current) return;
    const cy = cytoscape({ container: container.current,
      elements: [...data.nodes.map(n => ({ data: { ...n }, position: { x: n.x, y: n.y } })),
        ...data.edges.map((e, i) => ({ data: { ...e, id: `e${i}` } }))],
      layout: { name: 'preset', fit: true, padding: 50 }, minZoom: 0.25, maxZoom: 4,
      style: [
        { selector: 'node', style: { label: 'data(label)', 'background-color': '#6b947e', color: dark ? '#dde6df' : '#3c5446',
          'font-size': 11, 'text-valign': 'bottom', 'text-margin-y': 8, width: 'mapData(count, 20, 4000, 13, 52)', height: 'mapData(count, 20, 4000, 13, 52)', 'border-width': 3, 'border-color': dark ? '#20362a' : '#e0ebdf' } },
        { selector: 'edge', style: { width: 'mapData(jaccard, 0, 1, 0.5, 4)', 'line-color': dark ? '#526e5b' : '#b7c7bb', opacity: 0.5, 'curve-style': 'bezier' } },
        { selector: 'node:selected', style: { 'background-color': '#cc9b60', 'border-color': '#ecd4b4' } },
        { selector: '.dim', style: { opacity: 0.15 } },
      ],
    });
    graph.current = cy;
    cy.on('tap', 'node', event => {
      const node = event.target;
      cy.elements().removeClass('dim'); cy.elements().not(node.closedNeighborhood()).addClass('dim');
      onSelect(node.id());
    });
    cy.on('tap', event => { if (event.target === cy) cy.elements().removeClass('dim'); });
    const resize = new ResizeObserver(() => { cy.resize(); });
    resize.observe(container.current);
    return () => { resize.disconnect(); cy.destroy(); };
  }, [data, dark, onSelect]);
  return <div className="network-stage"><div ref={container} className="network-canvas" role="img" aria-label="Interactive scientific term co-occurrence network. Drag nodes, scroll to zoom, or select a concept from the accessible list." />
    <div className="network-tools"><button onClick={() => graph.current?.zoom((graph.current?.zoom() || 1) * 1.25)} aria-label="Zoom in">+</button><button onClick={() => graph.current?.zoom((graph.current?.zoom() || 1) / 1.25)} aria-label="Zoom out">−</button><button onClick={() => { graph.current?.fit(undefined, 50); graph.current?.elements().removeClass('dim'); }}>Fit graph</button></div></div>;
}
