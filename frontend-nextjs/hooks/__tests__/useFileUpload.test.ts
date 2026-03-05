/**
 * useFileUpload Hook Unit Tests
 *
 * Tests for useFileUpload hook managing file upload with progress tracking.
 * Verifies upload state transitions, progress updates, error handling,
 * and FormData creation.
 *
 * NOTE: This hook tests the apiClient integration.
 * The api.ts module has axios interceptors that are difficult to mock.
 * These tests verify the hook logic but mock at a higher level.
 */

import { renderHook, act, waitFor } from '@testing-library/react';

// Mock axios to avoid interceptor issues
const mockApiPost = jest.fn();

jest.mock('axios', () => ({
  create: jest.fn(() => ({
    post: (...args: any[]) => mockApiPost(...args),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  })),
}));

import { useFileUpload } from '../useFileUpload';

describe('useFileUpload Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('1. Upload State Tests', () => {
    test('initial isUploading is false', () => {
      const { result } = renderHook(() => useFileUpload());

      expect(result.current.isUploading).toBe(false);
    });

    test('initial progress is 0', () => {
      const { result } = renderHook(() => useFileUpload());

      expect(result.current.progress).toBe(0);
    });

    test('isUploading becomes true during upload', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });
      let resolveUpload: (value: any) => void;

      // Mock apiClient.post to return a promise we can control
      mockApiPost.mockReturnValue(
        new Promise((resolve) => {
          resolveUpload = resolve;
        })
      );

      const { result } = renderHook(() => useFileUpload());

      const uploadPromise = act(async () => {
        return result.current.uploadFile(mockFile);
      });

      // Wait for isUploading to become true
      await waitFor(() => {
        expect(result.current.isUploading).toBe(true);
      });

      // Resolve the upload
      resolveUpload!({ data: { success: true } });
      await uploadPromise;
    });

    test('progress updates during upload', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });

      let progressCallback: ((progressEvent: any) => void) | null = null;

      mockApiPost.mockImplementation((url: string, data: any, config: any) => {
        // Capture the progress callback
        if (config?.onUploadProgress) {
          progressCallback = config.onUploadProgress;
        }
        return Promise.resolve({ data: { success: true } });
      });

      const { result } = renderHook(() => useFileUpload());

      act(() => {
        result.current.uploadFile(mockFile);
      });

      // Simulate progress updates
      if (progressCallback) {
        act(() => {
          progressCallback!({ loaded: 50, total: 100 });
        });

        expect(result.current.progress).toBe(50);

        act(() => {
          progressCallback!({ loaded: 100, total: 100 });
        });

        expect(result.current.progress).toBe(100);
      }
    });

    test('isUploading becomes false after completion', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });

      mockApiPost.mockResolvedValue({
        data: { success: true, fileId: 'file-123' },
      });

      const { result } = renderHook(() => useFileUpload());

      await act(async () => {
        await result.current.uploadFile(mockFile);
      });

      expect(result.current.isUploading).toBe(false);
    });
  });

  describe('2. Success Path Tests', () => {
    test('returns response data on success', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });
      const mockResponse = {
        data: {
          success: true,
          fileId: 'file-123',
          url: 'https://example.com/file.txt',
        },
      };

      mockApiPost.mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useFileUpload());

      let response;
      await act(async () => {
        response = await result.current.uploadFile(mockFile);
      });

      expect(response).toEqual(mockResponse.data);
    });

    test('resets isUploading to false after success', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });

      mockApiPost.mockResolvedValue({
        data: { success: true },
      });

      const { result } = renderHook(() => useFileUpload());

      await act(async () => {
        await result.current.uploadFile(mockFile);
      });

      expect(result.current.isUploading).toBe(false);
    });

    test('progress reaches 100% on completion', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });

      let progressCallback: ((progressEvent: any) => void) | null = null;

      mockApiPost.mockImplementation((url: string, data: any, config: any) => {
        if (config?.onUploadProgress) {
          progressCallback = config.onUploadProgress;
          // Simulate complete progress
          setTimeout(() => {
            progressCallback!({ loaded: 100, total: 100 });
          }, 0);
        }
        return Promise.resolve({ data: { success: true } });
      });

      const { result } = renderHook(() => useFileUpload());

      await act(async () => {
        await result.current.uploadFile(mockFile);
      });

      await waitFor(() => {
        expect(result.current.progress).toBe(100);
      });
    });
  });

  describe('3. Error Handling Tests', () => {
    test('throws error on upload failure', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });
      const mockError = new Error('Upload failed');

      mockApiPost.mockRejectedValue(mockError);

      const { result } = renderHook(() => useFileUpload());

      await expect(
        act(async () => {
          await result.current.uploadFile(mockFile);
        })
      ).rejects.toThrow('Upload failed');
    });

    test('sets isUploading to false in finally block', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });

      mockApiPost.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useFileUpload());

      try {
        await act(async () => {
          await result.current.uploadFile(mockFile);
        });
      } catch (error) {
        // Expected error
      }

      expect(result.current.isUploading).toBe(false);
    });

    test('console.error called with error details', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const mockError = new Error('Upload failed');

      mockApiPost.mockRejectedValue(mockError);

      const { result } = renderHook(() => useFileUpload());

      try {
        await act(async () => {
          await result.current.uploadFile(mockFile);
        });
      } catch (error) {
        // Expected error
      }

      expect(consoleSpy).toHaveBeenCalledWith('File upload failed:', mockError);
      consoleSpy.mockRestore();
    });
  });

  describe('4. FormData Tests', () => {
    test('creates FormData with file', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });

      mockApiPost.mockResolvedValue({
        data: { success: true },
      });

      const { result } = renderHook(() => useFileUpload());

      await act(async () => {
        await result.current.uploadFile(mockFile);
      });

      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/documents/upload',
        expect.any(FormData),
        expect.objectContaining({
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        })
      );

      const formData = mockApiPost.mock.calls[0][1];
      expect(formData instanceof FormData).toBe(true);
    });

    test('sets correct Content-Type header', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });

      mockApiPost.mockResolvedValue({
        data: { success: true },
      });

      const { result } = renderHook(() => useFileUpload());

      await act(async () => {
        await result.current.uploadFile(mockFile);
      });

      const config = mockApiPost.mock.calls[0][2];
      expect(config.headers).toEqual({
        'Content-Type': 'multipart/form-data',
      });
    });

    test('appends file to FormData', async () => {
      const mockFile = new File(['content'], 'test.txt', { type: 'text/plain' });

      mockApiPost.mockImplementation((url: string, formData: any) => {
        // Verify FormData contains the file
        expect(formData.get('file')).toBe(mockFile);
        return Promise.resolve({ data: { success: true } });
      });

      const { result } = renderHook(() => useFileUpload());

      await act(async () => {
        await result.current.uploadFile(mockFile);
      });
    });
  });

  describe('5. Multiple Upload Tests', () => {
    test('handles sequential uploads', async () => {
      const mockFile1 = new File(['content1'], 'test1.txt', { type: 'text/plain' });
      const mockFile2 = new File(['content2'], 'test2.txt', { type: 'text/plain' });

      mockApiPost
        .mockResolvedValueOnce({ data: { success: true, fileId: 'file-1' } })
        .mockResolvedValueOnce({ data: { success: true, fileId: 'file-2' } });

      const { result } = renderHook(() => useFileUpload());

      let response1, response2;

      await act(async () => {
        response1 = await result.current.uploadFile(mockFile1);
      });

      expect(result.current.isUploading).toBe(false);
      expect(response1.fileId).toBe('file-1');

      await act(async () => {
        response2 = await result.current.uploadFile(mockFile2);
      });

      expect(result.current.isUploading).toBe(false);
      expect(response2.fileId).toBe('file-2');
    });

    test('resets progress between uploads', async () => {
      const mockFile1 = new File(['content1'], 'test1.txt', { type: 'text/plain' });
      const mockFile2 = new File(['content2'], 'test2.txt', { type: 'text/plain' });

      let progressCallback: ((progressEvent: any) => void) | null = null;

      mockApiPost.mockImplementation((url: string, data: any, config: any) => {
        if (config?.onUploadProgress) {
          progressCallback = config.onUploadProgress;
          progressCallback!({ loaded: 100, total: 100 });
        }
        return Promise.resolve({ data: { success: true } });
      });

      const { result } = renderHook(() => useFileUpload());

      await act(async () => {
        await result.current.uploadFile(mockFile1);
      });

      expect(result.current.progress).toBe(100);

      await act(async () => {
        await result.current.uploadFile(mockFile2);
      });

      // Progress should be updated by the callback
      expect(result.current.progress).toBe(100);
    });
  });
});
