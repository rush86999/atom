/**
 * mockData Fixtures Unit Tests
 *
 * Validates the shape/integrity of every mock fixture exported from
 * src/test-utils/mockData.ts — guards against accidental schema drift
 * and exercises the full module so coverage is meaningful.
 */

import mockDataModule, {
  mockUser,
  mockUsers,
  mockAgents,
  mockCanvases,
  mockWorkflows,
  mockWorkflowExecutions,
  mockEpisodes,
  mockConversations,
  mockMessages,
  mockDeviceInfo,
  mockDevicePermissions,
  mockNotifications,
  mockFormData,
  mockChartData,
  mockPendingActions,
} from '../mockData';

describe('mockData fixtures', () => {
  it('exports a default bundle with every named fixture', () => {
    expect(mockDataModule.user).toBe(mockUser);
    expect(mockDataModule.users).toBe(mockUsers);
    expect(mockDataModule.agents).toBe(mockAgents);
    expect(mockDataModule.canvases).toBe(mockCanvases);
    expect(mockDataModule.workflows).toBe(mockWorkflows);
    expect(mockDataModule.workflowExecutions).toBe(mockWorkflowExecutions);
    expect(mockDataModule.episodes).toBe(mockEpisodes);
    expect(mockDataModule.conversations).toBe(mockConversations);
    expect(mockDataModule.messages).toBe(mockMessages);
    expect(mockDataModule.deviceInfo).toBe(mockDeviceInfo);
    expect(mockDataModule.devicePermissions).toBe(mockDevicePermissions);
    expect(mockDataModule.notifications).toBe(mockNotifications);
    expect(mockDataModule.formData).toBe(mockFormData);
    expect(mockDataModule.chartData).toBe(mockChartData);
    expect(mockDataModule.pendingActions).toBe(mockPendingActions);
  });

  describe('users', () => {
    it('has a well-formed user', () => {
      expect(mockUser.id).toBe('user-123');
      expect(mockUser.email).toMatch(/@/);
      expect(mockUser.createdAt).toMatch(/^\d{4}-\d{2}-\d{2}/);
    });

    it('mockUsers references the same user', () => {
      expect(mockUsers).toHaveLength(1);
      expect(mockUsers[0]).toBe(mockUser);
    });
  });

  describe('agents', () => {
    it('covers all four maturity levels', () => {
      const levels = mockAgents.map((a: any) => a.maturityLevel);
      expect(levels).toEqual(
        expect.arrayContaining(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
      );
    });

    it('every agent has the required fields', () => {
      mockAgents.forEach((agent: any) => {
        expect(agent.id).toBeTruthy();
        expect(agent.name).toBeTruthy();
        expect(Array.isArray(agent.capabilities)).toBe(true);
        expect(typeof agent.isActive).toBe('boolean');
      });
    });
  });

  describe('canvases', () => {
    it('covers multiple canvas types', () => {
      const types = mockCanvases.map((c: any) => c.type);
      expect(new Set(types).size).toBeGreaterThanOrEqual(3);
    });

    it('every canvas has the required fields', () => {
      mockCanvases.forEach((canvas: any) => {
        expect(canvas.id).toBeTruthy();
        expect(canvas.title).toBeTruthy();
        expect(canvas.type).toBeTruthy();
      });
    });
  });

  describe('workflows and executions', () => {
    it('workflows have id/name/active flag', () => {
      mockWorkflows.forEach((wf: any) => {
        expect(wf.id).toBeTruthy();
        expect(wf.name).toBeTruthy();
        expect(typeof wf.isActive).toBe('boolean');
      });
    });

    it('workflow executions reference workflows', () => {
      expect(mockWorkflowExecutions.length).toBeGreaterThan(0);
      mockWorkflowExecutions.forEach((ex: any) => {
        expect(ex.id).toBeTruthy();
        expect(ex.status).toBeTruthy();
      });
    });
  });

  describe('episodes and conversations', () => {
    it('episodes have title and summary fields', () => {
      mockEpisodes.forEach((ep: any) => {
        expect(ep.id).toBeTruthy();
        expect(ep.title).toBeTruthy();
        expect(ep.summary).toBeTruthy();
      });
    });

    it('conversations have agent linkage', () => {
      mockConversations.forEach((conv: any) => {
        expect(conv.id).toBeTruthy();
        expect(conv.agent_id || conv.agentId).toBeTruthy();
      });
    });

    it('messages belong to a conversation', () => {
      mockMessages.forEach((msg: any) => {
        expect(msg.id).toBeTruthy();
        expect(msg.conversation_id || msg.conversationId).toBeTruthy();
      });
    });
  });

  describe('device fixtures', () => {
    it('deviceInfo describes a device', () => {
      expect(mockDeviceInfo.osName || mockDeviceInfo.platform).toBeTruthy();
      expect(mockDeviceInfo.modelName || mockDeviceInfo.model).toBeTruthy();
    });

    it('devicePermissions gate capabilities', () => {
      expect(['granted', 'denied']).toContain(mockDevicePermissions.camera);
      expect(['granted', 'denied']).toContain(mockDevicePermissions.location);
      expect(['granted', 'denied']).toContain(mockDevicePermissions.notifications);
      expect(['granted', 'denied']).toContain(mockDevicePermissions.biometric);
    });
  });

  describe('notifications', () => {
    it('notifications have content', () => {
      mockNotifications.forEach((n: any) => {
        expect(n.id).toBeTruthy();
        expect(n.title || n.body || n.message).toBeTruthy();
      });
    });
  });

  describe('form and chart data', () => {
    it('formData carries a form submission', () => {
      expect(mockFormData.name).toBeTruthy();
      expect(mockFormData.email).toMatch(/@/);
      expect(mockFormData.terms).toBe(true);
    });

    it('chartData has all three chart types', () => {
      expect(mockChartData.line.datasets).toHaveLength(1);
      expect(mockChartData.bar.labels.length).toBeGreaterThan(0);
      expect(mockChartData.pie.datasets[0].data).toHaveLength(3);
    });
  });

  describe('pending actions', () => {
    it('pending actions have retry metadata', () => {
      mockPendingActions.forEach((action: any) => {
        expect(action.id).toBeTruthy();
        expect(action.type).toBeTruthy();
        expect(typeof action.retryCount).toBe('number');
      });
    });
  });
});
