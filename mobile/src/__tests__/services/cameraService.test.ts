/**
 * Camera Service Tests
 *
 * Tests for camera functionality including:
 * - Permission requests (granted, denied, undetermined)
 * - Photo capture with success/failure scenarios
 * - Camera availability checking
 * - Error handling for camera not available, permission denied
 * - Platform-specific camera types (front/back for iOS vs Android)
 */

import { CameraView, CameraType } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system';
import { Platform } from 'react-native';
import { cameraService } from '../../services/cameraService';

// Mock expo-camera
jest.mock('expo-camera', () => ({
  CameraView: {
    requestCameraPermissionsAsync: jest.fn(),
    getCameraPermissionsAsync: jest.fn(),
    isAvailableAsync: jest.fn(),
    savePhotoToLibraryAsync: jest.fn(),
  },
  CameraType: {
    Front: 'front',
    Back: 'back',
  },
}));

// Mock expo-image-picker
jest.mock('expo-image-picker', () => ({
  launchImageLibraryAsync: jest.fn(),
  requestMediaLibraryPermissionsAsync: jest.fn(),
  PermissionStatus: {
    GRANTED: 'granted',
    DENIED: 'denied',
    UNDETERMINED: 'undetermined',
  },
  MediaTypeOptions: {
    Images: 'images',
    All: 'all',
  },
}));

// Mock expo-file-system
jest.mock('expo-file-system', () => ({
  getInfoAsync: jest.fn(),
}));

// Mock Platform
jest.mock('react-native', () => ({
  Platform: {
    OS: 'ios',
  },
}));

