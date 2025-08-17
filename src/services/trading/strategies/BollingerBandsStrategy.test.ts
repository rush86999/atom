import { BollingerBandsStrategy } from './BollingerBandsStrategy';
import { TradingAgentService } from '../../tradingAgentService';
import axios from 'axios';

jest.mock('../../tradingAgentService');
jest.mock('axios');

describe('BollingerBandsStrategy', () => {
  let strategy: BollingerBandsStrategy;
  let tradingService: jest.Mocked<TradingAgentService>;

  beforeEach(() => {
    tradingService = new TradingAgentService('test-user') as jest.Mocked<TradingAgentService>;
    strategy = new BollingerBandsStrategy('test-user');
    (strategy as any).tradingService = tradingService;
  });

  it('should generate a sell signal when the price is above the upper band', async () => {
    // Mock the historical data
    (axios.get as jest.Mock).mockResolvedValue({
      data: {
        'Time Series (Daily)': {
          // ... add data to make price > upper band
        },
      },
    });

    // Mock the executeTrade method
    tradingService.executeTrade.mockResolvedValue({
        orderId: '123',
        ticker: 'AAPL',
        quantity: 1,
        price: 100,
        status: 'filled',
    });

    const positions = [{ ticker: 'AAPL', quantity: 1 }];
    const trades = await strategy.execute('test-user', positions);

    expect(trades).toHaveLength(1);
    expect(trades[0].tradeType).toBe('sell');
  });

  it('should generate a buy signal when the price is below the lower band', async () => {
    // Mock the historical data
    (axios.get as jest.Mock).mockResolvedValue({
      data: {
        'Time Series (Daily)': {
          // ... add data to make price < lower band
        },
      },
    });

    // Mock the executeTrade method
    tradingService.executeTrade.mockResolvedValue({
        orderId: '123',
        ticker: 'AAPL',
        quantity: 1,
        price: 90,
        status: 'filled',
    });

    const positions = [{ ticker: 'AAPL', quantity: 1 }];
    const trades = await strategy.execute('test-user', positions);

    expect(trades).toHaveLength(1);
    expect(trades[0].tradeType).toBe('buy');
  });
});
