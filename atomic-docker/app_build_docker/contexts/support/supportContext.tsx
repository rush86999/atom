import React, {
  createContext,
  useContext,
  ReactNode,
  useCallback,
} from "react";
import { useDataFetching } from "../../lib/hooks/useDataFetching";

// Define the structure for a knowledge base article, matching the API response.
export interface Article {
  id: string;
  title: string;
  content: string;
  category: "HR" | "IT" | "Engineering";
  lastUpdated: string;
}

// Define the shape of the context data.
interface SupportContextType {
  articles: Article[];
  loading: boolean;
  error: Error | null;
  searchArticles: (query: string) => Promise<void>;
}

// Create the context with a default undefined value.
const SupportContext = createContext<SupportContextType | undefined>(undefined);

/**
 * Custom hook to access the SupportContext.
 * Ensures that the context is used within a SupportProvider.
 */
export const useSupport = () => {
  const context = useContext(SupportContext);
  if (!context) {
    throw new Error("useSupport must be used within a SupportProvider");
  }
  return context;
};

/**
 * Provider component that wraps parts of the application to provide
 * state management for the internal support agent feature.
 */
export const SupportProvider = ({ children }: { children: ReactNode }) => {
  const {
    data: articles,
    loading,
    error,
    fetchData,
  } = useDataFetching<Article[]>();

  /**
   * Fetches articles from the knowledge base API based on a search query.
   */
  const searchArticles = useCallback(
    async (query: string) => {
      const encodedQuery = encodeURIComponent(query);
      await fetchData(`/api/support/knowledge-base?q=${encodedQuery}`);
    },
    [fetchData],
  );

  const value = {
    articles: articles || [], // Ensure articles is never null
    loading,
    error,
    searchArticles,
  };

  return (
    <SupportContext.Provider value={value}>{children}</SupportContext.Provider>
  );
};
