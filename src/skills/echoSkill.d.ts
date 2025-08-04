import { TurnContext } from 'botbuilder';
export declare abstract class IEchoSkill {
    protected readonly context: TurnContext;
    protected readonly memory: any;
    protected readonly functions: any;
    constructor(context: TurnContext, memory: any, functions: any);
    abstract analyzeData(query: string): Promise<string>;
}
