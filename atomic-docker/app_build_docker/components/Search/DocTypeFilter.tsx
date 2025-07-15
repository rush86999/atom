import React from 'react';

// A hardcoded list of document types. In a real app, this might come from a config file.
const DOCUMENT_TYPES = [
  { value: 'gdrive_pdf', label: 'Google Drive PDF' },
  { value: 'gdrive_docx', label: 'Google Drive Doc' },
  { value: 'gdrive_sheet', label: 'Google Drive Sheet' },
  { value: 'gdrive_slide', label: 'Google Drive Slide' },
  { value: 'email_snippet', label: 'Email' },
  { value: 'notion_summary', label: 'Notion Page' },
  { value: 'document_chunk', label: 'Uploaded Document' },
  { value: 'upload_html', label: 'HTML File' },
];

interface DocTypeFilterProps {
  selectedTypes: string[];
  onChange: (selected: string[]) => void;
}

const DocTypeFilter: React.FC<DocTypeFilterProps> = ({ selectedTypes, onChange }) => {

  const handleCheckboxChange = (typeValue: string) => {
    const newSelectedTypes = selectedTypes.includes(typeValue)
      ? selectedTypes.filter(t => t !== typeValue)
      : [...selectedTypes, typeValue];
    onChange(newSelectedTypes);
  };

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        Document Types
      </label>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 p-2 border rounded-md bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600">
        {DOCUMENT_TYPES.map(docType => (
          <label key={docType.value} className="flex items-center space-x-2 text-sm text-gray-800 dark:text-gray-200">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
              checked={selectedTypes.includes(docType.value)}
              onChange={() => handleCheckboxChange(docType.value)}
            />
            <span>{docType.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
};

export default DocTypeFilter;
