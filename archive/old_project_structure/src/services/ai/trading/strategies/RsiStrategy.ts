import { TradingStrategy, TradeOrder } from './types';
import { TradeConfirmation } from '../../tradingAgentService';
import { TradingAgentService } from '../../tradingAgentService';
import { RSI } from 'technicalindicators';
import axios from 'axios';

const ALPHA_VANTAGE_API_KEY = 'YOUR_API_KEY'; // TODO: Replace with a real API key

export class RsiStrategy implements TradingStrategy {
  private tradingService: TradingAgentService;
  private rsiPeriod: number;
  private overboughtThreshold: number;
  private oversoldThreshold: number;

  constructor(userId: string, rsiPeriod: number = 14, overboughtThreshold: number = 70, oversoldThreshold: number = 30) {
    this.tradingService = new TradingAgentService(userId);
    this.rsiPeriod = rsiPeriod;
    this.overboughtThreshold = overboughtThreshold;
    this.oversoldThreshold = oversoldThreshold;
  }

  public async execute(userId: string, positions: any[]): Promise<TradeConfirmation[]> {
    const trades: any[] = [];

    for (const position of positions) {
      const historicalData = await this.fetchHistoricalData(position.ticker);

      if (historicalData.length < this.rsiPeriod) {
        console.warn(`Not enough historical data for ${position.ticker} to calculate RSI.`);
        continue;
      }

      const rsi = new RSI({ period: this.rsiPeriod, values: historicalData });
      const rsiValues = rsi.getResult();
      const lastRsi = rsiValues[rsiValues.length - 1];

      if (lastRsi > this.overboughtThreshold) {
        // Sell signal
        const trade = await this.tradingService.executeTrade({
            userId,
            ticker: position.ticker,
            quantity: position.quantity,
            tradeType: 'sell',
        });
        trades.push(trade);
      } else if (lastRsi < this.oversoldThreshold) {
        // Buy signal
        const trade = await this.tradingService.executeTrade({
            userId,
            ticker: position.ticker,
            quantity: 1, // Buy one share
            tradeType: 'buy',
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
