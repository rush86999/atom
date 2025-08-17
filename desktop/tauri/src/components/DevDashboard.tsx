import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { open } from '@tauri-apps/api/shell';
import { writeText } from '@tauri-apps/api/clipboard';

interface CloudDeployment {
  id: string;
  url: string;
  status: 'building' | 'ready' | 'failed';
  timestamp: string;
  branch: string;
  commit: string;
  provider: 'vercel' | 'netlify' | 'render';
  metrics: {
    buildTime: number;
    bundleSize: number;
    lighthouseScore: number;
  };
}

interface RepositoryInfo {
  name: string;
  branch: string;
  lastCommit: string;
  isClean: boolean;
}

interface DevelopmentSession {
  active: boolean;
  startTime: string;
  changes: number;
  previewUrl?: string;
}

const DevDashboard: React.FC = () => {
  const [deployments, setDeployments] = useState<CloudDeployment[]>([]);
  const [repoInfo, setRepoInfo] = useState<RepositoryInfo>({
    name: 'atom-web-dev',
    branch: 'main',
    lastCommit: 'Loading...',
    isClean: true
  });
  const [devSession, setDevSession] = useState<DevelopmentSession>({
    active: false,
    startTime: '',
    changes: 0
  });
  const [atomStatus, setAtomStatus] = useState<string>('idle');
  const [buildPopup, setBuildPopup] = useState<CloudDeployment | null>(null);

  useEffect(() => {
    // Initialize Git connection
    checkRepoStatus();

    // Start WebSocket connection to cloud services
    connectToCloud();

    // Setup event listeners
    const cleanup = setupEventListeners();

    return cleanup;
  }, []);

  const checkRepoStatus = async () => {
    try {
      const status = await invoke('get_repo_status');
      setRepoInfo(status as RepositoryInfo);
    } catch (error) {
      console.error('Failed to get repo status:', error);
    }
  };

  const connectToCloud = async () => {
    // Connect to deployment WebSocket
    const unlisten1 = await listen<CloudDeployment>('deployment-update', (event) => {
      setDeployments(prev => [event.payload, ...prev].slice(0, 5));

      // Show popup for new deployments
      if (event.payload.status === 'ready') {
        setBuildPopup(event.payload);
        setTimeout(() => setBuildPopup(null), 5000);
      }
    });

    // Listen for AI agent updates
    const unlisten2 = await listen<string>('atom-status', (event) => {
      setAtomStatus(event.payload);
    });

    return () => {
      unlisten1();
      unlisten2();
    };
  };

  const setupEventListeners = () => {
    // File watcher for live reload
    const interval = setInterval(async () => {
      try {
        const changes = await invoke('get_uncommited_changes');
        const changeCount = (changes as string[]).length;

        if (changeCount > 0 && !devSession.active) {
          startDevelopmentSession();
        }

        setDevSession(prev => ({ ...prev, changes: changeCount }));
      } catch (error) {
        console.error('Failed to check changes:', error);
      }
    }, 10000);

    return () => clearInterval(interval);
  };

  const startDevelopmentSession = () => {
    setDevSession({
      active: true,
      startTime: new Date().toISOString(),
      changes: 0
    });
  };

  const previewDeployment = async (deployment: CloudDeployment) => {
    await open(deployment.url);
  };

  const copyPreviewUrl = async (url: string) => {
    await writeText(url);
  };

  const triggerBuild = async () => {
    try {
      await invoke('trigger_cloud_build');
      setAtomStatus('building');
    } catch (error) {
      console.error('Failed to trigger build:', error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return 'text-green-600';
      case 'building': return 'text-yellow-600';
      case 'failed': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ready': return '✅';
      case 'building': return '🔄';
      case 'failed': return '❌';
      default: return '⏳';
    }
  };

  const formatTime
