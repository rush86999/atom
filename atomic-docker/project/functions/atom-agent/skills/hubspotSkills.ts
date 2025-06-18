import { Client } from '@hubspot/api-client';
import { ATOM_HUBSPOT_API_KEY } from '../_libs/constants';
import {
  HubSpotContactProperties,
  HubSpotContact,
  GetHubSpotContactResponse,
  CreateHubSpotContactResponse,
} from '../types';

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
