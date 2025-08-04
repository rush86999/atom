import { TurnContext } from 'botbuilder';

export abstract class IEchoSkill {
  protected readonly context: TurnContext;
  protected readonly memory: any;
  protected readonly functions: any;

  constructor(context: TurnContext, memory: any, functions: any) {
    this.context = context;
    this.memory = memory;
    this.functions = functions;
  }

  public abstract analyzeData(query: string): Promise<string>;
}
