import { TradingAgentService } from '../tradingAgentService';
import { FinanceAgentService } from '../financeAgentService';
import { StrategyFactory } from './StrategyFactory';
import { TradingStrategy } from './strategies/types';

export class AutonomousTradingService {
  private tradingService: TradingAgentService;
  private financeService: FinanceAgentService;
  private userId: string;
  private strategy: TradingStrategy;
  private isRunning: boolean = false;
  private intervalId: NodeJS.Timeout | null = null;

  constructor(userId: string, strategyName: string) {
    this.userId = userId;
    this.tradingService = new TradingAgentService(userId);
    this.financeService = new FinanceAgentService(userId);
    this.strategy = StrategyFactory.createStrategy(strategyName, this.userId);
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

    // Get account positions
    const positions = await this.tradingService.getAccountPositions(this.userId);
    console.log('Account Positions:', positions);

    // Execute the trading strategy
    await this.strategy.execute(this.userId, positions);
  }
}
