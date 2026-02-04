import { TradingStrategy } from './strategies/types';
import { MovingAverageCrossoverStrategy } from './strategies/MovingAverageCrossoverStrategy';
import { RsiStrategy } from './strategies/RsiStrategy';
import { BollingerBandsStrategy } from './strategies/BollingerBandsStrategy';

export class StrategyFactory {
  public static createStrategy(strategyName: string, userId: string): TradingStrategy {
    switch (strategyName) {
      case 'moving_average_crossover':
        return new MovingAverageCrossoverStrategy(userId);
      case 'rsi':
        return new RsiStrategy(userId);
      case 'bollinger_bands':
        return new BollingerBandsStrategy(userId);
      default:
        throw new Error(`Invalid strategy name: ${strategyName}`);
    }
  }
}
