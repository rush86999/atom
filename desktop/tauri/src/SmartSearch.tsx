import React, { useState } from "react";
import { invoke } from "@tauri-apps/api/tauri";

const SmartSearch = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);

  const handleSearch = async () => {
    const data = await invoke("smart_search", { query });
    setResults(data);
  };

  return (
    <div>
      <h2>Smart Search</h2>
      <p>Search across all agent skills.</p>
      <input
        type="text"
        placeholder="Enter your search query"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <button onClick={handleSearch}>Search</button>
      <div>
        <h3>Results</h3>
        {results.map((result) => (
          <div key={result.skill}>
            <a href={result.url}>
              <b>{result.skill}</b>
              <p>{result.title}</p>
            </a>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SmartSearch;
