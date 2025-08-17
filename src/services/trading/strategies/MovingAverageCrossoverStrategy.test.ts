import { MovingAverageCrossoverStrategy } from './MovingAverageCrossoverStrategy';
import { TradingAgentService } from '../../tradingAgentService';
import axios from 'axios';

jest.mock('../../tradingAgentService');
jest.mock('axios');

describe('MovingAverageCrossoverStrategy', () => {
  let strategy: MovingAverageCrossoverStrategy;
  let tradingService: jest.Mocked<TradingAgentService>;

  beforeEach(() => {
    tradingService = new TradingAgentService('test-user') as jest.Mocked<TradingAgentService>;
    strategy = new MovingAverageCrossoverStrategy('test-user');
    (strategy as any).tradingService = tradingService;
  });

  it('should generate a buy signal when the short-term SMA crosses above the long-term SMA', async () => {
    // Mock the historical data
    (axios.get as jest.Mock).mockResolvedValue({
      data: {
        'Time Series (Daily)': {
          '2025-08-16': { '4. close': '100' },
          '2025-08-15': { '4. close': '90' },
          // ... add more data to create a crossover
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
    expect(trades[0].tradeType).toBe('buy');
  });

  it('should generate a sell signal when the short-term SMA crosses below the long-term SMA', async () => {
    // Mock the historical data
    (axios.get as jest.Mock).mockResolvedValue({
      data: {
        'Time Series (Daily)': {
          '2025-08-16': { '4. close': '90' },
          '2025-08-15': { '4. close': '100' },
          // ... add more data to create a crossover
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
    expect(trades[0].tradeType).toBe('sell');
  });
});