describe('CameraService', () => {
  // Mock camera ref
  const mockCameraRef = {
    current: {
      takePictureAsync: jest.fn(),
      recordAsync: jest.fn(),
      stopRecording: jest.fn(),
    },
  } as any;

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset camera service state by re-importing
    jest.resetModules();

    // Default mock implementations
    (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
    });

    (CameraView.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
    });

    (CameraView.isAvailableAsync as jest.Mock).mockResolvedValue(true);

    (FileSystem.getInfoAsync as jest.Mock).mockResolvedValue({
      exists: true,
      size: '1024000',
      uri: 'file:///mock/photo.jpg',
    });

    (ImagePicker.requestMediaLibraryPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
    });
  });

  // ========================================================================
  // Permission Tests
  // ========================================================================

  describe('Permissions', () => {
    test('should request camera permissions and return granted', async () => {
      (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const status = await cameraService.requestPermissions();

      expect(status).toBe('granted');
      expect(CameraView.requestCameraPermissionsAsync).toHaveBeenCalledTimes(1);
    });

    test('should handle permission denied', async () => {
      (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
        expires: 'never',
      });

      const status = await cameraService.requestPermissions();

      expect(status).toBe('denied');
    });

    test('should handle undetermined permission status', async () => {
      (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'undetermined',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      const status = await cameraService.requestPermissions();

      expect(status).toBe('undetermined');
    });

    test('should get current permission status', async () => {
      (CameraView.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const status = await cameraService.getPermissionStatus();

      expect(status).toBe('granted');
      expect(CameraView.getCameraPermissionsAsync).toHaveBeenCalledTimes(1);
    });

    test('should return denied on permission check error', async () => {
      (CameraView.getCameraPermissionsAsync as jest.Mock).mockRejectedValue(
        new Error('Permission check failed')
      );

      const status = await cameraService.getPermissionStatus();

      expect(status).toBe('denied');
    });
  });

  // ========================================================================
  // Camera Availability Tests
  // ========================================================================

  describe('Camera Availability', () => {
    test('should check camera availability', async () => {
      (CameraView.isAvailableAsync as jest.Mock).mockResolvedValue(true);

      const isAvailable = await cameraService.isAvailable();

      expect(isAvailable).toBe(true);
      expect(CameraView.isAvailableAsync).toHaveBeenCalledTimes(1);
    });

    test('should return false when camera not available', async () => {
      (CameraView.isAvailableAsync as jest.Mock).mockResolvedValue(false);

      const isAvailable = await cameraService.isAvailable();

      expect(isAvailable).toBe(false);
    });

    test('should return false on web platform', async () => {
      // Mock web platform
      (Platform.OS as any) = 'web';

      const isAvailable = await cameraService.isAvailable();

      expect(isAvailable).toBe(false);
      expect(CameraView.isAvailableAsync).not.toHaveBeenCalled();
    });

    test('should return false on availability check error', async () => {
      (CameraView.isAvailableAsync as jest.Mock).mockRejectedValue(
        new Error('Camera check failed')
      );

      const isAvailable = await cameraService.isAvailable();

      expect(isAvailable).toBe(false);
    });
  });

  // ========================================================================
  // Photo Capture Tests
  // ========================================================================

  describe('Photo Capture', () => {
    beforeEach(() => {
      // Ensure permission is granted for capture tests
      (CameraView.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        granted: true,
        canAskAgain: true,
        expires: 'never',
      });

      mockCameraRef.current.takePictureAsync.mockResolvedValue({
        uri: 'file:///mock/photo.jpg',
        width: 1920,
        height: 1080,
      });
    });

    test('should take picture successfully', async () => {
      const media = await cameraService.takePicture(mockCameraRef);

      expect(media).toEqual({
        uri: 'file:///mock/photo.jpg',
        type: 'photo',
        width: 1920,
        height: 1080,
        size: 1024000,
      });
      expect(mockCameraRef.current.takePictureAsync).toHaveBeenCalledTimes(1);
    });

    test('should take picture with custom options', async () => {
      const options = {
        quality: 0.8,
        skipProcessing: true,
        exif: true,
      };

      await cameraService.takePicture(mockCameraRef, options);

      expect(mockCameraRef.current.takePictureAsync).toHaveBeenCalledWith(options);
    });

    test('should return null when camera ref not available', async () => {
      const emptyRef = { current: null } as any;

      const media = await cameraService.takePicture(emptyRef);

      expect(media).toBeNull();
    });

    test('should return null when permission not granted', async () => {
      // Request permissions first to set denied status
      (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        granted: false,
        canAskAgain: false,
        expires: 'never',
      });

      await cameraService.requestPermissions();

      const media = await cameraService.takePicture(mockCameraRef);

      expect(media).toBeNull();
    });

    test('should return null on capture error', async () => {
      mockCameraRef.current.takePictureAsync.mockRejectedValue(
        new Error('Capture failed')
      );

      const media = await cameraService.takePicture(mockCameraRef);

      expect(media).toBeNull();
    });

    test('should handle missing file size', async () => {
      (FileSystem.getInfoAsync as jest.Mock).mockResolvedValue({
        exists: true,
        uri: 'file:///mock/photo.jpg',
        // No size field
      });

      const media = await cameraService.takePicture(mockCameraRef);

      expect(media?.size).toBeUndefined();
    });
  });

  // ========================================================================
  // Camera Type Tests
  // ========================================================================

  describe('Camera Type (Front/Back)', () => {
    test('should get available camera types for iOS', async () => {
      (Platform.OS as any) = 'ios';

      const types = await cameraService.getAvailableCameraTypes();

      expect(types).toEqual(['back', 'front']);
    });

    test('should get available camera types for Android', async () => {
      (Platform.OS as any) = 'android';

      const types = await cameraService.getAvailableCameraTypes();

      expect(types).toEqual(['back', 'front']);
    });

    test('should return only back camera for unknown platforms', async () => {
      (Platform.OS as any) = 'unknown';

      const types = await cameraService.getAvailableCameraTypes();

      expect(types).toEqual(['back']);
    });

    test('should toggle camera between front and back', () => {
      const initial = cameraService.getCurrentCamera();
      expect(initial).toBe('back');

      const toggled = cameraService.toggleCamera();
      expect(toggled).toBe('front');
      expect(cameraService.getCurrentCamera()).toBe('front');

      const toggledBack = cameraService.toggleCamera();
      expect(toggledBack).toBe('back');
    });

    test('should set camera to specific type', () => {
      cameraService.setCamera('front');
      expect(cameraService.getCurrentCamera()).toBe('front');

      cameraService.setCamera('back');
      expect(cameraService.getCurrentCamera()).toBe('back');
    });

    test('should get CameraType for CameraView', () => {
      cameraService.setCamera('back');
      expect(cameraService.getCameraType()).toBe(CameraType.Back);

      cameraService.setCamera('front');
      expect(cameraService.getCameraType()).toBe(CameraType.Front);
    });
  });

  // ========================================================================
  // Flash Mode Tests
  // ========================================================================

  describe('Flash Mode', () => {
    test('should cycle through flash modes', () => {
      expect(cameraService.getFlashMode()).toBe('off');

      expect(cameraService.cycleFlash()).toBe('on');
      expect(cameraService.getFlashMode()).toBe('on');

      expect(cameraService.cycleFlash()).toBe('auto');
      expect(cameraService.getFlashMode()).toBe('auto');

      expect(cameraService.cycleFlash()).toBe('torch');
      expect(cameraService.getFlashMode()).toBe('torch');

      expect(cameraService.cycleFlash()).toBe('off');
      expect(cameraService.getFlashMode()).toBe('off');
    });

    test('should set flash mode directly', () => {
      cameraService.setFlash('on');
      expect(cameraService.getFlashMode()).toBe('on');

      cameraService.setFlash('off');
      expect(cameraService.getFlashMode()).toBe('off');
    });
  });

  // ========================================================================
  // Gallery Tests
  // ========================================================================

  describe('Gallery', () => {
    test('should pick image from gallery', async () => {
      (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
        canceled: false,
        assets: [
          {
            uri: 'file:///mock/gallery-image.jpg',
            width: 1920,
            height: 1080,
            fileSize: '2048000',
          },
        ],
      });

      const images = await cameraService.pickImage();

      expect(images).toHaveLength(1);
      expect(images[0]).toEqual({
        uri: 'file:///mock/gallery-image.jpg',
        type: 'photo',
        width: 1920,
        height: 1080,
        size: 2048000,
      });
    });

    test('should return empty array when picker cancelled', async () => {
      (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
        canceled: true,
        assets: [],
      });

      const images = await cameraService.pickImage();

      expect(images).toHaveLength(0);
    });

    test('should handle gallery permission denied', async () => {
      (ImagePicker.requestMediaLibraryPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
        expires: 'never',
      });

      await expect(cameraService.pickImage()).rejects.toThrow('Media library permission not granted');
    });

    test('should pick multiple images when allowed', async () => {
      (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
        canceled: false,
        assets: [
          {
            uri: 'file:///mock/image1.jpg',
            width: 1920,
            height: 1080,
            fileSize: '1024000',
          },
          {
            uri: 'file:///mock/image2.jpg',
            width: 1920,
            height: 1080,
            fileSize: '1536000',
          },
        ],
      });

      const images = await cameraService.pickImage({
        allowsMultiple: true,
        maxResults: 2,
      });

      expect(images).toHaveLength(2);
      expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalledWith({
        mediaTypes: 'images',
        allowsMultiple: true,
        maxResults: 2,
        quality: 0.9,
        exif: false,
      });
    });

    test('should throw error on picker failure', async () => {
      (ImagePicker.launchImageLibraryAsync as jest.Mock).mockRejectedValue(
        new Error('Picker failed')
      );

      await expect(cameraService.pickImage()).rejects.toThrow('Failed to pick image');
    });
  });

  // ========================================================================
  // Save to Gallery Tests
  // ========================================================================

  describe('Save to Gallery', () => {
    test('should save photo to gallery on iOS', async () => {
      (Platform.OS as any) = 'ios';
      (CameraView.savePhotoToLibraryAsync as jest.Mock).mockResolvedValue(undefined);

      const saved = await cameraService.saveToGallery('file:///mock/photo.jpg');

      expect(saved).toBe(true);
      expect(CameraView.savePhotoToLibraryAsync).toHaveBeenCalledWith('file:///mock/photo.jpg');
    });

    test('should return true on Android (auto-save)', async () => {
      (Platform.OS as any) = 'android';

      const saved = await cameraService.saveToGallery('file:///mock/photo.jpg');

      expect(saved).toBe(true);
      expect(CameraView.savePhotoToLibraryAsync).not.toHaveBeenCalled();
    });

    test('should return false on unsupported platform', async () => {
      (Platform.OS as any) = 'web';

      const saved = await cameraService.saveToGallery('file:///mock/photo.jpg');

      expect(saved).toBe(false);
    });

    test('should return false on save error', async () => {
      (Platform.OS as any) = 'ios';
      (CameraView.savePhotoToLibraryAsync as jest.Mock).mockRejectedValue(
        new Error('Save failed')
      );

      const saved = await cameraService.saveToGallery('file:///mock/photo.jpg');

      expect(saved).toBe(false);
    });
  });

  // ========================================================================
  // Video Recording Tests
  // ========================================================================

  describe('Video Recording', () => {
    beforeEach(() => {
      // Reset permission to granted for these tests
      (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      (CameraView.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        granted: true,
        canAskAgain: true,
        expires: 'never',
      });

      mockCameraRef.current.recordAsync.mockResolvedValue({
        uri: 'file:///mock/video.mp4',
      });
    });

    test('should start video recording', async () => {
      // Ensure permission is granted
      await cameraService.requestPermissions();

      const media = await cameraService.recordVideo(mockCameraRef);

      expect(media).toEqual({
        uri: 'file:///mock/video.mp4',
        type: 'video',
      });
      expect(mockCameraRef.current.recordAsync).toHaveBeenCalled();
    });

    test('should record with custom options', async () => {
      // Ensure permission is granted
      await cameraService.requestPermissions();

      const options = {
        quality: '720p' as const,
        maxDuration: 30,
        mute: true,
      };

      await cameraService.recordVideo(mockCameraRef, options);

      expect(mockCameraRef.current.recordAsync).toHaveBeenCalledWith(options);
    });

    test('should return null when camera ref not available for recording', async () => {
      const emptyRef = { current: null } as any;

      const media = await cameraService.recordVideo(emptyRef);

      expect(media).toBeNull();
    });

    test('should return null when permission not granted for recording', async () => {
      // Request permissions first to set denied status
      (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        granted: false,
        canAskAgain: false,
        expires: 'never',
      });

      await cameraService.requestPermissions();

      const media = await cameraService.recordVideo(mockCameraRef);

      expect(media).toBeNull();
    });
  });

  // ========================================================================
  // Platform-Specific Behavior Tests
  // ========================================================================

  describe('Platform-Specific Behavior', () => {
    test('should handle iOS platform differences', async () => {
      (Platform.OS as any) = 'ios';

      await cameraService.saveToGallery('file:///mock/photo.jpg');
      const types = await cameraService.getAvailableCameraTypes();

      expect(CameraView.savePhotoToLibraryAsync).toHaveBeenCalled();
      expect(types).toContain('front');
      expect(types).toContain('back');
    });

    test('should handle Android platform differences', async () => {
      (Platform.OS as any) = 'android';

      await cameraService.saveToGallery('file:///mock/photo.jpg');
      const types = await cameraService.getAvailableCameraTypes();

      expect(CameraView.savePhotoToLibraryAsync).not.toHaveBeenCalled();
      expect(types).toContain('front');
      expect(types).toContain('back');
    });
  });
});
