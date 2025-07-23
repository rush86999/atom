import React, {
  createContext,
  useContext,
  ReactNode,
  useCallback,
} from "react";
import { useDataFetching } from "../../lib/hooks/useDataFetching";

// Define TypeScript interfaces for our data structures for type safety.
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

// Define the shape of the context data
interface SalesContextType {
  salesData: SalesData | null;
  loading: boolean;
  error: Error | null;
  fetchSalesData: () => Promise<void>;
}

// Create the context with a default value
const SalesContext = createContext<SalesContextType | undefined>(undefined);

// Custom hook to use the SalesContext
export const useSales = () => {
  const context = useContext(SalesContext);
  if (!context) {
    throw new Error("useSales must be used within a SalesProvider");
  }
  return context;
};

// Create the provider component
export const SalesProvider = ({ children }: { children: ReactNode }) => {
  const {
    data: salesData,
    loading,
    error,
    fetchData,
  } = useDataFetching<SalesData>();

  // Function to fetch data from the CRM API, memoized with useCallback.
  const fetchSalesData = useCallback(async () => {
    await fetchData("/api/crm/data");
  }, [fetchData]);

  const value = {
    salesData,
    loading,
    error,
    fetchSalesData,
  };

  return (
    <SalesContext.Provider value={value}>{children}</SalesContext.Provider>
  );
};
