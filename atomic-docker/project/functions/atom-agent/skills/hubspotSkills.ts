import { Client } from '@hubspot/api-client';
import { ATOM_HUBSPOT_API_KEY } from '../_libs/constants';
import {
  HubSpotContactProperties,
  HubSpotContact,
  GetHubSpotContactResponse,
  CreateHubSpotContactResponse,
  HubSpotEmailEngagementProperties,
  HubSpotEngagement,
  LogEngagementResponse,
  GetContactActivitiesResponse,
  HubSpotEngagementAssociation,
} from '../types';
import { PublicObjectSearchRequest, CollectionResponseSimplePublicObjectForwardPaging, SimplePublicObjectInput } from '@hubspot/api-client/lib/codegen/crm/engagements/index.js';
// Note: For AssociationTypes, HubSpot client might not export a direct enum.
// Standard association type IDs are documented. Contact to Engagement is 203.
// https://developers.hubspot.com/docs/api/crm/associations/v2#get-all-association-types
// For v4, it's usually [{ associationCategory: "HUBSPOT_DEFINED", associationTypeId: <ID_AS_NUMBER> }]
// Contact to Engagement: Use type ID 19 for v4 (CONTACT_TO_ENGAGEMENT) basicApi.createAssociation
// For Engagements API create payload, association type ID 203 (contact_to_engagement) is used.
// Let's stick to the documented numeric IDs if no enum is readily available from the client.
// Engagement to Contact association type ID for engagement creation's association block:
const CONTACT_TO_ENGAGEMENT_ASSOCIATION_TYPE_ID = 203; // As per Engagements API documentation for associating to contacts.
// For searching engagements associated with a contact, the association definition ID is different.
// This is used with the associations API (crm.associations.v4.basicApi.getPage)
const CONTACT_OBJECT_TYPE_ID_FOR_ASSOCIATIONS_API = "0-1"; // Represents Contacts
const ENGAGEMENT_OBJECT_TYPE_ID_FOR_ASSOCIATIONS_API = "0-31"; // Represents Engagements

const getHubspotClient = () => {
  if (!ATOM_HUBSPOT_API_KEY) {
    console.error('HubSpot API key not configured.');
    return null;
  }
  return new Client({ apiKey: ATOM_HUBSPOT_API_KEY });
};

export async function getHubSpotContactByEmail(
  userId: string,
  email: string
): Promise<GetHubSpotContactResponse> {
  console.log(`getHubSpotContactByEmail called for userId: ${userId}, email: ${email}`);
  const hubspotClient = getHubspotClient();
  if (!hubspotClient) {
    return null;
  }

  try {
    const response = await hubspotClient.crm.contacts.searchApi.doSearch({
      query: email,
      properties: ['email', 'firstname', 'lastname', 'company', 'hs_object_id', 'createdate', 'lastmodifieddate'],
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
    });

    if (response.results && response.results.length > 0) {
      // Assuming the first result is the desired contact
      // Ensure the mapping here aligns with the HubSpotContact interface
      const contactData = response.results[0];
      const contact: HubSpotContact = {
        id: contactData.id,
        properties: {
          hs_object_id: contactData.properties.hs_object_id,
          createdate: contactData.properties.createdate,
          lastmodifieddate: contactData.properties.lastmodifieddate,
          email: contactData.properties.email,
          firstname: contactData.properties.firstname,
          lastname: contactData.properties.lastname,
          company: contactData.properties.company,
          // Include any other custom properties you expect
        },
        createdAt: contactData.createdAt.toISOString(),
        updatedAt: contactData.updatedAt.toISOString(),
        archived: contactData.archived || false, // Default to false if undefined
      };
      return contact;
    } else {
      console.log(`No HubSpot contact found for email: ${email}`);
      return null;
    }
  } catch (error: any) {
    console.error(`Error fetching HubSpot contact by email ${email} for userId ${userId}:`, error.message);
    if (error.response && error.response.body) {
      console.error('HubSpot API Error Body:', error.response.body);
    }
    return null;
  }
}

