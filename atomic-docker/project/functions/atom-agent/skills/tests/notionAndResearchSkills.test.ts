import axios from 'axios';
import {
  createNotionTask,
  queryNotionTasks,
  updateNotionTask,
} from '../notionAndResearchSkills';
import {
  CreateNotionTaskParams,
  QueryNotionTasksParams,
  UpdateNotionTaskParams,
  NotionTaskStatus,
  NotionTaskPriority,
  NotionTask, // For mock task data in queryNotionTasks
  SkillResponse,
  CreateTaskData,
  UpdateTaskData,
  TaskQueryResponse,
} from '../../types';
import * as constants from '../../_libs/constants';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock constants that are imported and used by notionAndResearchSkills.ts
// The path '../../_libs/constants' is relative to the module being tested (notionAndResearchSkills.ts)
// when it imports constants. However, jest.mock needs the path relative to THIS test file.
jest.mock('../../_libs/constants', () => ({
  ...jest.requireActual('../../_libs/constants'), // Preserve other constants if any
  PYTHON_NOTE_API_URL: 'http://mock-python-api.com/notes',
  NOTION_API_TOKEN: 'mock_notion_token',
  ATOM_NOTION_TASKS_DATABASE_ID: 'mock_tasks_db_id_from_constant', // Default fallback DB ID
}));

