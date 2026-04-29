/**
 * Mock useAgentStore
 * Placeholder for Zustand store
 */

import create from 'zustand';

interface Agent {
  id: string;
  name: string;
  // Add other agent properties as needed
}

interface AgentStore {
  agents: Agent[];
  selectedAgent: Agent | null;
  // Add other store methods/properties as needed
}

export const useAgentStore = create<AgentStore>(() => ({
  agents: [],
  selectedAgent: null,
}));
