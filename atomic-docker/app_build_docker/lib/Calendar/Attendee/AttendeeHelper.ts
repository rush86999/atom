
import { dayjs } from '@lib/date-utils'

// dayjs.extend(utc)

import {
  AttendeeEmailType,
  AttendeePhoneNumberType,
  AttendeeImAddressType,
  AttendeeType,
} from '@lib/dataTypes/AttendeeType'
import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client'
import deleteAttendeesByEventId from '@lib/apollo/gql/deleteAttendeesByEventId'
import listAttendeesByEventId from '@lib/apollo/gql/listAttendeesByEventId'
import deleteAttendeesByEventIds from '@lib/apollo/gql/deleteAttendeesByEventIds'

export const upsertAttendeesInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string,
  userId: string,
  eventId: string,
  emails: AttendeeEmailType[],
  name?: string | null,
  contactId?: string | null,
  phoneNumbers?: AttendeePhoneNumberType[] | null,
  imAddresses?: AttendeeImAddressType[] | null,
  additionalGuests?: number | null,
  optional?: boolean | null,
  resource?: boolean | null,
) => {
  try {
    // ASSUMPTION: A custom mutation 'bulkUpsertAttendees' is defined in PostGraphile (e.g., via a PG function)
    // The dynamic update_columns logic is now handled by the PG function.
    // The input type will likely be [AttendeeInput!]
    const upsertQuery = gql`
    mutation BulkUpsertAttendees($attendees: [AttendeeInput!]!) {
      bulkUpsertAttendees(input: { attendees: $attendees }) {
        # Assuming the custom function returns a list of the upserted attendees,
        # wrapped in a standard PostGraphile payload structure.
        results: attendees { # Or similar, depending on PG function and PostGraphile schema
          id
          additionalGuests
          comment
          contactId
          createdDate
          deleted
          emails # Assuming emails is a JSONB or similar scalar that PostGraphile handles
          eventId
          imAddresses # Assuming imAddresses is a JSONB or similar scalar
          name
          optional
          phoneNumbers # Assuming phoneNumbers is a JSONB or similar scalar
          resource
          responseStatus
          updatedAt
          userId
        }
        # affectedCount # If the function returns a count
      }
    }
  `
    // The type for client.mutate and variable preparation will need to adjust.
    // The 'attendees' variable now directly takes the array.
    const attendeesInput = [
      {
        id,
        userId,
        eventId,
        emails, // Ensure this matches the expected input type (e.g., JSON string or object array if PG can map it)
        name,
        contactId,
        phoneNumbers, // Ensure this matches the expected input type
        imAddresses,  // Ensure this matches the expected input type
        additionalGuests,
        optional,
        resource,
        updatedAt: dayjs().toISOString(),
        createdDate: dayjs().toISOString(), // createdDate might be set by DB default
        deleted: false,
      },
    ];

    const { data } = await client.mutate<{ bulkUpsertAttendees: { results: AttendeeType[] } } /* Adjust return type based on actual payload */>({
      mutation: upsertQuery,
      variables: {
        attendees: attendeesInput,
      },
      update(cache, { data }) {
        // The cache update logic might need significant changes based on how PostGraphile returns data
        // and how list queries are structured. This is a placeholder adjustment.
        const upsertedAttendees = data?.bulkUpsertAttendees?.results;
        if (upsertedAttendees && upsertedAttendees.length > 0) {
          console.log('bulkUpsertAttendees results', upsertedAttendees);

          // If you have a list query like 'allAttendees' that you want to update:
          // cache.modify({
          //   fields: {
          //     allAttendees(existingConnection = { nodes: [] }, { readField }) {
          //       const newConnection = { ...existingConnection, nodes: [...existingConnection.nodes] };
          //       upsertedAttendees.forEach(attendee => {
          //         const existingNode = newConnection.nodes.find(nodeRef => readField('id', nodeRef) === attendee.id);
          //         if (existingNode) {
          //           // If exists, Apollo Client might merge automatically, or you might need to explicitly update fields.
          //           // For simplicity, often re-fetching the list is easier unless fine-grained control is needed.
          //         } else {
          //           const newAttendeeRef = cache.writeFragment({
          //             data: attendee,
          //             fragment: gql`
          //               fragment NewAttendeeOnUpsert on Attendee {
          //                 id
          //                 # ... include all fields from the fragment below
          //                 additionalGuests
          //                 comment
          //                 contactId
          //                 createdDate
          //                 deleted
          //                 emails
          //                 eventId
          //                 imAddresses
          //                 name
          //                 optional
          //                 phoneNumbers
          //                 resource
          //                 responseStatus
          //                 updatedAt
          //                 userId
          //               }
          //             `
          //           });
          //           newConnection.nodes.push(newAttendeeRef);
          //         }
          //       });
          //       return newConnection;
          //     }
          //   }
          // });

          // The original cache logic was modifying a root field 'Attendee'.
          // This is less common with PostGraphile which usually uses connection types like 'allAttendees'.
          // This part is highly dependent on your actual queries and PostGraphile schema.
          // For now, I'll adapt the fragment writing part, but the field name 'Attendee' might be incorrect.
          cache.modify({
            fields: {
              // This field name 'Attendee' is likely incorrect for PostGraphile.
              // It would typically be 'allAttendees' or a specific query name.
              // This will need to be verified against the actual PostGraphile schema and queries used to populate the cache.
              Attendee: (existingAttendees = []) => { // Placeholder for existing cache update logic
                const newAttendeeRef = cache.writeFragment({
                  data: upsertedAttendees[0], // Assuming only one is upserted here, or loop if many
                  fragment: gql`
                    fragment NewAttendee on Attendee {
                      id
                      additionalGuests
                      comment
                      contactId
                      createdDate
                      deleted
                      emails
                      eventId
                      imAddresses
                      name
                      optional
                      phoneNumbers
                      resource
                      responseStatus
                      updatedAt
                      userId
                    }
                  `,
                });
                return [...existingAttendees, newAttendeeRef];
              },
            },
          });
        },
      },
    );

    console.log(data, ' successfully inserted attendees for event')

  } catch (e) {
    console.log(e, ' unable to save attendees in db')
  }
}

export const deleteAttendeesForEvents = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventIds: string[],
) => {
  try {
    const res = await client.mutate<{ delete_Attendee: { affected_rows: number } }>({
      mutation: deleteAttendeesByEventIds,
      variables: {
        eventIds,
      },
      update(cache, { data }) {
        if (data?.delete_Attendee?.affected_rows && data?.delete_Attendee?.affected_rows > 0) {
          console.log('delete_Attendee?.affected_rows', data)
        }

        cache.modify({
          fields: {
            Attendee(existingAttendees: AttendeeType[] = []) {
              const filteredAttendees = existingAttendees.filter(e => {
                return !eventIds.includes(e.eventId)
              })
              return filteredAttendees;
            }
          }
        })
      }
    })

    console.log(res?.data?.delete_Attendee?.affected_rows, 'successfully removed attendees for event')

  } catch (e) {
    console.log(e, ' unable to remove attendees for event')
  }
}
export const deleteAttendeesForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string,
) => {
  try {
    const res = await client.mutate<{ delete_Attendee: { affected_rows: number } }>({
      mutation: deleteAttendeesByEventId,
      variables: {
        eventId,
      },
    })

    console.log(res?.data?.delete_Attendee?.affected_rows, 'successfully removed attendees for event')

  } catch (e) {
    console.log(e, ' unable to remove attendees for event')
  }
}
export const listAttendeesForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string,
) => {
  try {
    const { data } = await client.query<{ Attendee: AttendeeType[] }>({
      query: listAttendeesByEventId,
      variables: {
        eventId,
      },
    })

    console.log(data?.Attendee, ' successfully received attendees')
    return data?.Attendee
  } catch (e) {
    console.log(e, ' unable to get attendees for event')
  }
}

/** end */
