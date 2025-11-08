import React from 'react';
import { Box, VStack, Text, Button } from '@chakra-ui/react';
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
    <Box p={4} border="1px" borderColor="gray.200" borderRadius="md">
      <VStack spacing={4} align="stretch">
        <Text fontSize="lg" fontWeight="bold">
          HubSpot Integration Test
        </Text>
        <Text fontSize="sm" color="gray.600">
          This component tests the HubSpotSearch functionality with mock data.
        </Text>

        <HubSpotSearch
          data={testContacts}
          dataType="contacts"
          onSearch={handleSearch}
          loading={false}
          totalCount={testContacts.length}
        />

        <Button
          colorScheme="blue"
          size="sm"
          onClick={() => console.log('Test button clicked')}
        >
          Test Button
        </Button>
      </VStack>
    </Box>
  );
};

export default HubSpotTest;
