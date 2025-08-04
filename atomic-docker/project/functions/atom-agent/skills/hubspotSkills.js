import { Client } from '@hubspot/api-client';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import { ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID, ATOM_HUBSPOT_PORTAL_ID, } from '../_libs/constants';
import { sendSlackMessage } from './slackSkills';
const CONTACT_TO_ENGAGEMENT_ASSOCIATION_TYPE_ID = 203;
const CONTACT_OBJECT_TYPE_ID_FOR_ASSOCIATIONS_API = '0-1';
const ENGAGEMENT_OBJECT_TYPE_ID_FOR_ASSOCIATIONS_API = '0-31';
async function getHubspotApiKey(userId) {
    const query = `
        query GetUserCredential($userId: String!, $serviceName: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                encrypted_secret
            }
        }
    `;
    const variables = {
        userId,
        serviceName: 'hubspot_api_key',
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
    }
    return null;
}
const getHubspotClient = async (userId) => {
    const apiKey = await getHubspotApiKey(userId);
    if (!apiKey) {
        console.error('HubSpot API key not configured for this user.');
        return null;
    }
    return new Client({ apiKey });
};
export async function getHubSpotContactByEmail(userId, email) {
    // Return null in data if not found but no error
    console.log(`getHubSpotContactByEmail called for userId: ${userId}, email: ${email}`);
    const hubspotClient = await getHubspotClient(userId);
    if (!hubspotClient) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'HubSpot API key not configured.',
            },
        };
    }
    if (!email || email.trim() === '') {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Email parameter is required.',
            },
        };
    }
    try {
        const response = await hubspotClient.crm.contacts.searchApi.doSearch({
            query: email, // Note: Using email directly in query might be too broad. Specific property filter is better.
            properties: [
                'email',
                'firstname',
                'lastname',
                'company',
                'hs_object_id',
                'createdate',
                'lastmodifieddate',
            ],
            filterGroups: [
                {
                    filters: [
                        {
                            propertyName: 'email',
                            operator: 'EQ',
                            value: email,
                        },
                    ],
                },
            ],
            limit: 1, // We only expect one contact by primary email
        });
        if (response.results && response.results.length > 0) {
            const contactData = response.results[0];
            const contact = {
                id: contactData.id,
                properties: {
                    hs_object_id: contactData.properties.hs_object_id,
                    createdate: contactData.properties.createdate,
                    lastmodifieddate: contactData.properties.lastmodifieddate,
                    email: contactData.properties.email,
                    firstname: contactData.properties.firstname,
                    lastname: contactData.properties.lastname,
                    company: contactData.properties.company,
                },
                createdAt: contactData.createdAt.toISOString(),
                updatedAt: contactData.updatedAt.toISOString(),
                archived: contactData.archived || false,
            };
            return { ok: true, data: contact };
        }
        else {
            console.log(`No HubSpot contact found for email: ${email}`);
            return { ok: true, data: null }; // Success, but no contact found
        }
    }
    catch (error) {
        console.error(`Error fetching HubSpot contact by email ${email} for userId ${userId}:`, error.message);
        let errorMessage = `Failed to fetch contact by email: ${error.message}`;
        let errorCode = 'HUBSPOT_API_ERROR';
        if (error.response && error.response.body) {
            console.error('HubSpot API Error Body:', error.response.body);
            try {
                const errorBodyString = Buffer.isBuffer(error.response.body)
                    ? error.response.body.toString()
                    : error.response.body;
                const errorBody = JSON.parse(errorBodyString);
                if (errorBody && errorBody.message) {
                    errorMessage = errorBody.message;
                    if (errorBody.category === 'VALIDATION_ERROR')
                        errorCode = 'VALIDATION_ERROR';
                }
            }
            catch (parseError) {
                /* Do nothing, use generic message */
            }
        }
        return {
            ok: false,
            error: { code: errorCode, message: errorMessage, details: error },
        };
    }
}
export async function createHubSpotContact(userId, contactProperties) {
    // Updated return type
    console.log(`createHubSpotContact called for userId: ${userId} with properties:`, contactProperties);
    const hubspotClient = await getHubspotClient(userId);
    if (!hubspotClient) {
        // Consistent error structure
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'HubSpot API key not configured.',
            },
        };
    }
    if (!contactProperties.email) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Email is required to create a HubSpot contact.',
            },
        };
    }
    try {
        const createResponse = await hubspotClient.crm.contacts.basicApi.create({
            properties: contactProperties,
        });
        // Map the response to HubSpotContact, ensuring all fields are covered
        const createdContact = {
            id: createResponse.id,
            properties: {
                hs_object_id: createResponse.properties.hs_object_id,
                createdate: createResponse.properties.createdate,
                lastmodifieddate: createResponse.properties.lastmodifieddate,
                email: createResponse.properties.email,
                firstname: createResponse.properties.firstname,
                lastname: createResponse.properties.lastname,
                company: createResponse.properties.company,
                // Include any other custom properties you expect or that are returned
            },
            createdAt: createResponse.createdAt.toISOString(),
            updatedAt: createResponse.updatedAt.toISOString(),
            archived: createResponse.archived || false, // Default to false if undefined
        };
        // Send Slack notification if channel ID is configured
        if (ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID) {
            let slackMessage = `New HubSpot Contact Created by user ${userId}:\n`;
            slackMessage += `Name: ${createdContact.properties.firstname || ''} ${createdContact.properties.lastname || ''}\n`;
            slackMessage += `Email: ${createdContact.properties.email}\n`;
            if (createdContact.properties.company) {
                slackMessage += `Company: ${createdContact.properties.company}\n`;
            }
            if (ATOM_HUBSPOT_PORTAL_ID) {
                slackMessage += `Link: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${createdContact.id}\n`;
            }
            else {
                slackMessage += `Contact ID: ${createdContact.id}\n`;
            }
            // Fire-and-forget Slack message, don't let its failure block the main response.
            sendSlackMessage(userId, ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID, slackMessage)
                .then((slackRes) => {
                if (!slackRes.ok) {
                    console.warn(`Failed to send Slack notification for new HubSpot contact ${createdContact.id}: ${slackRes.error}`);
                }
                else {
                    console.log(`Slack notification sent for new HubSpot contact ${createdContact.id}. Message ts: ${slackRes.ts}`);
                }
            })
                .catch((slackErr) => {
                console.error(`Error sending Slack notification for new HubSpot contact ${createdContact.id}:`, slackErr);
            });
        }
        return {
            ok: true, // success
            data: {
                // The actual payload as per CreateHubSpotContactResponse
                success: true,
                contactId: createResponse.id,
                message: 'Contact created successfully in HubSpot.',
                hubSpotContact: createdContact,
            },
        };
    }
    catch (error) {
        console.error(`Error creating HubSpot contact for userId ${userId} with email ${contactProperties.email}:`, error.message);
        let errorMessage = `Failed to create contact in HubSpot: ${error.message}`;
        let errorCode = 'HUBSPOT_API_ERROR';
        let errorDetails = error;
        if (error.response && error.response.body) {
            console.error('HubSpot API Error Body:', error.response.body);
            try {
                const errorBodyString = Buffer.isBuffer(error.response.body)
                    ? error.response.body.toString()
                    : error.response.body;
                const errorBody = JSON.parse(errorBodyString);
                errorDetails = errorBody; // Store parsed body as details
                if (errorBody && errorBody.message) {
                    errorMessage = errorBody.message; // Use HubSpot's message
                    if (errorBody.category === 'CONFLICT') {
                        errorCode = 'CONFLICT_ERROR'; // More specific error code
                        // Keep HubSpot's message as it might be more informative e.g. "Contact already exists. Existing ID: XXXXX"
                    }
                    else if (errorBody.category === 'VALIDATION_ERROR') {
                        errorCode = 'VALIDATION_ERROR';
                    }
                }
            }
            catch (parseError) {
                console.error('Could not parse HubSpot error body:', parseError);
                // errorDetails remains the original error object
            }
        }
        return {
            ok: false,
            error: { code: errorCode, message: errorMessage, details: errorDetails },
        };
    }
}
export async function logEmailToHubSpotContact(userId, contactId, emailDetails) {
    // Updated return type
    console.log(`logEmailToHubSpotContact called for userId: ${userId}, contactId: ${contactId}`);
    const hubspotClient = await getHubspotClient(userId);
    if (!hubspotClient) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'HubSpot API key not configured.',
            },
        };
    }
    if (!contactId) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Contact ID is required to log an email.',
            },
        };
    }
    if (!emailDetails ||
        !emailDetails.activityTimestamp ||
        !emailDetails.subject ||
        !emailDetails.htmlBody) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Email details (activityTimestamp, subject, htmlBody) are required.',
            },
        };
    }
    const engagementInput = {
        properties: {
            hs_timestamp: emailDetails.activityTimestamp.toString(), // Must be string in epoch milliseconds
            hs_engagement_type: 'EMAIL',
            hs_email_subject: emailDetails.subject,
            hs_body_preview: emailDetails.htmlBody.substring(0, 512), // Max length for preview
            // hs_email_html_body: emailDetails.htmlBody, // Not a standard property for simple engagement logging, use metadata or notes if full HTML needed.
            // hs_engagement_source: 'CRM_UI', // Example: if logged manually by a user. 'INTEGRATION' if by your app.
            // hs_engagement_source_id: 'YOUR_APP_ID', // If using 'INTEGRATION'
        },
        associations: [
            {
                to: { id: contactId },
                types: [
                    {
                        associationCategory: 'HUBSPOT_DEFINED',
                        associationTypeId: CONTACT_TO_ENGAGEMENT_ASSOCIATION_TYPE_ID, // Contact to Engagement
                    },
                ],
            },
        ],
    };
    if (emailDetails.direction) {
        engagementInput.properties.hs_email_direction = emailDetails.direction;
    }
    try {
        const createResponse = await hubspotClient.crm.engagements.basicApi.create(engagementInput);
        // Map the response to HubSpotEngagement, ensuring all fields are covered
        // Note: The response from engagement creation might be simpler than a full engagement search result.
        // We might need to fetch the engagement separately if more details are needed immediately.
        const createdEngagement = {
            id: createResponse.id,
            properties: {
                hs_object_id: createResponse.properties.hs_object_id || createResponse.id, // hs_object_id might not be in basic create response, use id
                hs_engagement_type: createResponse.properties.hs_engagement_type, // Cast as needed
                hs_timestamp: createResponse.properties.hs_timestamp,
                hs_body_preview: createResponse.properties.hs_body_preview,
                hs_email_subject: createResponse.properties.hs_email_subject,
                hs_email_direction: createResponse.properties.hs_email_direction,
                createdate: createResponse.properties.createdate ||
                    new Date(createResponse.createdAt).toISOString(),
                lastmodifieddate: createResponse.properties.lastmodifieddate ||
                    new Date(createResponse.updatedAt).toISOString(),
            },
            associations: createResponse.associations, // Cast if necessary, or map structure
            createdAt: createResponse.createdAt.toISOString(),
            updatedAt: createResponse.updatedAt.toISOString(),
            archived: createResponse.archived || false,
        };
        return {
            ok: true,
            data: {
                success: true,
                engagementId: createResponse.id,
                message: 'Email logged successfully to HubSpot contact.',
                hubSpotEngagement: createdEngagement,
            },
        };
    }
    catch (error) {
        console.error(`Error logging email to HubSpot contact ${contactId} for userId ${userId}:`, error.message);
        let errorMessage = `Failed to log email to HubSpot: ${error.message}`;
        let errorCode = 'HUBSPOT_API_ERROR';
        let errorDetails = error;
        if (error.response && error.response.body) {
            console.error('HubSpot API Error Body:', error.response.body);
            try {
                const errorBodyString = Buffer.isBuffer(error.response.body)
                    ? error.response.body.toString()
                    : error.response.body;
                const errorBody = JSON.parse(errorBodyString);
                errorDetails = errorBody;
                if (errorBody && errorBody.message) {
                    errorMessage = errorBody.message;
                    if (errorBody.category === 'VALIDATION_ERROR')
                        errorCode = 'VALIDATION_ERROR';
                }
            }
            catch (parseError) {
                console.error('Could not parse HubSpot error body:', parseError);
            }
        }
        return {
            ok: false,
            error: { code: errorCode, message: errorMessage, details: errorDetails },
        };
    }
}
export async function getHubSpotContactActivities(userId, contactId, filters) {
    // Updated return type
    console.log(`getHubSpotContactActivities called for userId: ${userId}, contactId: ${contactId}, filters:`, filters);
    const hubspotClient = await getHubspotClient(userId);
    if (!hubspotClient) {
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'HubSpot API key not configured.',
            },
        };
    }
    if (!contactId) {
        return {
            ok: false,
            error: { code: 'VALIDATION_ERROR', message: 'Contact ID is required.' },
        };
    }
    const searchRequest = {
        filterGroups: [
            {
                // This filter attempts to find engagements associated with the contact.
                // The exact propertyName for contact ID in engagement associations via search might vary or might not be directly supported.
                // HubSpot's Search API for engagements typically filters on engagement properties, not association properties directly in this manner.
                // A common pattern is to first get associated engagement IDs, then fetch/search those engagements.
                // However, if direct association search is supported, it would look something like:
                // filters: [{ propertyName: 'associations.contact', operator: 'EQ', value: contactId }] // This is speculative.
                // A more reliable way might be to use a dedicated association property if available or use the Associations API first (see alternative below).
                // For now, let's assume we are trying to filter by a property that implies association or use a workaround.
                // **Correction**: The primary method to get activities FOR a contact is to use the Associations API to list engagement IDs,
                // then use those IDs in a batch read or search. The search below is more for general engagement searching.
                // Let's adjust to use the search based on properties that might be available on engagements if direct association isn't straightforward in one search.
                // However, the prompt implies a search. So, we will construct a search assuming 'associations.contact.id' or similar exists.
                // If this fails, the alternative is Associations API + Batch Read/Search by IDs.
                // Let's assume 'associations.contact' doesn't work directly in search and instead we'd have to rely on properties on the engagement itself.
                // A common workaround if direct association property isn't available for search is to first get all engagement IDs for a contact,
                // then use those IDs in a search with `id` IN (...) filter.
                // Given the prompt's preference for Search API, and potential for direct association filtering:
                // The official way to search for engagements associated with a contact is to use the `crm.associations.v4.basicApi.getPage`
                // to get engagement IDs, then use those IDs in a `SearchApi.doSearch` with an ID filter.
                // However, let's try to construct the search as best as possible based on the prompt, assuming a more direct search.
                // This might require a specific HubSpot setup or custom property.
                // A filter on `associations.contact.id` is NOT standard for Engagements Search API.
                // Instead, you search engagements and hope they have a direct contact ID property, or use Associations API.
                // For the sake of the exercise, if we HAD to use search and filter by contact:
                // Let's assume a custom setup or a misunderstanding of direct search capabilities for associations.
                // The most robust way is:
                // 1. Get Engagement IDs via Associations API for the contact.
                // 2. Search Engagements with `hs_object_id` IN (those IDs).
                // Let's proceed with the direct search approach as per the prompt's structure, while noting its potential limitations.
                // The filter for contact association is tricky. HubSpot's standard search for engagements doesn't directly support `associations.contact.id`.
                // We'll add other filters and then discuss the association part.
                filters: [
                // This is the part that's hard with a single search.
                // To correctly filter by contact, you'd typically use the Associations API first.
                // For this exercise, we'll build the rest of the search.
                // If a direct property like 'hs_contact_id' existed on engagements, it would be:
                // { propertyName: 'hs_contact_id', operator: 'EQ', value: contactId }
                // Since it doesn't, this filter group might be ineffective for contact association by itself.
                ],
            },
        ],
        limit: filters?.limit || 10,
        after: filters?.after,
        sorts: [
            {
                propertyName: 'hs_timestamp',
                direction: filters?.sort === 'ASC' ? 'ASCENDING' : 'DESCENDING',
            },
        ],
        properties: [
            'hs_engagement_type',
            'hs_timestamp',
            'hs_body_preview',
            'hs_email_subject',
            'hs_meeting_title',
            'hs_createdate',
            'hs_lastmodifieddate',
            'hs_object_id',
            'hs_email_direction' /* any other relevant props */,
        ],
    };
    // Add activity type filters if provided
    if (filters?.activityTypes && filters.activityTypes.length > 0) {
        searchRequest.filterGroups[0].filters.push({
            // Add to the first (and only) filter group
            propertyName: 'hs_engagement_type',
            operator: 'IN', // Use IN operator for multiple values
            values: filters.activityTypes,
        });
    }
    // Add 'since' filter (hs_timestamp >= value)
    if (filters?.since) {
        let sinceTimestamp = filters.since;
        // HubSpot's hs_timestamp for search is usually epoch milliseconds
        if (!/^\d+$/.test(filters.since)) {
            // If not already epoch ms
            sinceTimestamp = new Date(filters.since).getTime().toString();
        }
        searchRequest.filterGroups[0].filters.push({
            propertyName: 'hs_timestamp',
            operator: 'GTE',
            value: sinceTimestamp,
        });
    }
    // The most reliable way to get engagements for a SPECIFIC contact is via the Associations API first.
    // Then use the returned engagement IDs in a search request.
    try {
        const associationResults = await hubspotClient.crm.associations.v4.basicApi.getPage(CONTACT_OBJECT_TYPE_ID_FOR_ASSOCIATIONS_API, // From Object Type (Contact)
        contactId, ENGAGEMENT_OBJECT_TYPE_ID_FOR_ASSOCIATIONS_API, // To Object Type (Engagement)
        filters?.after, // after for association pagination
        filters?.limit || 50 // limit for associations (can be different from final engagement limit)
        );
        if (!associationResults.results ||
            associationResults.results.length === 0) {
            return {
                success: true,
                activities: [],
                message: 'No activities found for this contact.',
            };
        }
        const engagementIds = associationResults.results.map((assoc) => assoc.toObjectId);
        // Now search for these specific engagement IDs
        const idFilter = {
            propertyName: 'hs_object_id',
            operator: 'IN',
            values: engagementIds,
        };
        // Add this ID filter to the existing filter group or a new one.
        // If the filter group is empty (e.g. no activityTypes or since filter), add it directly.
        if (searchRequest.filterGroups[0].filters.length === 0) {
            searchRequest.filterGroups[0].filters.push(idFilter);
        }
        else {
            // If other filters exist, create a new filter group for IDs to ensure AND logic
            // or add to existing if AND is desired for all conditions.
            // For this case, all filters should apply, so add to existing.
            searchRequest.filterGroups[0].filters.push(idFilter);
        }
        const response = await hubspotClient.crm.engagements.searchApi.doSearch(searchRequest);
        const activities = response.results
            ? response.results.map((eng) => {
                // Basic mapping, ensure all required fields from HubSpotEngagement are populated
                return {
                    id: eng.id,
                    properties: {
                        hs_object_id: eng.properties.hs_object_id || eng.id,
                        hs_engagement_type: eng.properties.hs_engagement_type,
                        hs_timestamp: eng.properties.hs_timestamp,
                        hs_body_preview: eng.properties.hs_body_preview,
                        hs_email_subject: eng.properties.hs_email_subject,
                        hs_email_direction: eng.properties.hs_email_direction,
                        // hs_meeting_title: eng.properties.hs_meeting_title,
                        createdate: eng.properties.createdate ||
                            new Date(eng.createdAt).toISOString(),
                        lastmodifieddate: eng.properties.lastmodifieddate ||
                            new Date(eng.updatedAt).toISOString(),
                        ...eng.properties, // include any other returned properties
                    },
                    // Associations are not typically returned in detail by engagement search,
                    // but if they were, you'd map them here.
                    // associations: eng.associations ? mapAssociations(eng.associations) : undefined,
                    createdAt: eng.createdAt.toISOString(),
                    updatedAt: eng.updatedAt.toISOString(),
                    archived: eng.archived || false,
                };
            })
            : [];
        return {
            ok: true,
            data: {
                success: true, // Retain success from original GetContactActivitiesResponse
                activities,
                nextPage: response.paging?.next?.after,
                message: activities.length > 0
                    ? 'Activities retrieved.'
                    : 'No activities found matching criteria.',
            },
        };
    }
    catch (error) {
        console.error(`Error fetching HubSpot contact activities for contact ${contactId}, userId ${userId}:`, error.message);
        let errorMessage = `Failed to fetch contact activities: ${error.message}`;
        let errorCode = 'HUBSPOT_API_ERROR';
        let errorDetails = error;
        if (error.response && error.response.body) {
            console.error('HubSpot API Error Body:', error.response.body);
            try {
                const errorBodyString = Buffer.isBuffer(error.response.body)
                    ? error.response.body.toString()
                    : error.response.body;
                const errorBody = JSON.parse(errorBodyString);
                errorDetails = errorBody;
                if (errorBody && errorBody.message) {
                    errorMessage = errorBody.message;
                    if (errorBody.category === 'VALIDATION_ERROR')
                        errorCode = 'VALIDATION_ERROR';
                }
            }
            catch (parseError) {
                console.error('Could not parse HubSpot error body:', parseError);
            }
        }
        return {
            ok: false,
            error: { code: errorCode, message: errorMessage, details: errorDetails },
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaHVic3BvdFNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImh1YnNwb3RTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLHFCQUFxQixDQUFDO0FBQzdDLE9BQU8sRUFBRSxPQUFPLEVBQUUsTUFBTSxpQkFBaUIsQ0FBQztBQUMxQyxPQUFPLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSx3QkFBd0IsQ0FBQztBQVc3RCxPQUFPLEVBQ0wsMENBQTBDLEVBQzFDLHNCQUFzQixHQUN2QixNQUFNLG9CQUFvQixDQUFDO0FBQzVCLE9BQU8sRUFBRSxnQkFBZ0IsRUFBRSxNQUFNLGVBQWUsQ0FBQztBQU9qRCxNQUFNLHlDQUF5QyxHQUFHLEdBQUcsQ0FBQztBQUN0RCxNQUFNLDJDQUEyQyxHQUFHLEtBQUssQ0FBQztBQUMxRCxNQUFNLDhDQUE4QyxHQUFHLE1BQU0sQ0FBQztBQUU5RCxLQUFLLFVBQVUsZ0JBQWdCLENBQUMsTUFBYztJQUM1QyxNQUFNLEtBQUssR0FBRzs7Ozs7O0tBTVgsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHO1FBQ2hCLE1BQU07UUFDTixXQUFXLEVBQUUsaUJBQWlCO0tBQy9CLENBQUM7SUFDRixNQUFNLFFBQVEsR0FBRyxNQUFNLG1CQUFtQixDQUV2QyxLQUFLLEVBQUUsU0FBUyxFQUFFLG1CQUFtQixFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQ2xELElBQUksUUFBUSxDQUFDLGdCQUFnQixJQUFJLFFBQVEsQ0FBQyxnQkFBZ0IsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7UUFDdEUsT0FBTyxPQUFPLENBQUMsUUFBUSxDQUFDLGdCQUFnQixDQUFDLENBQUMsQ0FBQyxDQUFDLGdCQUFnQixDQUFDLENBQUM7SUFDaEUsQ0FBQztJQUNELE9BQU8sSUFBSSxDQUFDO0FBQ2QsQ0FBQztBQUVELE1BQU0sZ0JBQWdCLEdBQUcsS0FBSyxFQUFFLE1BQWMsRUFBRSxFQUFF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T0FBTyxVQUFVLEVBQUUsQ0FBQztnQkFDcEIsT0FBTyxDQUFDLEtBQUssQ0FBQyxxQ0FBcUMsRUFBRSxVQUFVLENBQUMsQ0FBQztZQUNuRSxDQUFDO1FBQ0gsQ0FBQztRQUNELE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRSxFQUFFLElBQUksRUFBRSxTQUFTLEVBQUUsT0FBTyxFQUFFLFlBQVksRUFBRSxPQUFPLEVBQUUsWUFBWSxFQUFFO1NBQ3pFLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IENsaWVudCB9IGZyb20gJ0BodWJzcG90L2FwaS1jbGllbnQnO1xuaW1wb3J0IHsgZGVjcnlwdCB9IGZyb20gJy4uL19saWJzL2NyeXB0byc7XG5pbXBvcnQgeyBleGVjdXRlR3JhcGhRTFF1ZXJ5IH0gZnJvbSAnLi4vX2xpYnMvZ3JhcGhxbENsaWVudCc7XG5pbXBvcnQge1xuICBIdWJTcG90Q29udGFjdFByb3BlcnRpZXMsXG4gIEh1YlNwb3RDb250YWN0LFxuICBIdWJTcG90U2tpbGxSZXNwb25zZSxcbiAgQ3JlYXRlSHViU3BvdENvbnRhY3RSZXNwb25zZSxcbiAgSHViU3BvdEVtYWlsRW5nYWdlbWVudFByb3BlcnRpZXMsXG4gIEh1YlNwb3RFbmdhZ2VtZW50LFxuICBMb2dFbmdhZ2VtZW50UmVzcG9uc2UsXG4gIEdldENvbnRhY3RBY3Rpdml0aWVzUmVzcG9uc2UsXG59IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7XG4gIEFUT01fU0xBQ0tfSFVCU1BPVF9OT1RJRklDQVRJT05fQ0hBTk5FTF9JRCxcbiAgQVRPTV9IVUJTUE9UX1BPUlRBTF9JRCxcbn0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IHNlbmRTbGFja01lc3NhZ2UgfSBmcm9tICcuL3NsYWNrU2tpbGxzJztcbmltcG9ydCB7XG4gIFB1YmxpY09iamVjdFNlYXJjaFJlcXVlc3QsXG4gIENvbGxlY3Rpb25SZXNwb25zZVNpbXBsZVB1YmxpY09iamVjdEZvcndhcmRQYWdpbmcsXG4gIFNpbXBsZVB1YmxpY09iamVjdElucHV0LFxufSBmcm9tICdAaHVic3BvdC9hcGktY2xpZW50L2xpYi9jb2RlZ2VuL2NybS9lbmdhZ2VtZW50cy9pbmRleC5qcyc7XG5cbmNvbnN0IENPTlRBQ1RfVE9fRU5HQUdFTUVOVF9BU1NPQ0lBVElPTl9UWVBFX0lEID0gMjAzO1xuY29uc3QgQ09OVEFDVF9PQkpFQ1RfVFlQRV9JRF9GT1JfQVNTT0NJQVRJT05TX0FQSSA9ICcwLTEnO1xuY29uc3QgRU5HQUdFTUVOVF9PQkpFQ1RfVFlQRV9JRF9GT1JfQVNTT0NJQVRJT05TX0FQSSA9ICcwLTMxJztcblxuYXN5bmMgZnVuY3Rpb24gZ2V0SHVic3BvdEFwaUtleSh1c2VySWQ6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nIHwgbnVsbD4ge1xuICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgR2V0VXNlckNyZWRlbnRpYWwoJHVzZXJJZDogU3RyaW5nISwgJHNlcnZpY2VOYW1lOiBTdHJpbmchKSB7XG4gICAgICAgICAgICB1c2VyX2NyZWRlbnRpYWxzKHdoZXJlOiB7dXNlcl9pZDoge19lcTogJHVzZXJJZH0sIHNlcnZpY2VfbmFtZToge19lcTogJHNlcnZpY2VOYW1lfX0pIHtcbiAgICAgICAgICAgICAgICBlbmNyeXB0ZWRfc2VjcmV0XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgO1xuICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgdXNlcklkLFxuICAgIHNlcnZpY2VOYW1lOiAnaHVic3BvdF9hcGlfa2V5JyxcbiAgfTtcbiAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICB1c2VyX2NyZWRlbnRpYWxzOiB7IGVuY3J5cHRlZF9zZWNyZXQ6IHN0cmluZyB9W107XG4gIH0+KHF1ZXJ5LCB2YXJpYWJsZXMsICdHZXRVc2VyQ3JlZGVudGlhbCcsIHVzZXJJZCk7XG4gIGlmIChyZXNwb25zZS51c2VyX2NyZWRlbnRpYWxzICYmIHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHMubGVuZ3RoID4gMCkge1xuICAgIHJldHVybiBkZWNyeXB0KHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHNbMF0uZW5jcnlwdGVkX3NlY3JldCk7XG4gIH1cbiAgcmV0dXJuIG51bGw7XG59XG5cbmNvbnN0IGdldEh1YnNwb3RDbGllbnQgPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgY29uc3QgYXBpS2V5ID0gYXdhaXQgZ2V0SHVic3BvdEFwaUtleSh1c2VySWQpO1xuICBpZiAoIWFwaUtleSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0h1YlNwb3QgQVBJIGtleSBub3QgY29uZmlndXJlZCBmb3IgdGhpcyB1c2VyLicpO1xuICAgIHJldHVybiBudWxsO1xuICB9XG4gIHJldHVybiBuZXcgQ2xpZW50KHsgYXBpS2V5IH0pO1xufTtcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldEh1YlNwb3RDb250YWN0QnlFbWFpbChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVtYWlsOiBzdHJpbmdcbik6IFByb21pc2U8SHViU3BvdFNraWxsUmVzcG9uc2U8SHViU3BvdENvbnRhY3QgfCBudWxsPj4ge1xuICAvLyBSZXR1cm4gbnVsbCBpbiBkYXRhIGlmIG5vdCBmb3VuZCBidXQgbm8gZXJyb3JcbiAgY29uc29sZS5sb2coXG4gICAgYGdldEh1YlNwb3RDb250YWN0QnlFbWFpbCBjYWxsZWQgZm9yIHVzZXJJZDogJHt1c2VySWR9LCBlbWFpbDogJHtlbWFpbH1gXG4gICk7XG4gIGNvbnN0IGh1YnNwb3RDbGllbnQgPSBhd2FpdCBnZXRIdWJzcG90Q2xpZW50KHVzZXJJZCk7XG4gIGlmICghaHVic3BvdENsaWVudCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0h1YlNwb3QgQVBJIGtleSBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgaWYgKCFlbWFpbCB8fCBlbWFpbC50cmltKCkgPT09ICcnKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0VtYWlsIHBhcmFtZXRlciBpcyByZXF1aXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGh1YnNwb3RDbGllbnQuY3JtLmNvbnRhY3RzLnNlYXJjaEFwaS5kb1NlYXJjaCh7XG4gICAgICBxdWVyeTogZW1haWwsIC8vIE5vdGU6IFVzaW5nIGVtYWlsIGRpcmVjdGx5IGluIHF1ZXJ5IG1pZ2h0IGJlIHRvbyBicm9hZC4gU3BlY2lmaWMgcHJvcGVydHkgZmlsdGVyIGlzIGJldHRlci5cbiAgICAgIHByb3BlcnRpZXM6IFtcbiAgICAgICAgJ2VtYWlsJyxcbiAgICAgICAgJ2ZpcnN0bmFtZScsXG4gICAgICAgICdsYXN0bmFtZScsXG4gICAgICAgICdjb21wYW55JyxcbiAgICAgICAgJ2hzX29iamVjdF9pZCcsXG4gICAgICAgICdjcmVhdGVkYXRlJyxcbiAgICAgICAgJ2xhc3Rtb2RpZmllZGRhdGUnLFxuICAgICAgXSxcbiAgICAgIGZpbHRlckdyb3VwczogW1xuICAgICAgICB7XG4gICAgICAgICAgZmlsdGVyczogW1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICBwcm9wZXJ0eU5hbWU6ICdlbWFpbCcsXG4gICAgICAgICAgICAgIG9wZXJhdG9yOiAnRVEnLFxuICAgICAgICAgICAgICB2YWx1ZTogZW1haWwsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIF0sXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgICAgbGltaXQ6IDEsIC8vIFdlIG9ubHkgZXhwZWN0IG9uZSBjb250YWN0IGJ5IHByaW1hcnkgZW1haWxcbiAgICB9KTtcblxuICAgIGlmIChyZXNwb25zZS5yZXN1bHRzICYmIHJlc3BvbnNlLnJlc3VsdHMubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3QgY29udGFjdERhdGEgPSByZXNwb25zZS5yZXN1bHRzWzBdO1xuICAgICAgY29uc3QgY29udGFjdDogSHViU3BvdENvbnRhY3QgPSB7XG4gICAgICAgIGlkOiBjb250YWN0RGF0YS5pZCxcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIGhzX29iamVjdF9pZDogY29udGFjdERhdGEucHJvcGVydGllcy5oc19vYmplY3RfaWQsXG4gICAgICAgICAgY3JlYXRlZGF0ZTogY29udGFjdERhdGEucHJvcGVydGllcy5jcmVhdGVkYXRlLFxuICAgICAgICAgIGxhc3Rtb2RpZmllZGRhdGU6IGNvbnRhY3REYXRhLnByb3BlcnRpZXMubGFzdG1vZGlmaWVkZGF0ZSxcbiAgICAgICAgICBlbWFpbDogY29udGFjdERhdGEucHJvcGVydGllcy5lbWFpbCxcbiAgICAgICAgICBmaXJzdG5hbWU6IGNvbnRhY3REYXRhLnByb3BlcnRpZXMuZmlyc3RuYW1lLFxuICAgICAgICAgIGxhc3RuYW1lOiBjb250YWN0RGF0YS5wcm9wZXJ0aWVzLmxhc3RuYW1lLFxuICAgICAgICAgIGNvbXBhbnk6IGNvbnRhY3REYXRhLnByb3BlcnRpZXMuY29tcGFueSxcbiAgICAgICAgfSxcbiAgICAgICAgY3JlYXRlZEF0OiBjb250YWN0RGF0YS5jcmVhdGVkQXQudG9JU09TdHJpbmcoKSxcbiAgICAgICAgdXBkYXRlZEF0OiBjb250YWN0RGF0YS51cGRhdGVkQXQudG9JU09TdHJpbmcoKSxcbiAgICAgICAgYXJjaGl2ZWQ6IGNvbnRhY3REYXRhLmFyY2hpdmVkIHx8IGZhbHNlLFxuICAgICAgfTtcbiAgICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBjb250YWN0IH07XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnNvbGUubG9nKGBObyBIdWJTcG90IGNvbnRhY3QgZm91bmQgZm9yIGVtYWlsOiAke2VtYWlsfWApO1xuICAgICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IG51bGwgfTsgLy8gU3VjY2VzcywgYnV0IG5vIGNvbnRhY3QgZm91bmRcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEVycm9yIGZldGNoaW5nIEh1YlNwb3QgY29udGFjdCBieSBlbWFpbCAke2VtYWlsfSBmb3IgdXNlcklkICR7dXNlcklkfTpgLFxuICAgICAgZXJyb3IubWVzc2FnZVxuICAgICk7XG4gICAgbGV0IGVycm9yTWVzc2FnZSA9IGBGYWlsZWQgdG8gZmV0Y2ggY29udGFjdCBieSBlbWFpbDogJHtlcnJvci5tZXNzYWdlfWA7XG4gICAgbGV0IGVycm9yQ29kZSA9ICdIVUJTUE9UX0FQSV9FUlJPUic7XG4gICAgaWYgKGVycm9yLnJlc3BvbnNlICYmIGVycm9yLnJlc3BvbnNlLmJvZHkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ0h1YlNwb3QgQVBJIEVycm9yIEJvZHk6JywgZXJyb3IucmVzcG9uc2UuYm9keSk7XG4gICAgICB0cnkge1xuICAgICAgICBjb25zdCBlcnJvckJvZHlTdHJpbmcgPSBCdWZmZXIuaXNCdWZmZXIoZXJyb3IucmVzcG9uc2UuYm9keSlcbiAgICAgICAgICA/IGVycm9yLnJlc3BvbnNlLmJvZHkudG9TdHJpbmcoKVxuICAgICAgICAgIDogZXJyb3IucmVzcG9uc2UuYm9keTtcbiAgICAgICAgY29uc3QgZXJyb3JCb2R5ID0gSlNPTi5wYXJzZShlcnJvckJvZHlTdHJpbmcpO1xuICAgICAgICBpZiAoZXJyb3JCb2R5ICYmIGVycm9yQm9keS5tZXNzYWdlKSB7XG4gICAgICAgICAgZXJyb3JNZXNzYWdlID0gZXJyb3JCb2R5Lm1lc3NhZ2U7XG4gICAgICAgICAgaWYgKGVycm9yQm9keS5jYXRlZ29yeSA9PT0gJ1ZBTElEQVRJT05fRVJST1InKVxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ1ZBTElEQVRJT05fRVJST1InO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChwYXJzZUVycm9yKSB7XG4gICAgICAgIC8qIERvIG5vdGhpbmcsIHVzZSBnZW5lcmljIG1lc3NhZ2UgKi9cbiAgICAgIH1cbiAgICB9XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6IGVycm9yQ29kZSwgbWVzc2FnZTogZXJyb3JNZXNzYWdlLCBkZXRhaWxzOiBlcnJvciB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZUh1YlNwb3RDb250YWN0KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY29udGFjdFByb3BlcnRpZXM6IEh1YlNwb3RDb250YWN0UHJvcGVydGllc1xuKTogUHJvbWlzZTxIdWJTcG90U2tpbGxSZXNwb25zZTxDcmVhdGVIdWJTcG90Q29udGFjdFJlc3BvbnNlPj4ge1xuICAvLyBVcGRhdGVkIHJldHVybiB0eXBlXG4gIGNvbnNvbGUubG9nKFxuICAgIGBjcmVhdGVIdWJTcG90Q29udGFjdCBjYWxsZWQgZm9yIHVzZXJJZDogJHt1c2VySWR9IHdpdGggcHJvcGVydGllczpgLFxuICAgIGNvbnRhY3RQcm9wZXJ0aWVzXG4gICk7XG4gIGNvbnN0IGh1YnNwb3RDbGllbnQgPSBhd2FpdCBnZXRIdWJzcG90Q2xpZW50KHVzZXJJZCk7XG4gIGlmICghaHVic3BvdENsaWVudCkge1xuICAgIC8vIENvbnNpc3RlbnQgZXJyb3Igc3RydWN0dXJlXG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdDT05GSUdfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnSHViU3BvdCBBUEkga2V5IG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICBpZiAoIWNvbnRhY3RQcm9wZXJ0aWVzLmVtYWlsKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0VtYWlsIGlzIHJlcXVpcmVkIHRvIGNyZWF0ZSBhIEh1YlNwb3QgY29udGFjdC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBjcmVhdGVSZXNwb25zZSA9IGF3YWl0IGh1YnNwb3RDbGllbnQuY3JtLmNvbnRhY3RzLmJhc2ljQXBpLmNyZWF0ZSh7XG4gICAgICBwcm9wZXJ0aWVzOiBjb250YWN0UHJvcGVydGllcyxcbiAgICB9KTtcblxuICAgIC8vIE1hcCB0aGUgcmVzcG9uc2UgdG8gSHViU3BvdENvbnRhY3QsIGVuc3VyaW5nIGFsbCBmaWVsZHMgYXJlIGNvdmVyZWRcbiAgICBjb25zdCBjcmVhdGVkQ29udGFjdDogSHViU3BvdENvbnRhY3QgPSB7XG4gICAgICBpZDogY3JlYXRlUmVzcG9uc2UuaWQsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIGhzX29iamVjdF9pZDogY3JlYXRlUmVzcG9uc2UucHJvcGVydGllcy5oc19vYmplY3RfaWQsXG4gICAgICAgIGNyZWF0ZWRhdGU6IGNyZWF0ZVJlc3BvbnNlLnByb3BlcnRpZXMuY3JlYXRlZGF0ZSxcbiAgICAgICAgbGFzdG1vZGlmaWVkZGF0ZTogY3JlYXRlUmVzcG9uc2UucHJvcGVydGllcy5sYXN0bW9kaWZpZWRkYXRlLFxuICAgICAgICBlbWFpbDogY3JlYXRlUmVzcG9uc2UucHJvcGVydGllcy5lbWFpbCxcbiAgICAgICAgZmlyc3RuYW1lOiBjcmVhdGVSZXNwb25zZS5wcm9wZXJ0aWVzLmZpcnN0bmFtZSxcbiAgICAgICAgbGFzdG5hbWU6IGNyZWF0ZVJlc3BvbnNlLnByb3BlcnRpZXMubGFzdG5hbWUsXG4gICAgICAgIGNvbXBhbnk6IGNyZWF0ZVJlc3BvbnNlLnByb3BlcnRpZXMuY29tcGFueSxcbiAgICAgICAgLy8gSW5jbHVkZSBhbnkgb3RoZXIgY3VzdG9tIHByb3BlcnRpZXMgeW91IGV4cGVjdCBvciB0aGF0IGFyZSByZXR1cm5lZFxuICAgICAgfSxcbiAgICAgIGNyZWF0ZWRBdDogY3JlYXRlUmVzcG9uc2UuY3JlYXRlZEF0LnRvSVNPU3RyaW5nKCksXG4gICAgICB1cGRhdGVkQXQ6IGNyZWF0ZVJlc3BvbnNlLnVwZGF0ZWRBdC50b0lTT1N0cmluZygpLFxuICAgICAgYXJjaGl2ZWQ6IGNyZWF0ZVJlc3BvbnNlLmFyY2hpdmVkIHx8IGZhbHNlLCAvLyBEZWZhdWx0IHRvIGZhbHNlIGlmIHVuZGVmaW5lZFxuICAgIH07XG5cbiAgICAvLyBTZW5kIFNsYWNrIG5vdGlmaWNhdGlvbiBpZiBjaGFubmVsIElEIGlzIGNvbmZpZ3VyZWRcbiAgICBpZiAoQVRPTV9TTEFDS19IVUJTUE9UX05PVElGSUNBVElPTl9DSEFOTkVMX0lEKSB7XG4gICAgICBsZXQgc2xhY2tNZXNzYWdlID0gYE5ldyBIdWJTcG90IENvbnRhY3QgQ3JlYXRlZCBieSB1c2VyICR7dXNlcklkfTpcXG5gO1xuICAgICAgc2xhY2tNZXNzYWdlICs9IGBOYW1lOiAke2NyZWF0ZWRDb250YWN0LnByb3BlcnRpZXMuZmlyc3RuYW1lIHx8ICcnfSAke2NyZWF0ZWRDb250YWN0LnByb3BlcnRpZXMubGFzdG5hbWUgfHwgJyd9XFxuYDtcbiAgICAgIHNsYWNrTWVzc2FnZSArPSBgRW1haWw6ICR7Y3JlYXRlZENvbnRhY3QucHJvcGVydGllcy5lbWFpbH1cXG5gO1xuICAgICAgaWYgKGNyZWF0ZWRDb250YWN0LnByb3BlcnRpZXMuY29tcGFueSkge1xuICAgICAgICBzbGFja01lc3NhZ2UgKz0gYENvbXBhbnk6ICR7Y3JlYXRlZENvbnRhY3QucHJvcGVydGllcy5jb21wYW55fVxcbmA7XG4gICAgICB9XG4gICAgICBpZiAoQVRPTV9IVUJTUE9UX1BPUlRBTF9JRCkge1xuICAgICAgICBzbGFja01lc3NhZ2UgKz0gYExpbms6IGh0dHBzOi8vYXBwLmh1YnNwb3QuY29tL2NvbnRhY3RzLyR7QVRPTV9IVUJTUE9UX1BPUlRBTF9JRH0vY29udGFjdC8ke2NyZWF0ZWRDb250YWN0LmlkfVxcbmA7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzbGFja01lc3NhZ2UgKz0gYENvbnRhY3QgSUQ6ICR7Y3JlYXRlZENvbnRhY3QuaWR9XFxuYDtcbiAgICAgIH1cblxuICAgICAgLy8gRmlyZS1hbmQtZm9yZ2V0IFNsYWNrIG1lc3NhZ2UsIGRvbid0IGxldCBpdHMgZmFpbHVyZSBibG9jayB0aGUgbWFpbiByZXNwb25zZS5cbiAgICAgIHNlbmRTbGFja01lc3NhZ2UoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgQVRPTV9TTEFDS19IVUJTUE9UX05PVElGSUNBVElPTl9DSEFOTkVMX0lELFxuICAgICAgICBzbGFja01lc3NhZ2VcbiAgICAgIClcbiAgICAgICAgLnRoZW4oKHNsYWNrUmVzKSA9PiB7XG4gICAgICAgICAgaWYgKCFzbGFja1Jlcy5vaykge1xuICAgICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgICBgRmFpbGVkIHRvIHNlbmQgU2xhY2sgbm90aWZpY2F0aW9uIGZvciBuZXcgSHViU3BvdCBjb250YWN0ICR7Y3JlYXRlZENvbnRhY3QuaWR9OiAke3NsYWNrUmVzLmVycm9yfWBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgICBgU2xhY2sgbm90aWZpY2F0aW9uIHNlbnQgZm9yIG5ldyBIdWJTcG90IGNvbnRhY3QgJHtjcmVhdGVkQ29udGFjdC5pZH0uIE1lc3NhZ2UgdHM6ICR7c2xhY2tSZXMudHN9YFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0pXG4gICAgICAgIC5jYXRjaCgoc2xhY2tFcnIpID0+IHtcbiAgICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgICAgYEVycm9yIHNlbmRpbmcgU2xhY2sgbm90aWZpY2F0aW9uIGZvciBuZXcgSHViU3BvdCBjb250YWN0ICR7Y3JlYXRlZENvbnRhY3QuaWR9OmAsXG4gICAgICAgICAgICBzbGFja0VyclxuICAgICAgICAgICk7XG4gICAgICAgIH0pO1xuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSwgLy8gc3VjY2Vzc1xuICAgICAgZGF0YToge1xuICAgICAgICAvLyBUaGUgYWN0dWFsIHBheWxvYWQgYXMgcGVyIENyZWF0ZUh1YlNwb3RDb250YWN0UmVzcG9uc2VcbiAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgICAgY29udGFjdElkOiBjcmVhdGVSZXNwb25zZS5pZCxcbiAgICAgICAgbWVzc2FnZTogJ0NvbnRhY3QgY3JlYXRlZCBzdWNjZXNzZnVsbHkgaW4gSHViU3BvdC4nLFxuICAgICAgICBodWJTcG90Q29udGFjdDogY3JlYXRlZENvbnRhY3QsXG4gICAgICB9LFxuICAgIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEVycm9yIGNyZWF0aW5nIEh1YlNwb3QgY29udGFjdCBmb3IgdXNlcklkICR7dXNlcklkfSB3aXRoIGVtYWlsICR7Y29udGFjdFByb3BlcnRpZXMuZW1haWx9OmAsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICBsZXQgZXJyb3JNZXNzYWdlID0gYEZhaWxlZCB0byBjcmVhdGUgY29udGFjdCBpbiBIdWJTcG90OiAke2Vycm9yLm1lc3NhZ2V9YDtcbiAgICBsZXQgZXJyb3JDb2RlID0gJ0hVQlNQT1RfQVBJX0VSUk9SJztcbiAgICBsZXQgZXJyb3JEZXRhaWxzID0gZXJyb3I7XG5cbiAgICBpZiAoZXJyb3IucmVzcG9uc2UgJiYgZXJyb3IucmVzcG9uc2UuYm9keSkge1xuICAgICAgY29uc29sZS5lcnJvcignSHViU3BvdCBBUEkgRXJyb3IgQm9keTonLCBlcnJvci5yZXNwb25zZS5ib2R5KTtcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGVycm9yQm9keVN0cmluZyA9IEJ1ZmZlci5pc0J1ZmZlcihlcnJvci5yZXNwb25zZS5ib2R5KVxuICAgICAgICAgID8gZXJyb3IucmVzcG9uc2UuYm9keS50b1N0cmluZygpXG4gICAgICAgICAgOiBlcnJvci5yZXNwb25zZS5ib2R5O1xuICAgICAgICBjb25zdCBlcnJvckJvZHkgPSBKU09OLnBhcnNlKGVycm9yQm9keVN0cmluZyk7XG4gICAgICAgIGVycm9yRGV0YWlscyA9IGVycm9yQm9keTsgLy8gU3RvcmUgcGFyc2VkIGJvZHkgYXMgZGV0YWlsc1xuICAgICAgICBpZiAoZXJyb3JCb2R5ICYmIGVycm9yQm9keS5tZXNzYWdlKSB7XG4gICAgICAgICAgZXJyb3JNZXNzYWdlID0gZXJyb3JCb2R5Lm1lc3NhZ2U7IC8vIFVzZSBIdWJTcG90J3MgbWVzc2FnZVxuICAgICAgICAgIGlmIChlcnJvckJvZHkuY2F0ZWdvcnkgPT09ICdDT05GTElDVCcpIHtcbiAgICAgICAgICAgIGVycm9yQ29kZSA9ICdDT05GTElDVF9FUlJPUic7IC8vIE1vcmUgc3BlY2lmaWMgZXJyb3IgY29kZVxuICAgICAgICAgICAgLy8gS2VlcCBIdWJTcG90J3MgbWVzc2FnZSBhcyBpdCBtaWdodCBiZSBtb3JlIGluZm9ybWF0aXZlIGUuZy4gXCJDb250YWN0IGFscmVhZHkgZXhpc3RzLiBFeGlzdGluZyBJRDogWFhYWFhcIlxuICAgICAgICAgIH0gZWxzZSBpZiAoZXJyb3JCb2R5LmNhdGVnb3J5ID09PSAnVkFMSURBVElPTl9FUlJPUicpIHtcbiAgICAgICAgICAgIGVycm9yQ29kZSA9ICdWQUxJREFUSU9OX0VSUk9SJztcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH0gY2F0Y2ggKHBhcnNlRXJyb3IpIHtcbiAgICAgICAgY29uc29sZS5lcnJvcignQ291bGQgbm90IHBhcnNlIEh1YlNwb3QgZXJyb3IgYm9keTonLCBwYXJzZUVycm9yKTtcbiAgICAgICAgLy8gZXJyb3JEZXRhaWxzIHJlbWFpbnMgdGhlIG9yaWdpbmFsIGVycm9yIG9iamVjdFxuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgY29kZTogZXJyb3JDb2RlLCBtZXNzYWdlOiBlcnJvck1lc3NhZ2UsIGRldGFpbHM6IGVycm9yRGV0YWlscyB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGxvZ0VtYWlsVG9IdWJTcG90Q29udGFjdChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNvbnRhY3RJZDogc3RyaW5nLFxuICBlbWFpbERldGFpbHM6IEh1YlNwb3RFbWFpbEVuZ2FnZW1lbnRQcm9wZXJ0aWVzXG4pOiBQcm9taXNlPEh1YlNwb3RTa2lsbFJlc3BvbnNlPExvZ0VuZ2FnZW1lbnRSZXNwb25zZT4+IHtcbiAgLy8gVXBkYXRlZCByZXR1cm4gdHlwZVxuICBjb25zb2xlLmxvZyhcbiAgICBgbG9nRW1haWxUb0h1YlNwb3RDb250YWN0IGNhbGxlZCBmb3IgdXNlcklkOiAke3VzZXJJZH0sIGNvbnRhY3RJZDogJHtjb250YWN0SWR9YFxuICApO1xuICBjb25zdCBodWJzcG90Q2xpZW50ID0gYXdhaXQgZ2V0SHVic3BvdENsaWVudCh1c2VySWQpO1xuICBpZiAoIWh1YnNwb3RDbGllbnQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdIdWJTcG90IEFQSSBrZXkgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGlmICghY29udGFjdElkKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0NvbnRhY3QgSUQgaXMgcmVxdWlyZWQgdG8gbG9nIGFuIGVtYWlsLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgaWYgKFxuICAgICFlbWFpbERldGFpbHMgfHxcbiAgICAhZW1haWxEZXRhaWxzLmFjdGl2aXR5VGltZXN0YW1wIHx8XG4gICAgIWVtYWlsRGV0YWlscy5zdWJqZWN0IHx8XG4gICAgIWVtYWlsRGV0YWlscy5odG1sQm9keVxuICApIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdFbWFpbCBkZXRhaWxzIChhY3Rpdml0eVRpbWVzdGFtcCwgc3ViamVjdCwgaHRtbEJvZHkpIGFyZSByZXF1aXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgY29uc3QgZW5nYWdlbWVudElucHV0OiBTaW1wbGVQdWJsaWNPYmplY3RJbnB1dCA9IHtcbiAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICBoc190aW1lc3RhbXA6IGVtYWlsRGV0YWlscy5hY3Rpdml0eVRpbWVzdGFtcC50b1N0cmluZygpLCAvLyBNdXN0IGJlIHN0cmluZyBpbiBlcG9jaCBtaWxsaXNlY29uZHNcbiAgICAgIGhzX2VuZ2FnZW1lbnRfdHlwZTogJ0VNQUlMJyxcbiAgICAgIGhzX2VtYWlsX3N1YmplY3Q6IGVtYWlsRGV0YWlscy5zdWJqZWN0LFxuICAgICAgaHNfYm9keV9wcmV2aWV3OiBlbWFpbERldGFpbHMuaHRtbEJvZHkuc3Vic3RyaW5nKDAsIDUxMiksIC8vIE1heCBsZW5ndGggZm9yIHByZXZpZXdcbiAgICAgIC8vIGhzX2VtYWlsX2h0bWxfYm9keTogZW1haWxEZXRhaWxzLmh0bWxCb2R5LCAvLyBOb3QgYSBzdGFuZGFyZCBwcm9wZXJ0eSBmb3Igc2ltcGxlIGVuZ2FnZW1lbnQgbG9nZ2luZywgdXNlIG1ldGFkYXRhIG9yIG5vdGVzIGlmIGZ1bGwgSFRNTCBuZWVkZWQuXG4gICAgICAvLyBoc19lbmdhZ2VtZW50X3NvdXJjZTogJ0NSTV9VSScsIC8vIEV4YW1wbGU6IGlmIGxvZ2dlZCBtYW51YWxseSBieSBhIHVzZXIuICdJTlRFR1JBVElPTicgaWYgYnkgeW91ciBhcHAuXG4gICAgICAvLyBoc19lbmdhZ2VtZW50X3NvdXJjZV9pZDogJ1lPVVJfQVBQX0lEJywgLy8gSWYgdXNpbmcgJ0lOVEVHUkFUSU9OJ1xuICAgIH0sXG4gICAgYXNzb2NpYXRpb25zOiBbXG4gICAgICB7XG4gICAgICAgIHRvOiB7IGlkOiBjb250YWN0SWQgfSxcbiAgICAgICAgdHlwZXM6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBhc3NvY2lhdGlvbkNhdGVnb3J5OiAnSFVCU1BPVF9ERUZJTkVEJyxcbiAgICAgICAgICAgIGFzc29jaWF0aW9uVHlwZUlkOiBDT05UQUNUX1RPX0VOR0FHRU1FTlRfQVNTT0NJQVRJT05fVFlQRV9JRCwgLy8gQ29udGFjdCB0byBFbmdhZ2VtZW50XG4gICAgICAgICAgfSxcbiAgICAgICAgXSxcbiAgICAgIH0sXG4gICAgXSxcbiAgfTtcblxuICBpZiAoZW1haWxEZXRhaWxzLmRpcmVjdGlvbikge1xuICAgIGVuZ2FnZW1lbnRJbnB1dC5wcm9wZXJ0aWVzLmhzX2VtYWlsX2RpcmVjdGlvbiA9IGVtYWlsRGV0YWlscy5kaXJlY3Rpb247XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IGNyZWF0ZVJlc3BvbnNlID1cbiAgICAgIGF3YWl0IGh1YnNwb3RDbGllbnQuY3JtLmVuZ2FnZW1lbnRzLmJhc2ljQXBpLmNyZWF0ZShlbmdhZ2VtZW50SW5wdXQpO1xuXG4gICAgLy8gTWFwIHRoZSByZXNwb25zZSB0byBIdWJTcG90RW5nYWdlbWVudCwgZW5zdXJpbmcgYWxsIGZpZWxkcyBhcmUgY292ZXJlZFxuICAgIC8vIE5vdGU6IFRoZSByZXNwb25zZSBmcm9tIGVuZ2FnZW1lbnQgY3JlYXRpb24gbWlnaHQgYmUgc2ltcGxlciB0aGFuIGEgZnVsbCBlbmdhZ2VtZW50IHNlYXJjaCByZXN1bHQuXG4gICAgLy8gV2UgbWlnaHQgbmVlZCB0byBmZXRjaCB0aGUgZW5nYWdlbWVudCBzZXBhcmF0ZWx5IGlmIG1vcmUgZGV0YWlscyBhcmUgbmVlZGVkIGltbWVkaWF0ZWx5LlxuICAgIGNvbnN0IGNyZWF0ZWRFbmdhZ2VtZW50OiBIdWJTcG90RW5nYWdlbWVudCA9IHtcbiAgICAgIGlkOiBjcmVhdGVSZXNwb25zZS5pZCxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgaHNfb2JqZWN0X2lkOlxuICAgICAgICAgIGNyZWF0ZVJlc3BvbnNlLnByb3BlcnRpZXMuaHNfb2JqZWN0X2lkIHx8IGNyZWF0ZVJlc3BvbnNlLmlkLCAvLyBoc19vYmplY3RfaWQgbWlnaHQgbm90IGJlIGluIGJhc2ljIGNyZWF0ZSByZXNwb25zZSwgdXNlIGlkXG4gICAgICAgIGhzX2VuZ2FnZW1lbnRfdHlwZTogY3JlYXRlUmVzcG9uc2UucHJvcGVydGllcy5oc19lbmdhZ2VtZW50X3R5cGUgYXNcbiAgICAgICAgICB8ICdFTUFJTCdcbiAgICAgICAgICB8ICdNRUVUSU5HJywgLy8gQ2FzdCBhcyBuZWVkZWRcbiAgICAgICAgaHNfdGltZXN0YW1wOiBjcmVhdGVSZXNwb25zZS5wcm9wZXJ0aWVzLmhzX3RpbWVzdGFtcCxcbiAgICAgICAgaHNfYm9keV9wcmV2aWV3OiBjcmVhdGVSZXNwb25zZS5wcm9wZXJ0aWVzLmhzX2JvZHlfcHJldmlldyxcbiAgICAgICAgaHNfZW1haWxfc3ViamVjdDogY3JlYXRlUmVzcG9uc2UucHJvcGVydGllcy5oc19lbWFpbF9zdWJqZWN0LFxuICAgICAgICBoc19lbWFpbF9kaXJlY3Rpb246IGNyZWF0ZVJlc3BvbnNlLnByb3BlcnRpZXMuaHNfZW1haWxfZGlyZWN0aW9uIGFzXG4gICAgICAgICAgfCAnSU5DT01JTkcnXG4gICAgICAgICAgfCAnT1VUR09JTkcnLFxuICAgICAgICBjcmVhdGVkYXRlOlxuICAgICAgICAgIGNyZWF0ZVJlc3BvbnNlLnByb3BlcnRpZXMuY3JlYXRlZGF0ZSB8fFxuICAgICAgICAgIG5ldyBEYXRlKGNyZWF0ZVJlc3BvbnNlLmNyZWF0ZWRBdCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgbGFzdG1vZGlmaWVkZGF0ZTpcbiAgICAgICAgICBjcmVhdGVSZXNwb25zZS5wcm9wZXJ0aWVzLmxhc3Rtb2RpZmllZGRhdGUgfHxcbiAgICAgICAgICBuZXcgRGF0ZShjcmVhdGVSZXNwb25zZS51cGRhdGVkQXQpLnRvSVNPU3RyaW5nKCksXG4gICAgICB9LFxuICAgICAgYXNzb2NpYXRpb25zOiBjcmVhdGVSZXNwb25zZS5hc3NvY2lhdGlvbnMgYXMgYW55LCAvLyBDYXN0IGlmIG5lY2Vzc2FyeSwgb3IgbWFwIHN0cnVjdHVyZVxuICAgICAgY3JlYXRlZEF0OiBjcmVhdGVSZXNwb25zZS5jcmVhdGVkQXQudG9JU09TdHJpbmcoKSxcbiAgICAgIHVwZGF0ZWRBdDogY3JlYXRlUmVzcG9uc2UudXBkYXRlZEF0LnRvSVNPU3RyaW5nKCksXG4gICAgICBhcmNoaXZlZDogY3JlYXRlUmVzcG9uc2UuYXJjaGl2ZWQgfHwgZmFsc2UsXG4gICAgfTtcblxuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgICAgZW5nYWdlbWVudElkOiBjcmVhdGVSZXNwb25zZS5pZCxcbiAgICAgICAgbWVzc2FnZTogJ0VtYWlsIGxvZ2dlZCBzdWNjZXNzZnVsbHkgdG8gSHViU3BvdCBjb250YWN0LicsXG4gICAgICAgIGh1YlNwb3RFbmdhZ2VtZW50OiBjcmVhdGVkRW5nYWdlbWVudCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgRXJyb3IgbG9nZ2luZyBlbWFpbCB0byBIdWJTcG90IGNvbnRhY3QgJHtjb250YWN0SWR9IGZvciB1c2VySWQgJHt1c2VySWR9OmAsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICBsZXQgZXJyb3JNZXNzYWdlID0gYEZhaWxlZCB0byBsb2cgZW1haWwgdG8gSHViU3BvdDogJHtlcnJvci5tZXNzYWdlfWA7XG4gICAgbGV0IGVycm9yQ29kZSA9ICdIVUJTUE9UX0FQSV9FUlJPUic7XG4gICAgbGV0IGVycm9yRGV0YWlscyA9IGVycm9yO1xuICAgIGlmIChlcnJvci5yZXNwb25zZSAmJiBlcnJvci5yZXNwb25zZS5ib2R5KSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdIdWJTcG90IEFQSSBFcnJvciBCb2R5OicsIGVycm9yLnJlc3BvbnNlLmJvZHkpO1xuICAgICAgdHJ5IHtcbiAgICAgICAgY29uc3QgZXJyb3JCb2R5U3RyaW5nID0gQnVmZmVyLmlzQnVmZmVyKGVycm9yLnJlc3BvbnNlLmJvZHkpXG4gICAgICAgICAgPyBlcnJvci5yZXNwb25zZS5ib2R5LnRvU3RyaW5nKClcbiAgICAgICAgICA6IGVycm9yLnJlc3BvbnNlLmJvZHk7XG4gICAgICAgIGNvbnN0IGVycm9yQm9keSA9IEpTT04ucGFyc2UoZXJyb3JCb2R5U3RyaW5nKTtcbiAgICAgICAgZXJyb3JEZXRhaWxzID0gZXJyb3JCb2R5O1xuICAgICAgICBpZiAoZXJyb3JCb2R5ICYmIGVycm9yQm9keS5tZXNzYWdlKSB7XG4gICAgICAgICAgZXJyb3JNZXNzYWdlID0gZXJyb3JCb2R5Lm1lc3NhZ2U7XG4gICAgICAgICAgaWYgKGVycm9yQm9keS5jYXRlZ29yeSA9PT0gJ1ZBTElEQVRJT05fRVJST1InKVxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ1ZBTElEQVRJT05fRVJST1InO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChwYXJzZUVycm9yKSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoJ0NvdWxkIG5vdCBwYXJzZSBIdWJTcG90IGVycm9yIGJvZHk6JywgcGFyc2VFcnJvcik7XG4gICAgICB9XG4gICAgfVxuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiBlcnJvckNvZGUsIG1lc3NhZ2U6IGVycm9yTWVzc2FnZSwgZGV0YWlsczogZXJyb3JEZXRhaWxzIH0sXG4gICAgfTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0SHViU3BvdENvbnRhY3RBY3Rpdml0aWVzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY29udGFjdElkOiBzdHJpbmcsXG4gIGZpbHRlcnM/OiB7XG4gICAgYWN0aXZpdHlUeXBlcz86ICgnRU1BSUwnIHwgJ01FRVRJTkcnKVtdO1xuICAgIGxpbWl0PzogbnVtYmVyO1xuICAgIGFmdGVyPzogc3RyaW5nO1xuICAgIHNpbmNlPzogc3RyaW5nOyAvLyBJU08gRGF0ZSBzdHJpbmcgb3IgZXBvY2ggbXNcbiAgICBzb3J0PzogJ0FTQycgfCAnREVTQyc7XG4gIH1cbik6IFByb21pc2U8SHViU3BvdFNraWxsUmVzcG9uc2U8R2V0Q29udGFjdEFjdGl2aXRpZXNSZXNwb25zZT4+IHtcbiAgLy8gVXBkYXRlZCByZXR1cm4gdHlwZVxuICBjb25zb2xlLmxvZyhcbiAgICBgZ2V0SHViU3BvdENvbnRhY3RBY3Rpdml0aWVzIGNhbGxlZCBmb3IgdXNlcklkOiAke3VzZXJJZH0sIGNvbnRhY3RJZDogJHtjb250YWN0SWR9LCBmaWx0ZXJzOmAsXG4gICAgZmlsdGVyc1xuICApO1xuICBjb25zdCBodWJzcG90Q2xpZW50ID0gYXdhaXQgZ2V0SHVic3BvdENsaWVudCh1c2VySWQpO1xuICBpZiAoIWh1YnNwb3RDbGllbnQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdIdWJTcG90IEFQSSBrZXkgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBpZiAoIWNvbnRhY3RJZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdDb250YWN0IElEIGlzIHJlcXVpcmVkLicgfSxcbiAgICB9O1xuICB9XG5cbiAgY29uc3Qgc2VhcmNoUmVxdWVzdDogUHVibGljT2JqZWN0U2VhcmNoUmVxdWVzdCA9IHtcbiAgICBmaWx0ZXJHcm91cHM6IFtcbiAgICAgIHtcbiAgICAgICAgLy8gVGhpcyBmaWx0ZXIgYXR0ZW1wdHMgdG8gZmluZCBlbmdhZ2VtZW50cyBhc3NvY2lhdGVkIHdpdGggdGhlIGNvbnRhY3QuXG4gICAgICAgIC8vIFRoZSBleGFjdCBwcm9wZXJ0eU5hbWUgZm9yIGNvbnRhY3QgSUQgaW4gZW5nYWdlbWVudCBhc3NvY2lhdGlvbnMgdmlhIHNlYXJjaCBtaWdodCB2YXJ5IG9yIG1pZ2h0IG5vdCBiZSBkaXJlY3RseSBzdXBwb3J0ZWQuXG4gICAgICAgIC8vIEh1YlNwb3QncyBTZWFyY2ggQVBJIGZvciBlbmdhZ2VtZW50cyB0eXBpY2FsbHkgZmlsdGVycyBvbiBlbmdhZ2VtZW50IHByb3BlcnRpZXMsIG5vdCBhc3NvY2lhdGlvbiBwcm9wZXJ0aWVzIGRpcmVjdGx5IGluIHRoaXMgbWFubmVyLlxuICAgICAgICAvLyBBIGNvbW1vbiBwYXR0ZXJuIGlzIHRvIGZpcnN0IGdldCBhc3NvY2lhdGVkIGVuZ2FnZW1lbnQgSURzLCB0aGVuIGZldGNoL3NlYXJjaCB0aG9zZSBlbmdhZ2VtZW50cy5cbiAgICAgICAgLy8gSG93ZXZlciwgaWYgZGlyZWN0IGFzc29jaWF0aW9uIHNlYXJjaCBpcyBzdXBwb3J0ZWQsIGl0IHdvdWxkIGxvb2sgc29tZXRoaW5nIGxpa2U6XG4gICAgICAgIC8vIGZpbHRlcnM6IFt7IHByb3BlcnR5TmFtZTogJ2Fzc29jaWF0aW9ucy5jb250YWN0Jywgb3BlcmF0b3I6ICdFUScsIHZhbHVlOiBjb250YWN0SWQgfV0gLy8gVGhpcyBpcyBzcGVjdWxhdGl2ZS5cbiAgICAgICAgLy8gQSBtb3JlIHJlbGlhYmxlIHdheSBtaWdodCBiZSB0byB1c2UgYSBkZWRpY2F0ZWQgYXNzb2NpYXRpb24gcHJvcGVydHkgaWYgYXZhaWxhYmxlIG9yIHVzZSB0aGUgQXNzb2NpYXRpb25zIEFQSSBmaXJzdCAoc2VlIGFsdGVybmF0aXZlIGJlbG93KS5cbiAgICAgICAgLy8gRm9yIG5vdywgbGV0J3MgYXNzdW1lIHdlIGFyZSB0cnlpbmcgdG8gZmlsdGVyIGJ5IGEgcHJvcGVydHkgdGhhdCBpbXBsaWVzIGFzc29jaWF0aW9uIG9yIHVzZSBhIHdvcmthcm91bmQuXG4gICAgICAgIC8vICoqQ29ycmVjdGlvbioqOiBUaGUgcHJpbWFyeSBtZXRob2QgdG8gZ2V0IGFjdGl2aXRpZXMgRk9SIGEgY29udGFjdCBpcyB0byB1c2UgdGhlIEFzc29jaWF0aW9ucyBBUEkgdG8gbGlzdCBlbmdhZ2VtZW50IElEcyxcbiAgICAgICAgLy8gdGhlbiB1c2UgdGhvc2UgSURzIGluIGEgYmF0Y2ggcmVhZCBvciBzZWFyY2guIFRoZSBzZWFyY2ggYmVsb3cgaXMgbW9yZSBmb3IgZ2VuZXJhbCBlbmdhZ2VtZW50IHNlYXJjaGluZy5cbiAgICAgICAgLy8gTGV0J3MgYWRqdXN0IHRvIHVzZSB0aGUgc2VhcmNoIGJhc2VkIG9uIHByb3BlcnRpZXMgdGhhdCBtaWdodCBiZSBhdmFpbGFibGUgb24gZW5nYWdlbWVudHMgaWYgZGlyZWN0IGFzc29jaWF0aW9uIGlzbid0IHN0cmFpZ2h0Zm9yd2FyZCBpbiBvbmUgc2VhcmNoLlxuICAgICAgICAvLyBIb3dldmVyLCB0aGUgcHJvbXB0IGltcGxpZXMgYSBzZWFyY2guIFNvLCB3ZSB3aWxsIGNvbnN0cnVjdCBhIHNlYXJjaCBhc3N1bWluZyAnYXNzb2NpYXRpb25zLmNvbnRhY3QuaWQnIG9yIHNpbWlsYXIgZXhpc3RzLlxuICAgICAgICAvLyBJZiB0aGlzIGZhaWxzLCB0aGUgYWx0ZXJuYXRpdmUgaXMgQXNzb2NpYXRpb25zIEFQSSArIEJhdGNoIFJlYWQvU2VhcmNoIGJ5IElEcy5cbiAgICAgICAgLy8gTGV0J3MgYXNzdW1lICdhc3NvY2lhdGlvbnMuY29udGFjdCcgZG9lc24ndCB3b3JrIGRpcmVjdGx5IGluIHNlYXJjaCBhbmQgaW5zdGVhZCB3ZSdkIGhhdmUgdG8gcmVseSBvbiBwcm9wZXJ0aWVzIG9uIHRoZSBlbmdhZ2VtZW50IGl0c2VsZi5cbiAgICAgICAgLy8gQSBjb21tb24gd29ya2Fyb3VuZCBpZiBkaXJlY3QgYXNzb2NpYXRpb24gcHJvcGVydHkgaXNuJ3QgYXZhaWxhYmxlIGZvciBzZWFyY2ggaXMgdG8gZmlyc3QgZ2V0IGFsbCBlbmdhZ2VtZW50IElEcyBmb3IgYSBjb250YWN0LFxuICAgICAgICAvLyB0aGVuIHVzZSB0aG9zZSBJRHMgaW4gYSBzZWFyY2ggd2l0aCBgaWRgIElOICguLi4pIGZpbHRlci5cblxuICAgICAgICAvLyBHaXZlbiB0aGUgcHJvbXB0J3MgcHJlZmVyZW5jZSBmb3IgU2VhcmNoIEFQSSwgYW5kIHBvdGVudGlhbCBmb3IgZGlyZWN0IGFzc29jaWF0aW9uIGZpbHRlcmluZzpcbiAgICAgICAgLy8gVGhlIG9mZmljaWFsIHdheSB0byBzZWFyY2ggZm9yIGVuZ2FnZW1lbnRzIGFzc29jaWF0ZWQgd2l0aCBhIGNvbnRhY3QgaXMgdG8gdXNlIHRoZSBgY3JtLmFzc29jaWF0aW9ucy52NC5iYXNpY0FwaS5nZXRQYWdlYFxuICAgICAgICAvLyB0byBnZXQgZW5nYWdlbWVudCBJRHMsIHRoZW4gdXNlIHRob3NlIElEcyBpbiBhIGBTZWFyY2hBcGkuZG9TZWFyY2hgIHdpdGggYW4gSUQgZmlsdGVyLlxuICAgICAgICAvLyBIb3dldmVyLCBsZXQncyB0cnkgdG8gY29uc3RydWN0IHRoZSBzZWFyY2ggYXMgYmVzdCBhcyBwb3NzaWJsZSBiYXNlZCBvbiB0aGUgcHJvbXB0LCBhc3N1bWluZyBhIG1vcmUgZGlyZWN0IHNlYXJjaC5cbiAgICAgICAgLy8gVGhpcyBtaWdodCByZXF1aXJlIGEgc3BlY2lmaWMgSHViU3BvdCBzZXR1cCBvciBjdXN0b20gcHJvcGVydHkuXG4gICAgICAgIC8vIEEgZmlsdGVyIG9uIGBhc3NvY2lhdGlvbnMuY29udGFjdC5pZGAgaXMgTk9UIHN0YW5kYXJkIGZvciBFbmdhZ2VtZW50cyBTZWFyY2ggQVBJLlxuICAgICAgICAvLyBJbnN0ZWFkLCB5b3Ugc2VhcmNoIGVuZ2FnZW1lbnRzIGFuZCBob3BlIHRoZXkgaGF2ZSBhIGRpcmVjdCBjb250YWN0IElEIHByb3BlcnR5LCBvciB1c2UgQXNzb2NpYXRpb25zIEFQSS5cbiAgICAgICAgLy8gRm9yIHRoZSBzYWtlIG9mIHRoZSBleGVyY2lzZSwgaWYgd2UgSEFEIHRvIHVzZSBzZWFyY2ggYW5kIGZpbHRlciBieSBjb250YWN0OlxuICAgICAgICAvLyBMZXQncyBhc3N1bWUgYSBjdXN0b20gc2V0dXAgb3IgYSBtaXN1bmRlcnN0YW5kaW5nIG9mIGRpcmVjdCBzZWFyY2ggY2FwYWJpbGl0aWVzIGZvciBhc3NvY2lhdGlvbnMuXG4gICAgICAgIC8vIFRoZSBtb3N0IHJvYnVzdCB3YXkgaXM6XG4gICAgICAgIC8vIDEuIEdldCBFbmdhZ2VtZW50IElEcyB2aWEgQXNzb2NpYXRpb25zIEFQSSBmb3IgdGhlIGNvbnRhY3QuXG4gICAgICAgIC8vIDIuIFNlYXJjaCBFbmdhZ2VtZW50cyB3aXRoIGBoc19vYmplY3RfaWRgIElOICh0aG9zZSBJRHMpLlxuXG4gICAgICAgIC8vIExldCdzIHByb2NlZWQgd2l0aCB0aGUgZGlyZWN0IHNlYXJjaCBhcHByb2FjaCBhcyBwZXIgdGhlIHByb21wdCdzIHN0cnVjdHVyZSwgd2hpbGUgbm90aW5nIGl0cyBwb3RlbnRpYWwgbGltaXRhdGlvbnMuXG4gICAgICAgIC8vIFRoZSBmaWx0ZXIgZm9yIGNvbnRhY3QgYXNzb2NpYXRpb24gaXMgdHJpY2t5LiBIdWJTcG90J3Mgc3RhbmRhcmQgc2VhcmNoIGZvciBlbmdhZ2VtZW50cyBkb2Vzbid0IGRpcmVjdGx5IHN1cHBvcnQgYGFzc29jaWF0aW9ucy5jb250YWN0LmlkYC5cbiAgICAgICAgLy8gV2UnbGwgYWRkIG90aGVyIGZpbHRlcnMgYW5kIHRoZW4gZGlzY3VzcyB0aGUgYXNzb2NpYXRpb24gcGFydC5cbiAgICAgICAgZmlsdGVyczogW1xuICAgICAgICAgIC8vIFRoaXMgaXMgdGhlIHBhcnQgdGhhdCdzIGhhcmQgd2l0aCBhIHNpbmdsZSBzZWFyY2guXG4gICAgICAgICAgLy8gVG8gY29ycmVjdGx5IGZpbHRlciBieSBjb250YWN0LCB5b3UnZCB0eXBpY2FsbHkgdXNlIHRoZSBBc3NvY2lhdGlvbnMgQVBJIGZpcnN0LlxuICAgICAgICAgIC8vIEZvciB0aGlzIGV4ZXJjaXNlLCB3ZSdsbCBidWlsZCB0aGUgcmVzdCBvZiB0aGUgc2VhcmNoLlxuICAgICAgICAgIC8vIElmIGEgZGlyZWN0IHByb3BlcnR5IGxpa2UgJ2hzX2NvbnRhY3RfaWQnIGV4aXN0ZWQgb24gZW5nYWdlbWVudHMsIGl0IHdvdWxkIGJlOlxuICAgICAgICAgIC8vIHsgcHJvcGVydHlOYW1lOiAnaHNfY29udGFjdF9pZCcsIG9wZXJhdG9yOiAnRVEnLCB2YWx1ZTogY29udGFjdElkIH1cbiAgICAgICAgICAvLyBTaW5jZSBpdCBkb2Vzbid0LCB0aGlzIGZpbHRlciBncm91cCBtaWdodCBiZSBpbmVmZmVjdGl2ZSBmb3IgY29udGFjdCBhc3NvY2lhdGlvbiBieSBpdHNlbGYuXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgIF0sXG4gICAgbGltaXQ6IGZpbHRlcnM/LmxpbWl0IHx8IDEwLFxuICAgIGFmdGVyOiBmaWx0ZXJzPy5hZnRlcixcbiAgICBzb3J0czogW1xuICAgICAge1xuICAgICAgICBwcm9wZXJ0eU5hbWU6ICdoc190aW1lc3RhbXAnLFxuICAgICAgICBkaXJlY3Rpb246IGZpbHRlcnM/LnNvcnQgPT09ICdBU0MnID8gJ0FTQ0VORElORycgOiAnREVTQ0VORElORycsXG4gICAgICB9LFxuICAgIF0sXG4gICAgcHJvcGVydGllczogW1xuICAgICAgJ2hzX2VuZ2FnZW1lbnRfdHlwZScsXG4gICAgICAnaHNfdGltZXN0YW1wJyxcbiAgICAgICdoc19ib2R5X3ByZXZpZXcnLFxuICAgICAgJ2hzX2VtYWlsX3N1YmplY3QnLFxuICAgICAgJ2hzX21lZXRpbmdfdGl0bGUnLFxuICAgICAgJ2hzX2NyZWF0ZWRhdGUnLFxuICAgICAgJ2hzX2xhc3Rtb2RpZmllZGRhdGUnLFxuICAgICAgJ2hzX29iamVjdF9pZCcsXG4gICAgICAnaHNfZW1haWxfZGlyZWN0aW9uJyAvKiBhbnkgb3RoZXIgcmVsZXZhbnQgcHJvcHMgKi8sXG4gICAgXSxcbiAgfTtcblxuICAvLyBBZGQgYWN0aXZpdHkgdHlwZSBmaWx0ZXJzIGlmIHByb3ZpZGVkXG4gIGlmIChmaWx0ZXJzPy5hY3Rpdml0eVR5cGVzICYmIGZpbHRlcnMuYWN0aXZpdHlUeXBlcy5sZW5ndGggPiAwKSB7XG4gICAgc2VhcmNoUmVxdWVzdC5maWx0ZXJHcm91cHNbMF0uZmlsdGVycy5wdXNoKHtcbiAgICAgIC8vIEFkZCB0byB0aGUgZmlyc3QgKGFuZCBvbmx5KSBmaWx0ZXIgZ3JvdXBcbiAgICAgIHByb3BlcnR5TmFtZTogJ2hzX2VuZ2FnZW1lbnRfdHlwZScsXG4gICAgICBvcGVyYXRvcjogJ0lOJywgLy8gVXNlIElOIG9wZXJhdG9yIGZvciBtdWx0aXBsZSB2YWx1ZXNcbiAgICAgIHZhbHVlczogZmlsdGVycy5hY3Rpdml0eVR5cGVzLFxuICAgIH0pO1xuICB9XG5cbiAgLy8gQWRkICdzaW5jZScgZmlsdGVyIChoc190aW1lc3RhbXAgPj0gdmFsdWUpXG4gIGlmIChmaWx0ZXJzPy5zaW5jZSkge1xuICAgIGxldCBzaW5jZVRpbWVzdGFtcCA9IGZpbHRlcnMuc2luY2U7XG4gICAgLy8gSHViU3BvdCdzIGhzX3RpbWVzdGFtcCBmb3Igc2VhcmNoIGlzIHVzdWFsbHkgZXBvY2ggbWlsbGlzZWNvbmRzXG4gICAgaWYgKCEvXlxcZCskLy50ZXN0KGZpbHRlcnMuc2luY2UpKSB7XG4gICAgICAvLyBJZiBub3QgYWxyZWFkeSBlcG9jaCBtc1xuICAgICAgc2luY2VUaW1lc3RhbXAgPSBuZXcgRGF0ZShmaWx0ZXJzLnNpbmNlKS5nZXRUaW1lKCkudG9TdHJpbmcoKTtcbiAgICB9XG4gICAgc2VhcmNoUmVxdWVzdC5maWx0ZXJHcm91cHNbMF0uZmlsdGVycy5wdXNoKHtcbiAgICAgIHByb3BlcnR5TmFtZTogJ2hzX3RpbWVzdGFtcCcsXG4gICAgICBvcGVyYXRvcjogJ0dURScsXG4gICAgICB2YWx1ZTogc2luY2VUaW1lc3RhbXAsXG4gICAgfSk7XG4gIH1cblxuICAvLyBUaGUgbW9zdCByZWxpYWJsZSB3YXkgdG8gZ2V0IGVuZ2FnZW1lbnRzIGZvciBhIFNQRUNJRklDIGNvbnRhY3QgaXMgdmlhIHRoZSBBc3NvY2lhdGlvbnMgQVBJIGZpcnN0LlxuICAvLyBUaGVuIHVzZSB0aGUgcmV0dXJuZWQgZW5nYWdlbWVudCBJRHMgaW4gYSBzZWFyY2ggcmVxdWVzdC5cbiAgdHJ5IHtcbiAgICBjb25zdCBhc3NvY2lhdGlvblJlc3VsdHMgPVxuICAgICAgYXdhaXQgaHVic3BvdENsaWVudC5jcm0uYXNzb2NpYXRpb25zLnY0LmJhc2ljQXBpLmdldFBhZ2UoXG4gICAgICAgIENPTlRBQ1RfT0JKRUNUX1RZUEVfSURfRk9SX0FTU09DSUFUSU9OU19BUEksIC8vIEZyb20gT2JqZWN0IFR5cGUgKENvbnRhY3QpXG4gICAgICAgIGNvbnRhY3RJZCxcbiAgICAgICAgRU5HQUdFTUVOVF9PQkpFQ1RfVFlQRV9JRF9GT1JfQVNTT0NJQVRJT05TX0FQSSwgLy8gVG8gT2JqZWN0IFR5cGUgKEVuZ2FnZW1lbnQpXG4gICAgICAgIGZpbHRlcnM/LmFmdGVyLCAvLyBhZnRlciBmb3IgYXNzb2NpYXRpb24gcGFnaW5hdGlvblxuICAgICAgICBmaWx0ZXJzPy5saW1pdCB8fCA1MCAvLyBsaW1pdCBmb3IgYXNzb2NpYXRpb25zIChjYW4gYmUgZGlmZmVyZW50IGZyb20gZmluYWwgZW5nYWdlbWVudCBsaW1pdClcbiAgICAgICk7XG5cbiAgICBpZiAoXG4gICAgICAhYXNzb2NpYXRpb25SZXN1bHRzLnJlc3VsdHMgfHxcbiAgICAgIGFzc29jaWF0aW9uUmVzdWx0cy5yZXN1bHRzLmxlbmd0aCA9PT0gMFxuICAgICkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgICAgYWN0aXZpdGllczogW10sXG4gICAgICAgIG1lc3NhZ2U6ICdObyBhY3Rpdml0aWVzIGZvdW5kIGZvciB0aGlzIGNvbnRhY3QuJyxcbiAgICAgIH07XG4gICAgfVxuICAgIGNvbnN0IGVuZ2FnZW1lbnRJZHMgPSBhc3NvY2lhdGlvblJlc3VsdHMucmVzdWx0cy5tYXAoXG4gICAgICAoYXNzb2MpID0+IGFzc29jLnRvT2JqZWN0SWRcbiAgICApO1xuXG4gICAgLy8gTm93IHNlYXJjaCBmb3IgdGhlc2Ugc3BlY2lmaWMgZW5nYWdlbWVudCBJRHNcbiAgICBjb25zdCBpZEZpbHRlciA9IHtcbiAgICAgIHByb3BlcnR5TmFtZTogJ2hzX29iamVjdF9pZCcsXG4gICAgICBvcGVyYXRvcjogJ0lOJyxcbiAgICAgIHZhbHVlczogZW5nYWdlbWVudElkcyxcbiAgICB9O1xuICAgIC8vIEFkZCB0aGlzIElEIGZpbHRlciB0byB0aGUgZXhpc3RpbmcgZmlsdGVyIGdyb3VwIG9yIGEgbmV3IG9uZS5cbiAgICAvLyBJZiB0aGUgZmlsdGVyIGdyb3VwIGlzIGVtcHR5IChlLmcuIG5vIGFjdGl2aXR5VHlwZXMgb3Igc2luY2UgZmlsdGVyKSwgYWRkIGl0IGRpcmVjdGx5LlxuICAgIGlmIChzZWFyY2hSZXF1ZXN0LmZpbHRlckdyb3Vwc1swXS5maWx0ZXJzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgc2VhcmNoUmVxdWVzdC5maWx0ZXJHcm91cHNbMF0uZmlsdGVycy5wdXNoKGlkRmlsdGVyKTtcbiAgICB9IGVsc2Uge1xuICAgICAgLy8gSWYgb3RoZXIgZmlsdGVycyBleGlzdCwgY3JlYXRlIGEgbmV3IGZpbHRlciBncm91cCBmb3IgSURzIHRvIGVuc3VyZSBBTkQgbG9naWNcbiAgICAgIC8vIG9yIGFkZCB0byBleGlzdGluZyBpZiBBTkQgaXMgZGVzaXJlZCBmb3IgYWxsIGNvbmRpdGlvbnMuXG4gICAgICAvLyBGb3IgdGhpcyBjYXNlLCBhbGwgZmlsdGVycyBzaG91bGQgYXBwbHksIHNvIGFkZCB0byBleGlzdGluZy5cbiAgICAgIHNlYXJjaFJlcXVlc3QuZmlsdGVyR3JvdXBzWzBdLmZpbHRlcnMucHVzaChpZEZpbHRlcik7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2U6IENvbGxlY3Rpb25SZXNwb25zZVNpbXBsZVB1YmxpY09iamVjdEZvcndhcmRQYWdpbmcgPVxuICAgICAgYXdhaXQgaHVic3BvdENsaWVudC5jcm0uZW5nYWdlbWVudHMuc2VhcmNoQXBpLmRvU2VhcmNoKHNlYXJjaFJlcXVlc3QpO1xuXG4gICAgY29uc3QgYWN0aXZpdGllczogSHViU3BvdEVuZ2FnZW1lbnRbXSA9IHJlc3BvbnNlLnJlc3VsdHNcbiAgICAgID8gcmVzcG9uc2UucmVzdWx0cy5tYXAoKGVuZykgPT4ge1xuICAgICAgICAgIC8vIEJhc2ljIG1hcHBpbmcsIGVuc3VyZSBhbGwgcmVxdWlyZWQgZmllbGRzIGZyb20gSHViU3BvdEVuZ2FnZW1lbnQgYXJlIHBvcHVsYXRlZFxuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBpZDogZW5nLmlkLFxuICAgICAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgICAgICBoc19vYmplY3RfaWQ6IGVuZy5wcm9wZXJ0aWVzLmhzX29iamVjdF9pZCB8fCBlbmcuaWQsXG4gICAgICAgICAgICAgIGhzX2VuZ2FnZW1lbnRfdHlwZTogZW5nLnByb3BlcnRpZXMuaHNfZW5nYWdlbWVudF90eXBlIGFzXG4gICAgICAgICAgICAgICAgfCAnRU1BSUwnXG4gICAgICAgICAgICAgICAgfCAnTUVFVElORycsXG4gICAgICAgICAgICAgIGhzX3RpbWVzdGFtcDogZW5nLnByb3BlcnRpZXMuaHNfdGltZXN0YW1wLFxuICAgICAgICAgICAgICBoc19ib2R5X3ByZXZpZXc6IGVuZy5wcm9wZXJ0aWVzLmhzX2JvZHlfcHJldmlldyxcbiAgICAgICAgICAgICAgaHNfZW1haWxfc3ViamVjdDogZW5nLnByb3BlcnRpZXMuaHNfZW1haWxfc3ViamVjdCxcbiAgICAgICAgICAgICAgaHNfZW1haWxfZGlyZWN0aW9uOiBlbmcucHJvcGVydGllcy5oc19lbWFpbF9kaXJlY3Rpb24gYXNcbiAgICAgICAgICAgICAgICB8ICdJTkNPTUlORydcbiAgICAgICAgICAgICAgICB8ICdPVVRHT0lORycsXG4gICAgICAgICAgICAgIC8vIGhzX21lZXRpbmdfdGl0bGU6IGVuZy5wcm9wZXJ0aWVzLmhzX21lZXRpbmdfdGl0bGUsXG4gICAgICAgICAgICAgIGNyZWF0ZWRhdGU6XG4gICAgICAgICAgICAgICAgZW5nLnByb3BlcnRpZXMuY3JlYXRlZGF0ZSB8fFxuICAgICAgICAgICAgICAgIG5ldyBEYXRlKGVuZy5jcmVhdGVkQXQpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICAgIGxhc3Rtb2RpZmllZGRhdGU6XG4gICAgICAgICAgICAgICAgZW5nLnByb3BlcnRpZXMubGFzdG1vZGlmaWVkZGF0ZSB8fFxuICAgICAgICAgICAgICAgIG5ldyBEYXRlKGVuZy51cGRhdGVkQXQpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICAgIC4uLmVuZy5wcm9wZXJ0aWVzLCAvLyBpbmNsdWRlIGFueSBvdGhlciByZXR1cm5lZCBwcm9wZXJ0aWVzXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgLy8gQXNzb2NpYXRpb25zIGFyZSBub3QgdHlwaWNhbGx5IHJldHVybmVkIGluIGRldGFpbCBieSBlbmdhZ2VtZW50IHNlYXJjaCxcbiAgICAgICAgICAgIC8vIGJ1dCBpZiB0aGV5IHdlcmUsIHlvdSdkIG1hcCB0aGVtIGhlcmUuXG4gICAgICAgICAgICAvLyBhc3NvY2lhdGlvbnM6IGVuZy5hc3NvY2lhdGlvbnMgPyBtYXBBc3NvY2lhdGlvbnMoZW5nLmFzc29jaWF0aW9ucykgOiB1bmRlZmluZWQsXG4gICAgICAgICAgICBjcmVhdGVkQXQ6IGVuZy5jcmVhdGVkQXQudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZW5nLnVwZGF0ZWRBdC50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgYXJjaGl2ZWQ6IGVuZy5hcmNoaXZlZCB8fCBmYWxzZSxcbiAgICAgICAgICB9O1xuICAgICAgICB9KVxuICAgICAgOiBbXTtcblxuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgc3VjY2VzczogdHJ1ZSwgLy8gUmV0YWluIHN1Y2Nlc3MgZnJvbSBvcmlnaW5hbCBHZXRDb250YWN0QWN0aXZpdGllc1Jlc3BvbnNlXG4gICAgICAgIGFjdGl2aXRpZXMsXG4gICAgICAgIG5leHRQYWdlOiByZXNwb25zZS5wYWdpbmc/Lm5leHQ/LmFmdGVyLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgIGFjdGl2aXRpZXMubGVuZ3RoID4gMFxuICAgICAgICAgICAgPyAnQWN0aXZpdGllcyByZXRyaWV2ZWQuJ1xuICAgICAgICAgICAgOiAnTm8gYWN0aXZpdGllcyBmb3VuZCBtYXRjaGluZyBjcml0ZXJpYS4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBFcnJvciBmZXRjaGluZyBIdWJTcG90IGNvbnRhY3QgYWN0aXZpdGllcyBmb3IgY29udGFjdCAke2NvbnRhY3RJZH0sIHVzZXJJZCAke3VzZXJJZH06YCxcbiAgICAgIGVycm9yLm1lc3NhZ2VcbiAgICApO1xuICAgIGxldCBlcnJvck1lc3NhZ2UgPSBgRmFpbGVkIHRvIGZldGNoIGNvbnRhY3QgYWN0aXZpdGllczogJHtlcnJvci5tZXNzYWdlfWA7XG4gICAgbGV0IGVycm9yQ29kZSA9ICdIVUJTUE9UX0FQSV9FUlJPUic7XG4gICAgbGV0IGVycm9yRGV0YWlscyA9IGVycm9yO1xuICAgIGlmIChlcnJvci5yZXNwb25zZSAmJiBlcnJvci5yZXNwb25zZS5ib2R5KSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdIdWJTcG90IEFQSSBFcnJvciBCb2R5OicsIGVycm9yLnJlc3BvbnNlLmJvZHkpO1xuICAgICAgdHJ5IHtcbiAgICAgICAgY29uc3QgZXJyb3JCb2R5U3RyaW5nID0gQnVmZmVyLmlzQnVmZmVyKGVycm9yLnJlc3BvbnNlLmJvZHkpXG4gICAgICAgICAgPyBlcnJvci5yZXNwb25zZS5ib2R5LnRvU3RyaW5nKClcbiAgICAgICAgICA6IGVycm9yLnJlc3BvbnNlLmJvZHk7XG4gICAgICAgIGNvbnN0IGVycm9yQm9keSA9IEpTT04ucGFyc2UoZXJyb3JCb2R5U3RyaW5nKTtcbiAgICAgICAgZXJyb3JEZXRhaWxzID0gZXJyb3JCb2R5O1xuICAgICAgICBpZiAoZXJyb3JCb2R5ICYmIGVycm9yQm9keS5tZXNzYWdlKSB7XG4gICAgICAgICAgZXJyb3JNZXNzYWdlID0gZXJyb3JCb2R5Lm1lc3NhZ2U7XG4gICAgICAgICAgaWYgKGVycm9yQm9keS5jYXRlZ29yeSA9PT0gJ1ZBTElEQVRJT05fRVJST1InKVxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ1ZBTElEQVRJT05fRVJST1InO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChwYXJzZUVycm9yKSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoJ0NvdWxkIG5vdCBwYXJzZSBIdWJTcG90IGVycm9yIGJvZHk6JywgcGFyc2VFcnJvcik7XG4gICAgICB9XG4gICAgfVxuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiBlcnJvckNvZGUsIG1lc3NhZ2U6IGVycm9yTWVzc2FnZSwgZGV0YWlsczogZXJyb3JEZXRhaWxzIH0sXG4gICAgfTtcbiAgfVxufVxuIl19