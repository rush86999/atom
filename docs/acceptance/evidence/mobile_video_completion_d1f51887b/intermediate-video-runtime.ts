/**
 * Camera Service
 *
 * Manages camera functionality for mobile devices.
 *
 * Features:
 * - Photo capture with compression
 * - Video recording
 * - Camera permissions
 * - Front/back camera switching
 * - Flash control (auto/on/off/torch)
 * - Image gallery access
 * - Document capture; automatic edge detection is currently a placeholder
 * - Barcode/QR code scanning
 * - Multiple photo capture
 * - EXIF data preservation
 * - Image cropping and rotation
 *
 * Uses expo-camera for cross-platform camera support.
 */

import {
  Camera,
  CameraView,
  PermissionStatus,
  type BarcodeScanningResult,
  type CameraType,
} from 'expo-camera/next';
import * as ImagePicker from 'expo-image-picker';
import * as MediaLibrary from 'expo-media-library';
import * as FileSystem from 'expo-file-system';
import * as ImageManipulator from 'expo-image-manipulator';
import { Platform } from 'react-native';

// Types
export type CameraPermission = 'undetermined' | 'granted' | 'denied';

export type CameraFace = 'front' | 'back';

export type FlashMode = 'off' | 'on' | 'auto' | 'torch';

export type CameraMode = 'picture' | 'video' | 'document' | 'barcode';

export interface PhotoOptions {
  quality?: number; // 0-1
  skipProcessing?: boolean;
  exif?: boolean;
}

export interface VideoOptions {
  /** CameraView `videoQuality` prop; applied by the consumer, never passed to recordAsync. */
  quality?: VideoQuality;
  /** recordAsync option: maximum video duration in seconds. */
  maxDuration?: number;
  /** recordAsync option: maximum video file size in bytes. */
  maxFileSize?: number;
  /** CameraView `mute` prop; applied by the consumer, never passed to recordAsync. */
  mute?: boolean;
}

/** SDK-supported qualities plus the legacy 360p input, which refuses without coercion. */
export type VideoQuality = '2160p' | '1080p' | '720p' | '480p' | '4:3' | '360p';

const SUPPORTED_VIDEO_QUALITIES: readonly VideoQuality[] = [
  '2160p',
  '1080p',
  '720p',
  '480p',
  '4:3',
];

export interface CapturedMedia {
  uri: string;
  type: 'photo' | 'video';
  width?: number;
  height?: number;
  duration?: number; // Video duration in seconds
  size?: number; // File size in bytes
  exif?: any; // EXIF metadata
}

export interface DocumentEdge {
  x: number;
  y: number;
}

export interface DocumentCorners {
  topLeft: DocumentEdge;
  topRight: DocumentEdge;
  bottomRight: DocumentEdge;
  bottomLeft: DocumentEdge;
}

export interface BarcodeResult {
  type: string;
  data: string;
  corners?: DocumentCorners;
}

export interface CapturedPhotos {
  photos: CapturedMedia[];
  currentIndex: number;
}

// Configuration
const COMPRESSION_QUALITY = 0.8;
const MAX_IMAGE_DIMENSION = 2048;

interface InFlightRecording {
  readonly token: symbol;
  readonly completion: Promise<CapturedMedia | null>;
  stopping: boolean;
}

function toCameraPermission(status: PermissionStatus): CameraPermission {
  switch (status) {
    case PermissionStatus.GRANTED:
      return 'granted';
    case PermissionStatus.DENIED:
      return 'denied';
    default:
      return 'undetermined';
  }
}

/**
 * Camera Service
 */
class CameraService {
  private permissionStatus: CameraPermission = 'undetermined';
  private currentCamera: CameraFace = 'back';
  private currentFlash: FlashMode = 'off';
  private currentMode: CameraMode = 'picture';
  private capturedPhotos: CapturedMedia[] = [];
  private currentPhotoIndex = 0;
  private readonly activeRecordings = new WeakMap<CameraView, InFlightRecording>();

