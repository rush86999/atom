import { TradingStrategy, TradeOrder } from './types';
import { TradeConfirmation } from '../../tradingAgentService';
import { TradingAgentService } from '../../tradingAgentService';
import { SMA } from 'technicalindicators';
import axios from 'axios';

const ALPHA_VANTAGE_API_KEY = 'YOUR_API_KEY'; // TODO: Replace with a real API key

export class MovingAverageCrossoverStrategy implements TradingStrategy {
  private tradingService: TradingAgentService;
  private shortTermPeriod: number;
  private longTermPeriod: number;

  constructor(userId: string, shortTermPeriod: number = 20, longTermPeriod: number = 50) {
    this.tradingService = new TradingAgentService(userId);
    this.shortTermPeriod = shortTermPeriod;
    this.longTermPeriod = longTermPeriod;
  }

  public async execute(userId: string, positions: any[]): Promise<TradeConfirmation[]> {
    const trades: any[] = [];

    for (const position of positions) {
      const historicalData = await this.fetchHistoricalData(position.ticker);

      if (historicalData.length < this.longTermPeriod) {
        console.warn(`Not enough historical data for ${position.ticker} to calculate long-term SMA.`);
        continue;
      }

      const shortTermSma = new SMA({ period: this.shortTermPeriod, values: historicalData });
      const longTermSma = new SMA({ period: this.longTermPeriod, values: historicalData });

      const shortTermSmaValues = shortTermSma.getResult();
      const longTermSmaValues = longTermSma.getResult();

      const lastShortTermSma = shortTermSmaValues[shortTermSmaValues.length - 1];
      const lastLongTermSma = longTermSmaValues[longTermSmaValues.length - 1];

      const prevShortTermSma = shortTermSmaValues[shortTermSmaValues.length - 2];
      const prevLongTermSma = longTermSmaValues[longTermSmaValues.length - 2];

      if (prevShortTermSma <= prevLongTermSma && lastShortTermSma > lastLongTermSma) {
        // Buy signal
        const trade = await this.tradingService.executeTrade({
            userId,
            ticker: position.ticker,
            quantity: 1, // Buy one share
            tradeType: 'buy',
        });
        trades.push(trade);
      } else if (prevShortTermSma >= prevLongTermSma && lastShortTermSma < lastLongTermSma) {
        // Sell signal
        const trade = await this.tradingService.executeTrade({
            userId,
            ticker: position.ticker,
            quantity: position.quantity,
            tradeType: 'sell',
        });
        trades.push(trade);
      }
    }

    return trades;
  }

  private async fetchHistoricalData(ticker: string): Promise<number[]> {
    try {
      const response = await axios.get(
        `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol=${ticker}&apikey=${ALPHA_VANTAGE_API_KEY}`
      );
      const timeSeries = response.data['Time Series (Daily)'];
      const closingPrices = Object.values(timeSeries).map((day: any) => parseFloat(day['4. close']));
      return closingPrices.reverse();
    } catch (error) {
      console.error(`Error fetching historical data for ${ticker}:`, error);
      return [];
    }
  }
}