export async function createHubSpotContact(
  userId: string,
  contactProperties: HubSpotContactProperties
): Promise<CreateHubSpotContactResponse> {
  console.log(`createHubSpotContact called for userId: ${userId} with properties:`, contactProperties);
  const hubspotClient = getHubspotClient();
  if (!hubspotClient) {
    return { success: false, message: 'HubSpot API key not configured.' };
  }

  if (!contactProperties.email) {
    return { success: false, message: 'Email is required to create a HubSpot contact.' };
  }

  try {
    const createResponse = await hubspotClient.crm.contacts.basicApi.create({
      properties: contactProperties,
    });

    // Map the response to HubSpotContact, ensuring all fields are covered
    const createdContact: HubSpotContact = {
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

    return {
      success: true,
      contactId: createResponse.id,
      message: 'Contact created successfully in HubSpot.',
      hubSpotContact: createdContact,
    };
  } catch (error: any) {
    console.error(`Error creating HubSpot contact for userId ${userId} with email ${contactProperties.email}:`, error.message);
    let errorMessage = `Failed to create contact in HubSpot: ${error.message}`;
    if (error.response && error.response.body) {
      console.error('HubSpot API Error Body:', error.response.body);
      // Attempt to parse more specific error message from HubSpot
      try {
        const errorBody = JSON.parse(error.response.body.toString()); // or error.response.body if already an object
        if (errorBody && errorBody.message) {
          errorMessage = `Failed to create contact in HubSpot: ${errorBody.message}`;
          if (errorBody.category === 'CONFLICT') { // Example of handling specific error types
            errorMessage = `Failed to create contact in HubSpot: A contact with this email already exists.`;
          }
        }
      } catch (parseError) {
        console.error('Could not parse HubSpot error body:', parseError);
      }
    }
    return { success: false, message: errorMessage };
  }
}

export async function logEmailToHubSpotContact(
  userId: string,
  contactId: string,
  emailDetails: HubSpotEmailEngagementProperties
): Promise<LogEngagementResponse> {
  console.log(`logEmailToHubSpotContact called for userId: ${userId}, contactId: ${contactId}`);
  const hubspotClient = getHubspotClient();
  if (!hubspotClient) {
    return { success: false, message: 'HubSpot API key not configured.' };
  }

  if (!contactId) {
    return { success: false, message: 'Contact ID is required to log an email.' };
  }
  if (!emailDetails || !emailDetails.activityTimestamp || !emailDetails.subject || !emailDetails.htmlBody) {
    return { success: false, message: 'Email details (activityTimestamp, subject, htmlBody) are required.' };
  }

  const engagementInput: SimplePublicObjectInput = {
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
    const createdEngagement: HubSpotEngagement = {
        id: createResponse.id,
        properties: {
            hs_object_id: createResponse.properties.hs_object_id || createResponse.id, // hs_object_id might not be in basic create response, use id
            hs_engagement_type: createResponse.properties.hs_engagement_type as 'EMAIL' | 'MEETING', // Cast as needed
            hs_timestamp: createResponse.properties.hs_timestamp,
            hs_body_preview: createResponse.properties.hs_body_preview,
            hs_email_subject: createResponse.properties.hs_email_subject,
            hs_email_direction: createResponse.properties.hs_email_direction as 'INCOMING' | 'OUTGOING',
            createdate: createResponse.properties.createdate || new Date(createResponse.createdAt).toISOString(),
            lastmodifieddate: createResponse.properties.lastmodifieddate || new Date(createResponse.updatedAt).toISOString(),
        },
        associations: createResponse.associations as any, // Cast if necessary, or map structure
        createdAt: createResponse.createdAt.toISOString(),
        updatedAt: createResponse.updatedAt.toISOString(),
        archived: createResponse.archived || false,
    };


    return {
      success: true,
      engagementId: createResponse.id,
      message: 'Email logged successfully to HubSpot contact.',
      hubSpotEngagement: createdEngagement,
    };
  } catch (error: any) {
    console.error(`Error logging email to HubSpot contact ${contactId} for userId ${userId}:`, error.message);
    let errorMessage = `Failed to log email to HubSpot: ${error.message}`;
    if (error.response && error.response.body) {
      console.error('HubSpot API Error Body:', error.response.body);
      try {
        const errorBody = JSON.parse(error.response.body.toString());
        if (errorBody && errorBody.message) {
          errorMessage = `Failed to log email to HubSpot: ${errorBody.message}`;
        }
      } catch (parseError) {
        console.error('Could not parse HubSpot error body:', parseError);
      }
    }
    return { success: false, message: errorMessage };
  }
}

export async function getHubSpotContactActivities(
  userId: string,
  contactId: string,
  filters?: {
    activityTypes?: ('EMAIL' | 'MEETING')[];
    limit?: number;
    after?: string;
    since?: string; // ISO Date string or epoch ms
    sort?: 'ASC' | 'DESC';
  }
): Promise<GetContactActivitiesResponse> {
  console.log(`getHubSpotContactActivities called for userId: ${userId}, contactId: ${contactId}, filters:`, filters);
  const hubspotClient = getHubspotClient();
  if (!hubspotClient) {
    return { success: false, activities: [], message: 'HubSpot API key not configured.' };
  }
  if (!contactId) {
    return { success: false, activities: [], message: 'Contact ID is required.' };
  }

  const searchRequest: PublicObjectSearchRequest = {
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
        ]
      }
    ],
    limit: filters?.limit || 10,
    after: filters?.after,
    sorts: [{ propertyName: 'hs_timestamp', direction: (filters?.sort === 'ASC' ? 'ASCENDING' : 'DESCENDING') }],
    properties: ['hs_engagement_type', 'hs_timestamp', 'hs_body_preview', 'hs_email_subject', 'hs_meeting_title', 'hs_createdate', 'hs_lastmodifieddate', 'hs_object_id', 'hs_email_direction' /* any other relevant props */],
  };

  // Add activity type filters if provided
  if (filters?.activityTypes && filters.activityTypes.length > 0) {
    searchRequest.filterGroups[0].filters.push({ // Add to the first (and only) filter group
      propertyName: 'hs_engagement_type',
      operator: 'IN', // Use IN operator for multiple values
      values: filters.activityTypes,
    });
  }

  // Add 'since' filter (hs_timestamp >= value)
  if (filters?.since) {
    let sinceTimestamp = filters.since;
    // HubSpot's hs_timestamp for search is usually epoch milliseconds
    if (!/^\d+$/.test(filters.since)) { // If not already epoch ms
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
    const associationResults = await hubspotClient.crm.associations.v4.basicApi.getPage(
        CONTACT_OBJECT_TYPE_ID_FOR_ASSOCIATIONS_API, // From Object Type (Contact)
        contactId,
        ENGAGEMENT_OBJECT_TYPE_ID_FOR_ASSOCIATIONS_API, // To Object Type (Engagement)
        filters?.after, // after for association pagination
        filters?.limit || 50 // limit for associations (can be different from final engagement limit)
    );

    if (!associationResults.results || associationResults.results.length === 0) {
        return { success: true, activities: [], message: 'No activities found for this contact.' };
    }
    const engagementIds = associationResults.results.map(assoc => assoc.toObjectId);

    // Now search for these specific engagement IDs
    const idFilter = {
        propertyName: 'hs_object_id',
        operator: 'IN',
        values: engagementIds
    };
    // Add this ID filter to the existing filter group or a new one.
    // If the filter group is empty (e.g. no activityTypes or since filter), add it directly.
    if (searchRequest.filterGroups[0].filters.length === 0) {
        searchRequest.filterGroups[0].filters.push(idFilter);
    } else {
        // If other filters exist, create a new filter group for IDs to ensure AND logic
        // or add to existing if AND is desired for all conditions.
        // For this case, all filters should apply, so add to existing.
        searchRequest.filterGroups[0].filters.push(idFilter);
    }


    const response: CollectionResponseSimplePublicObjectForwardPaging = await hubspotClient.crm.engagements.searchApi.doSearch(searchRequest);

    const activities: HubSpotEngagement[] = response.results ? response.results.map(eng => {
      // Basic mapping, ensure all required fields from HubSpotEngagement are populated
      return {
        id: eng.id,
        properties: {
          hs_object_id: eng.properties.hs_object_id || eng.id,
          hs_engagement_type: eng.properties.hs_engagement_type as 'EMAIL' | 'MEETING',
          hs_timestamp: eng.properties.hs_timestamp,
          hs_body_preview: eng.properties.hs_body_preview,
          hs_email_subject: eng.properties.hs_email_subject,
          hs_email_direction: eng.properties.hs_email_direction as 'INCOMING' | 'OUTGOING',
          // hs_meeting_title: eng.properties.hs_meeting_title,
          createdate: eng.properties.createdate || new Date(eng.createdAt).toISOString(),
          lastmodifieddate: eng.properties.lastmodifieddate || new Date(eng.updatedAt).toISOString(),
          ...eng.properties // include any other returned properties
        },
        // Associations are not typically returned in detail by engagement search,
        // but if they were, you'd map them here.
        // associations: eng.associations ? mapAssociations(eng.associations) : undefined,
        createdAt: eng.createdAt.toISOString(),
        updatedAt: eng.updatedAt.toISOString(),
        archived: eng.archived || false,
      };
    }) : [];

    return {
      success: true,
      activities,
      nextPage: response.paging?.next?.after,
      message: activities.length > 0 ? 'Activities retrieved.' : 'No activities found matching criteria.',
    };
  } catch (error: any) {
    console.error(`Error fetching HubSpot contact activities for contact ${contactId}, userId ${userId}:`, error.message);
    let errorMessage = `Failed to fetch contact activities: ${error.message}`;
     if (error.response && error.response.body) {
      console.error('HubSpot API Error Body:', error.response.body);
      try {
        // error.response.body might be a Buffer
        const errorBodyString = Buffer.isBuffer(error.response.body) ? error.response.body.toString() : error.response.body;
        const errorBody = JSON.parse(errorBodyString);
        if (errorBody && errorBody.message) {
          errorMessage = `Failed to fetch contact activities: ${errorBody.message}`;
        }
      } catch (parseError) {
        console.error('Could not parse HubSpot error body:', parseError);
      }
    }
    return { success: false, activities: [], message: errorMessage };
  }
}
