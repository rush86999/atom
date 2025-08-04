import { TurnContext } from 'botbuilder';
import { IEchoSkill } from './echoSkill';
export declare class DataAnalystSkills extends IEchoSkill {
    constructor(context: TurnContext, memory: any, functions: any);
    dataAnalysis(entity: string): Promise<string>;
    generateReport(topic: string): Promise<string>;
}
