/** Controlled installed-SDK-shaped photo results; no native capture. */
import React from 'react';
import type { CameraProps } from 'expo-camera/next';
import { CameraView } from 'expo-camera/next';
import * as FileSystem from 'expo-file-system';
import * as ImageManipulator from 'expo-image-manipulator';
import { cameraService } from '../../services/cameraService';

jest.mock('expo-camera/next', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  class CameraView extends React.Component<CameraProps> {
    takePictureAsync = jest.fn();
  }
  return { CameraView, Camera: { requestCameraPermissionsAsync: jest.fn().mockResolvedValue({ status: 'granted' }) }, PermissionStatus: { GRANTED: 'granted', DENIED: 'denied', UNDETERMINED: 'undetermined' } };
});
jest.mock('expo-image-manipulator', () => ({ manipulateAsync: jest.fn(), SaveFormat: { JPEG: 'jpeg' } }));

describe('CameraService final photo material', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    cameraService.reset();
    await cameraService.requestPermissions();
    jest.mocked(FileSystem.getInfoAsync).mockReset().mockImplementation(async (uri) => ({ exists: true, isDirectory: false, modificationTime: 0, uri, size: uri.includes('resized') ? 111 : 2220 }));
    jest.mocked(ImageManipulator.manipulateAsync).mockReset().mockResolvedValue({ uri: 'file:///resized.jpg', width: 2048, height: 1024 });
  });

  function largePhoto() {
    const ref = React.createRef<CameraView>();
    const view = new CameraView({ mode: 'picture' });
    Object.defineProperty(ref, 'current', { value: view });
    jest.mocked(view.takePictureAsync).mockResolvedValue({ uri: 'file:///original.jpg', width: 4000, height: 2000 });
    return ref;
  }

  test('resized URI, dimensions and byte size describe the same final file', async () => {
    expect(await cameraService.takePicture(largePhoto())).toMatchObject({ uri: 'file:///resized.jpg', width: 2048, height: 1024, size: 111 });
    expect(FileSystem.getInfoAsync).toHaveBeenCalledWith('file:///resized.jpg');
  });

  test('explicit zero quality survives the resize encoder', async () => {
    await cameraService.takePicture(largePhoto(), { quality: 0 });
    expect(ImageManipulator.manipulateAsync).toHaveBeenCalledWith('file:///original.jpg', [{ resize: { width: 2048 } }], { compress: 0, format: ImageManipulator.SaveFormat.JPEG });
  });

  test('a missing final photo does not publish a media result', async () => {
    jest.mocked(FileSystem.getInfoAsync).mockImplementation(async (uri) => uri.includes('resized') ? { exists: false, isDirectory: false, uri } : { exists: true, isDirectory: false, modificationTime: 0, uri, size: 2220 });
    expect(await cameraService.takePicture(largePhoto())).toBeNull();
  });

  test('a final file read failure does not publish source-file metadata', async () => {
    jest.mocked(FileSystem.getInfoAsync).mockImplementation(async (uri) => {
      if (uri.includes('resized')) throw new Error('controlled final-file read failure');
      return { exists: true, isDirectory: false, modificationTime: 0, uri, size: 2220 };
    });
    expect(await cameraService.takePicture(largePhoto())).toBeNull();
  });
});
