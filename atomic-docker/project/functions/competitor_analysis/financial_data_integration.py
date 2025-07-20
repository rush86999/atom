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
        "financials": stock.financials,
        "balance_sheet": stock.balance_sheet,
        "cashflow": stock.cashflow,
    }
