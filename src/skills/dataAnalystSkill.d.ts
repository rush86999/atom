import { TurnContext } from 'botbuilder';
import { IEchoSkill } from './echoSkill';
export declare class DataAnalystSkill extends IEchoSkill {
    constructor(context: TurnContext, memory: any, functions: any);
    analyzeData(query: string): Promise<string>;
}
