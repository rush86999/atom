import React, { useEffect } from "react";
import { useSales, SalesProvider } from "../../contexts/sales/salesContext";
import FeaturePageGuard from "../../lib/components/FeaturePageGuard";

/**
 * The content for the Sales Meeting Assistant page.
 * This component is responsible for fetching and displaying sales data.
 * It assumes that role-based access has already been verified by a parent component.
 */
const SalesPageContent = () => {
  const { salesData, loading, error, fetchSalesData } = useSales();

  // Fetch sales data when the component mounts.
  useEffect(() => {
    fetchSalesData();
  }, [fetchSalesData]);

  if (loading) {
    return <div>Loading sales data...</div>;
  }

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
        <h1>Sales Meeting Assistant</h1>
        <button
          onClick={() => fetchSalesData()}
          disabled={loading}
          style={{ padding: "10px 15px", cursor: "pointer" }}
        >
          {loading ? "Refreshing..." : "Refresh Data"}
        </button>
      </div>
      {salesData ? (
        <>
          <h2>Upcoming Opportunities</h2>
          <ul>
            {salesData.opportunities.map((opp) => (
              <li key={opp.id}>
                <strong>{opp.name}</strong> - {opp.stage} ($
                {opp.value.toLocaleString()})
              </li>
            ))}
          </ul>

          <h2>Key Contacts</h2>
          <ul>
            {salesData.contacts.map((contact) => (
              <li key={contact.id}>{contact.name}</li>
            ))}
          </ul>

          <h2>Pending Tasks</h2>
          <ul>
            {salesData.tasks.map((task) => (
              <li key={task.id}>
                {task.description} (Due: {task.dueDate})
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p>No sales data available. Click "Refresh Data" to load.</p>
      )}
    </div>
  );
};

/**
 * The main Sales page component.
 * It uses the FeaturePageGuard to protect the route and wraps the page content
 * with the SalesProvider to provide the necessary context.
 */
const SalesPage = () => (
  <FeaturePageGuard role="sales" roleName="Sales Agent Skill">
    <SalesProvider>
      <SalesPageContent />
    </SalesProvider>
  </FeaturePageGuard>
);

export default SalesPage;
