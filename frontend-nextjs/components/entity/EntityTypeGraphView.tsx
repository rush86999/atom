import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import axios from 'axios';
import { 
  X,
  Info,
  Layers,
  Search,
  Maximize2,
  Minimize2,
  RefreshCw,
  Hash
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface EntityType {
  id: string;
  slug: string;
  display_name: string;
  description?: string;
  json_schema: any;
  is_system: boolean;
  version: number;
}

interface Node extends d3.SimulationNodeDatum {
  id: string;
  slug: string;
  display_name: string;
  is_system: boolean;
  property_count: number;
  x?: number;
  y?: number;
}

interface Link extends d3.SimulationLinkDatum<Node> {
  source: string | Node;
  target: string | Node;
}

export const EntityTypeGraphView: React.FC<{ workspaceId: string }> = ({ workspaceId }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [entityTypes, setEntityTypes] = useState<EntityType[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState<EntityType | null>(null);
  const [search, setSearch] = useState('');

  const width = 800;
  const height = 600;

  const fetchEntityTypes = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/entity-types', {
        params: { workspace_id: workspaceId, include_system: true }
      });
      const data = response.data.success ? response.data.data : response.data;
      setEntityTypes(Array.isArray(data) ? data : (data.entity_types || []));
    } catch (err) {
      console.error('Failed to fetch entity types for graph:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntityTypes();
  }, [workspaceId]);

  // Process data for D3
  const graphData = useMemo(() => {
    const nodes: Node[] = entityTypes.map(et => ({
      id: et.slug,
      slug: et.slug,
      display_name: et.display_name,
      is_system: et.is_system,
      property_count: Object.keys(et.json_schema?.properties || {}).length
    }));

    const links: Link[] = [];
    const typeSlugs = new Set(entityTypes.map(et => et.slug));

    entityTypes.forEach(et => {
      const properties = et.json_schema?.properties || {};
      Object.values(properties).forEach((prop: any) => {
        // Simple relationship detection: look for $ref or property names that match other slugs
        let targetSlug = '';
        if (prop.$ref && typeof prop.$ref === 'string') {
          targetSlug = prop.$ref.split('/').pop() || '';
        }

        if (targetSlug && typeSlugs.has(targetSlug) && targetSlug !== et.slug) {
          links.push({ source: et.slug, target: targetSlug });
        }
      });
    });

    return { nodes, links };
  }, [entityTypes]);

  useEffect(() => {
    if (!svgRef.current || graphData.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const container = svg.append('g');

    // Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 4])
      .on('zoom', (event) => {
        container.attr('transform', event.transform);
      });
    svg.call(zoom as any);

    // Forces
    const simulation = d3.forceSimulation<Node>(graphData.nodes)
      .force('link', d3.forceLink<Node, Link>(graphData.links).id(d => d.id).distance(150))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(60));

    // Links
    const link = container.append('g')
      .selectAll('line')
      .data(graphData.links)
      .join('line')
      .attr('stroke', 'rgba(255,255,255,0.1)')
      .attr('stroke-width', 2)
      .attr('marker-end', 'url(#arrowhead)');

    // Arrowhead marker
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('svg:path')
      .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
      .attr('fill', 'rgba(255,255,255,0.2)');

    // Nodes
    const node = container.append('g')
      .selectAll('g')
      .data(graphData.nodes)
      .join('g')
      .call((d3.drag<SVGGElement, Node>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }) as any))
      .on('click', (event, d: Node) => {
        const fullType = entityTypes.find(et => et.slug === d.slug);
        if (fullType) setSelectedType(fullType);
        event.stopPropagation();
      });

    // Node Circle
    node.append('circle')
      .attr('r', d => 15 + Math.sqrt(d.property_count) * 2)
      .attr('fill', d => d.is_system ? '#8b5cf6' : '#10b981')
      .attr('stroke', 'rgba(255,255,255,0.2)')
      .attr('stroke-width', 2)
      .attr('class', 'cursor-pointer hover:stroke-white transition-all shadow-[0_0_15px_rgba(0,0,0,0.5)]');

    // Labels
    node.append('text')
      .text(d => d.display_name)
      .attr('dy', d => 25 + Math.sqrt(d.property_count) * 2)
      .attr('text-anchor', 'middle')
      .attr('class', 'text-[10px] font-bold fill-white/60 pointer-events-none select-none uppercase tracking-tighter');

    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as Node).x!)
        .attr('y1', d => (d.source as Node).y!)
        .attr('x2', d => (d.target as Node).x!)
        .attr('y2', d => (d.target as Node).y!);

      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    return () => { simulation.stop(); };
  }, [graphData, entityTypes]);

  return (
    <div className="relative h-[600px] bg-zinc-950 rounded-xl border border-white/5 overflow-hidden group">
      {loading && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-2">
            <RefreshCw className="w-6 h-6 text-primary animate-spin" />
            <span className="text-xs text-white/40 uppercase font-black">Building Graph...</span>
          </div>
        </div>
      )}

      <div className="absolute top-4 left-4 z-20 flex flex-col gap-2">
        <div className="flex items-center gap-2 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 shadow-xl">
          <div className="w-2 h-2 rounded-full bg-[#8b5cf6]" />
          <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">System Type</span>
        </div>
        <div className="flex items-center gap-2 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 shadow-xl">
          <div className="w-2 h-2 rounded-full bg-[#10b981]" />
          <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">Custom Type</span>
        </div>
      </div>

      <svg 
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox={`0 0 ${width} ${height}`}
        className="cursor-move"
      />

      {/* Details Panel */}
      {selectedType && (
        <div className="absolute top-4 right-4 bottom-4 w-72 bg-zinc-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl z-20 flex flex-col animate-in slide-in-from-right duration-300">
          <div className="p-4 border-b border-white/10 flex items-center justify-between">
            <h3 className="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
              <Layers className="w-3 h-3 text-primary" />
              Type Details
            </h3>
            <button onClick={() => setSelectedType(null)} className="p-1 hover:bg-white/5 rounded-full text-white/40 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg font-bold text-white leading-tight">{selectedType.display_name}</span>
                <Badge variant="outline" className="text-[8px] h-4 bg-white/5 border-white/10 text-white/40 px-1">v{selectedType.version}</Badge>
              </div>
              <code className="text-[9px] text-primary/80 font-mono bg-primary/10 px-1.5 py-0.5 rounded italic">{selectedType.slug}</code>
            </div>

            {selectedType.description && (
              <p className="text-[11px] text-white/60 leading-relaxed italic border-l-2 border-white/10 pl-3">
                "{selectedType.description}"
              </p>
            )}

            <div className="space-y-2">
              <span className="text-[9px] font-black text-white/30 uppercase tracking-widest flex items-center gap-1">
                <Hash className="w-2.5 h-2.5" /> Properties ({Object.keys(selectedType.json_schema?.properties || {}).length})
              </span>
              <div className="space-y-1.5">
                {Object.entries(selectedType.json_schema?.properties || {}).map(([name, def]: [string, any]) => (
                  <div key={name} className="bg-white/5 p-2 rounded border border-white/5 hover:border-white/10 transition-colors">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-bold text-white/90 truncate">{name}</span>
                      <span className="text-[9px] text-white/30 font-mono italic">{def.type || 'any'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

