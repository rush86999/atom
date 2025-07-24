import React, {
  createContext,
  useContext,
  ReactNode,
  useCallback,
} from "react";
import { useDataFetching } from "../../lib/hooks/useDataFetching";

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

// Define the shape of the context data
interface FinanceContextType {
  financeData: FinanceData | null;
  loading: boolean;
  error: Error | null;
  fetchFinanceData: () => Promise<void>;
}

// Create the context with a default value
const FinanceContext = createContext<FinanceContextType | undefined>(undefined);

// Custom hook to use the FinanceContext
export const useFinance = () => {
  const context = useContext(FinanceContext);
  if (!context) {
    throw new Error("useFinance must be used within a FinanceProvider");
  }
  return context;
};

// Create the provider component
export const FinanceProvider = ({ children }: { children: ReactNode }) => {
  const {
    data: financeData,
    loading,
    error,
    fetchData,
  } = useDataFetching<FinanceData>();

  // Function to fetch data from the finance API, memoized with useCallback.
  const fetchFinanceData = useCallback(async () => {
    // This will need to be updated to fetch from the correct endpoints
    // and combine the data.
    const netWorthData = await fetchData("/api/financial-calculations/net-worth");
    const accountsData = await fetchData("/api/accounts");
    const investmentsData = await fetchData("/api/investments");

    // This is a simplified combination of the data.
    // A real implementation would need to be more robust.
    const combinedData = {
        netWorth: netWorthData.net_worth,
        accounts: accountsData,
        investments: investmentsData
    }

    // This is a hack to get the data into the context.
    // A better solution would be to update the useDataFetching hook
    // to handle multiple fetches.
    // @ts-ignore
    fetchData(null, combinedData)

  }, [fetchData]);

  const value = {
    financeData,
    loading,
    error,
    fetchFinanceData,
  };

  return (
    <FinanceContext.Provider value={value}>{children}</FinanceContext.Provider>
  );
};
