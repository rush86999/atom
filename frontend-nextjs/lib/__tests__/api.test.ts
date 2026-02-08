/**
 * Tests for API Client
 *
 * Tests the API client structure and exports
 */

import {
  systemAPI,
  serviceRegistryAPI,
  adminAPI,
  apiUtils,
  byokAPI,
  workflowAPI,
  emailVerificationAPI,
  tenantAPI,
  meetingAPI,
  financialAPI,
} from '../api';

describe('API Client', () => {
  describe('systemAPI', () => {
    it('should export systemAPI object', () => {
      expect(systemAPI).toBeDefined();
      expect(typeof systemAPI).toBe('object');
    });

    it('should have getHealth method', () => {
      expect(systemAPI.getHealth).toBeDefined();
      expect(typeof systemAPI.getHealth).toBe('function');
    });

    it('should have getStatus method', () => {
      expect(systemAPI.getStatus).toBeDefined();
      expect(typeof systemAPI.getStatus).toBe('function');
    });

    it('should have getSystemStatus method', () => {
      expect(systemAPI.getSystemStatus).toBeDefined();
      expect(typeof systemAPI.getSystemStatus).toBe('function');
    });
  });

  describe('serviceRegistryAPI', () => {
    it('should export serviceRegistryAPI object', () => {
      expect(serviceRegistryAPI).toBeDefined();
      expect(typeof serviceRegistryAPI).toBe('object');
    });

    it('should have getServices method', () => {
      expect(serviceRegistryAPI.getServices).toBeDefined();
      expect(typeof serviceRegistryAPI.getServices).toBe('function');
    });

    it('should have getService method', () => {
      expect(serviceRegistryAPI.getService).toBeDefined();
      expect(typeof serviceRegistryAPI.getService).toBe('function');
    });

    it('should have registerService method', () => {
      expect(serviceRegistryAPI.registerService).toBeDefined();
      expect(typeof serviceRegistryAPI.registerService).toBe('function');
    });

    it('should have updateService method', () => {
      expect(serviceRegistryAPI.updateService).toBeDefined();
      expect(typeof serviceRegistryAPI.updateService).toBe('function');
    });

    it('should have deleteService method', () => {
      expect(serviceRegistryAPI.deleteService).toBeDefined();
      expect(typeof serviceRegistryAPI.deleteService).toBe('function');
    });
  });

  describe('byokAPI', () => {
    it('should export byokAPI object', () => {
      expect(byokAPI).toBeDefined();
      expect(typeof byokAPI).toBe('object');
    });

    it('should have getProviders method', () => {
      expect(byokAPI.getProviders).toBeDefined();
      expect(typeof byokAPI.getProviders).toBe('function');
    });

    it('should have getProvider method', () => {
      expect(byokAPI.getProvider).toBeDefined();
      expect(typeof byokAPI.getProvider).toBe('function');
    });

    it('should have configureProvider method', () => {
      expect(byokAPI.configureProvider).toBeDefined();
      expect(typeof byokAPI.configureProvider).toBe('function');
    });
  });

  describe('workflowAPI', () => {
    it('should export workflowAPI object', () => {
      expect(workflowAPI).toBeDefined();
      expect(typeof workflowAPI).toBe('object');
    });
  });

  describe('emailVerificationAPI', () => {
    it('should export emailVerificationAPI object', () => {
      expect(emailVerificationAPI).toBeDefined();
      expect(typeof emailVerificationAPI).toBe('object');
    });

    it('should have sendVerificationEmail method', () => {
      expect(emailVerificationAPI.sendVerificationEmail).toBeDefined();
      expect(typeof emailVerificationAPI.sendVerificationEmail).toBe('function');
    });
  });

  describe('tenantAPI', () => {
    it('should export tenantAPI object', () => {
      expect(tenantAPI).toBeDefined();
      expect(typeof tenantAPI).toBe('object');
    });

    it('should have getTenantBySubdomain method', () => {
      expect(tenantAPI.getTenantBySubdomain).toBeDefined();
      expect(typeof tenantAPI.getTenantBySubdomain).toBe('function');
    });

    it('should have getTenantContext method', () => {
      expect(tenantAPI.getTenantContext).toBeDefined();
      expect(typeof tenantAPI.getTenantContext).toBe('function');
    });
  });

  describe('adminAPI', () => {
    it('should export adminAPI object', () => {
      expect(adminAPI).toBeDefined();
      expect(typeof adminAPI).toBe('object');
    });

    it('should have getAdminUsers method', () => {
      expect(adminAPI.getAdminUsers).toBeDefined();
      expect(typeof adminAPI.getAdminUsers).toBe('function');
    });

    it('should have updateAdminLastLogin method', () => {
      expect(adminAPI.updateAdminLastLogin).toBeDefined();
      expect(typeof adminAPI.updateAdminLastLogin).toBe('function');
    });
  });

  describe('meetingAPI', () => {
    it('should export meetingAPI object', () => {
      expect(meetingAPI).toBeDefined();
      expect(typeof meetingAPI).toBe('object');
    });

    it('should have getMeetingAttendance method', () => {
      expect(meetingAPI.getMeetingAttendance).toBeDefined();
      expect(typeof meetingAPI.getMeetingAttendance).toBe('function');
    });
  });

  describe('financialAPI', () => {
    it('should export financialAPI object', () => {
      expect(financialAPI).toBeDefined();
      expect(typeof financialAPI).toBe('object');
    });

    it('should have getNetWorthSummary method', () => {
      expect(financialAPI.getNetWorthSummary).toBeDefined();
      expect(typeof financialAPI.getNetWorthSummary).toBe('function');
    });

    it('should have listFinancialAccounts method', () => {
      expect(financialAPI.listFinancialAccounts).toBeDefined();
      expect(typeof financialAPI.listFinancialAccounts).toBe('function');
    });
  });

  describe('apiUtils', () => {
    describe('generateRequestId', () => {
      it('should generate unique request IDs', () => {
        const id1 = apiUtils.generateRequestId();
        const id2 = apiUtils.generateRequestId();

        expect(id1).toMatch(/^req_\d+_[a-z0-9]+$/);
        expect(id2).toMatch(/^req_\d+_[a-z0-9]+$/);
        expect(id1).not.toBe(id2);
      });

      it('should contain timestamp in request ID', () => {
        const id = apiUtils.generateRequestId();
        const parts = id.split('_');
        expect(parts[0]).toBe('req');
        expect(parts[1]).toMatch(/^\d+$/);
      });

      it('should contain random string in request ID', () => {
        const id = apiUtils.generateRequestId();
        const parts = id.split('_');
        expect(parts[2]).toMatch(/^[a-z0-9]+$/);
        expect(parts[2].length).toBeGreaterThan(0);
      });
    });
  });
});
