import React from 'react';

interface GmailSearchProps {
    data: any[];
    dataType: string;
    onSearch: (results: any[], filters: any, sort: any) => void;
    loading: boolean;
    totalCount: number;
}

const GmailSearch: React.FC<GmailSearchProps> = ({ data, dataType, onSearch, loading, totalCount }) => {
    return (
        <div className="p-4">
            <div className="mb-4">
                <input
                    type="text"
                    placeholder={`Search ${dataType}...`}
                    className="w-full px-3 py-2 border rounded-lg"
                    disabled={loading}
                />
            </div>
            <div className="text-sm text-gray-500">
                {loading ? 'Loading...' : `Showing ${data.length} of ${totalCount} items`}
            </div>
        </div>
    );
};

export default GmailSearch;
