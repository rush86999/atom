atom/desktop/tauri/src/components/MainDevInterface.tsx

import React, { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { open } from '@tauri-apps/api/shell';
import { writeText } from '@tauri-apps/api/clipboard';
import { message as showDialog } from '@tauri-apps/api/dialog';

interface DevelopmentProject {
  id: string;
  name: string;
  githubRepo: string;
  cloudProvider: string;
  status: 'initializing' | 'building' | 'ready' | 'failed' | 'updating';
  liveUrl: string;
  previewUrl: string;
  lastBuildTime?: number;
  performance?: {
    performance: number;
    accessibility: number;
    bestPractices: number;
+    seo: number;
+  };
  changes: number;
}

interface BuildMessage {
+  id: string;
+  timestamp: Date;
+  content: string;
+  status: 'info' | 'building' | 'success' | 'error';
+  visible: boolean;
}

interface WebDevAgentConversation {
+  id: string;
+  instruction: string;
+  response: string;
+  timestamp: Date;
+  status: 'pending' | 'processing' | 'complete' | 'error';
+  urls?: string[];
+}

const MainDevInterface: React.FC = () => {
+  const [activeProject, setActiveProject] = useState<DevelopmentProject | null>(null);
+  const [messages, setMessages] = useState<BuildMessage[]>([]);
+  const [chatInput, setChatInput] = useState('');
+  const [isProcessing, setIsProcessing] = useState(false);
+  const [projectHistory, setProjectHistory] = useState<DevelopmentProject[]>([]);
+  const [conversationHistory, setConversationHistory] = useState<WebDevAgentConversation[]>([]);

+  useEffect(() => {
+    setupWebSocketConnection();
+    loadProjectHistory();
+    setupEventListeners();
+  }, []);

+  const setupWebSocketConnection = useCallback(() => {
+    const wsUrl = 'wss://atom-cloud.webhook.app/dev-updates';
+    const ws = new WebSocket(wsUrl);
+
+    ws.onmessage = (event) => {
+      const data = JSON.parse(event.data);
+      updateDeploymentStatus(data);
+    };
+
+    ws.onerror = (error) => {
+      addMessage('WebSocket connection failed', 'error');
+    };
+  }, []);

+  const setupEventListeners = useCallback(async () => {
+    await listen('cloud-deployment-ready', (event) => {
+      const data = event.payload as DevelopmentProject;
+      setActiveProject(data);
+      addMessage('✅ Deployment ready! URL copied to clipboard', 'success');
+
+      if (data.liveUrl) {
+        writeText(data.liveUrl);
+      }
+    });

+    await listen('build-started', () => {
+      setIsProcessing(true);
+      addMessage('🔄 Starting cloud build...', 'building');
+    });

+    await listen('build-failed', (event) => {
+      const error = event.payload as string;
+      setIsProcessing(false);
+      addMessage(`❌ Build failed: ${error}`, 'error');
+      showDialog(error, { title: 'Build Error', type: 'error' });
+    });
+  }, []);

+  const createNewProject = async (name: string, instruction: string) => {
+    setIsProcessing(true);
+
+    const project: Omit<DevelopmentProject, 'id'> = {
+      name,
+      githubRepo: `atom-dev/${name}`,
+      cloudProvider: 'vercel',
+      status: 'initializing',
+      liveUrl: '',
+      previewUrl: '',
+      changes: 0
+    };

+    const newProject = await invoke('create_cloud_project', { project, instruction });
+    setActiveProject(newProject as DevelopmentProject);
+
+    const conversation: WebDevAgentConversation = {
+      id: `conv-${Date.now()}`,
+      instruction,
+      response: 'Creating project in cloud...',
+      timestamp: new Date(),
+      status: 'processing'
+    };
+
+    setConversationHistory(prev => [conversation, ...prev]);
+    addMessage(`🚀 Creating ${name} via cloud build...`, 'building');
+  };

+  const processInstruction = async (instruction: string) => {
+    if (!activeProject) {
+      const projectName = prompt('Project name?');
+
