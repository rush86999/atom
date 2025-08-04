export declare const castStringEnv: (envVar: string, defaultValue?: string) => string;
export declare const castBooleanEnv: (envVar: string, defaultValue?: boolean) => boolean;
export declare const castIntEnv: (envVar: string, defaultValue: number) => number;
export declare const castStringArrayEnv: (envVar: string, defaultValue?: string[]) => string[];
export declare const castObjectEnv: <T extends Record<string, unknown>>(envVar: string, defaultValue?: T) => T;
