import React, { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CheckCircle2, Clock, AlertCircle, Users, TrendingUp, DollarSign, Mail, Calendar } from 'lucide-react';
import { ConversationalOrchestration } from '../../orchestration/ConversationalOrchestration';

interface WorkflowStatus {
  id: string;
  type: string;
  status: 'running' | 'completed' | 'failed' | 'pending';
  progress: number;
  title: string;
  description: string;
  agentsAssigned: string[];
  estimatedCompletion: string;
  lastUpdate: Date;
  results?: any;
}

interface AgentStatus {
  id: string;
  name: string;
  status: 'healthy' | 'degraded' | 'critical';
  confidence: number;
  skills: string[];
  activeTasks: number;
  successRate: number;
}

interface SystemMetrics {
  totalWorkflows: number;
  completedWorkflows: number;
  successRate: number;
  activeAgents: number;
  totalAgents: number;
  averageDuration: string;
}

export default function OrchestrationDashboard() {
  const [workflows, setWorkflows] = useState<WorkflowStatus[]>([]);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [metrics, setMetrics] = useState<SystemMetrics>({
    totalWorkflows: 0,
    completedWorkflows: 0,
    successRate: 0,
    activeAgents: 0,
    totalAgents: 0,
    averageDuration: '0s'
+  });
+
+  const conversationalOrchestration = new ConversationalOrchestration();
+
+  // Initialize dashboard
+  useEffect(() => {
+    loadDashboardData();
+    const interval = setInterval(loadDashboardData, 5000);
+    return () => clearInterval(interval);
+  }, []);
+
+  const loadDashboardData = useCallback(() => {
+    // This would connect to your real orchestration manager
+    const mockWorkflows: WorkflowStatus[] = [
+      {
+        id: 'wf_20241215_001',
+        type: 'financial-planning',
+        status: 'running',
+        progress: 75,
+        title: 'Retirement & Business Growth Strategy',
+        description: 'Creating comprehensive plan for retiring at 55 while scaling business',
+        agentsAssigned: ['Business Intelligence Officer', 'Financial Advisor', 'Operations Manager'],
+        estimatedCompletion: '2 hours',
+        lastUpdate: new Date(),
+        results: {
+          newGoals: ['Retirement at 55 with $200k', 'Expand to 3 locations'],
+          projectedSavings: '$50,000/year',
+          timeSaved: '6 hours/week'
+        }
+      },
+      {
+        id: 'wf_20241215_002',
+        type: 'customer-automation',
+        status: 'completed',
+        progress: 100,
+        title: 'Customer Retention System',
+        description: 'Automated follow-up campaigns and loyalty program',
+        agentsAssigned: ['Customer Experience Manager', 'Marketing Coordinator'],
+        estimatedCompletion: 'Completed',
+        lastUpdate: new Date(Date.now() - 3600000),
+        results: {
+          retentionIncrease: '40%',
+          emailsSent: ['Birthday campaigns', 'Purchase follow-ups'],
+          timeSaved: '8 hours/week'
+        }
+      }
+    ];
+
+    const mockAgents: AgentStatus[] = [
+      {
+        id: 'business-strategist',
+        name: 'Business Intelligence Officer',
+        status: 'healthy',
+        confidence: 0.92,
+        skills: ['market-analysis', 'roi-calculation', 'competitive-intelligence'],
+        activeTasks: 2,
+        successRate: 0.95
+      },
+      {
+        id: 'financial-planner',
+        name: 'Personal Finance Advisor',
+        status: 'healthy',
+        confidence: 0.94,
+        skills: ['retirement-planning', 'tax-optimization', 'investment-strategy'],
+        activeTasks: 1,
+        successRate: 0.98
+      }
+    ];
+
+    setWorkflows(mockWorkflows);
+    setAgents(mockAgents);
+    setMetrics({
+      total
