import { extractApiErrorMessage } from '@/lib/api-error';

it('shows validation messages without rendering submitted credentials or context', () => {
  const result = extractApiErrorMessage({ detail: [
    { msg: 'Password must be shorter', input: 'private-fixture-value', ctx: { secret: 'hidden-context' } },
    { msg: 'A token is required', input: 'hidden-token-value' },
  ] }, 'Unable to continue');
  expect(result).toBe('Password must be shorter; A token is required');
  expect(result).not.toContain('private-fixture-value');
  expect(result).not.toContain('hidden-context');
  expect(result).not.toContain('hidden-token-value');
});

it('preserves ordinary string and structured-error compatibility', () => {
  expect(extractApiErrorMessage({ detail: 'Unavailable' }, 'Failed')).toBe('Unavailable');
  expect(extractApiErrorMessage({ error: { message: 'Try later' } }, 'Failed')).toBe('Try later');
  expect(extractApiErrorMessage(null, 'Failed')).toBe('Failed');
});
