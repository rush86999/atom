import yfinance as yf

def get_financial_data(ticker):
    """
    Fetches financial data for a public company.

    Args:
        ticker: The ticker symbol of the company.

    Returns:
        A dictionary containing the financial data.
    """
    stock = yf.Ticker(ticker)

    return {
        "info": stock.info,
        "quarterly_financials": stock.quarterly_financials,
        "quarterly_balance_sheet": stock.quarterly_balance_sheet,
        "quarterly_cashflow": stock.quarterly_cashflow,
    }
