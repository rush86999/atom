import React from 'react';
interface DocTypeFilterProps {
    selectedTypes: string[];
    onChange: (selected: string[]) => void;
}
declare const DocTypeFilter: React.FC<DocTypeFilterProps>;
export default DocTypeFilter;
