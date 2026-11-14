/**
 * Camera Screen - Full-featured camera interface
 *
 * Features:
 * - Live camera preview
 * - Capture button with animation
 * - Front/back camera toggle
 * - Flash control button
 * - Gallery thumbnail (last photo)
 * - Document mode with edge detection overlay
 * - Barcode/QR mode with scanning overlay
 * - Multi-capture review
 * - Retake/delete options
 * - Crop/edit before confirm
 * - Permission request overlay
 */

import React, { useRef, useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  StatusBar,
  Platform,
} from 'react-native';
import {
  Camera,
  CameraType,
  FlashMode as ExpoFlashMode,
  PermissionStatus,
} from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import { cameraService, CameraMode, FlashMode, CapturedMedia } from '../../services/cameraService';
import { registerActiveCameraCapture, isActiveCameraCapture, CameraCaptureFn } from '../../services/cameraCaptureRegistry';

interface CameraScreenProps {
  navigation: any;
  route: {
    params?: {
      mode?: CameraMode;
      multiCapture?: boolean;
      maxCount?: number;
    };
  };
}

export const CameraScreen: React.FC<CameraScreenProps> = ({ navigation, route }) => {
  const cameraRef = useRef<Camera>(null);
  const [permission, requestPermission] = Camera.useCameraPermissions();

  // Camera state
  const [facing, setFacing] = useState<'back' | 'front'>('back');
  const [flash, setFlash] = useState<FlashMode>('off');
  const [mode, setMode] = useState<CameraMode>(route.params?.mode || 'picture');
  const [isCapturing, setIsCapturing] = useState(false);

  // Background capture is only valid while this screen owns the visible,
  // ready preview. Navigating to CameraResult blurs (but does not unmount)
  // this screen, so navigation focus must gate the registry explicitly.
  const [isFocused, setIsFocused] = useState(
    () => navigation?.isFocused?.() ?? true
  );
  // A ref mirrors focus synchronously so an in-flight capture can re-check it
  // after awaiting permission, without waiting for a re-render.
  const isFocusedRef = useRef(isFocused);
  const [isPreviewReady, setIsPreviewReady] = useState(false);

  // Captured photos
  const [capturedPhotos, setCapturedPhotos] = useState<CapturedMedia[]>([]);
  const [currentPhotoIndex, setCurrentPhotoIndex] = useState(0);
  const [showReview, setShowReview] = useState(false);

  useEffect(() => {
    cameraService.setCameraMode(mode);
  }, [mode]);

  useEffect(() => {
    if (typeof navigation?.addListener !== 'function') {
      return;
    }

    const unsubscribeFocus = navigation.addListener('focus', () => {
      isFocusedRef.current = true;
      setIsFocused(true);
    });
    const unsubscribeBlur = navigation.addListener('blur', () => {
      isFocusedRef.current = false;
      setIsFocused(false);
    });

    return () => {
      unsubscribeFocus?.();
      unsubscribeBlur?.();
    };
  }, [navigation]);

  const permissionGranted = permission?.granted === true;

  // The preview can only become ready while it is rendered, which requires
  // permission. Drop readiness when permission is lost so a later grant waits
  // for onCameraReady instead of exposing a stale ref.
  useEffect(() => {
    if (!permissionGranted) {
      setIsPreviewReady(false);
    }
  }, [permissionGranted]);

  // Expose the mounted preview to background services (deviceSocket) only
  // while it is focused, ready, and permission is still granted. The release
  // returned by the registry is owned by this effect, so blur/unmount here
  // cannot clear another screen's registration.
  useEffect(() => {
    const camera = cameraRef.current;
    if (!permissionGranted || !isFocused || !isPreviewReady || !camera) {
      return;
    }

    const captureFn: CameraCaptureFn = async (options) => {
      // Capture must start on the visible preview, and permission can change
      // while the OS request is in flight.
      if (!isFocusedRef.current) {
        throw new Error('Camera preview is not focused');
      }
      if (cameraRef.current !== camera) {
        throw new Error('Camera preview is no longer available');
      }

      const { status } = await Camera.getCameraPermissionsAsync();

      // The await above yields: the screen may have blurred, unmounted, or
      // been replaced by a newer preview. Re-validate before driving the ref
      // captured by this (possibly stale) registration.
      if (status !== PermissionStatus.GRANTED) {
        throw new Error('Camera permission not granted');
      }
      if (!isActiveCameraCapture(captureFn)) {
        throw new Error('Camera preview is no longer active');
      }
      if (!isFocusedRef.current) {
        throw new Error('Camera preview is not focused');
      }
      if (cameraRef.current !== camera) {
        throw new Error('Camera preview is no longer available');
      }

      return camera.takePictureAsync(options);
    };

    return registerActiveCameraCapture(captureFn);
  }, [permissionGranted, isFocused, isPreviewReady]);

  const handleCameraReady = () => {
    if (!cameraRef.current) return;
    setIsPreviewReady(true);
  };

  // Request permission if not granted
  useEffect(() => {
    if (!permission?.granted) {
      requestPermission();
    }
  }, [permission]);

  if (!permission) {
    return <View style={styles.container} />;
  }

  if (!permission.granted) {
    return (
      <View style={styles.permissionContainer}>
        <Ionicons name="camera-outline" size={64} color="#2196F3" />
        <Text style={styles.permissionTitle}>Camera Permission Required</Text>
        <Text style={styles.permissionText}>
          We need your permission to use the camera
        </Text>
        <TouchableOpacity style={styles.permissionButton} onPress={requestPermission}>
          <Text style={styles.permissionButtonText}>Grant Permission</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const handleCapture = async () => {
    if (isCapturing) return;

    setIsCapturing(true);
    try {
      const photo = await cameraService.takePicture(cameraRef, {
        quality: 0.9,
        skipProcessing: false,
        exif: true,
      });

      if (photo) {
        if (route.params?.multiCapture) {
          const newPhotos = [...capturedPhotos, photo];
          setCapturedPhotos(newPhotos);
          setCurrentPhotoIndex(newPhotos.length - 1);

          const maxCount = route.params.maxCount || 5;
          if (newPhotos.length >= maxCount) {
            setShowReview(true);
          }
        } else {
          // Single capture - return result
          navigation.navigate('CameraResult', { photo });
        }
      }
    } catch (error: any) {
      Alert.alert('Capture Failed', error.message);
    } finally {
      setIsCapturing(false);
    }
  };

  const toggleCameraFacing = () => {
    const newFacing = facing === 'back' ? 'front' : 'back';
    setFacing(newFacing);
    cameraService.toggleCamera();
  };

  const cycleFlashMode = () => {
    const newFlash = cameraService.cycleFlash();
    setFlash(newFlash);
  };

  const getFlashIcon = () => {
    switch (flash) {
      case 'on':
        return 'flash';
      case 'auto':
        return 'flash-outline';
      case 'torch':
        return 'flashlight';
      default:
        return 'flash-off';
    }
  };

  const cameraFlashMode = (): ExpoFlashMode => {
    switch (flash) {
      case 'on':
        return ExpoFlashMode.on;
      case 'auto':
        return ExpoFlashMode.auto;
      case 'torch':
        return ExpoFlashMode.torch;
      default:
        return ExpoFlashMode.off;
    }
  };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" />

      <Camera
        ref={cameraRef}
        style={styles.camera}
        onCameraReady={handleCameraReady}
        type={facing === 'front' ? CameraType.front : CameraType.back}
        flashMode={cameraFlashMode()}
        barCodeScannerSettings={
          mode === 'barcode'
            ? {
                barCodeTypes: ['qr', 'ean13', 'ean8', 'upc_a', 'upc_e', 'code128', 'code39', 'code93'],
              }
            : undefined
        }
        onBarCodeScanned={
          mode === 'barcode'
            ? ({ data }) => {
                navigation.navigate('BarcodeResult', { data });
              }
            : undefined
        }
      >
        {/* Top controls */}
        <View style={styles.topControls}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Ionicons name="close" size={32} color="#fff" />
          </TouchableOpacity>

          <View style={styles.modeIndicator}>
            <Text style={styles.modeText}>{mode.toUpperCase()}</Text>
          </View>

          {mode === 'picture' && (
            <TouchableOpacity onPress={cycleFlashMode}>
              <Ionicons name={getFlashIcon() as any} size={28} color="#fff" />
            </TouchableOpacity>
          )}
        </View>

        {/* Document mode overlay */}
        {mode === 'document' && (
          <View style={styles.documentOverlay}>
            <View style={styles.documentCorner} />
            <View style={[styles.documentCorner, { alignSelf: 'flex-end' }]} />
            <View style={[styles.documentCorner, { alignSelf: 'flex-end', alignItems: 'flex-end' }]} />
            <View style={[styles.documentCorner, { alignItems: 'flex-end' }]} />
          </View>
        )}

        {/* Barcode mode overlay */}
        {mode === 'barcode' && (
          <View style={styles.barcodeOverlay}>
            <View style={styles.barcodeFrame} />
            <Text style={styles.barcodeText}>Align QR code or barcode within frame</Text>
          </View>
        )}

        {/* Bottom controls */}
        <View style={styles.bottomControls}>
          <TouchableOpacity style={styles.galleryButton}>
            <Ionicons name="images" size={28} color="#fff" />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.captureButton}
            onPress={handleCapture}
            disabled={isCapturing}
          >
            <View style={[styles.captureButtonInner, isCapturing && styles.captureButtonCapturing]} />
          </TouchableOpacity>

          <TouchableOpacity onPress={toggleCameraFacing}>
            <Ionicons name="camera-reverse" size={32} color="#fff" />
          </TouchableOpacity>
        </View>

        {/* Multi-capture indicator */}
        {route.params?.multiCapture && (
          <View style={styles.multiCaptureIndicator}>
            <Text style={styles.multiCaptureText}>
              {capturedPhotos.length} / {route.params.maxCount || 5}
            </Text>
          </View>
        )}
      </Camera>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  camera: {
    flex: 1,
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
    backgroundColor: '#fff',
  },
  permissionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    marginTop: 24,
    marginBottom: 12,
    textAlign: 'center',
  },
  permissionText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 24,
  },
  permissionButton: {
    backgroundColor: '#2196F3',
    paddingHorizontal: 32,
    paddingVertical: 12,
    borderRadius: 8,
  },
  permissionButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  topControls: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 60,
    paddingBottom: 20,
  },
  modeIndicator: {
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  modeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  bottomControls: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingHorizontal: 40,
    paddingBottom: 60,
  },
  captureButton: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: 'rgba(255, 255, 255, 0.3)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureButtonInner: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#fff',
  },
  captureButtonCapturing: {
    backgroundColor: '#2196F3',
  },
  galleryButton: {
    padding: 12,
  },
  documentOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'space-between',
    padding: 60,
  },
  documentCorner: {
    width: 60,
    height: 60,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderColor: '#fff',
  },
  barcodeOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  barcodeFrame: {
    width: 280,
    height: 280,
    borderWidth: 2,
    borderColor: '#fff',
    borderRadius: 12,
  },
  barcodeText: {
    color: '#fff',
    fontSize: 14,
    marginTop: 16,
    textAlign: 'center',
  },
  multiCaptureIndicator: {
    position: 'absolute',
    top: 100,
    alignSelf: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
  },
  multiCaptureText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
});

export default CameraScreen;
