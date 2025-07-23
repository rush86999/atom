import React, { useState } from 'react';
import { useMutation, gql } from '@apollo/client';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import TextField from '@components/TextField';
import { ActivityIndicator, FlatList, View, StyleSheet, Pressable, Modal, ScrollView } from 'react-native';
import { palette } from '@lib/theme/theme';
import { useToast } from '@chakra-ui/react';
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node';
import Session from 'supertokens-node/recipe/session';
import { backendConfig } from '@config/backendConfig';

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
      return { props: { fromSupertokens: 'needs-refresh' } };
    }
    throw err;
  }

  if (!session?.getUserId()) {
    return {
      redirect: {
        destination: '/User/Login/UserLogin',
        permanent: false,
      },
    };
  }
  return { props: { userId: session.getUserId() } };
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

const CREATE_EMAIL_REMINDER_MUTATION = gql`
  mutation CreateEmailReminder($input: CreateEmailReminderInput!) {
    createEmailReminder(input: $input) {
      id
    }
  }
`;

const GET_USER_GMAIL_CONTENT_MUTATION = gql`
  mutation GetUserGmailContent($input: GetUserGmailContentInput!) {
    getUserGmailContent(input: $input) {
      success
      message
      email {
        id
        threadId
        snippet
        subject
        from
        date
        body
      }
    }
  }
`;

