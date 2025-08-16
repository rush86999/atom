import { TradingAgentService } from '../services/tradingAgentService';
import { FinanceAgentService } from '../services/financeAgentService';

// A simple autonomous trading service
export class AutonomousTradingService {
  private tradingService: TradingAgentService;
  private financeService: FinanceAgentService;
  private userId: string;
  private isRunning: boolean = false;
  private intervalId: NodeJS.Timeout | null = null;

  constructor(userId: string) {
    this.userId = userId;
    this.tradingService = new TradingAgentService(userId);
    this.financeService = new FinanceAgentService(userId);
  }

  start() {
    if (this.isRunning) {
      return 'Autonomous trading is already running.';
    }

    this.isRunning = true;
    this.intervalId = setInterval(() => this.runTradingLogic(), 60000); // Run every minute
    return 'Autonomous trading has been started.';
  }

  stop() {
    if (!this.isRunning) {
      return 'Autonomous trading is not running.';
    }

    this.isRunning = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
    return 'Autonomous trading has been stopped.';
  }

  private async runTradingLogic() {
    console.log('Running autonomous trading logic...');

    // Get market data
    const investmentSummary = await this.financeService.getInvestmentSummary();
    console.log('Investment Summary:', investmentSummary);

    // Get account positions
    const positions = await this.tradingService.getAccountPositions(this.userId);
    console.log('Account Positions:', positions);

    // Simple trading logic: if a stock has gone up by more than 5%, sell it.
    // If a stock has gone down by more than 5%, buy it.
    for (const position of positions) {
      if (position.unrealized_pl_pct > 0.05) {
        await this.tradingService.executeTrade({
          userId: this.userId,
          ticker: position.ticker,
          quantity: position.quantity,
          tradeType: 'sell',
        });
      } else if (position.unrealized_pl_pct < -0.05) {
        await this.tradingService.executeTrade({
          userId: this.userId,
          ticker: position.ticker,
          quantity: 1, // Buy one share
          tradeType: 'buy',
        });
      }
    }
  }
}

// A map to store the running autonomous trading services
const autonomousTradingServices = new Map<string, AutonomousTradingService>();

export const tradingSkills = [
  {
    name: 'start_autonomous_trading',
    description: 'Start the autonomous trading system.',
    parameters: {
      type: 'object',
      properties: {
        userId: { type: 'string' },
      },
      required: ['userId'],
    },
    handler: async (params: any) => {
      let service = autonomousTradingServices.get(params.userId);
      if (!service) {
        service = new AutonomousTradingService(params.userId);
        autonomousTradingServices.set(params.userId, service);
      }
      return service.start();
    },
  },
  {
    name: 'stop_autonomous_trading',
    description: 'Stop the autonomous trading system.',
    parameters: {
      type: 'object',
      properties: {
        userId: { type: 'string' },
      },
      required: ['userId'],
    },
    handler: async (params: any) => {
      const service = autonomousTradingServices.get(params.userId);
      if (service) {
        return service.stop();
      }
      return 'Autonomous trading is not running.';
    },
  },
];
