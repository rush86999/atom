import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);

export { dayjs };

export function formatDate(date: Date | string | number, format: string = 'YYYY-MM-DD'): string {
    return dayjs(date).format(format);
}

export function formatDateTime(date: Date | string | number, format: string = 'YYYY-MM-DD HH:mm:ss'): string {
    return dayjs(date).format(format);
}

export function formatRelativeTime(date: Date | string | number): string {
    return dayjs(date).fromNow();
}

export function parseDate(dateString: string): Date {
    return dayjs(dateString).toDate();
}

export function isValidDate(date: any): boolean {
    return dayjs(date).isValid();
}

/**
 * Convert a date input (typically a date-only string like "2026-08-04" from an
 * <input type="date">) to an ISO string that preserves the user's calendar day
 * across timezones.
 *
 * Uses dayjs, which interprets date-only strings as LOCAL time (unlike
 * `new Date("2026-08-04")` which ES5 treats as UTC midnight — causing an
 * off-by-one when rendered via toLocaleDateString() in a UTC-negative zone).
 *
 * Returns '' for empty/invalid input so callers can serialize safely.
 */
export function toDateOnlyISO(dateStr: string): string {
    if (!dateStr) return '';
    const d = dayjs(dateStr);
    if (!d.isValid()) return '';
    return d.toISOString();
}
