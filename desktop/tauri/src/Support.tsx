import React, { useState, useEffect, useCallback } from "react";
import { useDataFetching } from "./hooks/useDataFetching";

// Define the structure for a knowledge base article
export interface Article {
  id: string;
  title: string;
  content: string;
  category: "HR" | "IT" | "Engineering";
  lastUpdated: string;
}

// Mock data representing a company's internal knowledge base for the desktop app
const allArticles: Article[] = [
  {
    id: "kb-d-1",
    title: "Desktop: How to Set Up Your VPN",
    content:
      "To set up your VPN on a desktop, please download the GlobalProtect client from the IT portal.",
    category: "IT",
    lastUpdated: "2024-06-18",
  },
  {
    id: "kb-d-2",
    title: "Desktop: Submitting Expense Reports",
    content:
      'All expense reports for desktop users must be submitted through the "Expenses" web portal.',
    category: "HR",
    lastUpdated: "2024-07-05",
  },
  {
    id: "kb-d-3",
    title: "Desktop: Requesting Time Off",
    content:
      "Paid time off (PTO) can be requested via the Workday portal. There is no separate desktop application for this.",
    category: "HR",
    lastUpdated: "2024-05-22",
  },
  {
    id: "kb-d-4",
    title: "Desktop: Git Branching Strategy",
    content:
      "Our standard Git branching strategy is GitFlow. Use your preferred Git client on your desktop.",
    category: "Engineering",
    lastUpdated: "2024-07-28",
  },
];

/**
 * A single article component for displaying search results.
 */
const ArticleCard = ({ article }: { article: Article }) => (
  <div
    style={{
      border: "1px solid #ddd",
      borderRadius: "8px",
      padding: "16px",
      marginBottom: "16px",
      backgroundColor: "#f9f9f9",
    }}
  >
    <h3 style={{ marginTop: 0 }}>{article.title}</h3>
    <p>{article.content}</p>
    <div style={{ fontSize: "0.9em", color: "#555" }}>
      <span style={{ fontWeight: "bold" }}>Category:</span> {article.category} |{" "}
      <span style={{ fontWeight: "bold" }}>Last Updated:</span>{" "}
      {article.lastUpdated}
    </div>
  </div>
);

/**
 * Internal Support Agent component for the desktop application.
 * It provides a searchable interface for a mock knowledge base.
 */
const Support: React.FC = () => {
  const {
    data: articles,
    loading,
    error,
    fetchData,
  } = useDataFetching<Article[]>();
  const [query, setQuery] = useState("");

  // Function to simulate searching for articles.
  const searchArticles = useCallback(
    (searchTerm: string) => {
      const dataFetcher = () =>
        new Promise<Article[]>((resolve) => {
          setTimeout(() => {
            try {
              if (!searchTerm) {
                resolve(allArticles);
              } else {
                const lowercasedQuery = searchTerm.toLowerCase();
                const results = allArticles.filter(
                  (article) =>
                    article.title.toLowerCase().includes(lowercasedQuery) ||
                    article.content.toLowerCase().includes(lowercasedQuery),
                );
                resolve(results);
              }
            } catch (e) {
              // In a real app, you might reject the promise here.
              // For this simulation, we'll just resolve with an empty array on error.
              resolve([]);
            }
          }, 500); // 0.5-second delay
        });
      fetchData(dataFetcher);
    },
    [fetchData],
  );

  // Perform an initial search to show all articles when the component mounts.
  useEffect(() => {
    searchArticles("");
  }, [searchArticles]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    searchArticles(query);
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1>Internal Support Agent (Desktop)</h1>
      <p>Search the knowledge base for articles and solutions.</p>

      <form
        onSubmit={handleSearch}
        style={{ margin: "20px 0", display: "flex", gap: "10px" }}
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g., 'vpn'"
          style={{
            width: "300px",
            padding: "10px",
            fontSize: "1em",
            border: "1px solid #ccc",
            borderRadius: "4px",
          }}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: "10px 15px",
            cursor: "pointer",
            border: "none",
            backgroundColor: "purple",
            color: "white",
            borderRadius: "4px",
          }}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error && (
        <div style={{ color: "red", marginBottom: "20px" }}>
          Error: {error.message}
        </div>
      )}

      <div>
        {loading ? (
          <p>Loading articles...</p>
        ) : articles && articles.length > 0 ? (
          articles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))
        ) : (
          <p>
            No articles found. Try a different search term or an empty search to
            see all articles.
          </p>
        )}
      </div>
    </div>
  );
};

export default Support;
