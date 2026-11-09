/** Real SDK stop returns void; only the original recording promise supplies media. */
import type { CameraProps } from 'expo-camera/next';
import { CameraView, Camera } from 'expo-camera/next';
import { cameraService, VideoOptions } from '../../services/cameraService';
import * as FileSystem from 'expo-file-system';

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
    jest.mocked(FileSystem.getInfoAsync).mockReset().mockImplementation(async (uri) => ({ exists: true, isDirectory: false, size: 0, modificationTime: 0, uri }));
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
  test.each<{ label: string; view: CameraProps; options: VideoOptions }>([
    { label: 'picture mode', view: { mode: 'picture' }, options: {} },
    { label: 'quality mismatch', view: { mode: 'video', videoQuality: '1080p' }, options: { quality: '720p' } },
    { label: 'mute mismatch', view: { mode: 'video', mute: false }, options: { mute: true } },
    { label: 'unsupported legacy quality', view: { mode: 'video' }, options: { quality: '360p' } },
  ])('settings contract: $label refuses before recording', async ({ view, options }) => {
    const ref = { current: new CameraView(view) };
    expect(await cameraService.recordVideo(ref, options)).toBeNull();
    expect(ref.current.recordAsync).not.toHaveBeenCalled();
  });

  test('forwards only real recording limits while verifying mounted quality and mute', async () => {
    const ref = { current: new CameraView({ mode: 'video', videoQuality: '720p', mute: true }) };
    jest.mocked(ref.current.recordAsync).mockResolvedValue({ uri: 'file:///controlled-exact-options.mp4' });
    expect(await cameraService.recordVideo(ref, { quality: '720p', mute: true, maxDuration: 30, maxFileSize: 1000 })).toEqual({ uri: 'file:///controlled-exact-options.mp4', type: 'video', size: 0 });
    expect(ref.current.recordAsync).toHaveBeenCalledWith({ maxDuration: 30, maxFileSize: 1000 });
  });

  test('duplicate stops signal once and join the original media', async () => {
    const ref = { current: new CameraView({ mode: 'video' }) };
    const pending = pendingVideo();
    jest.mocked(ref.current.recordAsync).mockReturnValue(pending.promise);
    const recording = cameraService.recordVideo(ref);
    const firstStop = cameraService.stopRecording(ref);
    const secondStop = cameraService.stopRecording(ref);
    pending.finish({ uri: 'file:///controlled-once.mp4' });
    expect(await firstStop).toEqual(await recording);
    expect(await secondStop).toEqual(await recording);
    expect(ref.current.stopRecording).toHaveBeenCalledTimes(1);
  });

  test('a second start with changed limits is refused without replacing the first capture', async () => {
    const ref = { current: new CameraView({ mode: 'video' }) };
    const pending = pendingVideo();
    jest.mocked(ref.current.recordAsync).mockReturnValue(pending.promise);
    const recording = cameraService.recordVideo(ref, { maxDuration: 30 });
    expect(await cameraService.recordVideo(ref, { maxDuration: 60 })).toBeNull();
    expect(ref.current.recordAsync).toHaveBeenCalledTimes(1);
    pending.finish({ uri: 'file:///controlled-first.mp4' });
    expect((await recording)?.uri).toBe('file:///controlled-first.mp4');
    jest.mocked(ref.current.recordAsync).mockResolvedValue({ uri: 'file:///controlled-next.mp4' });
    expect((await cameraService.recordVideo(ref))?.uri).toBe('file:///controlled-next.mp4');
    expect(ref.current.recordAsync).toHaveBeenCalledTimes(2);
  });

  test('different camera instances retain independent completions and stops', async () => {
    const a = { current: new CameraView({ mode: 'video' }) };
    const b = { current: new CameraView({ mode: 'video' }) };
    const pa = pendingVideo(); const pb = pendingVideo();
    jest.mocked(a.current.recordAsync).mockReturnValue(pa.promise);
    jest.mocked(b.current.recordAsync).mockReturnValue(pb.promise);
    const ra = cameraService.recordVideo(a); const rb = cameraService.recordVideo(b);
    const sa = cameraService.stopRecording(a);
    expect(b.current.stopRecording).not.toHaveBeenCalled();
    pa.finish({ uri: 'file:///controlled-a.mp4' });
    expect((await sa)?.uri).toBe('file:///controlled-a.mp4');
    expect(await ra).toEqual(await sa);
    const sb = cameraService.stopRecording(b); pb.finish({ uri: 'file:///controlled-b.mp4' });
    expect((await rb)?.uri).toBe('file:///controlled-b.mp4');
    expect(await sb).toEqual(await rb);
  });

  test('metadata inspection failure preserves the real capture without fabricating size', async () => {
    const ref = { current: new CameraView({ mode: 'video' }) };
    jest.mocked(ref.current.recordAsync).mockResolvedValue({ uri: 'file:///controlled-real.mp4' });
    jest.mocked(FileSystem.getInfoAsync).mockRejectedValueOnce(new Error('controlled metadata unavailable'));
    expect(await cameraService.recordVideo(ref)).toEqual({ uri: 'file:///controlled-real.mp4', type: 'video', size: undefined });
  });

  test('a completed native capture awaiting metadata is joined without another native stop', async () => {
    const ref = { current: new CameraView({ mode: 'video' }) };
    let finishMetadata: ((info: FileSystem.FileInfo) => void) | undefined;
    jest.mocked(FileSystem.getInfoAsync).mockImplementation(() => new Promise<FileSystem.FileInfo>((resolve) => { finishMetadata = resolve; }));
    jest.mocked(ref.current.recordAsync).mockResolvedValue({ uri: 'file:///controlled-completed.mp4' });
    const recording = cameraService.recordVideo(ref);
    await Promise.resolve();
    const stopping = cameraService.stopRecording(ref);
    if (!finishMetadata) throw new Error('controlled metadata inspection did not start');
    finishMetadata({ exists: false, isDirectory: false, uri: 'file:///controlled-completed.mp4' });
    expect((await recording)?.uri).toBe('file:///controlled-completed.mp4');
    expect(await stopping).toEqual(await recording);
    expect(ref.current.stopRecording).not.toHaveBeenCalled();
  });

  test('native rejection stays null and releases only its completed recording', async () => {
    const ref = { current: new CameraView({ mode: 'video' }) };
    jest.mocked(ref.current.recordAsync).mockRejectedValueOnce(new Error('controlled recording failure'));
    expect(await cameraService.recordVideo(ref)).toBeNull();
    jest.mocked(ref.current.recordAsync).mockResolvedValue({ uri: 'file:///controlled-retry.mp4' });
    expect((await cameraService.recordVideo(ref))?.uri).toBe('file:///controlled-retry.mp4');
  });

});
