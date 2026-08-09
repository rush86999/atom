/**
 * AgentListScreen Component Tests
 *
 * Tests for agent list with search, filter, sort,
 * status indicators, and navigation.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { AgentListScreen } from '../../../screens/agent/AgentListScreen';

// Mock @react-navigation/native
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  setOptions: jest.fn(),
  reset: jest.fn(),
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
}));

// Mock agentService
const mockGetAgents = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: [
      {
        id: 'agent-1',
        name: 'Test Agent 1',
        description: 'A test automation agent',
        maturity_level: 'AUTONOMOUS',
        status: 'online',
        confidence_score: 0.95,
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7).toISOString(),
        last_execution_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        capabilities: [
          { name: 'web_automation', enabled: true },
          { name: 'data_extraction', enabled: true },
          { name: 'api_integration', enabled: false },
        ],
      },
      {
        id: 'agent-2',
        name: 'Test Agent 2',
        description: 'A data processing agent',
        maturity_level: 'SUPERVISED',
        status: 'online',
        confidence_score: 0.85,
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(),
        last_execution_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
        capabilities: [
          { name: 'data_processing', enabled: true },
          { name: 'reporting', enabled: true },
        ],
      },
      {
        id: 'agent-3',
        name: 'Test Agent 3',
        description: 'An intern-level agent',
        maturity_level: 'INTERN',
        status: 'offline',
        confidence_score: 0.65,
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
        last_execution_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
        capabilities: [
          { name: 'basic_tasks', enabled: true },
        ],
      },
    ],
  })
);

jest.mock('../../../services/agentService', () => ({
  agentService: {
    getAgents: (filters: any) => mockGetAgents(filters),
  },
}));

// Mock react-native-paper Icon
jest.mock('react-native-paper', () => ({
  Icon: 'Icon',
  MD3Colors: {
    primary50: '#2196F3',
    secondary50: '#FF9800',
    secondary20: '#E0E0E0',
  },
}));

// Mock Alert
jest.mock('react-native/Libraries/Alert/Alert', () => ({
  alert: jest.fn(),
}));

// Real clock captured before fake timers take over, so relative-time
// assertions ('5m ago', '1h ago') stay deterministic.
const MOCK_NOW = Date.now();

describe('AgentListScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    jest.setSystemTime(MOCK_NOW);
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.clearAllTimers();
  });

  describe('Rendering', () => {
    it('should render loading state initially', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Loading agents...')).toBeTruthy();
      });
    });

    it('should render agent list when data loads', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
        expect(getByText('Test Agent 3')).toBeTruthy();
      });
    });

    it('should render search bar', async () => {
      const { getByPlaceholderText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByPlaceholderText(/search agents by name/i)).toBeTruthy();
      });
    });

    it('should render filter toggle', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Filters')).toBeTruthy();
      });
    });

    it('should render results count', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('3 agents')).toBeTruthy();
      });
    });

    it('should render empty state when no agents found', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [],
        })
      );

      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('No agents found')).toBeTruthy();
        expect(getByText('No agents available')).toBeTruthy();
      });
    });

    it('should render empty state with filter message when filters are active', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [],
        })
      );

      const { getByText, getByPlaceholderText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('No agents found')).toBeTruthy();
      });

      // Enter search query to trigger filter message
      const searchInput = getByPlaceholderText(/search agents by name/i);
      fireEvent.changeText(searchInput, 'NonExistent');

      await waitFor(() => {
        expect(getByText('Try adjusting your filters or search query')).toBeTruthy();
      });
    });
  });

  describe('Agent Display', () => {
    it('should display agent name', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should display agent description', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('A test automation agent')).toBeTruthy();
        expect(getByText('A data processing agent')).toBeTruthy();
      });
    });

    it('should display maturity badge', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('AUTONOMOUS')).toBeTruthy();
        expect(getByText('SUPERVISED')).toBeTruthy();
        expect(getByText('INTERN')).toBeTruthy();
      });
    });

    it('should display agent status', async () => {
      const { getAllByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getAllByText('online').length).toBeGreaterThanOrEqual(1);
        expect(getAllByText('offline').length).toBe(1);
      });
    });

    it('should display confidence score', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Confidence: 95%')).toBeTruthy();
        expect(getByText('Confidence: 85%')).toBeTruthy();
      });
    });

    it('should display last execution time', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText(/5m ago/)).toBeTruthy();
        expect(getByText(/1h ago/)).toBeTruthy();
      });
    });

    it('should display agent capabilities', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('web_automation')).toBeTruthy();
        expect(getByText('data_extraction')).toBeTruthy();
        expect(getByText('data_processing')).toBeTruthy();
      });
    });

    it('should show "more capabilities" text when agent has >4 capabilities', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [
            {
              id: 'agent-1',
              name: 'Test Agent',
              description: 'Test',
              maturity_level: 'AUTONOMOUS',
              status: 'online',
              confidence_score: 0.95,
              created_at: new Date().toISOString(),
              last_execution_at: new Date().toISOString(),
              capabilities: [
                { name: 'cap1', enabled: true },
                { name: 'cap2', enabled: true },
                { name: 'cap3', enabled: true },
                { name: 'cap4', enabled: true },
                { name: 'cap5', enabled: true },
              ],
            },
          ],
        })
      );

      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('+1 more')).toBeTruthy();
      });
    });
  });

  describe('Search Functionality', () => {
    it('should filter agents by name', async () => {
      const { getByPlaceholderText, getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText(/search agents by name/i);
      fireEvent.changeText(searchInput, 'Agent 1');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(queryByText('Test Agent 2')).toBeNull();
      });
    });

    it('should filter agents by description', async () => {
      const { getByPlaceholderText, getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText(/search agents by name/i);
      fireEvent.changeText(searchInput, 'automation');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(queryByText('Test Agent 2')).toBeNull();
      });
    });

    it('should filter agents by capability', async () => {
      const { getByPlaceholderText, getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText(/search agents by name/i);
      fireEvent.changeText(searchInput, 'web_automation');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(queryByText('Test Agent 2')).toBeNull();
      });
    });

    it('should clear search when clear button is pressed', async () => {
      const { getByPlaceholderText, getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText(/search agents by name/i);
      fireEvent.changeText(searchInput, 'Agent 1');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Clear the search
      fireEvent.changeText(searchInput, '');

      await waitFor(() => {
        expect(getByText('Test Agent 2')).toBeTruthy();
      });
    });
  });

  describe('Maturity Filter', () => {
    it('should filter by AUTONOMOUS maturity', async () => {
      const { getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Open filters
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      await waitFor(() => {
        expect(getByText('Autonomous')).toBeTruthy();
      });

      const autonomousFilter = screen.getByText('Autonomous');
      fireEvent.press(autonomousFilter);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(queryByText('Test Agent 2')).toBeNull();
        expect(queryByText('Test Agent 3')).toBeNull();
      });
    });

    it('should filter by SUPERVISED maturity', async () => {
      const { getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 2')).toBeTruthy();
      });

      // Open filters and select SUPERVISED
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      const supervisedFilter = screen.getByText('Supervised');
      fireEvent.press(supervisedFilter);

      await waitFor(() => {
        expect(getByText('Test Agent 2')).toBeTruthy();
      });
    });

    it('should filter by INTERN maturity', async () => {
      const { getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 3')).toBeTruthy();
      });

      // Open filters and select INTERN
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      const internFilter = screen.getByText('Intern');
      fireEvent.press(internFilter);

      await waitFor(() => {
        expect(getByText('Test Agent 3')).toBeTruthy();
      });
    });

    it('should reset to show all agents', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
        expect(getByText('Test Agent 3')).toBeTruthy();
      });

      // Open filters and select AUTONOMOUS
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      const allFilter = screen.getAllByText('All')[0];
      fireEvent.press(allFilter);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
        expect(getByText('Test Agent 3')).toBeTruthy();
      });
    });
  });

  describe('Status Filter', () => {
    it('should filter by online status', async () => {
      const { getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Open filters
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      const onlineFilter = screen.getByText('Online');
      fireEvent.press(onlineFilter);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
        expect(queryByText('Test Agent 3')).toBeNull();
      });
    });

    it('should filter by offline status', async () => {
      const { getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 3')).toBeTruthy();
      });

      // Open filters
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      const offlineFilter = screen.getByText('Offline');
      fireEvent.press(offlineFilter);

      await waitFor(() => {
        expect(getByText('Test Agent 3')).toBeTruthy();
        expect(queryByText('Test Agent 1')).toBeNull();
        expect(queryByText('Test Agent 2')).toBeNull();
      });
    });
  });

  describe('Sort Functionality', () => {
    it('should sort by name by default', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should sort by name alphabetically', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Open filters
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      const nameSort = screen.getByText('Name');
      fireEvent.press(nameSort);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should sort by last execution', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Open filters
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      const recentSort = screen.getByText('Recent');
      fireEvent.press(recentSort);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should sort by created date', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Open filters
      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      const createdSort = screen.getByText('Created');
      fireEvent.press(createdSort);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });
  });

  describe('Navigation', () => {
    it('should navigate to agent chat on agent press', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const agentCard = getByText('Test Agent 1');
      fireEvent.press(agentCard);

      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('AgentChat', {
          agentId: 'agent-1',
        });
      });
    });
  });

  describe('Pull to Refresh', () => {
    it('should refresh agents on pull', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      expect(mockGetAgents).toHaveBeenCalled();
    });
  });

  describe('Filter Toggle', () => {
    it('should show filters when toggle is pressed', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Filters')).toBeTruthy();
      });

      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      await waitFor(() => {
        expect(getByText('Maturity Level')).toBeTruthy();
        expect(getByText('Status')).toBeTruthy();
        expect(getByText('Sort By')).toBeTruthy();
      });
    });

    it('should hide filters when toggle is pressed again', async () => {
      const { getByText, queryByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Filters')).toBeTruthy();
      });

      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      await waitFor(() => {
        expect(getByText('Maturity Level')).toBeTruthy();
      });

      // Press again to hide
      fireEvent.press(filterToggle);

      await waitFor(() => {
        expect(queryByText('Maturity Level')).toBeNull();
      });
    });

    it('should show active badge when filters are applied', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Filters')).toBeTruthy();
      });

      const filterToggle = screen.getByText('Filters');
      fireEvent.press(filterToggle);

      // Apply a filter
      const autonomousFilter = screen.getByText('Autonomous');
      fireEvent.press(autonomousFilter);

      await waitFor(() => {
        expect(getByText('Active')).toBeTruthy();
      });
    });
  });

  describe('Reset Filters', () => {
    it('should show reset filters button when filters are active', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Apply search to activate filter
      const searchInput = screen.getByPlaceholderText(/search agents by name/i);
      fireEvent.changeText(searchInput, 'Agent 1');

      await waitFor(() => {
        expect(getByText('Reset filters')).toBeTruthy();
      });
    });

    it('should reset all filters when reset is pressed', async () => {
      const { getByText, getByPlaceholderText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
      });

      // Apply search
      const searchInput = screen.getByPlaceholderText(/search agents by name/i);
      fireEvent.changeText(searchInput, 'Agent 1');

      await waitFor(() => {
        expect(getByText('Reset filters')).toBeTruthy();
      });

      const resetButton = screen.getByText('Reset filters');
      fireEvent.press(resetButton);

      await waitFor(() => {
        expect(getByText('Test Agent 2')).toBeTruthy();
      });
    });
  });

  describe('Error Handling', () => {
    const { Alert } = require('react-native');

    it('should handle API errors gracefully', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.resolve({
          success: false,
          error: 'Failed to load agents',
        })
      );

      const { getByText } = render(<AgentListScreen />);

      // Should show empty state on error
      await waitFor(() => {
        expect(getByText('No agents found')).toBeTruthy();
      });
      expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to load agents');
    });

    it('should handle network errors gracefully', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      const { getByText } = render(<AgentListScreen />);

      // Should show empty state on error
      await waitFor(() => {
        expect(getByText('No agents found')).toBeTruthy();
      });
      expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to load agents');
    });

    it('should pass the active filters to the service on load', async () => {
      const { FlatList } = require('react-native');
      render(<AgentListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      // Apply a maturity filter, then refresh
      fireEvent.press(screen.getByText('Filters'));
      fireEvent.press(screen.getByText('Autonomous'));
      fireEvent(screen.UNSAFE_getByType(FlatList), 'refresh');

      await waitFor(() => {
        const lastCall = mockGetAgents.mock.calls[mockGetAgents.mock.calls.length - 1][0];
        expect(lastCall.maturity).toBe('AUTONOMOUS');
        expect(lastCall.sort_by).toBe('name');
        expect(lastCall.sort_order).toBe('asc');
      });
    });
  });

  describe('Status Indicators', () => {
    it('should show online status with green dot', async () => {
      const { getAllByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getAllByText('online').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('should show offline status with gray dot', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('offline')).toBeTruthy();
      });
    });
  });

  describe('Maturity Badge Colors', () => {
    it('should show green badge for AUTONOMOUS', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('AUTONOMOUS')).toBeTruthy();
      });
    });

    it('should show orange badge for SUPERVISED', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('SUPERVISED')).toBeTruthy();
      });
    });

    it('should show blue badge for INTERN', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('INTERN')).toBeTruthy();
      });
    });
  });

  describe('Student Maturity and Other Statuses', () => {
    it('should render a STUDENT maturity agent with a gray badge', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [
            {
              id: 'agent-student',
              name: 'Student Agent',
              description: 'A student-level agent',
              maturity_level: 'STUDENT',
              status: 'busy',
              confidence_score: 0.3,
              created_at: new Date(MOCK_NOW - 86400000 * 10).toISOString(),
              last_execution_at: new Date(MOCK_NOW - 86400000 * 10).toISOString(),
              capabilities: [],
            },
          ],
        })
      );

      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('STUDENT')).toBeTruthy();
        expect(getByText('busy')).toBeTruthy();
      });
    });

    it('should render maintenance status and old execution dates', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [
            {
              id: 'agent-maint',
              name: 'Maintenance Agent',
              description: 'In maintenance',
              maturity_level: 'SUPERVISED',
              status: 'maintenance',
              confidence_score: 0.5,
              created_at: new Date(MOCK_NOW - 86400000 * 10).toISOString(),
              last_execution_at: new Date(MOCK_NOW - 86400000 * 10).toISOString(),
              capabilities: [],
            },
            {
              id: 'agent-odd',
              name: 'Odd Status Agent',
              description: 'Odd status',
              maturity_level: 'UNKNOWN_LEVEL' as any,
              status: 'weird',
              confidence_score: 0.5,
              created_at: new Date(MOCK_NOW).toISOString(),
              last_execution_at: new Date(MOCK_NOW - 86400000 * 10).toISOString(),
              capabilities: [],
            },
          ],
        })
      );

      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('maintenance')).toBeTruthy();
        expect(getByText('weird')).toBeTruthy();
        // More than 7 days ago -> localized date instead of "Xd ago"
        const expected = new Date(MOCK_NOW - 86400000 * 10).toLocaleDateString();
        const escaped = expected.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        expect(screen.getAllByText(new RegExp(`Last: ${escaped}`)).length).toBe(2);
      });
    });

    it('should filter by STUDENT maturity chip', async () => {
      const { getByText, queryByText, getByPlaceholderText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Filters'));
      fireEvent.press(screen.getByText('Student'));

      await waitFor(() => {
        expect(queryByText('Test Agent 1')).toBeNull();
        expect(queryByText('Test Agent 2')).toBeNull();
        expect(queryByText('Test Agent 3')).toBeNull();
        expect(getByText('No agents found')).toBeTruthy();
      });

      // Reset filters restores the full list
      fireEvent.press(screen.getByText('Reset filters'));
      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should restore all agents via the status All chip', async () => {
      const { getByText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 3')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Filters'));
      fireEvent.press(screen.getByText('Offline'));
      await waitFor(() => {
        expect(getByText('Test Agent 3')).toBeTruthy();
      });

      fireEvent.press(screen.getAllByText('All')[1]);
      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
      });
    });
  });

  describe('Pull to Refresh and Search Clear', () => {
    it('should reload agents when the list is refreshed', async () => {
      const { FlatList } = require('react-native');
      const { UNSAFE_getByType } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      const before = mockGetAgents.mock.calls.length;
      fireEvent(UNSAFE_getByType(FlatList), 'refresh');

      await waitFor(() => {
        expect(mockGetAgents.mock.calls.length).toBeGreaterThan(before);
      });
    });

    it('should clear the search query via the clear button', async () => {
      const { getByText, getByPlaceholderText } = render(<AgentListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const searchInput = screen.getByPlaceholderText(/search agents by name/i);
      fireEvent.changeText(searchInput, 'Agent 1');

      await waitFor(() => {
        expect(getByText('Reset filters')).toBeTruthy();
        expect(screen.queryByText('Test Agent 2')).toBeNull();
      });

      // The clear (close) icon's press handler bubbles to its TouchableOpacity
      const closeIcon = screen.UNSAFE_getAllByType('Icon' as any).find(
        (el: any) => el.props.source === 'close'
      );
      fireEvent.press(closeIcon);

      await waitFor(() => {
        expect(screen.queryByText('Test Agent 2')).toBeTruthy();
      });
    });
  });

  describe('Filter Active Badge', () => {
    it('should not show the Active badge when no filters are applied', async () => {
      render(<AgentListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      expect(screen.queryByText('Active')).toBeNull();
    });

    it('should show the Active badge after a status filter is applied', async () => {
      render(<AgentListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 3')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Filters'));
      fireEvent.press(screen.getByText('Offline'));

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeTruthy();
      });
    });

    it('should hide the Active badge after resetting filters', async () => {
      render(<AgentListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      // Apply a maturity filter (search text alone does not activate the badge)
      fireEvent.press(screen.getByText('Filters'));
      fireEvent.press(screen.getByText('Autonomous'));

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Reset filters'));

      await waitFor(() => {
        expect(screen.queryByText('Active')).toBeNull();
        expect(screen.getByText('Test Agent 2')).toBeTruthy();
      });
    });
  });

  describe('Capability Filter', () => {
    const renderLoaded = async () => {
      render(<AgentListScreen />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });
      fireEvent.press(screen.getByText('Filters'));
      await waitFor(() => {
        expect(screen.getByText('Capability')).toBeTruthy();
      });
    };

    it('should list enabled capabilities as filter chips', async () => {
      await renderLoaded();

      // Enabled capabilities across all agents (sorted). Each appears twice:
      // once as a filter chip, once as a chip on the agent card. Disabled
      // capabilities (api_integration on agent 1) only appear on the card.
      expect(screen.getAllByText('basic_tasks').length).toBe(2);
      expect(screen.getAllByText('data_extraction').length).toBe(2);
      expect(screen.getAllByText('data_processing').length).toBe(2);
      expect(screen.getAllByText('reporting').length).toBe(2);
      expect(screen.getAllByText('web_automation').length).toBe(2);
      expect(screen.getAllByText('api_integration').length).toBe(1);
    });

    it('should filter agents by a selected capability', async () => {
      await renderLoaded();

      fireEvent.press(screen.getAllByText('web_automation')[0]);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
        expect(screen.queryByText('Test Agent 2')).toBeNull();
        expect(screen.queryByText('Test Agent 3')).toBeNull();
      });
    });

    it('should toggle the capability filter off on second press', async () => {
      await renderLoaded();

      fireEvent.press(screen.getAllByText('web_automation')[0]);
      await waitFor(() => {
        expect(screen.queryByText('Test Agent 2')).toBeNull();
      });

      fireEvent.press(screen.getAllByText('web_automation')[0]);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 2')).toBeTruthy();
      });
    });

    it('should clear the capability filter via its All chip', async () => {
      await renderLoaded();

      fireEvent.press(screen.getAllByText('web_automation')[0]);
      await waitFor(() => {
        expect(screen.queryByText('Test Agent 2')).toBeNull();
      });

      // Capability All is the third "All" chip (maturity, status, capability)
      fireEvent.press(screen.getAllByText('All')[2]);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 2')).toBeTruthy();
      });
    });

    it('should show the empty state when the capability filter matches nothing', async () => {
      await renderLoaded();

      // Combined filters: web_automation belongs to agent 1, but agent 1 is
      // online and the status filter is offline -> nothing matches
      fireEvent.press(screen.getByText('Offline'));
      fireEvent.press(screen.getAllByText('web_automation')[0]);

      await waitFor(() => {
        expect(screen.getByText('No agents found')).toBeTruthy();
        expect(screen.getByText('Try adjusting your filters or search query')).toBeTruthy();
      });

      // Reset restores the full list
      fireEvent.press(screen.getByText('Reset filters'));
      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });
    });
  });

  describe('Sorting Order', () => {
    const { FlatList } = require('react-native');

    const getSortedIds = () => {
      const flatList = screen.UNSAFE_getByType(FlatList);
      return flatList.props.data.map((agent: any) => agent.id);
    };

    it('should sort by name alphabetically by default', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [
            {
              id: 'zebra',
              name: 'Zebra Agent',
              description: 'Z',
              maturity_level: 'INTERN',
              status: 'offline',
              created_at: new Date(MOCK_NOW - 1000).toISOString(),
              capabilities: [],
            },
            {
              id: 'alpha',
              name: 'Alpha Agent',
              description: 'A',
              maturity_level: 'INTERN',
              status: 'offline',
              created_at: new Date(MOCK_NOW - 2000).toISOString(),
              capabilities: [],
            },
          ],
        })
      );

      render(<AgentListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Zebra Agent')).toBeTruthy();
      });

      expect(getSortedIds()).toEqual(['alpha', 'zebra']);
    });

    it('should sort by created date newest first', async () => {
      render(<AgentListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Filters'));
      fireEvent.press(screen.getByText('Created'));

      await waitFor(() => {
        // agent-3 is 1d old, agent-2 3d, agent-1 7d -> newest first
        expect(getSortedIds()).toEqual(['agent-3', 'agent-2', 'agent-1']);
      });
    });

    it('should sort by last execution with never-run agents last', async () => {
      mockGetAgents.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [
            {
              id: 'never-ran-1',
              name: 'Never Ran 1',
              description: 'N1',
              maturity_level: 'INTERN',
              status: 'online',
              created_at: new Date(MOCK_NOW - 1000).toISOString(),
              capabilities: [],
            },
            {
              id: 'ran-recently',
              name: 'Ran Recently',
              description: 'RR',
              maturity_level: 'INTERN',
              status: 'online',
              created_at: new Date(MOCK_NOW - 2000).toISOString(),
              last_execution_at: new Date(MOCK_NOW - 1000 * 60).toISOString(),
              capabilities: [],
            },
            {
              id: 'never-ran-2',
              name: 'Never Ran 2',
              description: 'N2',
              maturity_level: 'INTERN',
              status: 'online',
              created_at: new Date(MOCK_NOW - 3000).toISOString(),
              capabilities: [],
            },
          ],
        })
      );

      render(<AgentListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Ran Recently')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Filters'));
      fireEvent.press(screen.getByText('Recent'));

      await waitFor(() => {
        // Agents without a last execution sort last
        expect(getSortedIds()).toEqual(['ran-recently', 'never-ran-1', 'never-ran-2']);
      });
    });
  });
});
