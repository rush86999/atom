/**
 * Active Camera Capture Registry
 *
 * expo-camera captures photos through a mounted preview ref, not through a
 * module-level helper. The camera screen registers the active preview here
 * while it is mounted (and only after permission has been granted) so
 * background services such as deviceSocket can request a snapshot without
 * reaching into UI internals.
 *
 * When no preview is registered, callers must report an explicit failure
 * instead of fabricating a capture result.
 */

export interface CameraCaptureOptions {
  quality?: number;
  base64?: boolean;
  exif?: boolean;
  skipProcessing?: boolean;
}

export interface CameraCaptureResult {
  uri: string;
  base64?: string;
  width?: number;
  height?: number;
}

export type CameraCaptureFn = (
  options?: CameraCaptureOptions
) => Promise<CameraCaptureResult>;

let activeCapture: CameraCaptureFn | null = null;

/**
 * Register the currently mounted camera preview, or pass null to clear it.
 */
export const registerActiveCameraCapture = (
  capture: CameraCaptureFn | null
): void => {
  activeCapture = capture;
};

/**
 * Return the mounted camera preview capture function, if one is active.
 */
export const getActiveCameraCapture = (): CameraCaptureFn | null => activeCapture;