  /**
   * Initialize the camera service
   */
  async initialize(): Promise<void> {
    try {
      const { status } = await Camera.getCameraPermissionsAsync();
      this.permissionStatus = toCameraPermission(status);

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
      const { status } = await Camera.requestCameraPermissionsAsync();
      this.permissionStatus = toCameraPermission(status);

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
      const { status } = await Camera.getCameraPermissionsAsync();
      this.permissionStatus = toCameraPermission(status);
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
      quality: COMPRESSION_QUALITY,
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
      if (!photo) {
        return null;
      }

      // Get file info
      const fileInfo = await FileSystem.getInfoAsync(photo.uri);

      // Compress image if needed
      let finalUri = photo.uri;
      if (photo.width && photo.height) {
        const maxDimension = Math.max(photo.width, photo.height);
        if (maxDimension > MAX_IMAGE_DIMENSION) {
          const scale = MAX_IMAGE_DIMENSION / maxDimension;
          const compressed = await ImageManipulator.manipulateAsync(
            photo.uri,
            [{ resize: { width: Math.round(photo.width * scale) } }],
            {
              compress: COMPRESSION_QUALITY,
              format: ImageManipulator.SaveFormat.JPEG,
            }
          );
          finalUri = compressed.uri;
        }
      }

      const media: CapturedMedia = {
        uri: finalUri,
        type: 'photo',
        width: photo.width,
        height: photo.height,
        size: fileInfo.exists ? fileInfo.size : undefined,
        exif: photo.exif || undefined,
      };

      console.log('CameraService: Photo captured', media);
      return media;
    } catch (error) {
      console.error('CameraService: Failed to take picture:', error);
      return null;
    }
  }

  /**
   * Fail closed when requested CameraView props do not match the mounted
   * camera, instead of silently recording with different settings.
   */
  private assertVideoCameraConfigured(camera: CameraView, options: VideoOptions): void {
    if (camera.props.mode !== 'video') {
      throw new Error("Set mode='video' on CameraView before starting a recording.");
    }
    if (options.quality !== undefined) {
      if (!SUPPORTED_VIDEO_QUALITIES.includes(options.quality)) {
        throw new Error(
          `Unsupported video quality '${options.quality}'. Supported values: ${SUPPORTED_VIDEO_QUALITIES.join(', ')}. ` +
            `360p is not supported by expo-camera and is not coerced.`
        );
      }

      if (camera.props.videoQuality !== options.quality) {
        throw new Error(
          `Video quality '${options.quality}' is a CameraView prop, not a recordAsync option. ` +
            `Set videoQuality='${options.quality}' on CameraView (currently '${camera.props.videoQuality ?? 'default'}').`
        );
      }
    }

    if (options.mute !== undefined && (camera.props.mute ?? false) !== options.mute) {
      throw new Error(
        `mute=${String(options.mute)} is a CameraView prop, not a recordAsync option. ` +
          `Set mute={${String(options.mute)}} on CameraView (currently ${String(camera.props.mute ?? false)}).`
      );
    }
  }

  /**
   * Resolve exactly when the native recording completes and clean up only the
   * generation that owns this token.
   */
  private async awaitRecording(
    camera: CameraView,
    token: symbol,
    nativeRecording: Promise<{ uri: string } | undefined>
  ): Promise<CapturedMedia | null> {
    try {
      const video = await nativeRecording;
      if (!video || typeof video.uri !== 'string' || video.uri.length === 0) {
        return null;
      }

      let size: number | undefined;
      try {
        const fileInfo = await FileSystem.getInfoAsync(video.uri);
        if (fileInfo.exists) {
          size = fileInfo.size;
        }
      } catch (error) {
        console.error('CameraService: Failed to inspect recorded video:', error);
      }

      return {
        uri: video.uri,
        type: 'video',
        size,
      };
    } catch (error) {
      console.error('CameraService: Video recording failed:', error);
      return null;
    } finally {
      const active = this.activeRecordings.get(camera);
      if (active?.token === token) {
        this.activeRecordings.delete(camera);
      }
    }
  }

  /**
   * Record video. The returned promise resolves with the completed recording
   * when stopRecording, maxDuration, or maxFileSize ends it.
   */
  async recordVideo(
    cameraRef: React.RefObject<CameraView>,
    options: VideoOptions = {
      maxDuration: 60, // 1 minute
    }
  ): Promise<CapturedMedia | null> {
    try {
      const camera = cameraRef.current;
      if (!camera) {
        throw new Error('Camera ref not available');
      }

      if (this.permissionStatus !== 'granted') {
        throw new Error('Camera permission not granted');
      }

      if (this.activeRecordings.has(camera)) {
        // A second request is not the original capture, even if its settings
        // happen to match. Keep that capture tracked until its real completion.
        throw new Error('A video recording is already in progress for this camera.');
      }

      this.assertVideoCameraConfigured(camera, options);

      const recordingOptions: { maxDuration?: number; maxFileSize?: number } = {};
      if (options.maxDuration !== undefined) {
        recordingOptions.maxDuration = options.maxDuration;
      }
      if (options.maxFileSize !== undefined) {
        recordingOptions.maxFileSize = options.maxFileSize;
      }

      const nativeRecording = camera.recordAsync(recordingOptions);
      const token = Symbol('camera-recording');
      const entry: InFlightRecording = {
        token,
        stopping: false,
        completion: this.awaitRecording(camera, token, nativeRecording),
      };

      this.activeRecordings.set(camera, entry);
      console.log('CameraService: Video recording started');

      return entry.completion;
    } catch (error) {
      console.error('CameraService: Failed to record video:', error);
      return null;
    }
  }

