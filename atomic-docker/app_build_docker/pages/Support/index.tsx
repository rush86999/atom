import React, { useState, useEffect } from "react";
import {
  useSupport,
  SupportProvider,
  Article,
} from "../../contexts/support/supportContext";
import FeaturePageGuard from "../../lib/components/FeaturePageGuard";

/**
 * A single article component for displaying search results.
 * It provides a clean, card-like interface for each article.
 */
const ArticleCard = ({ article }: { article: Article }) => {
  return (
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
        <span style={{ fontWeight: "bold" }}>Category:</span> {article.category}{" "}
        | <span style={{ fontWeight: "bold" }}>Last Updated:</span>{" "}
        {article.lastUpdated}
      </div>
    </div>
  );
};

/**
 * The main content component for the Internal Support Agent page.
 * It provides a search interface for the knowledge base and displays results.
 */
const SupportPageContent = () => {
  const { articles, loading, error, searchArticles } = useSupport();
  const [query, setQuery] = useState("");

  // On component mount, perform an initial empty search
  // to populate the page with all available articles.
  useEffect(() => {
    searchArticles("");
  }, [searchArticles]);

  // Handles the form submission for searching articles.
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    searchArticles(query);
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1>Internal Support Agent</h1>
      <p>
        Search the knowledge base for articles, guides, and solutions to common
        questions.
      </p>

      <form
        onSubmit={handleSearch}
        style={{ margin: "20px 0", display: "flex", gap: "10px" }}
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g., 'how to reset password'"
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
        ) : articles.length > 0 ? (
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

/**
 * The main Support page component.
 * It wraps the page content with the SupportProvider to ensure
 * the context is available to all child components.
 */
const SupportPage = () => (
  <FeaturePageGuard role="support" roleName="Support Agent Skill">
    <SupportProvider>
      <SupportPageContent />
    </SupportProvider>
  </FeaturePageGuard>
);

export default SupportPage;
