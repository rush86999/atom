import React, { useState } from 'react';
import { useMutation, gql } from '@apollo/client';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import TextField from '@components/TextField';
import { ActivityIndicator, FlatList, View, StyleSheet } from 'react-native';
import { palette } from '@lib/theme/theme';
import { useToast } from '@chakra-ui/react';
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node';
import Session from 'supertokens-node/recipe/session';
import { backendConfig } from '@config/backendConfig';

// getServerSideProps for session validation (standard for pages needing auth)
export async function getServerSideProps({ req, res }: { req: NextApiRequest, res: NextApiResponse }) {
  supertokensNode.init(backendConfig());
  let session;
  try {
    session = await Session.getSession(req, res, {
      overrideGlobalClaimValidators: async () => [],
    });
  } catch (err: any) {
    if (err.type === Session.Error.TRY_REFRESH_TOKEN) {
      return { props: { fromSupertokens: 'needs-refresh' } };
    } else if (err.type === Session.Error.UNAUTHORISED) {
      return { props: { fromSupertokens: 'needs-refresh' } }; // Will force frontend to redirect to login
    }
    throw err;
  }

  if (!session?.getUserId()) {
    return {
      redirect: {
        destination: '/User/Login/UserLogin', // Adjust to your login path
        permanent: false,
      },
    };
  }
  return { props: { userId: session.getUserId() } }; // Pass userId if needed, or just let page render
}


const SEARCH_USER_GMAIL_MUTATION = gql`
  mutation SearchUserGmail($input: GmailSearchQueryInput!) {
    searchUserGmail(input: $input) {
      success
      message
      results {
        id
        threadId
        snippet
        subject
        from
        date
      }
    }
  }
`;

interface GmailSearchResultItemFE {
  id: string;
  threadId?: string | null;
  snippet?: string | null;
  subject?: string | null;
  from?: string | null;
  date?: string | null;
}

const UserGmailSearchPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<GmailSearchResultItemFE[]>([]);
  const toast = useToast();

  const [searchGmailMutation, { loading, error }] = useMutation(SEARCH_USER_GMAIL_MUTATION, {
    onCompleted: (data) => {
      if (data.searchUserGmail.success) {
        const results = data.searchUserGmail.results || [];
        setSearchResults(results);
        if (results.length === 0 && searchQuery.trim() !== '') { // Only show no results if a search was made
          toast({
            title: 'No Results',
            description: 'Your search did not return any emails.',
            status: 'info',
            duration: 3000,
            isClosable: true,
          });
        }
      } else {
        toast({
          title: 'Search Failed',
          description: data.searchUserGmail.message || 'An error occurred during the search.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        setSearchResults([]);
      }
    },
    onError: (err) => {
      toast({
        title: 'Search Error',
        description: err.message || 'An unexpected error occurred.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setSearchResults([]);
    },
  });

  const handleSearch = () => {
    if (searchQuery.trim() === '') {
      toast({
        title: 'Empty Search Query',
        description: 'Please enter a search query.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }
    setSearchResults([]); // Clear previous results before new search
    searchGmailMutation({ variables: { input: { query: searchQuery, maxResults: 20 } } });
  };

  const renderItem = ({ item }: { item: GmailSearchResultItemFE }) => (
    <View style={styles.itemContainer}>
      <Text style={styles.itemTextStrong}>ID: {item.id}</Text>
      {item.threadId && <Text style={styles.itemText}>Thread ID: {item.threadId}</Text>}
      {item.snippet && <Text style={styles.itemText}>Snippet: {item.snippet}</Text>}
      {item.subject && <Text style={styles.itemText}>Subject: {item.subject}</Text>}
      {item.from && <Text style={styles.itemText}>From: {item.from}</Text>}
      {item.date && <Text style={styles.itemText}>Date: {item.date}</Text>}
    </View>
  );

  return (
    <Box flex={1} p="m" alignItems="center" backgroundColor="primaryCardBackground" style={styles.pageContainer}>
      <Text variant="header" mb="l" style={styles.headerText}>Search Your Gmail</Text>

      <Box width="100%" maxWidth={600} mb="m">
        <TextField
          placeholder="e.g., from:name@example.com subject:contract"
          value={searchQuery}
          onChangeText={setSearchQuery}
          // Consider adding a specific style or ensuring TextField fits theme
        />
      </Box>

      <Button label="Search Emails" onClick={handleSearch} disabled={loading}
        // Ensure Button component takes simple label or children
      />

      {loading && <ActivityIndicator size="large" color={palette.primary} style={styles.activityIndicator} />}

      {error && (
        <Text color="error" mt="m" style={styles.errorText}>
          Error: {error.message}
        </Text>
      )}

      {!loading && searchResults.length > 0 && (
        <FlatList
          data={searchResults}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          style={styles.listStyle}
        />
      )}
       {!loading && !error && searchResults.length === 0 && searchQuery !== '' && !loading && (
         <Text mt="m" style={styles.itemText}>No results found for your query.</Text>
       )}
    </Box>
  );
};

const styles = StyleSheet.create({
  pageContainer: {
    paddingTop: 20, // Add some padding at the top
  },
  headerText: {
    color: palette.text, // Example, adjust to your theme
  },
  itemContainer: {
    padding: 15,
    borderBottomWidth: 1,
    borderBottomColor: palette.mediumGray, // Use theme color
    backgroundColor: palette.white, // Example item background
    borderRadius: 5,
    marginVertical: 5,
  },
  itemText: {
    fontSize: 14,
    color: palette.text, // Example text color
  },
  itemTextStrong: {
    fontSize: 14,
    fontWeight: 'bold',
    color: palette.text,
  },
  activityIndicator: {
    marginTop: 20,
  },
  errorText: {
    fontSize: 14,
  },
  listStyle: {
    width: '100%',
    maxWidth: 600,
    marginTop: 20,
  }
});

export default UserGmailSearchPage;
