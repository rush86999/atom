import React from 'react';
interface MetadataFilterProps {
    properties: Record<string, string>;
    onChange: (properties: Record<string, string>) => void;
}
declare const MetadataFilter: React.FC<MetadataFilterProps>;
export default MetadataFilter;
