/** Consumer controls shaped against installed Expo 50 declarations; no native device. */
import { Camera, PermissionStatus } from 'expo-camera/next';
import * as MediaLibrary from 'expo-media-library';
import { Platform } from 'react-native';
import { cameraService } from '../../services/cameraService';

jest.mock('expo-camera/next', () => ({
  Camera: {
    getCameraPermissionsAsync: jest.fn(),
    requestCameraPermissionsAsync: jest.fn(),
  },
  CameraView: { isAvailableAsync: jest.fn() },
  PermissionStatus: { GRANTED: 'granted', DENIED: 'denied', UNDETERMINED: 'undetermined' },
}));
jest.mock('expo-media-library', () => ({
  requestPermissionsAsync: jest.fn(),
  saveToLibraryAsync: jest.fn(),
}));

describe('CameraService installed SDK contract', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    cameraService.reset();
    jest.replaceProperty(Platform, 'OS', 'ios');
    jest.mocked(Camera.getCameraPermissionsAsync).mockReset().mockResolvedValue({ status: PermissionStatus.GRANTED, granted: true, canAskAgain: true, expires: 'never' });
    jest.mocked(MediaLibrary.requestPermissionsAsync).mockReset().mockResolvedValue({ status: PermissionStatus.GRANTED, granted: true, canAskAgain: true, expires: 'never' });
    jest.mocked(MediaLibrary.saveToLibraryAsync).mockReset().mockResolvedValue(undefined);
  });
  afterEach(() => jest.restoreAllMocks());

  test('reads permission from the Camera namespace, not static view methods', async () => {
    expect(await cameraService.getPermissionStatus()).toBe('granted');
    expect(Camera.getCameraPermissionsAsync).toHaveBeenCalledTimes(1);
  });
  test('preserves a denied native permission', async () => {
    jest.mocked(Camera.getCameraPermissionsAsync).mockResolvedValueOnce({ status: PermissionStatus.DENIED, granted: false, canAskAgain: false, expires: 'never' });
    expect(await cameraService.getPermissionStatus()).toBe('denied');
    expect(Camera.getCameraPermissionsAsync).toHaveBeenCalledTimes(1);
  });
  test('decodes the SDK single barcode result without a fabricated barcodes wrapper', async () => {
    expect(await cameraService.scanBarcode({ type: 'qr', data: 'controlled-barcode', cornerPoints: [{ x: 0, y: 0 }, { x: 2, y: 0 }, { x: 2, y: 2 }, { x: 0, y: 2 }], bounds: { origin: { x: 0, y: 0 }, size: { width: 2, height: 2 } } })).toEqual({ type: 'qr', data: 'controlled-barcode', corners: { topLeft: { x: 0, y: 0 }, topRight: { x: 2, y: 0 }, bottomRight: { x: 2, y: 2 }, bottomLeft: { x: 0, y: 2 } } });
  });
  test.each(['ios', 'android'] as const)('gallery success requires the actual %s library write', async (os) => {
    jest.replaceProperty(Platform, 'OS', os);
    expect(await cameraService.saveToGallery('file:///controlled-photo.jpg')).toBe(true);
    expect(MediaLibrary.requestPermissionsAsync).toHaveBeenCalledWith(true);
    expect(MediaLibrary.saveToLibraryAsync).toHaveBeenCalledWith('file:///controlled-photo.jpg');
  });
  test('denied library permission writes nothing', async () => {
    jest.mocked(MediaLibrary.requestPermissionsAsync).mockResolvedValueOnce({ status: PermissionStatus.DENIED, granted: false, canAskAgain: false, expires: 'never' });
    expect(await cameraService.saveToGallery('file:///controlled-photo.jpg')).toBe(false);
    expect(MediaLibrary.saveToLibraryAsync).not.toHaveBeenCalled();
  });
  test('a rejected library write is not reported as saved', async () => {
    jest.mocked(MediaLibrary.saveToLibraryAsync).mockRejectedValueOnce(new Error('controlled write failure'));
    expect(await cameraService.saveToGallery('file:///controlled-photo.jpg')).toBe(false);
  });
});
