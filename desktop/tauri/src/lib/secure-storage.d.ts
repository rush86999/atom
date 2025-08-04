export declare function saveSetting(key: string, value: string): Promise<void>;
export declare function getSetting(key: string): Promise<string | null>;
export declare function getSettingStatus(key: string): Promise<boolean>;
