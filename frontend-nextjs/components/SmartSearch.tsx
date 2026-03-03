import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";

interface SearchResult {
    skill: string;
    title: string;
    url: string;
}

const SmartSearch: React.FC = () => {
    const [query, setQuery] = useState<string>("");
    const [results, setResults] = useState<SearchResult[]>([]);

    const handleSearch = async () => {
        const res = await fetch(`/api/smart-search?query=${query}`);
        const data = await res.json();
        setResults(data);
    };

    return (
        <div className="space-y-4">
            <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Smart Search</h2>
                <p className="text-gray-600 dark:text-gray-400 mt-1">Search across all agent skills.</p>
            </div>

            <div className="flex gap-2">
                <Input
                    placeholder="Enter your search query"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="flex-1"
                />
                <Button onClick={handleSearch}>
                    Search
                </Button>
            </div>

            {results.length > 0 && (
                <div className="mt-6">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Results</h3>
                    <div className="space-y-2">
                        {results.map((result) => (
                            <Link
                                key={result.skill}
                                href={result.url}
                                className="block p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-500 hover:bg-blue-50 transition-colors"
                            >
                                <p className="font-semibold text-gray-900 dark:text-gray-100">{result.skill}</p>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{result.title}</p>
                            </Link>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default SmartSearch;
