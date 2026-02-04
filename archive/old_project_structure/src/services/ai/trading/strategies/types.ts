import { TradeConfirmation } from '../../tradingAgentService';

export interface TradingStrategy {
  execute(userId: string, positions: any[]): Promise<TradeConfirmation[]>;
}

export interface TradeOrder {
    ticker: string;
    quantity: number;
    tradeType: 'buy' | 'sell';
}
