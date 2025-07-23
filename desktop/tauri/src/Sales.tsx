import React, { useEffect, useCallback } from "react";
import { useDataFetching } from "./hooks/useDataFetching";

// Define TypeScript interfaces for better type safety and code clarity
interface Opportunity {
  id: string;
  name: string;
  stage: string;
  value: number;
}

interface Contact {
  id: string;
  name: string;
  opportunityId: string;
}

interface Task {
  id: string;
  description: string;
  dueDate: string;
}

interface SalesData {
  opportunities: Opportunity[];
  contacts: Contact[];
  tasks: Task[];
}

/**
 * Sales component for the desktop application.
 * Displays sales-related information like opportunities, contacts, and tasks.
 */
const Sales: React.FC = () => {
  const {
    data: salesData,
    loading,
    error,
    fetchData,
  } = useDataFetching<SalesData>();

  // Function to simulate fetching data from a CRM API
  const fetchSalesData = useCallback(() => {
    const dataFetcher = () =>
      new Promise<SalesData>((resolve) => {
        setTimeout(() => {
          // In a real desktop app, this might come from a local database or a backend service.
          const mockDesktopCrmData: SalesData = {
            opportunities: [
              {
                id: "opp1",
                name: "Desktop Synergy Corp Website Revamp",
                stage: "Qualification",
                value: 125000,
              },
              {
                id: "opp2",
                name: "Desktop Quantum Solutions Cloud Migration",
                stage: "Proposal",
                value: 355000,
              },
              {
                id: "opp3",
                name: "Desktop Innovate LLC AI Chatbot",
                stage: "Negotiation",
                value: 80000,
              },
            ],
            contacts: [
              {
                id: "cont1",
                name: "Laura Chen (Desktop)",
                opportunityId: "opp1",
              },
              {
                id: "cont2",
                name: "David Rodriguez (Desktop)",
                opportunityId: "opp2",
              },
              {
                id: "cont3",
                name: "Samantha Williams (Desktop)",
                opportunityId: "opp3",
              },
            ],
            tasks: [
              {
                id: "task1",
                description:
                  "Schedule desktop discovery call with Synergy Corp",
                dueDate: "2024-08-06",
              },
              {
                id: "task2",
                description: "Finalize desktop proposal for Quantum Solutions",
                dueDate: "2024-08-11",
              },
              {
                id: "task3",
                description: "Send updated desktop contract to Innovate LLC",
                dueDate: "2024-07-31",
              },
            ],
          };
          resolve(mockDesktopCrmData);
        }, 1000); // 1-second delay
      });
    fetchData(dataFetcher);
  }, [fetchData]);

  // Fetch data when the component first mounts
  useEffect(() => {
    fetchSalesData();
  }, [fetchSalesData]);

  if (loading && !salesData) {
    // Show initial loading spinner
    return (
      <div className="sales-container" style={{ padding: "20px" }}>
        Loading sales data...
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="sales-container"
        style={{ padding: "20px", color: "red" }}
      >
        Error: {error.message}
      </div>
    );
  }

  return (
    <div
      className="sales-container"
      style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Sales Meeting Assistant (Desktop)</h1>
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

export default Sales;
