/**
 * Camera Service
 *
 * Manages camera functionality for mobile devices.
 *
 * Features:
 * - Photo capture
 * - Video recording
 * - Camera permissions
 * - Front/back camera switching
 * - Flash control
 * - Image gallery access
 *
 * Uses expo-camera for cross-platform camera support.
 */

import { CameraView, CameraType, CameraPermissionStatus } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system';
import { Platform } from 'react-native';

// Types
export type CameraPermission = 'undetermined' | 'granted' | 'denied';

export type CameraFace = 'front' | 'back';

export type FlashMode = 'off' | 'on' | 'auto' | 'torch';

export type CameraMode = 'picture' | 'video';

export interface PhotoOptions {
  quality: number; // 0-1
  skipProcessing: boolean;
  exif?: boolean;
}

export interface VideoOptions {
  quality?: VideoQuality;
  maxDuration?: number; // seconds
  maxFileSize?: number; // bytes
  mute?: boolean;
}

export type VideoQuality = '2160p' | '1080p' | '720p' | '480p' | '360p';

export interface CapturedMedia {
  uri: string;
  type: 'photo' | 'video';
  width?: number;
  height?: number;
  duration?: number; // Video duration in seconds
  size?: number; // File size in bytes
}

/**
 * Camera Service
 */
class CameraService {
  private permissionStatus: CameraPermission = 'undetermined';
  private currentCamera: CameraFace = 'back';
  private currentFlash: FlashMode = 'off';

  /**
   * Initialize the camera service
   */
  async initialize(): Promise<void> {
    try {
      const { status } = await CameraView.getCameraPermissionsAsync();
      this.permissionStatus = status === 'granted' ? 'granted' : status;

      console.log('CameraService: Initialized, permission:', this.permissionStatus);
    } catch (error) {
      console.error('CameraService: Failed to initialize:', error);
    }
  }

  /**
   * Request camera permissions
   */
  async requestPermissions(): Promise<CameraPermission> {
    try {
      const { status } = await CameraView.requestCameraPermissionsAsync();
      this.permissionStatus = status === 'granted' ? 'granted' : status;

      console.log('CameraService: Permission requested, status:', this.permissionStatus);
      return this.permissionStatus;
    } catch (error) {
      console.error('CameraService: Failed to request permissions:', error);
      return 'denied';
    }
  }

  /**
   * Get current permission status
   */
  async getPermissionStatus(): Promise<CameraPermission> {
    try {
      const { status } = await CameraView.getCameraPermissionsAsync();
      this.permissionStatus = status === 'granted' ? 'granted' : status;
      return this.permissionStatus;
    } catch (error) {
      console.error('CameraService: Failed to get permission status:', error);
      return 'denied';
    }
  }

  /**
   * Check if camera is available
   */
  async isAvailable(): Promise<boolean> {
    try {
      if (Platform.OS === 'web') {
        return false; // Camera not supported on web
      }

      const isAvailable = await CameraView.isAvailableAsync();
      return isAvailable;
    } catch (error) {
      console.error('CameraService: Failed to check availability:', error);
      return false;
    }
  }

  /**
   * Take a picture
   */
  async takePicture(
    cameraRef: React.RefObject<CameraView>,
    options: PhotoOptions = {
      quality: 0.9,
      skipProcessing: false,
    }
  ): Promise<CapturedMedia | null> {
    try {
      if (!cameraRef.current) {
        throw new Error('Camera ref not available');
      }

      if (this.permissionStatus !== 'granted') {
        throw new Error('Camera permission not granted');
      }

      const photo = await cameraRef.current.takePictureAsync(options);

      // Get file info
      const fileInfo = await FileSystem.getInfoAsync(photo.uri);

      const media: CapturedMedia = {
        uri: photo.uri,
        type: 'photo',
        width: photo.width,
        height: photo.height,
        size: fileInfo.size ? parseInt(fileInfo.size, 10) : undefined,
      };

      console.log('CameraService: Photo captured', media);
      return media;
    } catch (error) {
      console.error('CameraService: Failed to take picture:', error);
      return null;
    }
  }

  /**
   * Record video
   */
  async recordVideo(
    cameraRef: React.RefObject<CameraView>,
    options: VideoOptions = {
      quality: '1080p',
      maxDuration: 60, // 1 minute
      mute: false,
    }
  ): Promise<CapturedMedia | null> {
    try {
      if (!cameraRef.current) {
        throw new Error('Camera ref not available');
      }

      if (this.permissionStatus !== 'granted') {
        throw new Error('Camera permission not granted');
      }

      const video = await cameraRef.current.recordAsync(options);

      console.log('CameraService: Video recording started');
      // Note: The video recording is ongoing, caller must call stopRecording

      return {
        uri: video.uri,
        type: 'video',
      };
    } catch (error) {
      console.error('CameraService: Failed to record video:', error);
      return null;
    }
  }

