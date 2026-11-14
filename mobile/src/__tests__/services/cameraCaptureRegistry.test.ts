/**
 * Camera Capture Registry lifecycle tests.
 *
 * The registry is a single active slot shared by mounted camera screens and
 * background command handlers. These tests pin down ownership semantics so a
 * stale screen cleanup cannot withdraw a newer preview.
 */

import {
  getActiveCameraCapture,
  isActiveCameraCapture,
  registerActiveCameraCapture,
} from '../../services/cameraCaptureRegistry';

describe('cameraCaptureRegistry', () => {
  beforeEach(() => {
    registerActiveCameraCapture(null);
  });

  it('returns the registered capture', () => {
    const capture = jest.fn();

    registerActiveCameraCapture(capture);

    expect(getActiveCameraCapture()).toBe(capture);
  });

  it('only clears the registration owned by the release function', () => {
    const first = jest.fn();
    const second = jest.fn();

    const releaseFirst = registerActiveCameraCapture(first);
    const releaseSecond = registerActiveCameraCapture(second);

    // The newer registration is active; releasing the older one is a no-op.
    releaseFirst();
    expect(getActiveCameraCapture()).toBe(second);

    releaseSecond();
    expect(getActiveCameraCapture()).toBeNull();
  });

  it('keeps a newer registration when an older release runs again', () => {
    const first = jest.fn();
    const second = jest.fn();

    const releaseFirst = registerActiveCameraCapture(first);
    releaseFirst();
    registerActiveCameraCapture(second);

    // A repeated/late cleanup from the old registration must not clear the
    // preview that replaced it.
    releaseFirst();

    expect(getActiveCameraCapture()).toBe(second);
  });

  it('clears the registry when registered with null', () => {
    registerActiveCameraCapture(jest.fn());

    registerActiveCameraCapture(null);

    expect(getActiveCameraCapture()).toBeNull();
  });

  it('reports whether a capture is still the active registration', () => {
    const first = jest.fn();
    const second = jest.fn();

    const releaseFirst = registerActiveCameraCapture(first);
    expect(isActiveCameraCapture(first)).toBe(true);
    expect(isActiveCameraCapture(second)).toBe(false);

    registerActiveCameraCapture(second);
    // A newer preview replaced `first`, even before its release runs.
    expect(isActiveCameraCapture(first)).toBe(false);
    expect(isActiveCameraCapture(second)).toBe(true);

    releaseFirst();
    expect(isActiveCameraCapture(second)).toBe(true);
  });
});
