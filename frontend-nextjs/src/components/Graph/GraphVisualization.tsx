'use client';

import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { 
  Plus, 
  Search, 
  Settings, 
  Filter, 
  Trash2, 
  Link as LinkIcon, 
  Info, 
  X,
  ChevronRight,
  Database,
  User,
  Ticket,
  ClipboardList,
  Layout,
  Layers,
  Zap
} from 'lucide-react';

interface Node extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  type: string;
  description: string;
  properties: Record<string, any>;
  x?: number;
  y?: number;
}

interface Link extends d3.SimulationLinkDatum<Node> {
  id: string;
  source: string | Node;
  target: string | Node;
  type: string;
  properties: Record<string, any>;
}

interface GraphData {
  nodes: Node[];
  links: Link[];
}

export default function GraphVisualization() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [isAddNodeOpen, setIsAddNodeOpen] = useState(false);
  const [isAddLinkOpen, setIsAddLinkOpen] = useState(false);
  
  // New Node Form State
  const [newNode, setNewNode] = useState({
    name: '',
    type: 'Concept',
    description: '',
    canonical_type: '',
    canonical_id: '',
    specialty: ''
  });
  
  const [canonicalSearch, setCanonicalSearch] = useState('');
  const [canonicalResults, setCanonicalResults] = useState<any[]>([]);
  const [isSearchingCanonical, setIsSearchingCanonical] = useState(false);

  // Constants
  const width = 1000;
  const height = 800;
  const colors: Record<string, string> = {
    User: '#3b82f6',      // blue
    Workspace: '#10b981', // emerald
    Team: '#f59e0b',      // amber
    Ticket: '#ef4444',    // red
    Formula: '#8b5cf6',   // violet
    Task: '#6366f1',      // indigo
    Concept: '#6b7280',   // gray
    default: '#14b8a6'    // teal
  };

  useEffect(() => {
    fetchGraphData();
  }, []);

  const fetchGraphData = async () => {
    setLoading(true);
    try {
      const [nodesRes, linksRes] = await Promise.all([
        fetch('/api/graphrag/entities?workspace_id=default_workspace&limit=200'),
        fetch('/api/graphrag/relationships?workspace_id=default_workspace&limit=300')
      ]);
      
      const nodesData = await nodesRes.json();
      const linksData = await linksRes.json();
      
      if (nodesData.success && linksData.success) {
        setData({
          nodes: nodesData.data.entities || [],
          links: linksData.data.relationships.map((l: any) => ({
            ...l,
            source: l.from_entity,
            target: l.to_entity
          })) || []
        });
      }
    } catch (err) {
      console.error('Failed to fetch graph data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!svgRef.current || data.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const container = svg.append('g');

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        container.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Simulation
    const simulation = d3.forceSimulation<Node>(data.nodes)
      .force('link', d3.forceLink<Node, Link>(data.links).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(50));

    // Links
    const link = container.append('g')
      .selectAll('line')
      .data(data.links)
      .join('line')
      .attr('stroke', '#e5e7eb')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.6);

    // Nodes
    const node = container.append('g')
      .selectAll('g')
      .data(data.nodes)
      .join('g')
      .call(d3.drag<SVGGElement, Node>()
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
        }))
      .on('click', (event, d) => {
        setSelectedNode(d);
        event.stopPropagation();
      });

    node.append('circle')
      .attr('r', 20)
      .attr('fill', d => colors[d.type] || colors.default)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .attr('class', 'cursor-pointer hover:opacity-80 transition-opacity drop-shadow-sm');

    node.append('text')
      .text(d => d.name)
      .attr('dy', 35)
      .attr('text-anchor', 'middle')
      .attr('class', 'text-xs font-medium fill-gray-700 pointer-events-none select-none');

    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as Node).x!)
        .attr('y1', d => (d.source as Node).y!)
        .attr('x2', d => (d.target as Node).x!)
        .attr('y2', d => (d.target as Node).y!);

      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    return () => simulation.stop();
  }, [data]);

  const handleAddNode = async () => {
    try {
      const res = await fetch('/api/graphrag/entities?workspace_id=default_workspace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newNode.name,
          type: newNode.type,
          description: newNode.description,
          properties: {
            canonical_type: newNode.canonical_type,
            canonical_id: newNode.canonical_id,
            specialty: newNode.specialty
          }
        })
      });
      
      const result = await res.json();
      if (result.success) {
        setIsAddNodeOpen(false);
        setNewNode({ name: '', type: 'Concept', description: '', canonical_type: '', canonical_id: '', specialty: '' });
        fetchGraphData();
      }
    } catch (err) {
      console.error('Failed to add node:', err);
    }
  };

  const searchCanonical = async (query: string) => {
    if (!newNode.canonical_type || query.length < 2) return;
    
    setIsSearchingCanonical(true);
    try {
      const res = await fetch(`/api/graphrag/canonical-search?workspace_id=default_workspace&type=${newNode.canonical_type}&q=${query}`);
      const result = await res.json();
      if (result.success) {
        setCanonicalResults(result.data.results || []);
      }
    } catch (err) {
      console.error('Canonical search failed:', err);
    } finally {
      setIsSearchingCanonical(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden font-sans">
      {/* Sidebar - Controls */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col shadow-sm z-10">
        <div className="p-6 border-b border-gray-100 bg-white sticky top-0">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-indigo-600 p-2 rounded-lg shadow-md">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">GraphRAG Explorer</h1>
          </div>
          
          <div className="flex flex-col gap-3">
            <button 
              onClick={() => setIsAddNodeOpen(true)}
              className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white py-2.5 px-4 rounded-xl font-semibold transition-all shadow-sm active:scale-95"
            >
              <Plus className="w-4 h-4" />
              Add Entity
            </button>
            <button 
              onClick={() => setIsAddLinkOpen(true)}
              className="w-full flex items-center justify-center gap-2 bg-white hover:bg-gray-50 text-gray-700 py-2.5 px-4 rounded-xl font-semibold border border-gray-200 transition-all shadow-sm active:scale-95"
            >
              <LinkIcon className="w-4 h-4" />
              Add Relationship
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {selectedNode ? (
            <div className="space-y-6 animate-in slide-in-from-right duration-300">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-gray-900">Entity Details</h2>
                <button 
                  onClick={() => setSelectedNode(null)} 
                  className="p-1.5 hover:bg-gray-100 rounded-full transition-colors text-gray-400"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              
              <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: colors[selectedNode.type] || colors.default }}></span>
                  <span className="text-xs font-bold uppercase tracking-wider text-gray-500">{selectedNode.type}</span>
                </div>
                <h3 className="text-2xl font-bold text-gray-900 mb-2">{selectedNode.name}</h3>
                <p className="text-sm text-gray-600 leading-relaxed mb-4">{selectedNode.description || 'No description available.'}</p>
                
                {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                  <div className="space-y-3 pt-4 border-t border-gray-200">
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Metadata</h4>
                    <div className="space-y-2">
                      {Object.entries(selectedNode.properties).map(([key, val]) => (
                        <div key={key} className="flex flex-col bg-white p-2.5 rounded-xl border border-gray-100 shadow-sm">
                          <span className="text-xs font-semibold text-gray-400">{key}</span>
                          <span className="text-sm font-medium text-gray-700 truncate">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              
              <button className="w-full flex items-center justify-center gap-2 text-red-600 hover:bg-red-50 py-2.5 rounded-xl border border-red-100 px-4 font-semibold transition-colors">
                <Trash2 className="w-4 h-4" />
                Delete Node
              </button>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center px-4">
              <div className="bg-gray-100 p-4 rounded-full mb-4">
                <Info className="w-8 h-8 text-gray-400" />
              </div>
              <p className="text-gray-500 font-medium">Select an entity on the graph to view details and metadata.</p>
            </div>
          )}
        </div>
      </div>

      {/* Main Graph Area */}
      <div className="flex-1 relative bg-white">
        {loading && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/60 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-4">
              <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
              <p className="text-indigo-600 font-bold tracking-tight">Loading Knowledge Graph...</p>
            </div>
          </div>
        )}
        
        <svg 
          ref={svgRef} 
          width="100%" 
          height="100%" 
          viewBox={`0 0 ${width} ${height}`}
          className="cursor-move"
        />

        {/* Legend */}
        <div className="absolute bottom-6 left-6 flex flex-wrap gap-3 bg-white/90 backdrop-blur-md p-4 rounded-2xl shadow-xl border border-white/50 z-10 max-w-sm">
          {Object.entries(colors).map(([type, color]) => (
            <div key={type} className="flex items-center gap-2 bg-gray-50/50 px-3 py-1.5 rounded-full border border-gray-100">
              <div className="w-2.5 h-2.5 rounded-full shadow-sm" style={{ backgroundColor: color }}></div>
              <span className="text-[10px] font-bold text-gray-600 uppercase tracking-wider">{type}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Add Node Modal */}
      {isAddNodeOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-white w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-8 border-b border-gray-100 flex items-center justify-between bg-white sticky top-0">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Add New Entity</h2>
                <p className="text-gray-500 text-sm mt-1">Create a semantic node in your knowledge graph.</p>
              </div>
              <button 
                onClick={() => setIsAddNodeOpen(false)}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <X className="w-6 h-6 text-gray-400" />
              </button>
            </div>
            
            <div className="p-8 space-y-6 max-h-[70vh] overflow-y-auto">
              {/* Type Selection */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1">Entity Type</label>
                  <select 
                    value={newNode.type}
                    onChange={(e) => setNewNode({ ...newNode, type: e.target.value })}
                    className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all appearance-none"
                  >
                    <option value="User">User</option>
                    <option value="Workspace">Workspace</option>
                    <option value="Team">Team</option>
                    <option value="Ticket">Ticket</option>
                    <option value="Formula">Formula</option>
                    <option value="Task">Task</option>
                    <option value="Concept">Concept</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1">Canonical Anchor</label>
                  <select 
                    value={newNode.canonical_type}
                    onChange={(e) => {
                      setNewNode({ ...newNode, canonical_type: e.target.value, canonical_id: '' });
                      setCanonicalResults([]);
                    }}
                    className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all appearance-none"
                  >
                    <option value="">No Anchor (Standalone)</option>
                    <option value="user">Anchor to User</option>
                    <option value="workspace">Anchor to Workspace</option>
                    <option value="team">Anchor to Team</option>
                    <option value="ticket">Anchor to Ticket</option>
                    <option value="formula">Anchor to Formula</option>
                    <option value="task">Anchor to Task</option>
                  </select>
                </div>
              </div>

              {/* Canonical Search */}
              {newNode.canonical_type && (
                <div className="space-y-2 p-5 bg-indigo-50/50 rounded-2xl border border-indigo-100 animate-in slide-in-from-top-4 duration-300">
                  <label className="text-xs font-bold text-indigo-400 uppercase tracking-widest px-1">Search Database Record</label>
                  <div className="relative">
                    <input 
                      type="text"
                      placeholder="Type to search existing records..."
                      value={canonicalSearch}
                      onChange={(e) => {
                        setCanonicalSearch(e.target.value);
                        searchCanonical(e.target.value);
                      }}
                      className="w-full bg-white border border-indigo-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all shadow-sm"
                    />
                    <Search className="absolute left-3 top-3.5 w-4 h-4 text-indigo-300" />
                    {isSearchingCanonical && (
                      <div className="absolute right-3 top-3.5 w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                    )}
                  </div>
                  
                  {canonicalResults.length > 0 && (
                    <div className="mt-3 bg-white rounded-xl border border-indigo-100 shadow-md max-h-40 overflow-y-auto divide-y divide-gray-50">
                      {canonicalResults.map(r => (
                        <div 
                          key={r.id}
                          onClick={() => {
                            setNewNode({ ...newNode, canonical_id: r.id, name: r.name });
                            setCanonicalResults([]);
                            setCanonicalSearch(r.name);
                          }}
                          className={`flex items-center justify-between p-3 hover:bg-indigo-50 cursor-pointer transition-colors ${newNode.canonical_id === r.id ? 'bg-indigo-50' : ''}`}
                        >
                          <span className="text-sm font-medium text-gray-700">{r.name}</span>
                          {newNode.canonical_id === r.id && <Zap className="w-4 h-4 text-indigo-500 fill-indigo-500" />}
                        </div>
                      ))}
                    </div>
                  )}
                  {newNode.canonical_id && (
                    <div className="mt-4 p-3 bg-white/80 rounded-xl border border-indigo-200 border-dashed flex items-center gap-3">
                      <div className="bg-indigo-600 p-1.5 rounded-lg">
                        <Database className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider leading-none mb-1">Anchored Record</span>
                        <span className="text-sm font-bold text-gray-900">{newNode.name}</span>
                      </div>
                    </div>
                  )}
                  
                  {/* Specialty for Users */}
                  {newNode.canonical_type === 'user' && (
                    <div className="mt-4 animate-in slide-in-from-top-2">
                       <label className="text-xs font-bold text-indigo-400 uppercase tracking-widest px-1">User Specialty (Sync)</label>
                       <input 
                        type="text"
                        placeholder="e.g. Sales Director, System Admin"
                        value={newNode.specialty}
                        onChange={(e) => setNewNode({ ...newNode, specialty: e.target.value })}
                        className="w-full mt-2 bg-white border border-indigo-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none shadow-sm"
                      />
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-2">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1">Display Name</label>
                <input 
                  type="text"
                  placeholder="The name shown on graph"
                  value={newNode.name}
                  onChange={(e) => setNewNode({ ...newNode, name: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1">Description</label>
                <textarea 
                  rows={3}
                  placeholder="Briefly describe this entity..."
                  value={newNode.description}
                  onChange={(e) => setNewNode({ ...newNode, description: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all resize-none"
                />
              </div>
            </div>
            
            <div className="p-8 bg-gray-50 border-t border-gray-100 flex gap-3">
              <button 
                onClick={() => setIsAddNodeOpen(false)}
                className="flex-1 px-6 py-3 rounded-xl border border-gray-200 bg-white hover:bg-gray-100 font-bold text-gray-600 transition-all active:scale-95"
              >
                Cancel
              </button>
              <button 
                onClick={handleAddNode}
                disabled={!newNode.name}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:hover:bg-indigo-600 text-white px-6 py-3 rounded-xl font-bold transition-all shadow-lg shadow-indigo-200 active:scale-95"
              >
                Create Hub Node
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
