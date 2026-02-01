import axios from 'axios';
import { z } from 'zod';

// Zod schemas for secure parameter validation
const TradeParamsSchema = z.object({
  userId: z.string(),
  ticker: z.string(),
  quantity: z.number().positive(),
  tradeType: z.enum(['buy', 'sell']),
});

// Types
export type TradeConfirmation = {
  orderId: string;
  ticker: string;
  quantity: number;
  price: number;
  status: 'filled' | 'pending' | 'failed';
};

export class TradingAgentService {
  private apiBaseUrl: string;
  private userId: string;

  constructor(userId: string, apiBaseUrl: string = '/api/brokerage') {
    this.userId = userId;
    this.apiBaseUrl = apiBaseUrl;
  }

  async executeTrade(
    params: z.infer<typeof TradeParamsSchema>
  ): Promise<string> {
    try {
      const validated = TradeParamsSchema.parse({
        ...params,
        userId: this.userId,
      });
      const response = await axios.post(`${this.apiBaseUrl}/orders`, validated);

      const data = response.data as TradeConfirmation;

      if (data.status === 'filled') {
        return `✅ Your order to ${params.tradeType} ${
          data.quantity
        } shares of ${data.ticker.toUpperCase()} has been filled at an average price of $${data.price.toLocaleString()}.`;
      } else if (data.status === 'pending') {
        return `⏳ Your order to ${params.tradeType} ${
          data.quantity
        } shares of ${data.ticker.toUpperCase()} has been submitted and is pending execution.`;
      } else {
        return `❌ Your order to ${params.tradeType} ${
          data.quantity
        } shares of ${data.ticker.toUpperCase()} failed to execute. Please try again later.`;
      }
    } catch (error) {
      console.error('Error executing trade:', error);
      return "I couldn't execute the trade. Please check your brokerage connection and try again.";
    }
  }

  async getAccountPositions(userId: string): Promise<any[]> {
    try {
      const response = await axios.get(`${this.apiBaseUrl}/positions`, {
        params: { userId },
      });
      return response.data.positions;
    } catch (error) {
      console.error('Error fetching account positions:', error);
      return [];
    }
  }
}
