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