interface DetailedEmailContent {
  id: string;
  threadId?: string | null;
  subject?: string | null;
  from?: string | null;
  date?: string | null;
  body?: string | null;
  snippet?: string | null;
}

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

  const [selectedEmail, setSelectedEmail] = useState<DetailedEmailContent | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);
  const [showDetailModal, setShowDetailModal] = useState<boolean>(false);
  const [showReminderModal, setShowReminderModal] = useState<boolean>(false);
  const [reminderDate, setReminderDate] = useState(new Date());

  const [searchGmailMutation, { loading: searchLoading, error: searchError }] = useMutation(SEARCH_USER_GMAIL_MUTATION, {
    onCompleted: (data) => {
      if (data.searchUserGmail.success) {
        const results = data.searchUserGmail.results || [];
        setSearchResults(results);
        if (results.length === 0 && searchQuery.trim() !== '') {
          toast({
            title: 'No Search Results',
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

  const [
    getGmailContentMutation,
    { loading: detailFetchLoading, error: detailFetchError },
  ] = useMutation(GET_USER_GMAIL_CONTENT_MUTATION, {
    onCompleted: (data) => {
      setIsDetailLoading(false);
      if (data.getUserGmailContent.success && data.getUserGmailContent.email) {
        const emailData = data.getUserGmailContent.email;
        setSelectedEmail({
          id: emailData.id,
          threadId: emailData.threadId || null,
          subject: emailData.subject || null,
          from: emailData.from || null,
          date: emailData.date || null,
          body: emailData.body || null,
          snippet: emailData.snippet || null,
        });
      } else {
        toast({
          title: 'Error Fetching Email Details',
          description: data.getUserGmailContent.message || 'Could not load email details.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        setSelectedEmail(null);
        setShowDetailModal(false);
      }
    },
    onError: (err) => {
      setIsDetailLoading(false);
      toast({
        title: 'Error Fetching Email Details',
        description: err.message || 'An unexpected error occurred.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setSelectedEmail(null);
      setShowDetailModal(false);
    },
  });

  const [createEmailReminderMutation, { loading: reminderLoading, error: reminderError }] = useMutation(CREATE_EMAIL_REMINDER_MUTATION, {
    onCompleted: (data) => {
      if (data.createEmailReminder.id) {
        toast({
          title: 'Reminder Set',
          description: 'Your reminder has been set successfully.',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        setShowReminderModal(false);
      } else {
        toast({
          title: 'Failed to Set Reminder',
          description: 'An error occurred while setting the reminder.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    },
    onError: (err) => {
      toast({
        title: 'Reminder Error',
        description: err.message || 'An unexpected error occurred.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    },
  });

  const handleSetReminder = () => {
    if (selectedEmail) {
      createEmailReminderMutation({
        variables: {
          input: {
            emailId: selectedEmail.id,
            service: 'gmail',
            remindAt: reminderDate.toISOString(),
          },
        },
      });
    }
  };

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
    setShowDetailModal(false); // Close detail modal on new search
    setSelectedEmail(null);
    setSearchResults([]);
    searchGmailMutation({ variables: { input: { query: searchQuery, maxResults: 20 } } });
  };

  const handleViewDetails = (emailId: string) => {
    if (!emailId) return;
    setSelectedEmail(null);
    setIsDetailLoading(true);
    setShowDetailModal(true);
    getGmailContentMutation({ variables: { input: { emailId } } });
  };

  const renderItem = ({ item }: { item: GmailSearchResultItemFE }) => (
    <Pressable onPress={() => handleViewDetails(item.id)} style={styles.itemContainer}>
      <Text style={styles.itemTextStrong}>ID: {item.id}</Text>
      {item.snippet && <Text style={styles.itemText} numberOfLines={2}>Snippet: {item.snippet}</Text>}
      {item.subject && <Text style={styles.itemText}>Subject: {item.subject}</Text>}
      {item.from && <Text style={styles.itemText}>From: {item.from}</Text>}
      {item.date && <Text style={styles.itemText}>Date: {item.date}</Text>}
      <Text style={styles.viewDetailsLink}>View Details</Text>
    </Pressable>
  );

  return (
    <Box flex={1} p="m" alignItems="center" backgroundColor="primaryCardBackground" style={styles.pageContainer}>
      <Text variant="header" mb="l" style={styles.headerText}>Search Your Gmail</Text>

      <Box width="100%" maxWidth={600} mb="m">
        <TextField
          placeholder="e.g., from:name@example.com subject:contract"
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </Box>

      <Button label="Search Emails" onClick={handleSearch} disabled={searchLoading} />

      {searchLoading && <ActivityIndicator size="large" color={palette.primary} style={styles.activityIndicator} />}

      {searchError && (
        <Text color="error" mt="m" style={styles.errorText}>
          Error searching: {searchError.message}
        </Text>
      )}

      {!searchLoading && searchResults.length > 0 && (
        <FlatList
          data={searchResults}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          style={styles.listStyle}
        />
      )}
       {!searchLoading && !searchError && searchResults.length === 0 && searchQuery !== '' && (
         <Text mt="m" style={styles.itemText}>No results found for your query.</Text>
       )}

      {showDetailModal && (
        <Modal
          animationType="slide"
          transparent={true}
          visible={showDetailModal}
          onRequestClose={() => {
            setShowDetailModal(false);
            setSelectedEmail(null);
          }}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContainer}>
              <ScrollView>
                {isDetailLoading && <ActivityIndicator size="large" color={palette.primary} />}
                {detailFetchError && <Text color="error">Error loading details: {detailFetchError.message}</Text>}
                {selectedEmail && !isDetailLoading && (
                  <>
                    <Text style={styles.modalTitle}>Email Details</Text>
                    <Text style={styles.modalTextStrong}>ID:</Text>
                    <Text style={styles.modalText}>{selectedEmail.id}</Text>

                    <Text style={styles.modalTextStrong}>Subject:</Text>
                    <Text style={styles.modalText}>{selectedEmail.subject || 'N/A'}</Text>

                    <Text style={styles.modalTextStrong}>From:</Text>
                    <Text style={styles.modalText}>{selectedEmail.from || 'N/A'}</Text>

                    <Text style={styles.modalTextStrong}>Date:</Text>
                    <Text style={styles.modalText}>{selectedEmail.date || 'N/A'}</Text>

                    <Text style={styles.modalTextStrong}>Snippet:</Text>
                    <Text style={styles.modalText}>{selectedEmail.snippet || 'N/A'}</Text>

                    <Text style={styles.modalTextStrong}>Body:</Text>
                    <Text style={styles.modalTextBody}>{selectedEmail.body || '(No body content)'}</Text>
                  </>
                )}
              </ScrollView>
              <Button label="Remind me" onClick={() => setShowReminderModal(true)} />
              <Pressable
                style={styles.closeButton}
                onPress={() => {
                  setShowDetailModal(false);
                  setSelectedEmail(null);
                }}
              >
                <Text style={styles.closeButtonText}>Close</Text>
              </Pressable>
            </View>
          </View>
        </Modal>
      )}

      {showReminderModal && (
        <Modal
          animationType="slide"
          transparent={true}
          visible={showReminderModal}
          onRequestClose={() => setShowReminderModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContainer}>
              <Text style={styles.modalTitle}>Set Reminder</Text>
              <Text>Select a date and time for your reminder:</Text>
              {/* I will use a simple text input for now, a proper date picker would be better */}
              <TextField
                placeholder="YYYY-MM-DDTHH:mm:ss.sssZ"
                value={reminderDate.toISOString()}
                onChangeText={(text) => setReminderDate(new Date(text))}
              />
              <Button label="Set Reminder" onClick={handleSetReminder} disabled={reminderLoading} />
              <Pressable
                style={styles.closeButton}
                onPress={() => setShowReminderModal(false)}
              >
                <Text style={styles.closeButtonText}>Cancel</Text>
              </Pressable>
            </View>
          </View>
        </Modal>
      )}
    </Box>
  );
};

const styles = StyleSheet.create({
  pageContainer: {
    paddingTop: 20,
  },
  headerText: {
    color: palette.text,
  },
  itemContainer: {
    padding: 15,
    borderBottomWidth: 1,
    borderBottomColor: palette.mediumGray,
    backgroundColor: palette.white,
    borderRadius: 5,
    marginVertical: 5,
  },
  itemText: {
    fontSize: 14,
    color: palette.text,
    marginBottom: 3,
  },
  itemTextStrong: {
    fontSize: 14,
    fontWeight: 'bold',
    color: palette.text,
    marginBottom: 3,
  },
  viewDetailsLink: {
    fontSize: 14,
    color: palette.primary, // Use primary color for link
    marginTop: 5,
    textDecorationLine: 'underline',
  },
  activityIndicator: {
    marginTop: 20,
  },
  errorText: {
    fontSize: 14,
    color: palette.error, // Ensure palette has an error color
  },
  listStyle: {
    width: '100%',
    maxWidth: 600,
    marginTop: 20,
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.5)', // Semi-transparent background
  },
  modalContainer: {
    width: '90%',
    maxWidth: 600,
    maxHeight: '80%',
    backgroundColor: palette.white,
    borderRadius: 10,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 15,
    color: palette.text,
    textAlign: 'center',
  },
  modalTextStrong: {
    fontSize: 15,
    fontWeight: 'bold',
    marginTop: 10,
    color: palette.text,
  },
  modalText: {
    fontSize: 14,
    marginBottom: 5,
    color: palette.textSecondary, // Assuming a secondary text color
  },
  modalTextBody: {
    fontSize: 14,
    marginBottom: 5,
    color: palette.textSecondary,
    marginTop: 5,
    borderWidth: 1,
    borderColor: palette.lightGray, // Assuming lightGray
    padding: 10,
    borderRadius: 3,
    maxHeight: 200, // Make body scrollable if too long, but ScrollView handles this
  },
  closeButton: {
    marginTop: 20,
    backgroundColor: palette.primary,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 5,
    alignSelf: 'center',
  },
  closeButtonText: {
    color: palette.white,
    fontWeight: 'bold',
    textAlign: 'center',
  },
});

export default UserGmailSearchPage;
