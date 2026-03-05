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
import * as ImageManipulator from 'expo-image-manipulator';
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

// Mock expo-image-manipulator
jest.mock('expo-image-manipulator', () => {
  return {
    manipulateAsync: jest.fn().mockResolvedValue({
      uri: 'file:///mock/manipulated.jpg',
      width: 1920,
      height: 1080,
    }),
    SaveFormat: {
      JPEG: 'jpeg',
      PNG: 'png',
    },
    FlipType: {
      Horizontal: 'horizontal',
      Vertical: 'vertical',
    },
    default: {
      manipulateAsync: jest.fn().mockResolvedValue({
        uri: 'file:///mock/manipulated.jpg',
        width: 1920,
        height: 1080,
      }),
      SaveFormat: {
        JPEG: 'jpeg',
        PNG: 'png',
      },
      FlipType: {
        Horizontal: 'horizontal',
        Vertical: 'vertical',
      },
    },
  };
});

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
    // Don't reset modules - it breaks the mocks

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

    // Re-setup ImageManipulator mock after clearing
    (ImageManipulator.manipulateAsync as jest.Mock).mockResolvedValue({
      uri: 'file:///mock/manipulated.jpg',
      width: 1920,
      height: 1080,
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
        quality: 0.8,
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

  // ========================================================================
  // Barcode Scanning Tests
  // ========================================================================

  describe('Barcode Scanning', () => {
    test('should scan QR code successfully', async () => {
      const mockBarcodeResult = {
        barcodes: [
          {
            type: 'qr',
            rawValue: 'https://example.com',
            cornerPoints: [
              { x: 0, y: 0 },
              { x: 100, y: 0 },
              { x: 100, y: 100 },
              { x: 0, y: 100 },
            ],
          },
        ],
      };

      const result = await cameraService.scanBarcode(mockBarcodeResult as any);

      expect(result).toEqual({
        type: 'qr',
        data: 'https://example.com',
        corners: {
          topLeft: { x: 0, y: 0 },
          topRight: { x: 100, y: 0 },
          bottomRight: { x: 100, y: 100 },
          bottomLeft: { x: 0, y: 100 },
        },
      });
    });

    test('should return first barcode when multiple present', async () => {
      const mockBarcodeResult = {
        barcodes: [
          {
            type: 'qr',
            rawValue: 'https://example.com',
            cornerPoints: [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 100 }, { x: 0, y: 100 }],
          },
          {
            type: 'code128',
            rawValue: '123456789',
            cornerPoints: [{ x: 10, y: 10 }, { x: 90, y: 10 }, { x: 90, y: 90 }, { x: 10, y: 90 }],
          },
          {
            type: 'ean13',
            rawValue: '9780141026626',
            cornerPoints: [{ x: 20, y: 20 }, { x: 80, y: 20 }, { x: 80, y: 80 }, { x: 20, y: 80 }],
          },
        ],
      };

      const result = await cameraService.scanBarcode(mockBarcodeResult as any);

      expect(result).toEqual({
        type: 'qr',
        data: 'https://example.com',
        corners: {
          topLeft: { x: 0, y: 0 },
          topRight: { x: 100, y: 0 },
          bottomRight: { x: 100, y: 100 },
          bottomLeft: { x: 0, y: 100 },
        },
      });
    });

    test('should return null when no barcodes present', async () => {
      const mockBarcodeResult = {
        barcodes: [],
      };

      const result = await cameraService.scanBarcode(mockBarcodeResult as any);

      expect(result).toBeNull();
    });

    test('should return null when barcode result is null', async () => {
      const result = await cameraService.scanBarcode(null);

      expect(result).toBeNull();
    });

    test('should return undefined corners when corner points missing', async () => {
      const mockBarcodeResult = {
        barcodes: [
          {
            type: 'qr',
            rawValue: 'https://example.com',
            cornerPoints: [
              { x: 0, y: 0 },
              { x: 100, y: 0 },
              // Missing 2 corner points
            ],
          },
        ],
      };

      const result = await cameraService.scanBarcode(mockBarcodeResult as any);

      expect(result).toEqual({
        type: 'qr',
        data: 'https://example.com',
        corners: undefined,
      });
    });
  });

  // ========================================================================
  // Multiple Photo Capture Tests
  // ========================================================================

  describe('Multiple Photos', () => {
    beforeEach(async () => {
      // Initialize camera service to set permission status
      await cameraService.initialize();

      // Ensure permission is granted for capture tests
      (CameraView.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        granted: true,
        canAskAgain: true,
        expires: 'never',
      });

      // Mock takePictureAsync for multiple calls
      mockCameraRef.current.takePictureAsync.mockImplementation(async () => ({
        uri: `file:///mock/photo-${Date.now()}.jpg`,
        width: 1920,
        height: 1080,
      }));
    });

    test('should capture multiple photos', async () => {
      const photos = await cameraService.captureMultiplePhotos(mockCameraRef, 3);

      expect(photos).toHaveLength(3);
      expect(mockCameraRef.current.takePictureAsync).toHaveBeenCalledTimes(3);
      expect(photos[0].uri).toContain('photo-');
      expect(photos[0].type).toBe('photo');
      expect(photos[0].width).toBe(1920);
      expect(photos[0].height).toBe(1080);
    });

    test('should get captured photos with index', async () => {
      await cameraService.captureMultiplePhotos(mockCameraRef, 2);

      const captured = cameraService.getCapturedPhotos();

      expect(captured.photos).toHaveLength(2);
      expect(captured.currentIndex).toBe(0);
      expect(captured.photos[0].type).toBe('photo');
    });

    test('should delete captured photo at index', async () => {
      await cameraService.captureMultiplePhotos(mockCameraRef, 3);

      cameraService.deleteCapturedPhoto(1);

      const captured = cameraService.getCapturedPhotos();
      expect(captured.photos).toHaveLength(2);
      expect(captured.photos[0].uri).toBeTruthy();
      expect(captured.photos[1].uri).toBeTruthy();
    });

    test('should clear all captured photos', async () => {
      await cameraService.captureMultiplePhotos(mockCameraRef, 3);

      cameraService.clearCapturedPhotos();

      const captured = cameraService.getCapturedPhotos();
      expect(captured.photos).toHaveLength(0);
      expect(captured.currentIndex).toBe(0);
    });

    test('should handle delete with invalid index gracefully', async () => {
      await cameraService.captureMultiplePhotos(mockCameraRef, 3);

      const beforeDelete = cameraService.getCapturedPhotos();
      cameraService.deleteCapturedPhoto(10); // Invalid index
      const afterDelete = cameraService.getCapturedPhotos();

      expect(beforeDelete.photos).toHaveLength(afterDelete.photos.length);
      expect(beforeDelete.photos[0].uri).toBe(afterDelete.photos[0].uri);
    });
  });

  // ========================================================================
  // Image Manipulation Tests
  // ========================================================================

  describe('Image Manipulation', () => {
    test('should rotate image by 90 degrees', async () => {
      const resultUri = await cameraService.rotateImage('file:///mock/photo.jpg', 90);

      expect(resultUri).toBe('file:///mock/manipulated.jpg');
      expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith(
        'file:///mock/photo.jpg',
        [{ rotate: 90 }],
        {
          compress: 0.8,
          format: ImageManipulator.SaveFormat.JPEG,
        }
      );
    });

    test('should flip image horizontally', async () => {
      const resultUri = await cameraService.flipImage('file:///mock/photo.jpg', true);

      expect(resultUri).toBe('file:///mock/manipulated.jpg');
      expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith(
        'file:///mock/photo.jpg',
        [{ flip: ImageManipulator.FlipType.Horizontal }],
        {
          compress: 0.8,
          format: ImageManipulator.SaveFormat.JPEG,
        }
      );
    });

    test('should flip image vertically', async () => {
      const resultUri = await cameraService.flipImage('file:///mock/photo.jpg', false);

      expect(resultUri).toBe('file:///mock/manipulated.jpg');
      expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith(
        'file:///mock/photo.jpg',
        [{ flip: ImageManipulator.FlipType.Vertical }],
        {
          compress: 0.8,
          format: ImageManipulator.SaveFormat.JPEG,
        }
      );
    });

    test('should rotate image by 180 degrees (2x90)', async () => {
      const resultUri = await cameraService.rotateImage('file:///mock/photo.jpg', 180);

      expect(resultUri).toBe('file:///mock/manipulated.jpg');
      expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith(
        'file:///mock/photo.jpg',
        [{ rotate: 180 }, { rotate: 180 }],
        {
          compress: 0.8,
          format: ImageManipulator.SaveFormat.JPEG,
        }
      );
    });

    test('should crop image to document bounds', async () => {
      const mockCorners = {
        topLeft: { x: 10, y: 10 },
        topRight: { x: 90, y: 10 },
        bottomRight: { x: 90, y: 90 },
        bottomLeft: { x: 10, y: 90 },
      };

      const resultUri = await cameraService.cropToDocument('file:///mock/photo.jpg', mockCorners);

      expect(resultUri).toBe('file:///mock/manipulated.jpg');
      expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith(
        'file:///mock/photo.jpg',
        [{ crop: { originX: 10, originY: 10, width: 80, height: 80 } }],
        {
          compress: 0.8,
          format: ImageManipulator.SaveFormat.JPEG,
        }
      );
    });
  });

  // ========================================================================
  // Camera Mode Tests
  // ========================================================================

  describe('Camera Mode', () => {
    beforeEach(() => {
      // Reset camera mode to default before each test
      cameraService.reset();
    });

    test('should get default camera mode', () => {
      const mode = cameraService.getCameraMode();

      expect(mode).toBe('picture');
    });

    test('should set camera mode to video', () => {
      cameraService.setCameraMode('video');

      expect(cameraService.getCameraMode()).toBe('video');
    });

    test('should set camera mode to document', () => {
      cameraService.setCameraMode('document');

      expect(cameraService.getCameraMode()).toBe('document');
    });

    test('should set camera mode to barcode', () => {
      cameraService.setCameraMode('barcode');

      expect(cameraService.getCameraMode()).toBe('barcode');
    });

    test('should cycle through all camera modes', () => {
      expect(cameraService.getCameraMode()).toBe('picture');

      cameraService.setCameraMode('video');
      expect(cameraService.getCameraMode()).toBe('video');

      cameraService.setCameraMode('document');
      expect(cameraService.getCameraMode()).toBe('document');

      cameraService.setCameraMode('barcode');
      expect(cameraService.getCameraMode()).toBe('barcode');

      cameraService.setCameraMode('picture');
      expect(cameraService.getCameraMode()).toBe('picture');
    });
  });

  // ========================================================================
  // Document Edge Detection Tests
  // ========================================================================

  describe('Document Edge Detection', () => {
    test('should return null for document edge detection (not implemented)', async () => {
      const corners = await cameraService.detectDocumentEdges('file:///mock/photo.jpg');

      expect(corners).toBeNull();
    });

    test('should handle edge detection error gracefully', async () => {
      // The function logs and returns null on any error
      const corners = await cameraService.detectDocumentEdges('invalid-uri');

      expect(corners).toBeNull();
    });
  });

  // ========================================================================
  // EXIF Data Tests
  // ========================================================================

  describe('EXIF Data', () => {
    beforeEach(async () => {
      // Reset camera service
      cameraService.reset();

      // Initialize and grant permission
      await cameraService.initialize();

      // Ensure permission is granted
      (CameraView.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        granted: true,
        canAskAgain: true,
        expires: 'never',
      });

      (FileSystem.getInfoAsync as jest.Mock).mockResolvedValue({
        exists: true,
        size: '1024000',
        uri: 'file:///mock/photo.jpg',
      });
    });

    test('should preserve EXIF data when available', async () => {
      const mockExifData = {
        DateTime: '2024:03:04 12:00:00',
        Make: 'Apple',
        Model: 'iPhone 14',
        Orientation: 1,
        GPSLatitude: 37.7749,
        GPSLongitude: -122.4194,
      };

      mockCameraRef.current.takePictureAsync.mockResolvedValue({
        uri: 'file:///mock/photo.jpg',
        width: 1920,
        height: 1080,
        exif: mockExifData,
      });

      const media = await cameraService.takePicture(mockCameraRef, { exif: true });

      expect(media?.exif).toEqual(mockExifData);
      expect(media?.exif?.Make).toBe('Apple');
      expect(media?.exif?.Model).toBe('iPhone 14');
    });

    test('should handle missing EXIF data gracefully', async () => {
      mockCameraRef.current.takePictureAsync.mockResolvedValue({
        uri: 'file:///mock/photo.jpg',
        width: 1920,
        height: 1080,
        // No exif property
      });

      const media = await cameraService.takePicture(mockCameraRef);

      expect(media?.exif).toBeUndefined();
    });

    test('should request EXIF data when exif option is true', async () => {
      mockCameraRef.current.takePictureAsync.mockResolvedValue({
        uri: 'file:///mock/photo.jpg',
        width: 1920,
        height: 1080,
        exif: { DateTime: '2024:03:04 12:00:00' },
      });

      await cameraService.takePicture(mockCameraRef, { exif: true });

      expect(mockCameraRef.current.takePictureAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          exif: true,
        })
      );
    });
  });

  // ========================================================================
  // Additional Platform-Specific Tests
  // ========================================================================

  describe('Additional Platform-Specific Behavior', () => {
    afterEach(() => {
      // Restore platform to iOS after each test
      (Platform.OS as any) = 'ios';
    });

    test('should get available camera types for Android', async () => {
      (Platform.OS as any) = 'android';

      const types = await cameraService.getAvailableCameraTypes();

      expect(types).toEqual(['back', 'front']);
    });

    test('should get available camera types for iOS', async () => {
      (Platform.OS as any) = 'ios';

      const types = await cameraService.getAvailableCameraTypes();

      expect(types).toEqual(['back', 'front']);
    });

    test('should handle getCameraTypes error', async () => {
      (Platform.OS as any) = 'unknown';

      const types = await cameraService.getAvailableCameraTypes();

      expect(types).toEqual(['back']);
    });
  });

  // ========================================================================
  // Service Reset Tests
  // ========================================================================

  describe('Service Reset', () => {
    test('should reset service state to defaults', () => {
      // Change some state
      cameraService.setCamera('front');
      cameraService.setFlash('on');
      cameraService.setCameraMode('video');

      // Reset
      cameraService.reset();

      // Verify defaults
      expect(cameraService.getCurrentCamera()).toBe('back');
      expect(cameraService.getFlashMode()).toBe('off');
      expect(cameraService.getCameraMode()).toBe('picture');
    });

    test('should clear captured photos on reset', async () => {
      // Capture some photos
      await cameraService.initialize();
      (CameraView.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        granted: true,
        canAskAgain: true,
        expires: 'never',
      });

      mockCameraRef.current.takePictureAsync.mockImplementation(async () => ({
        uri: `file:///mock/photo-${Date.now()}.jpg`,
        width: 1920,
        height: 1080,
      }));

      await cameraService.captureMultiplePhotos(mockCameraRef, 3);

      // Reset
      cameraService.reset();

      // Verify photos cleared
      const captured = cameraService.getCapturedPhotos();
      expect(captured.photos).toHaveLength(0);
      expect(captured.currentIndex).toBe(0);
    });
  });

  // ========================================================================
  // Error Handling Tests
  // ========================================================================

  describe('Error Handling', () => {
    test('should handle rotateImage error gracefully', async () => {
      (ImageManipulator.manipulateAsync as jest.Mock).mockRejectedValue(
        new Error('Manipulation failed')
      );

      const resultUri = await cameraService.rotateImage('file:///mock/photo.jpg', 90);

      expect(resultUri).toBeNull();
    });

    test('should handle flipImage error gracefully', async () => {
      (ImageManipulator.manipulateAsync as jest.Mock).mockRejectedValue(
        new Error('Flip failed')
      );

      const resultUri = await cameraService.flipImage('file:///mock/photo.jpg', true);

      expect(resultUri).toBeNull();
    });

    test('should handle cropToDocument error gracefully', async () => {
      (ImageManipulator.manipulateAsync as jest.Mock).mockRejectedValue(
        new Error('Crop failed')
      );

      const mockCorners = {
        topLeft: { x: 10, y: 10 },
        topRight: { x: 90, y: 10 },
        bottomRight: { x: 90, y: 90 },
        bottomLeft: { x: 10, y: 90 },
      };

      const resultUri = await cameraService.cropToDocument('file:///mock/photo.jpg', mockCorners);

      expect(resultUri).toBeNull();
    });

    test('should handle requestPermissions error gracefully', async () => {
      (CameraView.requestCameraPermissionsAsync as jest.Mock).mockRejectedValue(
        new Error('Permission request failed')
      );

      const status = await cameraService.requestPermissions();

      expect(status).toBe('denied');
    });

    test('should handle initialize error gracefully', async () => {
      (CameraView.getCameraPermissionsAsync as jest.Mock).mockRejectedValue(
        new Error('Initialize failed')
      );

      await cameraService.initialize();

      // Should not throw, just log error
      expect(CameraView.getCameraPermissionsAsync).toHaveBeenCalled();
    });
  });
});
