import React from 'react';
import { HybridSearchFilters } from '../../../lib/dataTypes/SearchResultsTypes'; // Adjust path if needed

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

const DateRangeFilter: React.FC<DateRangeFilterProps> = ({ filters, onChange }) => {

  const handleDateChange = (field: 'date_after' | 'date_before', value: string) => {
    // If the date is cleared, pass undefined to remove it from the filter state
    const dateValue = value ? new Date(value).toISOString() : undefined;
    onChange({ [field]: dateValue });
  };

  const handleFieldChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ date_field_to_filter: e.target.value as DateField });
  };

  // Helper to format ISO string to YYYY-MM-DD for the date input value
  const getInputValue = (isoString?: string) => {
    if (!isoString) return '';
    try {
      return isoString.split('T')[0];
    } catch {
      return '';
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        Filter by Date
      </label>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-2 border rounded-md bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600">
        {/* Date Field Selector */}
        <div>
          <label htmlFor="date_field_select" className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Date Type
          </label>
          <select
            id="date_field_select"
            value={filters.date_field_to_filter || 'ingested_at'}
            onChange={handleFieldChange}
            className="block w-full text-sm rounded-md border-gray-300 dark:border-gray-500 dark:bg-gray-600 dark:text-white shadow-sm focus:border-sky-500 focus:ring-sky-500"
          >
            <option value="ingested_at">Ingested Date</option>
            <option value="created_at_source">Creation Date</option>
            <option value="last_modified_source">Modified Date</option>
          </select>
        </div>

        {/* Date After */}
        <div>
          <label htmlFor="date_after" className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            From
          </label>
          <input
            type="date"
            id="date_after"
            value={getInputValue(filters.date_after)}
            onChange={(e) => handleDateChange('date_after', e.target.value)}
            className="block w-full text-sm rounded-md border-gray-300 dark:border-gray-500 dark:bg-gray-600 dark:text-white shadow-sm focus:border-sky-500 focus:ring-sky-500"
          />
        </div>

        {/* Date Before */}
        <div>
          <label htmlFor="date_before" className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            To
          </label>
          <input
            type="date"
            id="date_before"
            value={getInputValue(filters.date_before)}
            onChange={(e) => handleDateChange('date_before', e.target.value)}
            className="block w-full text-sm rounded-md border-gray-300 dark:border-gray-500 dark:bg-gray-600 dark:text-white shadow-sm focus:border-sky-500 focus:ring-sky-500"
          />
        </div>
      </div>
    </div>
  );
};

export default DateRangeFilter;
