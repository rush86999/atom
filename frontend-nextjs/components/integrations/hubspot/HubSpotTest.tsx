import React from 'react';
import { Button } from '@/components/ui/button';
import HubSpotSearch from './HubSpotSearch';

// Simple test data
const testContacts = [
  {
    id: 'test-1',
    firstName: 'Test',
    lastName: 'User',
    email: 'test@example.com',
    company: 'Test Corp',
    phone: '+1-555-0001',
    lifecycleStage: 'Lead',
    leadStatus: 'Active',
    leadScore: 50,
    lastActivityDate: '2024-01-15',
    createdDate: '2024-01-10',
    owner: 'Test Owner',
    industry: 'Technology',
    country: 'United States',
  },
];

const HubSpotTest: React.FC = () => {
  const handleSearch = (results: any[], filters: any, sort: any) => {
    console.log('Test search results:', results);
    console.log('Test filters:', filters);
    console.log('Test sort:', sort);
  };

  return (
    <div className="p-4 border border-gray-200 rounded-md">
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold text-gray-900">
            HubSpot Integration Test
          </h3>
          <p className="text-sm text-gray-600 mt-1">
            This component tests the HubSpotSearch functionality with mock data.
          </p>
        </div>

        <HubSpotSearch
          data={testContacts}
          dataType="contacts"
          onSearch={handleSearch}
          loading={false}
          totalCount={testContacts.length}
        />

        <Button
          variant="default"
          size="sm"
          onClick={() => console.log('Test button clicked')}
        >
          Test Button
        </Button>
      </div>
    </div>
  );
};

export default HubSpotTest;

