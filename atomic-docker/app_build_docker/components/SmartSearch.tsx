import React, { useState } from "react";
import { Input, Button, Box, Heading, Text, Link } from "@chakra-ui/react";

const SmartSearch = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);

  const handleSearch = async () => {
    const res = await fetch(`/api/smart-search?query=${query}`);
    const data = await res.json();
    setResults(data);
  };

  return (
    <Box>
      <Heading>Smart Search</Heading>
      <Text>Search across all agent skills.</Text>
      <Input
        placeholder="Enter your search query"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <Button mt={4} onClick={handleSearch}>
        Search
      </Button>
      <Box mt={4}>
        <Heading size="md">Results</Heading>
        {results.map((result) => (
          <Box key={result.skill} mt={2}>
            <Link href={result.url}>
              <Text fontWeight="bold">{result.skill}</Text>
              <Text>{result.title}</Text>
            </Link>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

export default SmartSearch;
