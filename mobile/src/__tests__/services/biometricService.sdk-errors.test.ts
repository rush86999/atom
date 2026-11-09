/** Installed Expo failure union carries a string error; no real biometric prompt. */
import * as LocalAuthentication from 'expo-local-authentication';
import { biometricService, type BiometricError } from '../../services/biometricService';

describe('BiometricService actual SDK error values', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    biometricService._resetState();
    jest.mocked(LocalAuthentication.hasHardwareAsync).mockResolvedValue(true);
    jest.mocked(LocalAuthentication.isEnrolledAsync).mockResolvedValue(true);
    jest.mocked(LocalAuthentication.supportedAuthenticationTypesAsync).mockResolvedValue([LocalAuthentication.AuthenticationType.FINGERPRINT]);
    jest.mocked(LocalAuthentication.authenticateAsync).mockReset();
  });

  test.each<{ code: string; error: BiometricError; message: string }>([
    { code: 'not_enrolled', error: 'not_enrolled', message: 'No biometric enrolled' },
    { code: 'lockout', error: 'locked_out', message: 'temporarily locked' },
    { code: 'locked_out', error: 'locked_out', message: 'temporarily locked' },
    { code: 'user_cancel', error: 'user_cancelled', message: 'cancelled' },
    { code: 'system_cancel', error: 'system_cancelled', message: 'cancelled' },
    { code: 'passcode_not_set', error: 'passcode_not_set', message: 'passcode is not set' },
    { code: 'not_available', error: 'not_available', message: 'not available' },
    { code: 'authentication_failed', error: 'authentication_failed', message: 'Authentication failed' },
    { code: 'unexpected_sdk_code', error: 'authentication_failed', message: 'Authentication failed' },
  ])('$code remains a truthful failed attempt with its SDK classification', async ({ code, error, message }) => {
    jest.mocked(LocalAuthentication.authenticateAsync).mockResolvedValueOnce({ success: false, error: code });
    const result = await biometricService.authenticate();
    expect(result.success).toBe(false);
    expect(result.error).toContain(message);
    expect(biometricService.getRecentAttempts()).toHaveLength(1);
    expect(biometricService.getRecentAttempts()[0]).toMatchObject({ success: false, error, biometricType: 'fingerprint' });
  });

  test('the actual success discriminant remains successful without an invented error', async () => {
    jest.mocked(LocalAuthentication.authenticateAsync).mockResolvedValueOnce({ success: true });
    expect(await biometricService.authenticate()).toMatchObject({ success: true, error: undefined, biometricType: 'fingerprint' });
    expect(biometricService.getLockoutStatus().locked).toBe(false);
  });
});