  /**
   * Stop video recording. stopRecording() returns void; the media comes from
   * the exact in-flight recordAsync completion for this camera.
   */
  async stopRecording(cameraRef: React.RefObject<CameraView>): Promise<CapturedMedia | null> {
    const camera = cameraRef.current;
    if (!camera) {
      console.error('CameraService: Failed to stop recording: camera ref not available');
      return null;
    }

    const active = this.activeRecordings.get(camera);
    if (!active) {
      console.log('CameraService: No in-flight video recording to stop');
      return null;
    }

    if (active.stopping) {
      return active.completion;
    }

    active.stopping = true;
    try {
      camera.stopRecording();
    } catch (error) {
      active.stopping = false;
      console.error('CameraService: Failed to stop recording:', error);
      return null;
    }

    return active.completion;
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
        allowsMultipleSelection: options?.allowsMultiple ?? false,
        selectionLimit: options?.maxResults ?? 1,
        quality: options?.quality ?? COMPRESSION_QUALITY,
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
        size: asset.fileSize,
      }));

      console.log(`CameraService: ${media.length} image(s) picked`);
      return media;
    } catch (error) {
      console.error('CameraService: Failed to pick image:', error);
      throw new Error(
        error instanceof Error
          ? `Failed to pick image: ${error.message}`
          : 'Failed to pick image from gallery'
      );
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
        quality: options?.camera?.quality ?? COMPRESSION_QUALITY,
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
   * Scan barcode/QR code
   */
  async scanBarcode(
    barcodeScanningResult: BarcodeScanningResult | {
      barcodes: { type: string; rawValue?: string; cornerPoints?: DocumentEdge[] }[];
    } | null
  ): Promise<BarcodeResult | null> {
    try {
      if (!barcodeScanningResult) {
        return null;
      }

      // The SDK emits one result. Retain the service's pre-existing batch input
      // for callers that already supply it; do not invent that wrapper at the SDK boundary.
      const barcode = 'barcodes' in barcodeScanningResult
        ? barcodeScanningResult.barcodes[0]
        : { ...barcodeScanningResult, rawValue: barcodeScanningResult.data };
      if (!barcode || typeof barcode.type !== 'string') return null;
      return {
        type: barcode.type,
        data: barcode.rawValue || '',
        corners: barcode.cornerPoints?.length === 4
          ? {
              topLeft: barcode.cornerPoints[0],
              topRight: barcode.cornerPoints[1],
              bottomRight: barcode.cornerPoints[2],
              bottomLeft: barcode.cornerPoints[3],
            }
          : undefined,
      };
    } catch (error) {
      console.error('CameraService: Failed to scan barcode:', error);
      return null;
    }
  }

  /**
   * Detect document edges in image
   */
  async detectDocumentEdges(imageUri: string): Promise<DocumentCorners | null> {
    try {
      // This is a simplified implementation
      // In production, you would use OpenCV or ML Kit for accurate edge detection
      // For now, we return null to indicate no edges detected
      console.log('CameraService: Document edge detection not implemented');
      return null;
    } catch (error) {
      console.error('CameraService: Failed to detect document edges:', error);
      return null;
    }
  }

  /**
   * Crop image to document bounds
   */
  async cropToDocument(
    imageUri: string,
    corners: DocumentCorners
  ): Promise<string | null> {
    try {
      // Calculate crop region from corners
      const minX = Math.min(
        corners.topLeft.x,
        corners.topRight.x,
        corners.bottomLeft.x,
        corners.bottomRight.x
      );
      const minY = Math.min(
        corners.topLeft.y,
        corners.topRight.y,
        corners.bottomLeft.y,
        corners.bottomRight.y
      );
      const width = Math.max(
        corners.topRight.x - corners.topLeft.x,
        corners.bottomRight.x - corners.bottomLeft.x
      );
      const height = Math.max(
        corners.bottomLeft.y - corners.topLeft.y,
        corners.bottomRight.y - corners.topRight.y
      );

      const result = await ImageManipulator.manipulateAsync(
        imageUri,
        [{ crop: { originX: minX, originY: minY, width, height } }],
        {
          compress: COMPRESSION_QUALITY,
          format: ImageManipulator.SaveFormat.JPEG,
        }
      );

      console.log('CameraService: Image cropped to document');
      return result.uri;
    } catch (error) {
      console.error('CameraService: Failed to crop image:', error);
      return null;
    }
  }

  /**
   * Rotate image
   */
  async rotateImage(imageUri: string, degrees: number): Promise<string | null> {
    try {
      const rotations = Math.round(degrees / 90);
      const result = await ImageManipulator.manipulateAsync(
        imageUri,
        Array(rotations).fill({ rotate: degrees }),
        {
          compress: COMPRESSION_QUALITY,
          format: ImageManipulator.SaveFormat.JPEG,
        }
      );

      console.log('CameraService: Image rotated', degrees, 'degrees');
      return result.uri;
    } catch (error) {
      console.error('CameraService: Failed to rotate image:', error);
      return null;
    }
  }

  /**
   * Flip image (horizontal or vertical)
   */
  async flipImage(imageUri: string, horizontal: boolean = true): Promise<string | null> {
    try {
      const result = await ImageManipulator.manipulateAsync(
        imageUri,
        [{ flip: horizontal ? ImageManipulator.FlipType.Horizontal : ImageManipulator.FlipType.Vertical }],
        {
          compress: COMPRESSION_QUALITY,
          format: ImageManipulator.SaveFormat.JPEG,
        }
      );

      console.log('CameraService: Image flipped');
      return result.uri;
    } catch (error) {
      console.error('CameraService: Failed to flip image:', error);
      return null;
    }
  }

  /**
   * Capture multiple photos
   */
  async captureMultiplePhotos(
    cameraRef: React.RefObject<CameraView>,
    count: number,
    options?: PhotoOptions
  ): Promise<CapturedMedia[]> {
    try {
      const photos: CapturedMedia[] = [];

      for (let i = 0; i < count; i++) {
        const photo = await this.takePicture(cameraRef, options);
        if (photo) {
          photos.push(photo);
        }
      }

      this.capturedPhotos = photos;
      this.currentPhotoIndex = 0;

      console.log(`CameraService: ${photos.length} photos captured`);
      return photos;
    } catch (error) {
      console.error('CameraService: Failed to capture multiple photos:', error);
      return [];
    }
  }

  /**
   * Get captured photos
   */
  getCapturedPhotos(): CapturedPhotos {
    return {
      photos: this.capturedPhotos,
      currentIndex: this.currentPhotoIndex,
    };
  }

  /**
   * Delete captured photo at index
   */
  deleteCapturedPhoto(index: number): void {
    if (index >= 0 && index < this.capturedPhotos.length) {
      this.capturedPhotos.splice(index, 1);
      if (this.currentPhotoIndex >= this.capturedPhotos.length) {
        this.currentPhotoIndex = Math.max(0, this.capturedPhotos.length - 1);
      }
      console.log('CameraService: Photo deleted at index', index);
    }
  }

  /**
   * Clear captured photos
   */
  clearCapturedPhotos(): void {
    this.capturedPhotos = [];
    this.currentPhotoIndex = 0;
    console.log('CameraService: Captured photos cleared');
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
   * Get current camera mode
   */
  getCameraMode(): CameraMode {
    return this.currentMode;
  }

  /**
   * Set camera mode
   */
  setCameraMode(mode: CameraMode): void {
    this.currentMode = mode;
    console.log('CameraService: Camera mode set to', mode);
  }

  /** Save only after explicit library permission and a completed SDK write. */
  async saveToGallery(uri: string): Promise<boolean> {
    try {
      if (Platform.OS !== 'ios' && Platform.OS !== 'android') return false;
      const permission = await MediaLibrary.requestPermissionsAsync(true);
      if (permission.status !== 'granted' || permission.granted !== true) return false;
      await MediaLibrary.saveToLibraryAsync(uri);
      console.log('CameraService: Photo saved to gallery');
      return true;
    } catch (error) {
      console.error('CameraService: Failed to save to gallery:', error);
      return false;
    }
  }

  /**
   * Get camera type for CameraView
   */
  getCameraType(): CameraType {
    return this.currentCamera === 'front' ? 'front' : 'back';
  }

  /**
   * Reset service state
   */
  reset(): void {
    this.permissionStatus = 'undetermined';
    this.currentCamera = 'back';
    this.currentFlash = 'off';
    this.currentMode = 'picture';
    this.capturedPhotos = [];
    this.currentPhotoIndex = 0;
    console.log('CameraService: Service state reset');
  }
}

// Export singleton instance
export const cameraService = new CameraService();

export default cameraService;
