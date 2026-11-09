/** Real SDK stop returns void; only the original recording promise supplies media. */
import type { CameraProps } from 'expo-camera/next';
import { CameraView, Camera } from 'expo-camera/next';
import { cameraService } from '../../services/cameraService';

jest.mock('expo-camera/next', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  class CameraView extends React.Component<CameraProps> {
    recordAsync = jest.fn();
    stopRecording = jest.fn();
  }
  return { CameraView, Camera: { requestCameraPermissionsAsync: jest.fn().mockResolvedValue({ status: 'granted', granted: true, canAskAgain: true, expires: 'never' }) }, PermissionStatus: { GRANTED: 'granted', DENIED: 'denied', UNDETERMINED: 'undetermined' } };
});

function pendingVideo() {
  let complete: ((value: { uri: string } | undefined) => void) | undefined;
  const promise = new Promise<{ uri: string } | undefined>((resolve) => { complete = resolve; });
  return { promise, finish(value: { uri: string } | undefined) { if (!complete) throw new Error('missing controlled resolver'); complete(value); } };
}

describe('CameraService recording SDK contract', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    cameraService.reset();
    await cameraService.requestPermissions();
  });

  test('stop joins the exact recording promise instead of reading a void stop result', async () => {
    const ref = { current: new CameraView({ mode: 'video', videoQuality: '1080p', mute: false }) };
    const pending = pendingVideo();
    jest.mocked(ref.current.recordAsync).mockReturnValue(pending.promise);
    const recording = cameraService.recordVideo(ref);
    const stopping = cameraService.stopRecording(ref);
    pending.finish({ uri: 'file:///controlled-video.mp4' });
    expect((await recording)?.uri).toBe('file:///controlled-video.mp4');
    expect((await stopping)?.uri).toBe('file:///controlled-video.mp4');
    expect(ref.current.stopRecording).toHaveBeenCalledTimes(1);
  });

  test('duplicate starts cannot dispatch a second recording for the same view', async () => {
    const ref = { current: new CameraView({ mode: 'video', videoQuality: '1080p', mute: false }) };
    const pending = pendingVideo();
    jest.mocked(ref.current.recordAsync).mockReturnValue(pending.promise);
    const first = cameraService.recordVideo(ref);
    const second = cameraService.recordVideo(ref);
    pending.finish({ uri: 'file:///controlled-original.mp4' });
    await Promise.all([first, second]);
    expect(ref.current.recordAsync).toHaveBeenCalledTimes(1);
  });

  test('no active recording produces no stop dispatch or invented media', async () => {
    const ref = { current: new CameraView({ mode: 'video' }) };
    expect(await cameraService.stopRecording(ref)).toBeNull();
    expect(ref.current.stopRecording).not.toHaveBeenCalled();
  });

  test('undefined SDK completion remains no media', async () => {
    const ref = { current: new CameraView({ mode: 'video', videoQuality: '1080p', mute: false }) };
    jest.mocked(ref.current.recordAsync).mockResolvedValue(undefined);
    expect(await cameraService.recordVideo(ref)).toBeNull();
  });
});
