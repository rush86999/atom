"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.listAttendeesForEvent = exports.deleteAttendeesForEvent = exports.deleteAttendeesForEvents = exports.upsertAttendeesInDb = void 0;
const date_utils_1 = require("@lib/date-utils");
const client_1 = require("@apollo/client");
const deleteAttendeesByEventId_1 = __importDefault(require("@lib/apollo/gql/deleteAttendeesByEventId"));
const listAttendeesByEventId_1 = __importDefault(require("@lib/apollo/gql/listAttendeesByEventId"));
const deleteAttendeesByEventIds_1 = __importDefault(require("@lib/apollo/gql/deleteAttendeesByEventIds"));
const upsertAttendeesInDb = async (client, id, userId, eventId, emails, name, contactId, phoneNumbers, imAddresses, additionalGuests, optional, resource) => {
    try {
        // ASSUMPTION: A custom mutation 'bulkUpsertAttendees' is defined in PostGraphile (e.g., via a PG function)
        // The dynamic update_columns logic is now handled by the PG function.
        // The input type will likely be [AttendeeInput!]
        const upsertQuery = (0, client_1.gql) `
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
  `;
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
                imAddresses, // Ensure this matches the expected input type
                additionalGuests,
                optional,
                resource,
                updatedAt: (0, date_utils_1.dayjs)().toISOString(),
                createdDate: (0, date_utils_1.dayjs)().toISOString(), // createdDate might be set by DB default
                deleted: false,
            },
        ];
        const { data } = await client.mutate({
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
                            Attendee: (existingAttendees = []) => {
                                const newAttendeeRef = cache.writeFragment({
                                    data: upsertedAttendees[0], // Assuming only one is upserted here, or loop if many
                                    fragment: (0, client_1.gql) `
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
                }
            },
        });
        console.log(data, ' successfully inserted attendees for event');
    }
    catch (e) {
        console.log(e, ' unable to save attendees in db');
    }
};
exports.upsertAttendeesInDb = upsertAttendeesInDb;
const deleteAttendeesForEvents = async (client, eventIds) => {
    try {
        const res = await client.mutate({
            mutation: deleteAttendeesByEventIds_1.default,
            variables: {
                eventIds,
            },
            update(cache, { data }) {
                if (data?.delete_Attendee?.affected_rows && data?.delete_Attendee?.affected_rows > 0) {
                    console.log('delete_Attendee?.affected_rows', data);
                }
                cache.modify({
                    fields: {
                        Attendee(existingAttendees = []) {
                            const filteredAttendees = existingAttendees.filter(e => {
                                return !eventIds.includes(e.eventId);
                            });
                            return filteredAttendees;
                        }
                    }
                });
            }
        });
        console.log(res?.data?.delete_Attendee?.affected_rows, 'successfully removed attendees for event');
    }
    catch (e) {
        console.log(e, ' unable to remove attendees for event');
    }
};
exports.deleteAttendeesForEvents = deleteAttendeesForEvents;
const deleteAttendeesForEvent = async (client, eventId) => {
    try {
        const res = await client.mutate({
            mutation: deleteAttendeesByEventId_1.default,
            variables: {
                eventId,
            },
        });
        console.log(res?.data?.delete_Attendee?.affected_rows, 'successfully removed attendees for event');
    }
    catch (e) {
        console.log(e, ' unable to remove attendees for event');
    }
};
exports.deleteAttendeesForEvent = deleteAttendeesForEvent;
const listAttendeesForEvent = async (client, eventId) => {
    try {
        const { data } = await client.query({
            query: listAttendeesByEventId_1.default,
            variables: {
                eventId,
            },
        });
        console.log(data?.Attendee, ' successfully received attendees');
        return data?.Attendee;
    }
    catch (e) {
        console.log(e, ' unable to get attendees for event');
    }
};
exports.listAttendeesForEvent = listAttendeesForEvent;
/** end */
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQXR0ZW5kZWVIZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJBdHRlbmRlZUhlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFDQSxnREFBdUM7QUFVdkMsMkNBQXlFO0FBQ3pFLHdHQUErRTtBQUMvRSxvR0FBMkU7QUFDM0UsMEdBQWlGO0FBRTFFLE1BQU0sbUJBQW1CLEdBQUcsS0FBSyxFQUN0QyxNQUEyQyxFQUMzQyxFQUFVLEVBQ1YsTUFBYyxFQUNkLE9BQWUsRUFDZixNQUEyQixFQUMzQixJQUFvQixFQUNwQixTQUF5QixFQUN6QixZQUErQyxFQUMvQyxXQUE0QyxFQUM1QyxnQkFBZ0MsRUFDaEMsUUFBeUIsRUFDekIsUUFBeUIsRUFDekIsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILDJHQUEyRztRQUMzRyxzRUFBc0U7UUFDdEUsaURBQWlEO1FBQ2pELE1BQU0sV0FBVyxHQUFHLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztHQTBCeEIsQ0FBQTtRQUNDLDJFQUEyRTtRQUMzRSx5REFBeUQ7UUFDekQsTUFBTSxjQUFjLEdBQUc7WUFDckI7Z0JBQ0UsRUFBRTtnQkFDRixNQUFNO2dCQUNOLE9BQU87Z0JBQ1AsTUFBTSxFQUFFLG1HQUFtRztnQkFDM0csSUFBSTtnQkFDSixTQUFTO2dCQUNULFlBQVksRUFBRSw4Q0FBOEM7Z0JBQzVELFdBQVcsRUFBRyw4Q0FBOEM7Z0JBQzVELGdCQUFnQjtnQkFDaEIsUUFBUTtnQkFDUixRQUFRO2dCQUNSLFNBQVMsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUU7Z0JBQ2hDLFdBQVcsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUUsRUFBRSx5Q0FBeUM7Z0JBQzdFLE9BQU8sRUFBRSxLQUFLO2FBQ2Y7U0FDRixDQUFDO1FBRUYsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FBd0c7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QUE7SUFFcEcsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSx1Q0FBdUMsQ0FBQyxDQUFBO0lBQ3pELENBQUM7QUFDSCxDQUFDLENBQUE7QUFqQlksUUFBQSx1QkFBdUIsMkJBaUJuQztBQUNNLE1BQU0scUJBQXFCLEdBQUcsS0FBSyxFQUN4QyxNQUEyQyxFQUMzQyxPQUFlLEVBQ2YsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sRUFBRSxJQUFJLEVBQUUsR0FBRyxNQUFNLE1BQU0sQ0FBQyxLQUFLLENBQStCO1lBQ2hFLEtBQUssRUFBRSxnQ0FBc0I7WUFDN0IsU0FBUyxFQUFFO2dCQUNULE9BQU87YUFDUjtTQUNGLENBQUMsQ0FBQTtRQUVGLE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxFQUFFLFFBQVEsRUFBRSxrQ0FBa0MsQ0FBQyxDQUFBO1FBQy9ELE9BQU8sSUFBSSxFQUFFLFFBQVEsQ0FBQTtJQUN2QixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLG9DQUFvQyxDQUFDLENBQUE7SUFDdEQsQ0FBQztBQUNILENBQUMsQ0FBQTtBQWpCWSxRQUFBLHFCQUFxQix5QkFpQmpDO0FBRUQsVUFBVSIsInNvdXJjZXNDb250ZW50IjpbIlxuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAbGliL2RhdGUtdXRpbHMnXG5cbi8vIGRheWpzLmV4dGVuZCh1dGMpXG5cbmltcG9ydCB7XG4gIEF0dGVuZGVlRW1haWxUeXBlLFxuICBBdHRlbmRlZVBob25lTnVtYmVyVHlwZSxcbiAgQXR0ZW5kZWVJbUFkZHJlc3NUeXBlLFxuICBBdHRlbmRlZVR5cGUsXG59IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0F0dGVuZGVlVHlwZSdcbmltcG9ydCB7IEFwb2xsb0NsaWVudCwgZ3FsLCBOb3JtYWxpemVkQ2FjaGVPYmplY3QgfSBmcm9tICdAYXBvbGxvL2NsaWVudCdcbmltcG9ydCBkZWxldGVBdHRlbmRlZXNCeUV2ZW50SWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2RlbGV0ZUF0dGVuZGVlc0J5RXZlbnRJZCdcbmltcG9ydCBsaXN0QXR0ZW5kZWVzQnlFdmVudElkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0QXR0ZW5kZWVzQnlFdmVudElkJ1xuaW1wb3J0IGRlbGV0ZUF0dGVuZGVlc0J5RXZlbnRJZHMgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2RlbGV0ZUF0dGVuZGVlc0J5RXZlbnRJZHMnXG5cbmV4cG9ydCBjb25zdCB1cHNlcnRBdHRlbmRlZXNJbkRiID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBpZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZXZlbnRJZDogc3RyaW5nLFxuICBlbWFpbHM6IEF0dGVuZGVlRW1haWxUeXBlW10sXG4gIG5hbWU/OiBzdHJpbmcgfCBudWxsLFxuICBjb250YWN0SWQ/OiBzdHJpbmcgfCBudWxsLFxuICBwaG9uZU51bWJlcnM/OiBBdHRlbmRlZVBob25lTnVtYmVyVHlwZVtdIHwgbnVsbCxcbiAgaW1BZGRyZXNzZXM/OiBBdHRlbmRlZUltQWRkcmVzc1R5cGVbXSB8IG51bGwsXG4gIGFkZGl0aW9uYWxHdWVzdHM/OiBudW1iZXIgfCBudWxsLFxuICBvcHRpb25hbD86IGJvb2xlYW4gfCBudWxsLFxuICByZXNvdXJjZT86IGJvb2xlYW4gfCBudWxsLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gQVNTVU1QVElPTjogQSBjdXN0b20gbXV0YXRpb24gJ2J1bGtVcHNlcnRBdHRlbmRlZXMnIGlzIGRlZmluZWQgaW4gUG9zdEdyYXBoaWxlIChlLmcuLCB2aWEgYSBQRyBmdW5jdGlvbilcbiAgICAvLyBUaGUgZHluYW1pYyB1cGRhdGVfY29sdW1ucyBsb2dpYyBpcyBub3cgaGFuZGxlZCBieSB0aGUgUEcgZnVuY3Rpb24uXG4gICAgLy8gVGhlIGlucHV0IHR5cGUgd2lsbCBsaWtlbHkgYmUgW0F0dGVuZGVlSW5wdXQhXVxuICAgIGNvbnN0IHVwc2VydFF1ZXJ5ID0gZ3FsYFxuICAgIG11dGF0aW9uIEJ1bGtVcHNlcnRBdHRlbmRlZXMoJGF0dGVuZGVlczogW0F0dGVuZGVlSW5wdXQhXSEpIHtcbiAgICAgIGJ1bGtVcHNlcnRBdHRlbmRlZXMoaW5wdXQ6IHsgYXR0ZW5kZWVzOiAkYXR0ZW5kZWVzIH0pIHtcbiAgICAgICAgIyBBc3N1bWluZyB0aGUgY3VzdG9tIGZ1bmN0aW9uIHJldHVybnMgYSBsaXN0IG9mIHRoZSB1cHNlcnRlZCBhdHRlbmRlZXMsXG4gICAgICAgICMgd3JhcHBlZCBpbiBhIHN0YW5kYXJkIFBvc3RHcmFwaGlsZSBwYXlsb2FkIHN0cnVjdHVyZS5cbiAgICAgICAgcmVzdWx0czogYXR0ZW5kZWVzIHsgIyBPciBzaW1pbGFyLCBkZXBlbmRpbmcgb24gUEcgZnVuY3Rpb24gYW5kIFBvc3RHcmFwaGlsZSBzY2hlbWFcbiAgICAgICAgICBpZFxuICAgICAgICAgIGFkZGl0aW9uYWxHdWVzdHNcbiAgICAgICAgICBjb21tZW50XG4gICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgZW1haWxzICMgQXNzdW1pbmcgZW1haWxzIGlzIGEgSlNPTkIgb3Igc2ltaWxhciBzY2FsYXIgdGhhdCBQb3N0R3JhcGhpbGUgaGFuZGxlc1xuICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICBpbUFkZHJlc3NlcyAjIEFzc3VtaW5nIGltQWRkcmVzc2VzIGlzIGEgSlNPTkIgb3Igc2ltaWxhciBzY2FsYXJcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgb3B0aW9uYWxcbiAgICAgICAgICBwaG9uZU51bWJlcnMgIyBBc3N1bWluZyBwaG9uZU51bWJlcnMgaXMgYSBKU09OQiBvciBzaW1pbGFyIHNjYWxhclxuICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgcmVzcG9uc2VTdGF0dXNcbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICB1c2VySWRcbiAgICAgICAgfVxuICAgICAgICAjIGFmZmVjdGVkQ291bnQgIyBJZiB0aGUgZnVuY3Rpb24gcmV0dXJucyBhIGNvdW50XG4gICAgICB9XG4gICAgfVxuICBgXG4gICAgLy8gVGhlIHR5cGUgZm9yIGNsaWVudC5tdXRhdGUgYW5kIHZhcmlhYmxlIHByZXBhcmF0aW9uIHdpbGwgbmVlZCB0byBhZGp1c3QuXG4gICAgLy8gVGhlICdhdHRlbmRlZXMnIHZhcmlhYmxlIG5vdyBkaXJlY3RseSB0YWtlcyB0aGUgYXJyYXkuXG4gICAgY29uc3QgYXR0ZW5kZWVzSW5wdXQgPSBbXG4gICAgICB7XG4gICAgICAgIGlkLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICAgIGVtYWlscywgLy8gRW5zdXJlIHRoaXMgbWF0Y2hlcyB0aGUgZXhwZWN0ZWQgaW5wdXQgdHlwZSAoZS5nLiwgSlNPTiBzdHJpbmcgb3Igb2JqZWN0IGFycmF5IGlmIFBHIGNhbiBtYXAgaXQpXG4gICAgICAgIG5hbWUsXG4gICAgICAgIGNvbnRhY3RJZCxcbiAgICAgICAgcGhvbmVOdW1iZXJzLCAvLyBFbnN1cmUgdGhpcyBtYXRjaGVzIHRoZSBleHBlY3RlZCBpbnB1dCB0eXBlXG4gICAgICAgIGltQWRkcmVzc2VzLCAgLy8gRW5zdXJlIHRoaXMgbWF0Y2hlcyB0aGUgZXhwZWN0ZWQgaW5wdXQgdHlwZVxuICAgICAgICBhZGRpdGlvbmFsR3Vlc3RzLFxuICAgICAgICBvcHRpb25hbCxcbiAgICAgICAgcmVzb3VyY2UsXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLCAvLyBjcmVhdGVkRGF0ZSBtaWdodCBiZSBzZXQgYnkgREIgZGVmYXVsdFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgIH0sXG4gICAgXTtcblxuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGJ1bGtVcHNlcnRBdHRlbmRlZXM6IHsgcmVzdWx0czogQXR0ZW5kZWVUeXBlW10gfSB9IC8qIEFkanVzdCByZXR1cm4gdHlwZSBiYXNlZCBvbiBhY3R1YWwgcGF5bG9hZCAqLz4oe1xuICAgICAgbXV0YXRpb246IHVwc2VydFF1ZXJ5LFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGF0dGVuZGVlczogYXR0ZW5kZWVzSW5wdXQsXG4gICAgICB9LFxuICAgICAgdXBkYXRlKGNhY2hlLCB7IGRhdGEgfSkge1xuICAgICAgICAvLyBUaGUgY2FjaGUgdXBkYXRlIGxvZ2ljIG1pZ2h0IG5lZWQgc2lnbmlmaWNhbnQgY2hhbmdlcyBiYXNlZCBvbiBob3cgUG9zdEdyYXBoaWxlIHJldHVybnMgZGF0YVxuICAgICAgICAvLyBhbmQgaG93IGxpc3QgcXVlcmllcyBhcmUgc3RydWN0dXJlZC4gVGhpcyBpcyBhIHBsYWNlaG9sZGVyIGFkanVzdG1lbnQuXG4gICAgICAgIGNvbnN0IHVwc2VydGVkQXR0ZW5kZWVzID0gZGF0YT8uYnVsa1Vwc2VydEF0dGVuZGVlcz8ucmVzdWx0cztcbiAgICAgICAgaWYgKHVwc2VydGVkQXR0ZW5kZWVzICYmIHVwc2VydGVkQXR0ZW5kZWVzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnYnVsa1Vwc2VydEF0dGVuZGVlcyByZXN1bHRzJywgdXBzZXJ0ZWRBdHRlbmRlZXMpO1xuXG4gICAgICAgICAgLy8gSWYgeW91IGhhdmUgYSBsaXN0IHF1ZXJ5IGxpa2UgJ2FsbEF0dGVuZGVlcycgdGhhdCB5b3Ugd2FudCB0byB1cGRhdGU6XG4gICAgICAgICAgLy8gY2FjaGUubW9kaWZ5KHtcbiAgICAgICAgICAvLyAgIGZpZWxkczoge1xuICAgICAgICAgIC8vICAgICBhbGxBdHRlbmRlZXMoZXhpc3RpbmdDb25uZWN0aW9uID0geyBub2RlczogW10gfSwgeyByZWFkRmllbGQgfSkge1xuICAgICAgICAgIC8vICAgICAgIGNvbnN0IG5ld0Nvbm5lY3Rpb24gPSB7IC4uLmV4aXN0aW5nQ29ubmVjdGlvbiwgbm9kZXM6IFsuLi5leGlzdGluZ0Nvbm5lY3Rpb24ubm9kZXNdIH07XG4gICAgICAgICAgLy8gICAgICAgdXBzZXJ0ZWRBdHRlbmRlZXMuZm9yRWFjaChhdHRlbmRlZSA9PiB7XG4gICAgICAgICAgLy8gICAgICAgICBjb25zdCBleGlzdGluZ05vZGUgPSBuZXdDb25uZWN0aW9uLm5vZGVzLmZpbmQobm9kZVJlZiA9PiByZWFkRmllbGQoJ2lkJywgbm9kZVJlZikgPT09IGF0dGVuZGVlLmlkKTtcbiAgICAgICAgICAvLyAgICAgICAgIGlmIChleGlzdGluZ05vZGUpIHtcbiAgICAgICAgICAvLyAgICAgICAgICAgLy8gSWYgZXhpc3RzLCBBcG9sbG8gQ2xpZW50IG1pZ2h0IG1lcmdlIGF1dG9tYXRpY2FsbHksIG9yIHlvdSBtaWdodCBuZWVkIHRvIGV4cGxpY2l0bHkgdXBkYXRlIGZpZWxkcy5cbiAgICAgICAgICAvLyAgICAgICAgICAgLy8gRm9yIHNpbXBsaWNpdHksIG9mdGVuIHJlLWZldGNoaW5nIHRoZSBsaXN0IGlzIGVhc2llciB1bmxlc3MgZmluZS1ncmFpbmVkIGNvbnRyb2wgaXMgbmVlZGVkLlxuICAgICAgICAgIC8vICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAvLyAgICAgICAgICAgY29uc3QgbmV3QXR0ZW5kZWVSZWYgPSBjYWNoZS53cml0ZUZyYWdtZW50KHtcbiAgICAgICAgICAvLyAgICAgICAgICAgICBkYXRhOiBhdHRlbmRlZSxcbiAgICAgICAgICAvLyAgICAgICAgICAgICBmcmFnbWVudDogZ3FsYFxuICAgICAgICAgIC8vICAgICAgICAgICAgICAgZnJhZ21lbnQgTmV3QXR0ZW5kZWVPblVwc2VydCBvbiBBdHRlbmRlZSB7XG4gICAgICAgICAgLy8gICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgLy8gICAgICAgICAgICAgICAgICMgLi4uIGluY2x1ZGUgYWxsIGZpZWxkcyBmcm9tIHRoZSBmcmFnbWVudCBiZWxvd1xuICAgICAgICAgIC8vICAgICAgICAgICAgICAgICBhZGRpdGlvbmFsR3Vlc3RzXG4gICAgICAgICAgLy8gICAgICAgICAgICAgICAgIGNvbW1lbnRcbiAgICAgICAgICAvLyAgICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgLy8gICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgLy8gICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAvLyAgICAgICAgICAgICAgICAgZW1haWxzXG4gICAgICAgICAgLy8gICAgICAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAvLyAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgICAvLyAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgIC8vICAgICAgICAgICAgICAgICBvcHRpb25hbFxuICAgICAgICAgIC8vICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAvLyAgICAgICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAvLyAgICAgICAgICAgICAgICAgcmVzcG9uc2VTdGF0dXNcbiAgICAgICAgICAvLyAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgLy8gICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIC8vICAgICAgICAgICAgICAgfVxuICAgICAgICAgIC8vICAgICAgICAgICAgIGBcbiAgICAgICAgICAvLyAgICAgICAgICAgfSk7XG4gICAgICAgICAgLy8gICAgICAgICAgIG5ld0Nvbm5lY3Rpb24ubm9kZXMucHVzaChuZXdBdHRlbmRlZVJlZik7XG4gICAgICAgICAgLy8gICAgICAgICB9XG4gICAgICAgICAgLy8gICAgICAgfSk7XG4gICAgICAgICAgLy8gICAgICAgcmV0dXJuIG5ld0Nvbm5lY3Rpb247XG4gICAgICAgICAgLy8gICAgIH1cbiAgICAgICAgICAvLyAgIH1cbiAgICAgICAgICAvLyB9KTtcblxuICAgICAgICAgIC8vIFRoZSBvcmlnaW5hbCBjYWNoZSBsb2dpYyB3YXMgbW9kaWZ5aW5nIGEgcm9vdCBmaWVsZCAnQXR0ZW5kZWUnLlxuICAgICAgICAgIC8vIFRoaXMgaXMgbGVzcyBjb21tb24gd2l0aCBQb3N0R3JhcGhpbGUgd2hpY2ggdXN1YWxseSB1c2VzIGNvbm5lY3Rpb24gdHlwZXMgbGlrZSAnYWxsQXR0ZW5kZWVzJy5cbiAgICAgICAgICAvLyBUaGlzIHBhcnQgaXMgaGlnaGx5IGRlcGVuZGVudCBvbiB5b3VyIGFjdHVhbCBxdWVyaWVzIGFuZCBQb3N0R3JhcGhpbGUgc2NoZW1hLlxuICAgICAgICAgIC8vIEZvciBub3csIEknbGwgYWRhcHQgdGhlIGZyYWdtZW50IHdyaXRpbmcgcGFydCwgYnV0IHRoZSBmaWVsZCBuYW1lICdBdHRlbmRlZScgbWlnaHQgYmUgaW5jb3JyZWN0LlxuICAgICAgICAgIGNhY2hlLm1vZGlmeSh7XG4gICAgICAgICAgICBmaWVsZHM6IHtcbiAgICAgICAgICAgICAgLy8gVGhpcyBmaWVsZCBuYW1lICdBdHRlbmRlZScgaXMgbGlrZWx5IGluY29ycmVjdCBmb3IgUG9zdEdyYXBoaWxlLlxuICAgICAgICAgICAgICAvLyBJdCB3b3VsZCB0eXBpY2FsbHkgYmUgJ2FsbEF0dGVuZGVlcycgb3IgYSBzcGVjaWZpYyBxdWVyeSBuYW1lLlxuICAgICAgICAgICAgICAvLyBUaGlzIHdpbGwgbmVlZCB0byBiZSB2ZXJpZmllZCBhZ2FpbnN0IHRoZSBhY3R1YWwgUG9zdEdyYXBoaWxlIHNjaGVtYSBhbmQgcXVlcmllcyB1c2VkIHRvIHBvcHVsYXRlIHRoZSBjYWNoZS5cbiAgICAgICAgICAgICAgQXR0ZW5kZWU6IChleGlzdGluZ0F0dGVuZGVlcyA9IFtdKSA9PiB7IC8vIFBsYWNlaG9sZGVyIGZvciBleGlzdGluZyBjYWNoZSB1cGRhdGUgbG9naWNcbiAgICAgICAgICAgICAgICBjb25zdCBuZXdBdHRlbmRlZVJlZiA9IGNhY2hlLndyaXRlRnJhZ21lbnQoe1xuICAgICAgICAgICAgICAgICAgZGF0YTogdXBzZXJ0ZWRBdHRlbmRlZXNbMF0sIC8vIEFzc3VtaW5nIG9ubHkgb25lIGlzIHVwc2VydGVkIGhlcmUsIG9yIGxvb3AgaWYgbWFueVxuICAgICAgICAgICAgICAgICAgZnJhZ21lbnQ6IGdxbGBcbiAgICAgICAgICAgICAgICAgICAgZnJhZ21lbnQgTmV3QXR0ZW5kZWUgb24gQXR0ZW5kZWUge1xuICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgICAgYWRkaXRpb25hbEd1ZXN0c1xuICAgICAgICAgICAgICAgICAgICAgIGNvbW1lbnRcbiAgICAgICAgICAgICAgICAgICAgICBjb250YWN0SWRcbiAgICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgICBlbWFpbHNcbiAgICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgICAgb3B0aW9uYWxcbiAgICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgICAgICAgIHJlc3BvbnNlU3RhdHVzXG4gICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgIGAsXG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgcmV0dXJuIFsuLi5leGlzdGluZ0F0dGVuZGVlcywgbmV3QXR0ZW5kZWVSZWZdO1xuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KTtcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IGluc2VydGVkIGF0dGVuZGVlcyBmb3IgZXZlbnQnKVxuXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzYXZlIGF0dGVuZGVlcyBpbiBkYicpXG4gIH1cbn1cblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUF0dGVuZGVlc0ZvckV2ZW50cyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgZXZlbnRJZHM6IHN0cmluZ1tdLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGRlbGV0ZV9BdHRlbmRlZTogeyBhZmZlY3RlZF9yb3dzOiBudW1iZXIgfSB9Pih7XG4gICAgICBtdXRhdGlvbjogZGVsZXRlQXR0ZW5kZWVzQnlFdmVudElkcyxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBldmVudElkcyxcbiAgICAgIH0sXG4gICAgICB1cGRhdGUoY2FjaGUsIHsgZGF0YSB9KSB7XG4gICAgICAgIGlmIChkYXRhPy5kZWxldGVfQXR0ZW5kZWU/LmFmZmVjdGVkX3Jvd3MgJiYgZGF0YT8uZGVsZXRlX0F0dGVuZGVlPy5hZmZlY3RlZF9yb3dzID4gMCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKCdkZWxldGVfQXR0ZW5kZWU/LmFmZmVjdGVkX3Jvd3MnLCBkYXRhKVxuICAgICAgICB9XG5cbiAgICAgICAgY2FjaGUubW9kaWZ5KHtcbiAgICAgICAgICBmaWVsZHM6IHtcbiAgICAgICAgICAgIEF0dGVuZGVlKGV4aXN0aW5nQXR0ZW5kZWVzOiBBdHRlbmRlZVR5cGVbXSA9IFtdKSB7XG4gICAgICAgICAgICAgIGNvbnN0IGZpbHRlcmVkQXR0ZW5kZWVzID0gZXhpc3RpbmdBdHRlbmRlZXMuZmlsdGVyKGUgPT4ge1xuICAgICAgICAgICAgICAgIHJldHVybiAhZXZlbnRJZHMuaW5jbHVkZXMoZS5ldmVudElkKVxuICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICByZXR1cm4gZmlsdGVyZWRBdHRlbmRlZXM7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9KVxuICAgICAgfVxuICAgIH0pXG5cbiAgICBjb25zb2xlLmxvZyhyZXM/LmRhdGE/LmRlbGV0ZV9BdHRlbmRlZT8uYWZmZWN0ZWRfcm93cywgJ3N1Y2Nlc3NmdWxseSByZW1vdmVkIGF0dGVuZGVlcyBmb3IgZXZlbnQnKVxuXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZW1vdmUgYXR0ZW5kZWVzIGZvciBldmVudCcpXG4gIH1cbn1cbmV4cG9ydCBjb25zdCBkZWxldGVBdHRlbmRlZXNGb3JFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgZXZlbnRJZDogc3RyaW5nLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGRlbGV0ZV9BdHRlbmRlZTogeyBhZmZlY3RlZF9yb3dzOiBudW1iZXIgfSB9Pih7XG4gICAgICBtdXRhdGlvbjogZGVsZXRlQXR0ZW5kZWVzQnlFdmVudElkLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGV2ZW50SWQsXG4gICAgICB9LFxuICAgIH0pXG5cbiAgICBjb25zb2xlLmxvZyhyZXM/LmRhdGE/LmRlbGV0ZV9BdHRlbmRlZT8uYWZmZWN0ZWRfcm93cywgJ3N1Y2Nlc3NmdWxseSByZW1vdmVkIGF0dGVuZGVlcyBmb3IgZXZlbnQnKVxuXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZW1vdmUgYXR0ZW5kZWVzIGZvciBldmVudCcpXG4gIH1cbn1cbmV4cG9ydCBjb25zdCBsaXN0QXR0ZW5kZWVzRm9yRXZlbnQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGV2ZW50SWQ6IHN0cmluZyxcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQXR0ZW5kZWU6IEF0dGVuZGVlVHlwZVtdIH0+KHtcbiAgICAgIHF1ZXJ5OiBsaXN0QXR0ZW5kZWVzQnlFdmVudElkLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGV2ZW50SWQsXG4gICAgICB9LFxuICAgIH0pXG5cbiAgICBjb25zb2xlLmxvZyhkYXRhPy5BdHRlbmRlZSwgJyBzdWNjZXNzZnVsbHkgcmVjZWl2ZWQgYXR0ZW5kZWVzJylcbiAgICByZXR1cm4gZGF0YT8uQXR0ZW5kZWVcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBhdHRlbmRlZXMgZm9yIGV2ZW50JylcbiAgfVxufVxuXG4vKiogZW5kICovXG4iXX0=