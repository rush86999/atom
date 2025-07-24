import React, { useEffect } from "react";
import {
  useFinance,
  FinanceProvider,
} from "../../contexts/finance/financeContext";
import FeaturePageGuard from "../../lib/components/FeaturePageGuard";

/**
 * The main content component for the Finance page.
 * It handles fetching, displaying, and refreshing financial data,
 * and ensures the user has the correct role to view the content.
 */
const FinancePageContent = () => {
  const { financeData, loading, error, fetchFinanceData } = useFinance();

  useEffect(() => {
    // Fetch data when the component mounts.
    fetchFinanceData();
  }, [fetchFinanceData]);

  // Show a loading message while fetching data.
  if (loading && !financeData) {
    return <div>Loading financial data...</div>;
  }

  // Show an error message if fetching fails.
  if (error) {
    return <div>Error: {error.message}</div>;
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
        <h1>Financial Overview</h1>
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

/**
 * The main Finance page component.
 * It wraps the page content with the FinanceProvider to ensure
 * the context is available to all child components.
 */
const FinancePage = () => (
  <FeaturePageGuard
    role="financial_analyst"
    roleName="Financial Analyst Agent Skill"
  >
    <FinanceProvider>
      <FinancePageContent />
    </FinanceProvider>
  </FeaturePageGuard>
);

export default FinancePage;
