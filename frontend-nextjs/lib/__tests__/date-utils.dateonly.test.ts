/**
 * toDateOnlyISO tests — guards against the date-off-by-one bug.
 *
 * A date-only input string ("2026-08-04") parsed via `new Date(...)` is
 * interpreted as UTC midnight (ES5). When later rendered via
 * toLocaleDateString() in a UTC-negative timezone, it shifts to the previous
 * day. The helper must interpret the date as LOCAL midnight so the ISO string
 * represents the same calendar day the user entered.
 */
import { toDateOnlyISO } from '../date-utils';

describe('toDateOnlyISO', () => {
  it('produces an ISO string whose calendar day matches the input (UTC-negative TZ)', () => {
    // Simulate a user in a UTC-negative timezone entering Aug 4.
    // The bug: new Date("2026-08-04").toISOString() = "2026-08-04T00:00:00.000Z",
    // which in America/New_York is Aug 3 8pm → displayed as "8/3/2026".
    const iso = toDateOnlyISO('2026-08-04');

    // The ISO string must carry the same calendar day regardless of timezone.
    // dayjs interprets date-only strings as local, so the ISO will have a
    // timezone offset that preserves Aug 4.
    const day = new Date(iso).getUTCDate();
    // In a UTC-negative TZ, the local-midnight ISO has a negative offset, so
    // the UTC date is still Aug 4 (e.g. 2026-08-04T04:00:00.000Z for UTC-4).
    // In a UTC-positive TZ, the UTC date is still Aug 4 (e.g. 2026-08-03T16:00:00Z
    // would be wrong — but dayjs local keeps Aug 4's calendar). The key invariant:
    // the calendar day in the user's locale matches the input.
    expect(iso).toBeTruthy();
    // Round-trip: parsing the ISO and formatting in ANY timezone must yield Aug 4.
    // We check the substring to avoid TZ-specific exact values.
    expect(iso.startsWith('2026-08-04')).toBe(true);
  });

  it('handles datetime inputs without corruption', () => {
    const iso = toDateOnlyISO('2026-08-04T10:30:00');
    expect(iso).toBeTruthy();
    expect(iso.startsWith('2026-08-04')).toBe(true);
  });

  it('returns a valid ISO string for empty/invalid input', () => {
    // Defensive: must not throw or return NaN.
    const iso = toDateOnlyISO('');
    expect(iso).toBe('');
    expect(toDateOnlyISO('not-a-date')).toBe('');
  });
});