describe('Notion Task Management Skills', () => {
  const userId = 'testUser123';

  afterEach(() => {
    jest.clearAllMocks(); // Clear mocks after each test
  });

  // --- Tests for createNotionTask ---
  describe('createNotionTask', () => {
    const params: CreateNotionTaskParams = {
      description: 'Test Task',
      dueDate: '2024-12-31',
      status: 'To Do' as NotionTaskStatus,
      priority: 'High' as NotionTaskPriority,
      listName: 'Work',
      notes: 'Some notes',
      notionTasksDbId: 'custom_tasks_db_id', // Test with specific DB ID
    };

    it('should create a task successfully using specific notionTasksDbId', async () => {
      const mockApiResponse = {
        ok: true,
        data: { taskId: 'newPage123', taskUrl: 'http://notion.so/newPage123', message: 'Task created' },
      };
      mockedAxios.post.mockResolvedValueOnce({ data: mockApiResponse });

      const result = await createNotionTask(userId, params);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        `${constants.PYTHON_NOTE_API_URL}/create-notion-task`,
        expect.objectContaining({
          // description: 'Test Task', // These are spread from params
          // dueDate: '2024-12-31',
          user_id: userId,
          notion_api_token: constants.NOTION_API_TOKEN,
          notion_db_id: 'custom_tasks_db_id', // Ensure this specific one is used
        })
      );
      expect(result.ok).toBe(true);
      expect(result.data?.taskId).toBe('newPage123');
      expect(result.data?.taskUrl).toBe('http://notion.so/newPage123');
    });

    it('should use ATOM_NOTION_TASKS_DATABASE_ID if params.notionTasksDbId is not provided', async () => {
      const mockApiResponse = { ok: true, data: { taskId: 'newPage456', taskUrl: 'http://notion.so/newPage456' }};
      mockedAxios.post.mockResolvedValueOnce({ data: mockApiResponse });

      const paramsWithoutDbId: CreateNotionTaskParams = {
        description: 'Another task',
        // notionTasksDbId is omitted here
      };

      await createNotionTask(userId, paramsWithoutDbId);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        `${constants.PYTHON_NOTE_API_URL}/create-notion-task`,
        expect.objectContaining({
          notion_db_id: constants.ATOM_NOTION_TASKS_DATABASE_ID, // Check fallback
        })
      );
    });

    it('should return error if Python API service fails', async () => {
      const mockApiErrorResponse = {
        ok: false,
        error: { code: 'PYTHON_ERROR', message: 'Python backend exploded' },
      };
      mockedAxios.post.mockResolvedValueOnce({ data: mockApiErrorResponse });
      const result = await createNotionTask(userId, params);
      expect(result.ok).toBe(false);
      expect(result.error?.code).toBe('PYTHON_ERROR');
      expect(result.error?.message).toBe('Python backend exploded');
    });

    it('should return error if axios call itself fails (network error)', async () => {
      mockedAxios.post.mockRejectedValueOnce(new Error('Network Error'));
      const result = await createNotionTask(userId, params);
      expect(result.ok).toBe(false);
      expect(result.error?.message).toContain('Failed to create Notion task: Network Error');
    });

    it('should return config error if PYTHON_NOTE_API_URL is not set', async () => {
      const originalUrl = constants.PYTHON_NOTE_API_URL;
      // To modify constants for a single test, ensure the mock setup allows it or re-mock per test.
      // This type of direct modification is tricky with jest.mock at module level.
      // A better way is to have constants injectable or use a more granular mock for this specific test.
      // For now, this test highlights the dependency. If constants were not module-level mocked, this would be easier.
      // Given the current jest.mock, this test might not reflect an actual scenario where only one const is missing.
      // However, the function's internal check is what's being "tested".
      jest.isolateModules(() => { // To ensure a fresh mock for constants for this test
        jest.mock('../../_libs/constants', () => ({
            ...jest.requireActual('../../_libs/constants'),
            PYTHON_NOTE_API_URL: '', // Mock as empty for this test
            NOTION_API_TOKEN: 'mock_notion_token', // Keep others valid
            ATOM_NOTION_TASKS_DATABASE_ID: 'mock_tasks_db_id_from_constant',
        }));
        // Need to re-import the skill to use the modified constants for this isolated test
        const skillWithMockedConst = require('../notionAndResearchSkills');
        const promise = skillWithMockedConst.createNotionTask(userId, params);
        promise.then((result: SkillResponse<CreateTaskData>) => {
            expect(result.ok).toBe(false);
            expect(result.error?.code).toBe('CONFIG_ERROR');
            expect(result.error?.message).toContain('Python Note API URL is not configured');
        });
      });
    });
  });

  // --- Tests for queryNotionTasks ---
  describe('queryNotionTasks', () => {
    const params: QueryNotionTasksParams = {
      status: 'To Do' as NotionTaskStatus,
      listName: 'Personal',
      notionTasksDbId: 'custom_query_db_id', // Specific DB for this query
    };
    const mockTasksResult: NotionTask[] = [
      { id: 'task1', description: 'Query Task 1', status: 'To Do', createdDate: '2023-01-01T00:00:00Z', url: 'http://notion.so/task1', priority: 'High', listName: 'Personal' },
    ];

    it('should query tasks successfully', async () => {
      const mockApiResponse = { ok: true, data: mockTasksResult, message: 'Tasks retrieved' };
      mockedAxios.post.mockResolvedValueOnce({ data: mockApiResponse });

      const result = await queryNotionTasks(userId, params);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        `${constants.PYTHON_NOTE_API_URL}/query-notion-tasks`,
        expect.objectContaining({
          // status: 'To Do', // These are spread from params
          // listName: 'Personal',
          user_id: userId,
          notion_api_token: constants.NOTION_API_TOKEN,
          notion_db_id: 'custom_query_db_id',
        })
      );
      expect(result.success).toBe(true);
      expect(result.tasks).toEqual(mockTasksResult);
      expect(result.message).toBe('Tasks retrieved');
    });

    it('should return empty array if no tasks found but API call is ok', async () => {
        const mockApiResponse = { ok: true, data: [], message: 'No tasks found matching criteria' };
        mockedAxios.post.mockResolvedValueOnce({ data: mockApiResponse });
        const result = await queryNotionTasks(userId, params);
        expect(result.success).toBe(true);
        expect(result.tasks).toEqual([]);
        expect(result.message).toBe('No tasks found matching criteria');
    });

    it('should adapt Python API error to TaskQueryResponse error', async () => {
      const mockApiErrorResponse = { ok: false, error: { code: 'PYTHON_ERROR', message: 'DB query failed', details: 'Some detail' }};
      mockedAxios.post.mockResolvedValueOnce({ data: mockApiErrorResponse });
      const result = await queryNotionTasks(userId, params);
      expect(result.success).toBe(false);
      expect(result.tasks).toEqual([]);
      expect(result.error).toBe('DB query failed');
      expect(result.message).toBe('Some detail');
    });
  });

  // --- Tests for updateNotionTask ---
  describe('updateNotionTask', () => {
    const params: UpdateNotionTaskParams = {
      taskId: 'taskToUpdate123',
      status: 'Done' as NotionTaskStatus,
      notes: 'Updated notes.',
    };
    const mockUpdateData: UpdateTaskData = { taskId: 'taskToUpdate123', updatedProperties: ['status', 'notes'], message: 'Task updated' };

    it('should update a task successfully', async () => {
      const mockApiResponse = { ok: true, data: mockUpdateData };
      mockedAxios.post.mockResolvedValueOnce({ data: mockApiResponse });

      const result = await updateNotionTask(userId, params);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        `${constants.PYTHON_NOTE_API_URL}/update-notion-task`,
        expect.objectContaining({
          taskId: 'taskToUpdate123',
          status: 'Done',
          notes: 'Updated notes.',
          user_id: userId,
          notion_api_token: constants.NOTION_API_TOKEN,
        })
      );
      expect(result.ok).toBe(true);
      expect(result.data).toEqual(mockUpdateData);
    });

    it('should return error if taskId is missing', async () => {
        const paramsWithoutId = { ...params };
        // Casting to any to delete a required property for testing purposes
        delete (paramsWithoutId as any).taskId;
        const result = await updateNotionTask(userId, paramsWithoutId as UpdateNotionTaskParams); // Cast back
        expect(result.ok).toBe(false);
        expect(result.error?.code).toBe('VALIDATION_ERROR');
        expect(result.error?.message).toContain('Task ID (taskId) is required for update.');
    });
  });
});
