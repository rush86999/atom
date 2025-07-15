import React, { useState } from 'react';
import { Button } from '../chat/ui/button'; // Assuming button is available
import { IconPlus, IconTrash } from '../chat/ui/icons'; // Assuming icons are available

interface MetadataFilterProps {
  properties: Record<string, string>;
  onChange: (properties: Record<string, string>) => void;
}

const MetadataFilter: React.FC<MetadataFilterProps> = ({ properties, onChange }) => {
  // Convert the properties object into an array of {key, value} for easier mapping
  const propertyArray = Object.entries(properties).map(([key, value]) => ({ key, value }));

  const handlePropertyChange = (index: number, field: 'key' | 'value', newValue: string) => {
    const newArray = [...propertyArray];
    newArray[index] = { ...newArray[index], [field]: newValue };

    // Convert back to an object, ensuring no empty keys which can be problematic
    const newProperties = newArray.reduce((acc, prop) => {
      if (prop.key.trim()) {
        acc[prop.key.trim()] = prop.value;
      }
      return acc;
    }, {} as Record<string, string>);

    onChange(newProperties);
  };

  const handleAddProperty = () => {
    // Add a new empty property, which will be finalized on input change
    const newProperties = { ...properties, '': '' };
    onChange(newProperties);
  };

  const handleRemoveProperty = (keyToRemove: string) => {
    const newProperties = { ...properties };
    delete newProperties[keyToRemove];
    onChange(newProperties);
  };

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        Filter by Metadata
      </label>
      <div className="space-y-2 p-2 border rounded-md bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600">
        {propertyArray.map((prop, index) => (
          <div key={index} className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Property Key (e.g., author)"
              value={prop.key}
              onChange={(e) => handlePropertyChange(index, 'key', e.target.value)}
              className="flex-1 text-sm rounded-md border-gray-300 dark:border-gray-500 dark:bg-gray-600 dark:text-white shadow-sm focus:border-sky-500 focus:ring-sky-500"
            />
            <input
              type="text"
              placeholder="Property Value"
              value={prop.value}
              onChange={(e) => handlePropertyChange(index, 'value', e.target.value)}
              className="flex-1 text-sm rounded-md border-gray-300 dark:border-gray-500 dark:bg-gray-600 dark:text-white shadow-sm focus:border-sky-500 focus:ring-sky-500"
            />
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-gray-500 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/50 dark:hover:text-red-400"
              onClick={() => handleRemoveProperty(prop.key)}
            >
              <IconTrash className="h-4 w-4" />
            </Button>
          </div>
        ))}
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={handleAddProperty}
        >
          <IconPlus className="mr-1 h-4 w-4" />
          Add Property
        </Button>
      </div>
    </div>
  );
};

export default MetadataFilter;
