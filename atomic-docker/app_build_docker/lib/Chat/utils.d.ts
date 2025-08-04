import { type ClassValue } from 'clsx';
export declare function cn(...inputs: ClassValue[]): string;
export declare const nanoid: (size?: number) => string;
export declare function fetcher<JSON = any>(input: RequestInfo, init?: RequestInit): Promise<JSON>;
export declare function formatDate(input: string | number | Date): string;
