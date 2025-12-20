import { TradingStrategy, TradeOrder } from './types';
import { TradeConfirmation } from '../../tradingAgentService';
import { TradingAgentService } from '../../tradingAgentService';
import { BollingerBands } from 'technicalindicators';
import axios from 'axios';

const ALPHA_VANTAGE_API_KEY = 'YOUR_API_KEY'; // TODO: Replace with a real API key

export class BollingerBandsStrategy implements TradingStrategy {
  private tradingService: TradingAgentService;
  private period: number;
  private stdDev: number;

  constructor(userId: string, period: number = 20, stdDev: number = 2) {
    this.tradingService = new TradingAgentService(userId);
    this.period = period;
    this.stdDev = stdDev;
  }

  public async execute(userId: string, positions: any[]): Promise<TradeConfirmation[]> {
    const trades: any[] = [];

    for (const position of positions) {
      const historicalData = await this.fetchHistoricalData(position.ticker);

      if (historicalData.length < this.period) {
        console.warn(`Not enough historical data for ${position.ticker} to calculate Bollinger Bands.`);
        continue;
      }

      const bbInput = { period: this.period, stdDev: this.stdDev, values: historicalData };
      const bb = new BollingerBands(bbInput);
      const bbValues = bb.getResult();
      const lastBb = bbValues[bbValues.length - 1];
      const lastPrice = historicalData[historicalData.length - 1];

      if (lastPrice > lastBb.upper) {
        // Sell signal
        const trade = await this.tradingService.executeTrade({
            userId,
            ticker: position.ticker,
            quantity: position.quantity,
            tradeType: 'sell',
        });
        trades.push(trade);
      } else if (lastPrice < lastBb.lower) {
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
