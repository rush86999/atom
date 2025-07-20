import yfinance as yf

def get_financial_data(ticker):
    """
    Gets financial data for a ticker.

    Args:
        ticker: The ticker symbol of the company.

    Returns:
        A dictionary containing the financial data.
    """
    if not ticker:
        return {
            "info": {
                "marketCap": "N/A",
                "enterpriseValue": "N/A",
                "trailingPE": "N/A",
                "forwardPE": "N/A",
                "pegRatio": "N/A",
            }
        }
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
    except Exception as e:
        print(f"Error getting financial data: {e}")
        return {
            "info": {
                "marketCap": "N/A",
                "enterpriseValue": "N/A",
                "trailingPE": "N/A",
                "forwardPE": "N/A",
                "pegRatio": "N/A",
            }
        }

    return {
        "info": {
            "marketCap": info.get("marketCap", "N/A"),
            "enterpriseValue": info.get("enterpriseValue", "N/A"),
            "trailingPE": info.get("trailingPE", "N/A"),
            "forwardPE": info.get("forwardPE", "N/A"),
            "pegRatio": info.get("pegRatio", "N/A"),
        }
    }
