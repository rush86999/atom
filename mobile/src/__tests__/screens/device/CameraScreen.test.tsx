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

// Mock expo-camera with a renderable CameraView and controllable
// permission hook (jest.mock factories may only reference `mock*` variables)
const mockPermissionState = { value: { granted: true, canAskAgain: true } };
const mockRequestPermission = jest.fn().mockResolvedValue({ granted: true });

jest.mock('expo-camera', () => {
  const React = require('react');
  const { View } = require('react-native');
  const CameraView = React.forwardRef((props: any, ref: any) => {
    return React.createElement(View, { ...props, ref, testID: 'camera-view' });
  });
  return {
    CameraView,
    useCameraPermissions: () => [mockPermissionState.value, mockRequestPermission],
  };
});

const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
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

describe('CameraScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPermissionState.value = { granted: true, canAskAgain: true };
    cameraService.takePicture.mockResolvedValue(mockPhoto);
    cameraService.cycleFlash.mockReturnValue('on');
  });

  describe('Permission Flow', () => {
    it('requests permission automatically when not granted', () => {
      mockPermissionState.value = { granted: false };
      renderScreen();

      expect(mockRequestPermission).toHaveBeenCalled();
    });

    it('renders permission required UI when denied', () => {
      mockPermissionState.value = { granted: false };
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

      // Fire the onBarcodeScanned callback passed to CameraView
      const cameraView = screen.getByTestId('camera-view');
      const props = cameraView.props;
      expect(props.barcodeScannerSettings).toBeDefined();
      props.onBarcodeScanned({ data: 'QR-DATA-123', type: 'qr' });

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
