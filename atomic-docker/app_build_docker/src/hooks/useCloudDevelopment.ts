import { useState, useEffect, useCallback } from 'react';
import { open } from '@tauri-apps/api/shell';

export interface CloudProject {
  id: string;
  name: string;
  status: 'initializing' | 'building' | 'ready' | 'failed';
  url: string;
  previewUrl?: string;
  buildLog?: string[];
  createdAt: Date;
  lastUpdate: Date;
}

export interface BuildInstruction {
  id: string;
  text: string;
  type: 'create' | 'update' | 'deploy' | 'optimize';
  status: 'pending' | 'processing' | 'complete' | 'error';
  result?: {
    url: string;
    performance?: {
      score: number;
      description: string;
    };
  };
}

export interface CloudStatus {
  provider: 'vercel' | 'netlify' | 'render';
  currentBuild: CloudProject | null;
  queue: BuildInstruction[];
  lastUpdate: Date;
}

export const useCloudDevelopment = () => {
  const [activeProject, setActiveProject] = useState<CloudProject | null>(null);
  const [buildQueue, setBuildQueue] = useState<BuildInstruction[]>([]);
  const [status, setStatus] = useState<CloudStatus>({
    provider: 'vercel',
    currentBuild: null,
    queue: [],
    lastUpdate: new Date()
+  });
+  const [isConnected, setIsConnected] = useState(false);
+  const [buildHistory, setBuildHistory] = useState<CloudProject[]>([]);

+  // WebSocket connection to cloud services
+  useEffect(() => {
+    const wsUrl = 'wss://atom-dev-api.fly.dev/ws'; // Cloud WebSocket
+    const ws = new WebSocket(wsUrl);

+    ws.onopen = () => setIsConnected(true);
+    ws.onclose = () => {
+      setIsConnected(false);
+      // Auto-reconnect after 2 seconds
+      setTimeout(() => useCloudDevelopment(), 2000);
+    };

+    ws.onmessage = (event) => {
+      const data = JSON.parse(event.data);
+      handleDeploymentUpdate(data);
+    };

+    return () => ws.close();
+  }, []);

+  const handleDeploymentUpdate = (update: Partial<CloudProject>) => {
+    if (update.status === 'ready') {
+      setBuildHistory(prev => [update as CloudProject, ...prev]);
+    }
+
+    setActiveProject(prev => prev?.id === update.id ? { ...prev, ...update } as CloudProject : prev);
+    setStatus(prev => ({ ...prev, lastUpdate: new Date() }));
+  };

+  const createProject = useCallback(async (name: string, template?: string) => {
+    const project: Omit<CloudProject, 'id' | 'createdAt' | 'lastUpdate'> = {
+      name,
+      status: 'initializing',
+      url: '',
+      ...(template && { buildLog: [`Starting ${template} template...`] })
+    };

+    const response = await fetch('https://atom-dev-api.fly.dev/projects', {
+      method: 'POST',
+      headers: { 'Content-Type': 'application/json' },
+      body: JSON.stringify(project)
+    });

+    const created = await response.json();
+    setActiveProject(created);
+
+    return created;
+  }, []);

+  const buildViaConversation = useCallback(async (instruction: string, projectId?: string) => {
+    const buildInstruction: Omit<BuildInstruction, 'id' | 'status' | 'createdAt'> = {
+      text: instruction,
+      type: getInstructionType(instruction),
+    };

+    const response = await fetch('https://atom-dev-api.fly.dev/build', {
+      method: 'POST',
+      headers: { 'Content-Type': 'application/json' },
+      body: JSON.stringify({
+        instruction: buildInstruction,
+        projectId: projectId || activeProject?.id
+      })
+    });

+    const instructionCreated = await response.json();
+    setBuildQueue(prev => [instructionCreated, ...prev]);
+
+    return instructionCreated;
+  }, [activeProject]);

+  const getInstructionType = (text: string): BuildInstruction['type'] => {
+    if (text.includes('create') || text.includes('make') || text.includes('build')) {
+      return 'create';
+    }
+    if (text.includes('update') || text.includes('change') || text.includes('modify')) {
+      return 'update';
+    }
+    if (text.includes('deploy') || text
