import React from 'react';
type DateField = 'ingested_at' | 'created_at_source' | 'last_modified_source';
interface DateRangeFilterProps {
    filters: {
        date_after?: string;
        date_before?: string;
        date_field_to_filter?: DateField;
    };
    onChange: (update: {
        date_after?: string;
        date_before?: string;
        date_field_to_filter?: DateField;
    }) => void;
}
declare const DateRangeFilter: React.FC<DateRangeFilterProps>;
export default DateRangeFilter;
