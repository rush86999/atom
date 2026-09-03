import React, { useState } from 'react';

interface GmailSearchProps {
    data: any[];
    dataType: string;
    onSearch: (results: any[], filters: any, sort: any) => void;
    loading: boolean;
    totalCount: number;
    /** Items currently shown after filtering (defaults to data.length). */
    resultCount?: number;
}

const GmailSearch: React.FC<GmailSearchProps> = ({ data, dataType, onSearch, loading, totalCount, resultCount }) => {
    const [query, setQuery] = useState('');

    const handleSearchChange = (value: string) => {
        setQuery(value);
        const q = value.toLowerCase();
        const filtered = q
            ? data.filter((item) => {
                const fields =
                    dataType === 'contacts'
                        ? [item.name, item.email, item.company]
                        : [item.from, item.to, item.subject, item.preview];
                return fields.some(
                    (field) => typeof field === 'string' && field.toLowerCase().includes(q)
                );
            })
            : data;
        onSearch(filtered, { query: value, dataType }, {});
    };

    return (
        <div className="p-4">
            <div className="mb-4">
                <input
                    type="text"
                    placeholder={`Search ${dataType}...`}
                    value={query}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg"
                    disabled={loading}
                    data-testid="gmail-search-input"
                />
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">
                {loading ? 'Loading...' : `Showing ${resultCount ?? data.length} of ${totalCount} items`}
            </div>
        </div>
    );
};

export default GmailSearch;
