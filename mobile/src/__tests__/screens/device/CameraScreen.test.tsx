/**
 * CameraScreen Component Tests
 *
 * Tests for permission flows, camera UI rendering, capture behavior
 * (single and multi), camera/flash toggles, mode overlays, and
 * barcode navigation.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { CameraScreen } from '../../../screens/device/CameraScreen';
import {
  getActiveCameraCapture,
  registerActiveCameraCapture,
} from '../../../services/cameraCaptureRegistry';

// Mock expo-camera with a renderable Camera component and controllable
// permission hook (jest.mock factories may only reference `mock*` variables)
const mockPermissionState = { value: { granted: true, canAskAgain: true } };
const mockRequestPermission = jest.fn().mockResolvedValue({ granted: true });
const mockTakePicture = jest.fn();
const mockGetCameraPermissions = jest.fn().mockResolvedValue({
  status: 'granted',
  granted: true,
  canAskAgain: true,
  expires: 'never',
});

jest.mock('expo-camera', () => {
  const React = require('react');
  const { View } = require('react-native');
  const Camera = React.forwardRef((props: any, ref: any) => {
    React.useImperativeHandle(ref, () => ({ takePictureAsync: mockTakePicture }), []);
    return React.createElement(View, { ...props, ref, testID: 'camera-view' });
  });
  Camera.useCameraPermissions = () => [
    mockPermissionState.value,
    mockRequestPermission,
  ];
  Camera.getCameraPermissionsAsync = (...args: any[]) =>
    mockGetCameraPermissions(...args);
  return {
    Camera,
    CameraType: { front: 'front', back: 'back' },
    FlashMode: { on: 'on', off: 'off', auto: 'auto', torch: 'torch' },
    PermissionStatus: {
      GRANTED: 'granted',
      DENIED: 'denied',
      UNDETERMINED: 'undetermined',
    },
  };
});

type NavigationListener = () => void;

const mockNavigationListeners = new Map<string, Set<NavigationListener>>();

const emitNavigationEvent = (event: string) => {
  const listeners = mockNavigationListeners.get(event);
  if (!listeners) return;
  Array.from(listeners).forEach((listener) => listener());
};

const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  isFocused: jest.fn(() => true),
  addListener: jest.fn((event: string, listener: NavigationListener) => {
    const listeners = mockNavigationListeners.get(event) ?? new Set();
    listeners.add(listener);
    mockNavigationListeners.set(event, listeners);
    return () => {
      listeners.delete(listener);
    };
  }),
};

// Mock cameraService
jest.mock('../../../services/cameraService', () => ({
  cameraService: {
    setCameraMode: jest.fn(),
    takePicture: jest.fn(),
    toggleCamera: jest.fn(),
    cycleFlash: jest.fn(),
  },
}));

const { cameraService } = require('../../../services/cameraService');

const mockPhoto = {
  uri: 'file:///mock/photo.jpg',
  type: 'photo',
  width: 1920,
  height: 1080,
};

const defaultRoute = { params: {} };

function renderScreen(route: any = defaultRoute) {
  return render(<CameraScreen navigation={mockNavigation} route={route} />);
}

function markPreviewReady() {
  act(() => {
    screen.getByTestId('camera-view').props.onCameraReady?.();
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

const grantedPermission = {
  status: 'granted',
  granted: true,
  canAskAgain: true,
  expires: 'never',
};

describe('CameraScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    registerActiveCameraCapture(null);
    mockNavigationListeners.clear();
    mockPermissionState.value = { granted: true, canAskAgain: true };
    mockGetCameraPermissions.mockResolvedValue({
      status: 'granted',
      granted: true,
      canAskAgain: true,
      expires: 'never',
    });
    mockTakePicture.mockResolvedValue(mockPhoto);
    cameraService.takePicture.mockResolvedValue(mockPhoto);
    cameraService.cycleFlash.mockReturnValue('on');
  });

  describe('Permission Flow', () => {
    it('requests permission automatically when not granted', () => {
      mockPermissionState.value = { granted: false, canAskAgain: false };
      renderScreen();

      expect(mockRequestPermission).toHaveBeenCalled();
    });

    it('renders permission required UI when denied', () => {
      mockPermissionState.value = { granted: false, canAskAgain: false };
      renderScreen();

      expect(getByText('Camera Permission Required')).toBeTruthy();
      expect(getByText('We need your permission to use the camera')).toBeTruthy();

      fireEvent.press(getByText('Grant Permission'));
      expect(mockRequestPermission).toHaveBeenCalled();
    });

    it('renders camera UI when permission granted', () => {
      renderScreen();

      expect(getByText('PICTURE')).toBeTruthy();
      expect(screen.getByTestId('camera-view')).toBeTruthy();
    });

    it('registers the mounted preview for background capture and clears it on unmount', () => {
      const { unmount } = renderScreen();

      markPreviewReady();
      expect(getActiveCameraCapture()).not.toBeNull();

      unmount();
      expect(getActiveCameraCapture()).toBeNull();
    });
  });

  describe('Background capture lifecycle', () => {
    it('does not expose capture before the preview is ready', () => {
      renderScreen();

      expect(getActiveCameraCapture()).toBeNull();
    });

    it('withdraws capture when the screen blurs and restores it on focus', () => {
      renderScreen();
      markPreviewReady();
      expect(getActiveCameraCapture()).not.toBeNull();

      act(() => {
        emitNavigationEvent('blur');
      });
      expect(getActiveCameraCapture()).toBeNull();

      act(() => {
        emitNavigationEvent('focus');
      });
      expect(getActiveCameraCapture()).not.toBeNull();
    });

    it('clears capture when permission is revoked while the screen stays mounted', () => {
      const view = renderScreen();
      markPreviewReady();
      expect(getActiveCameraCapture()).not.toBeNull();

      mockPermissionState.value = { granted: false, canAskAgain: false };
      view.rerender(
        <CameraScreen navigation={mockNavigation} route={defaultRoute} />
      );

      expect(screen.getByText('Camera Permission Required')).toBeTruthy();
      expect(getActiveCameraCapture()).toBeNull();
    });

    it('rejects capture if permission is revoked after registration', async () => {
      renderScreen();
      markPreviewReady();

      const capture = getActiveCameraCapture();
      expect(capture).not.toBeNull();

      mockGetCameraPermissions.mockResolvedValueOnce({
        status: 'denied',
        granted: false,
        canAskAgain: false,
        expires: 'never',
      });

      await expect(capture!({ quality: 0.5 })).rejects.toThrow(
        'Camera permission not granted'
      );
      expect(mockTakePicture).not.toHaveBeenCalled();
    });

    it('delegates to the ready preview while permission remains granted', async () => {
      renderScreen();
      markPreviewReady();

      const capture = getActiveCameraCapture();
      expect(capture).not.toBeNull();

      await expect(
        capture!({ quality: 0.5, base64: true })
      ).resolves.toBe(mockPhoto);
      expect(mockTakePicture).toHaveBeenCalledWith({
        quality: 0.5,
        base64: true,
      });
    });

    it('does not capture when the screen blurs while permission is resolving', async () => {
      renderScreen();
      markPreviewReady();

      const permission = deferred<typeof grantedPermission>();
      mockGetCameraPermissions.mockReturnValueOnce(permission.promise);

      const capture = getActiveCameraCapture();
      expect(capture).not.toBeNull();

      const outcome = capture!({ quality: 0.5 }).then(
        () => 'resolved',
        (error: Error) => error.message
      );

      act(() => {
        emitNavigationEvent('blur');
      });
      expect(getActiveCameraCapture()).toBeNull();

      await act(async () => {
        permission.resolve(grantedPermission);
        await expect(outcome).resolves.toBe('Camera preview is no longer active');
      });
      expect(mockTakePicture).not.toHaveBeenCalled();
    });

    it('does not capture when a newer preview registers while permission is resolving', async () => {
      renderScreen();
      markPreviewReady();

      const permission = deferred<typeof grantedPermission>();
      mockGetCameraPermissions.mockReturnValueOnce(permission.promise);

      const capture = getActiveCameraCapture();
      expect(capture).not.toBeNull();

      const outcome = capture!({ quality: 0.5 }).then(
        () => 'resolved',
        (error: Error) => error.message
      );

      const replacement = jest.fn().mockResolvedValue(mockPhoto);
      act(() => {
        registerActiveCameraCapture(replacement);
      });

      await act(async () => {
        permission.resolve(grantedPermission);
        await expect(outcome).resolves.toBe('Camera preview is no longer active');
      });
      expect(mockTakePicture).not.toHaveBeenCalled();
      expect(getActiveCameraCapture()).toBe(replacement);
    });

    it('does not capture when the preview is withdrawn while permission is resolving', async () => {
      const view = renderScreen();
      markPreviewReady();

      const permission = deferred<typeof grantedPermission>();
      mockGetCameraPermissions.mockReturnValueOnce(permission.promise);

      const capture = getActiveCameraCapture();
      expect(capture).not.toBeNull();

      const outcome = capture!({ quality: 0.5 }).then(
        () => 'resolved',
        (error: Error) => error.message
      );

      mockPermissionState.value = { granted: false, canAskAgain: false };
      view.rerender(
        <CameraScreen navigation={mockNavigation} route={defaultRoute} />
      );
      expect(getActiveCameraCapture()).toBeNull();

      await act(async () => {
        permission.resolve(grantedPermission);
        await expect(outcome).resolves.toBe('Camera preview is no longer active');
      });
      expect(mockTakePicture).not.toHaveBeenCalled();
    });
  });

  describe('Capture', () => {
    it('captures a photo and navigates to CameraResult in single mode', async () => {
      renderScreen();

      const captureButton = findCaptureButton();
      fireEvent.press(captureButton);

      await waitFor(() => {
        expect(cameraService.takePicture).toHaveBeenCalledWith(
          expect.anything(),
          expect.objectContaining({ quality: 0.9, skipProcessing: false, exif: true })
        );
        expect(mockNavigation.navigate).toHaveBeenCalledWith('CameraResult', {
          photo: mockPhoto,
        });
      });
    });

    it('shows capture failed alert when takePicture throws', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;
      cameraService.takePicture.mockRejectedValue(new Error('Camera busy'));

      renderScreen();

      fireEvent.press(findCaptureButton());

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Capture Failed', 'Camera busy');
      });
    });

    it('accumulates photos in multi-capture mode without navigating', async () => {
      renderScreen({ params: { multiCapture: true, maxCount: 2 } });

      expect(getByText('0 / 2')).toBeTruthy();

      fireEvent.press(findCaptureButton());
      await waitFor(() => {
        expect(getByText('1 / 2')).toBeTruthy();
      });

      fireEvent.press(findCaptureButton());
      await waitFor(() => {
        expect(getByText('2 / 2')).toBeTruthy();
      });

      expect(mockNavigation.navigate).not.toHaveBeenCalled();
    });
  });

  describe('Controls', () => {
    it('toggles camera facing and calls cameraService.toggleCamera', () => {
      renderScreen();

      fireEvent.press(screen.getByTestId('icon-camera-reverse'));

      expect(cameraService.toggleCamera).toHaveBeenCalled();
    });

    it('cycles flash mode on flash button press', () => {
      renderScreen();

      fireEvent.press(screen.getByTestId('icon-flash-off'));

      expect(cameraService.cycleFlash).toHaveBeenCalled();
      // Flash icon reflects the new mode
      expect(screen.getByTestId('icon-flash')).toBeTruthy();
    });

    it('navigates back on close button press', () => {
      renderScreen();

      fireEvent.press(screen.getByTestId('icon-close'));

      expect(mockNavigation.goBack).toHaveBeenCalled();
    });
  });

  describe('Modes', () => {
    it('renders document overlay in document mode', () => {
      renderScreen({ params: { mode: 'document' } });

      expect(getByText('DOCUMENT')).toBeTruthy();
    });

    it('renders barcode overlay and navigates on barcode scan', async () => {
      const route = { params: { mode: 'barcode' } };
      renderScreen(route);

      expect(getByText('BARCODE')).toBeTruthy();
      expect(getByText('Align QR code or barcode within frame')).toBeTruthy();

      // Fire the onBarCodeScanned callback passed to CameraView
      const cameraView = screen.getByTestId('camera-view');
      const props = cameraView.props;
      expect(props.barCodeScannerSettings).toBeDefined();
      props.onBarCodeScanned({ data: 'QR-DATA-123', type: 'qr' });

      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('BarcodeResult', {
          data: 'QR-DATA-123',
        });
      });
    });

    it('hides flash control outside picture mode', () => {
      renderScreen({ params: { mode: 'document' } });

      expect(screen.queryByTestId('icon-flash-off')).toBeNull();
    });
  });
});

function getByText(text: string | RegExp) {
  return screen.getByText(text);
}

function findCaptureButton() {
  const { TouchableOpacity } = require('react-native');
  const buttons = screen.UNSAFE_getAllByType(TouchableOpacity);
  const capture = buttons.find((b: any) => b.props.disabled !== undefined);
  if (!capture) {
    throw new Error('Capture button not found');
  }
  return capture;
}
