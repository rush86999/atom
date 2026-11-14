/**
 * Active Camera Capture Registry
 *
 * expo-camera captures photos through a mounted preview ref, not through a
 * module-level helper. The camera screen registers the active preview here
 * while it is mounted (and only after permission has been granted) so
 * background services such as deviceSocket can request a snapshot without
 * reaching into UI internals.
 *
 * Registration is owned by the caller: registering returns a release function
 * that only clears the registration it created. A stale release (for example
 * an older CameraScreen instance unmounting after a newer one registered) must
 * not clear the newer preview.
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

export type CameraCaptureRelease = () => void;

let activeCapture: CameraCaptureFn | null = null;
let activeOwner: symbol | null = null;

/**
 * Register the currently mounted camera preview, or pass null to clear it.
 *
 * Returns a release function owned by this registration. Calling it only
 * clears the preview if this registration still owns the active slot, so a
 * late cleanup from an older screen cannot withdraw a newer screen's preview.
 */
export const registerActiveCameraCapture = (
  capture: CameraCaptureFn | null
): CameraCaptureRelease => {
  if (!capture) {
    activeCapture = null;
    activeOwner = null;
    return () => undefined;
  }

  const owner = Symbol('active-camera-capture');
  activeCapture = capture;
  activeOwner = owner;

  return () => {
    if (activeOwner !== owner) {
      // A newer preview replaced this one; its registration owns cleanup now.
      return;
    }
    activeCapture = null;
    activeOwner = null;
  };
};

/**
 * Return the mounted camera preview capture function, if one is active.
 */
export const getActiveCameraCapture = (): CameraCaptureFn | null => activeCapture;

/**
 * True while `capture` is still the active registration.
 *
 * Capture paths await the OS (permission checks) before touching the preview
 * ref. This lets them re-validate ownership after the await so a blur,
 * unmount, or replacement cannot drive a stale registration.
 */
export const isActiveCameraCapture = (capture: CameraCaptureFn): boolean =>
  activeCapture === capture;
