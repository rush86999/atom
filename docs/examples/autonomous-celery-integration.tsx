//atom/examples/autonomous-celery-integration.tsx

import React, { useState, useEffect } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

// Celery Integration for autonomous workflows
interface CeleryAutonomousConfig {
  workflowId: string;
  apiEndpoint: string;
}

class CeleryAutonomousSystem {
  private config: CeleryAutonomousConfig;

  constructor(config: CeleryAutonomousConfig) {
    this.config = config;
  }

  async registerAutonomousTrigger(
    triggerType: 'web-polling' | 'api-monitoring' | 'sales-threshold',
    parameters: any,
    schedule?: string
  ): Promise<string> {
    const response = await fetch(`${this.config.apiEndpoint}/triggers/smart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workflow_id: this.config.workflowId,
        trigger_type: triggerType,
        parameters,
        schedule,
        enable_learning: true
      })
    });
    const result = await response.json();
    return result.id;
  }

  async getWorkflowExecutions(): Promise<any[]> {
    const response = await fetch(`${this.config.apiEndpoint}/metrics/${this.config.workflowId}`);
    return await response.json();
  }

  async triggerWorkflowManually(): Promise<void> {
    await fetch(`${this.config.apiEndpoint}/workflows/${this.config.workflowId}/trigger`, {
      method: 'POST'
    });
  }
}

// Enhanced React Flow with autonomous capabilities
const AutonomousWorkflowDashboard: React.FC = () => {
  // Sample workflow data matching your existing React Flow structure
  const initialNodes: Node[] = [
    {
      id: 'smart-trigger',
      type: 'smartTrigger',
      position: { x: 50, y: 50 },
      data: {
        label: 'Smart Sales Monitor',
        config: {
          type: 'sales-threshold',
          threshold: 25,
          frequency: '*/15 * * * *', // Every 15 minutes via Celery
          autoOptimize: true
        }
      }
    },
    {
      id: 'gmail-scan',
      type: 'gmailTrigger',
      position: { x: 300, y: 50 },
      data: {
        query: 'is:new from:customer@company.com',
        maxResults: 10
      }
    },
    {
      id: 'ai-process',
      type: 'aiTask',
      position: { x: 550, y: 50 },
      data: {
        prompt: 'Identify urgent customer inquiries from this email'
      }
    },
    {
      id: 'notion-sync',
      type: 'notionAction',
      position: { x: 800, y: 50 },
      data: {
        databaseId: 'customer_support_db'
      }
    }
  ];

  const initialEdges: Edge[] = [
    {
      id: 'e1-2',
      source: 'smart-trigger',
      target: 'gmail-scan',
      animated: true,
      style: { stroke: '#10b981' }
    },
    {
      id: 'e2-3',
      source: 'gmail-scan',
      target: 'ai-process',
      animated: true
    },
    {
      id: 'e3-4',
      source: 'ai-process',
      target: 'notion-sync',
      animated: true
    }
  ];

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [executions, setExecutions] = useState([]);
  const [metrics, setMetrics] = useState({
    success_rate: 0.95,
    avg_duration: 45,
    total_executions: 0
  });
  const [isLoading, setIsLoading] = useState(false);

  // Enhanced with autonomous Celery integration
  const autonomousSystem = new CeleryAutonomousSystem({
    workflowId: 'demo-autonomous-workflow',
    apiEndpoint: 'http://localhost:8004'
  });

  useEffect(() => {
    loadMetrics();
    const interval = setInterval(() => {
      loadMetrics();
    }, 30000); // Auto-update every 30s
    return () => clearInterval(interval);
  }, []);

  const loadMetrics = async () => {
    try {
      const data = await autonomousSystem.getWorkflowExecutions();
      setExecutions(data);
      setMetrics({
        success_rate: data.filter(e => e.success).length /
