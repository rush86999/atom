import React, { useEffect, useCallback } from "react";
import { useDataFetching } from "./hooks/useDataFetching";

// Define TypeScript interfaces for our data structures for type safety.
interface Account {
  id: string;
  account_name: string;
  account_type: string;
  balance: number;
}

interface Holding {
    id: string;
    ticker: string;
    shares: number;
    purchase_price: number;
    current_price: number;
}

interface Investment {
  id: string;
  investment_name: string;
  investment_type: string;
  holdings: Holding[];
}

interface FinanceData {
  netWorth: number;
  accounts: Account[];
  investments: Investment[];
}

/**
 * Finance component for the desktop application.
 * It fetches financial data and displays it in a dashboard format.
 */
const Finance: React.FC = () => {
  const {
    data: financeData,
    loading,
    error,
    fetchData,
  } = useDataFetching<FinanceData>();

  // Function to fetch data from the finance API.
  const fetchFinanceData = useCallback(() => {
    const dataFetcher = async () => {
        const netWorthResponse = await fetch("/api/financial-calculations/net-worth?user_id=test_user");
        const netWorthData = await netWorthResponse.json();

        const accountsResponse = await fetch("/api/accounts?user_id=test_user");
        const accountsData = await accountsResponse.json();

        const investmentsResponse = await fetch("/api/investments?user_id=test_user");
        const investmentsData = await investmentsResponse.json();

        return {
            netWorth: netWorthData.data.net_worth,
            accounts: accountsData.data,
            investments: investmentsData.data
        }
    }
    fetchData(dataFetcher);
  }, [fetchData]);

  // Fetch data when the component first mounts.
  useEffect(() => {
    fetchFinanceData();
  }, [fetchFinanceData]);

  if (loading && !financeData) {
    return <div style={{ padding: "20px" }}>Loading financial data...</div>;
  }

  if (error) {
    return (
      <div style={{ padding: "20px", color: "red" }}>
        Error: {error.message}
      </div>
    );
  }

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Financial Overview (Desktop)</h1>
        <button
          onClick={() => fetchFinanceData()}
          disabled={loading}
          style={{ padding: "10px 15px", cursor: "pointer" }}
        >
          {loading ? "Refreshing..." : "Refresh Data"}
        </button>
      </div>

      {financeData ? (
        <div>
          {/* Net Worth Section */}
          <div style={{ marginBottom: "30px" }}>
            <h2>
              Net Worth: ${financeData.netWorth.toFixed(2)}
            </h2>
          </div>

          {/* Accounts Section */}
          <div style={{ marginBottom: "30px" }}>
            <h3>Accounts</h3>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {financeData.accounts.map((account) => (
                <li
                  key={account.id}
                  style={{ borderBottom: "1px solid #eee", padding: "10px 0" }}
                >
                  <strong>{account.account_name}</strong> - {account.account_type} (${account.balance.toFixed(2)})
                </li>
              ))}
            </ul>
          </div>

          {/* Investments Section */}
          <div style={{ marginBottom: "30px" }}>
            <h3>Investments</h3>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {financeData.investments.map((investment) => (
                <li
                  key={investment.id}
                  style={{ borderBottom: "1px solid #eee", padding: "10px 0" }}
                >
                  <strong>{investment.investment_name}</strong> - {investment.investment_type}
                  <ul>
                    {investment.holdings.map((holding) => (
                        <li key={holding.id}>
                            {holding.ticker}: {holding.shares} shares @ ${holding.current_price.toFixed(2)} = ${(holding.shares * holding.current_price).toFixed(2)}
                        </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <p>No financial data available. Click "Refresh Data" to load.</p>
      )}
    </div>
  );
};

export default Finance;
