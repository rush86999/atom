import { ReactNode } from "react";
export interface Article {
    id: string;
    title: string;
    content: string;
    category: "HR" | "IT" | "Engineering";
    lastUpdated: string;
}
interface SupportContextType {
    articles: Article[];
    loading: boolean;
    error: Error | null;
    searchArticles: (query: string) => Promise<void>;
}
/**
 * Custom hook to access the SupportContext.
 * Ensures that the context is used within a SupportProvider.
 */
export declare const useSupport: () => SupportContextType;
/**
 * Provider component that wraps parts of the application to provide
 * state management for the internal support agent feature.
 */
export declare const SupportProvider: ({ children }: {
    children: ReactNode;
}) => JSX.Element;
export {};
