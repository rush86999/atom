import { Tool } from 'langchain/tools';
declare class OpenBrowser extends Tool {
    name: string;
    description: string;
    _call(url: string): Promise<string>;
}
declare class Click extends Tool {
    name: string;
    description: string;
    _call(selector: string): Promise<string>;
}
declare class Type extends Tool {
    name: string;
    description: string;
    _call(input: {
        selector: string;
        text: string;
    }): Promise<string>;
}
declare class Extract extends Tool {
    name: string;
    description: string;
    _call(input: {
        selector: string;
        attribute?: string;
    }): Promise<string>;
}
declare class Screenshot extends Tool {
    name: string;
    description: string;
    _call(path: string): Promise<string>;
}
export declare const browserSkills: (OpenBrowser | Click | Type | Extract | Screenshot)[];
export {};