  /**
   * Stop video recording
   */
  async stopRecording(cameraRef: React.RefObject<CameraView>): Promise<CapturedMedia | null> {
    try {
      if (!cameraRef.current) {
        throw new Error('Camera ref not available');
      }

      const video = await cameraRef.current.stopRecording();

      // Get file info
      const fileInfo = await FileSystem.getInfoAsync(video.uri);

      const media: CapturedMedia = {
        uri: video.uri,
        type: 'video',
        size: fileInfo.size ? parseInt(fileInfo.size, 10) : undefined,
      };

      console.log('CameraService: Video recording stopped', media);
      return media;
    } catch (error) {
      console.error('CameraService: Failed to stop recording:', error);
      return null;
    }
  }

  /**
   * Pick image from gallery
   */
  async pickImage(options?: {
    allowsMultiple?: boolean;
    maxResults?: number;
    quality?: number;
    exif?: boolean;
  }): Promise<CapturedMedia[]> {
    try {
      // Request media library permissions
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();

      if (status !== ImagePicker.PermissionStatus.GRANTED) {
        throw new Error('Media library permission not granted');
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsMultiple: options?.allowsMultiple ?? false,
        maxResults: options?.maxResults ?? 1,
        quality: options?.quality ?? 0.9,
        exif: options?.exif ?? false,
      });

      if (result.canceled) {
        return [];
      }

      const media: CapturedMedia[] = result.assets.map((asset) => ({
        uri: asset.uri,
        type: 'photo',
        width: asset.width,
        height: asset.height,
        size: asset.fileSize ? parseInt(asset.fileSize, 10) : undefined,
      }));

      console.log(`CameraService: ${media.length} image(s) picked`);
      return media;
    } catch (error) {
      console.error('CameraService: Failed to pick image:', error);
      return [];
    }
  }

  /**
   * Take a picture or pick from gallery (user choice)
   */
  async captureOrPick(options?: {
    camera?: PhotoOptions;
    gallery?: ImagePicker.ImagePickerOptions;
    allowsEditing?: boolean;
  }): Promise<CapturedMedia | null> {
    try {
      // Request camera and media library permissions
      await this.requestPermissions();
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();

      if (status !== ImagePicker.PermissionStatus.GRANTED) {
        throw new Error('Media library permission not granted');
      }

      // Show picker with camera option
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        selectionLimit: 1,
        quality: options?.camera?.quality ?? 0.9,
        exif: options?.camera?.exif ?? false,
      });

      if (result.canceled || result.assets.length === 0) {
        // User cancelled, could offer to use camera here
        return null;
      }

      const asset = result.assets[0];
      return {
        uri: asset.uri,
        type: 'photo',
        width: asset.width,
        height: asset.height,
      };
    } catch (error) {
      console.error('CameraService: Failed to capture or pick:', error);
      return null;
    }
  }

  /**
   * Get available camera types
   */
  async getAvailableCameraTypes(): Promise<CameraFace[]> {
    try {
      if (Platform.OS === 'android') {
        return ['back', 'front'];
      } else if (Platform.OS === 'ios') {
        return ['back', 'front'];
      }
      return ['back'];
    } catch (error) {
      console.error('CameraService: Failed to get camera types:', error);
      return ['back'];
    }
  }

  /**
   * Switch camera (front/back)
   */
  toggleCamera(): CameraFace {
    this.currentCamera = this.currentCamera === 'back' ? 'front' : 'back';
    console.log('CameraService: Camera switched to', this.currentCamera);
    return this.currentCamera;
  }

  /**
   * Get current camera
   */
  getCurrentCamera(): CameraFace {
    return this.currentCamera;
  }

  /**
   * Set camera
   */
  setCamera(camera: CameraFace): void {
    this.currentCamera = camera;
  }

  /**
   * Cycle flash mode
   */
  cycleFlash(): FlashMode {
    const modes: FlashMode[] = ['off', 'on', 'auto', 'torch'];
    const currentIndex = modes.indexOf(this.currentFlash);
    const nextIndex = (currentIndex + 1) % modes.length;
    this.currentFlash = modes[nextIndex];
    console.log('CameraService: Flash mode set to', this.currentFlash);
    return this.currentFlash;
  }

  /**
   * Get current flash mode
   */
  getFlashMode(): FlashMode {
    return this.currentFlash;
  }

  /**
   * Set flash mode
   */
  setFlash(mode: FlashMode): void {
    this.currentFlash = mode;
  }

  /**
   * Save photo to device gallery
   */
  async saveToGallery(uri: string): Promise<boolean> {
    try {
      if (Platform.OS === 'ios') {
        await CameraView.savePhotoToLibraryAsync(uri);
        console.log('CameraService: Photo saved to gallery');
        return true;
      } else if (Platform.OS === 'android') {
        // Android automatically saves to gallery
        console.log('CameraService: Photo automatically saved to gallery');
        return true;
      }
      return false;
    } catch (error) {
      console.error('CameraService: Failed to save to gallery:', error);
      return false;
    }
  }

  /**
   * Get camera type for CameraView
   */
  getCameraType(): CameraType {
    return this.currentCamera === 'front' ? CameraType.Front : CameraType.Back;
  }
}

// Export singleton instance
export const cameraService = new CameraService();

export default cameraService;
