import {
  HubSpotContactProperties,
  CreateHubSpotContactResponse,
  HubSpotContact,
} from '../../types';
import {
  createHubSpotContact as create,
  getHubSpotContactByEmail as getByEmail,
} from './hubspotSkills';
import { ATOM_HUBSPOT_PORTAL_ID } from '../../_libs/constants';
import { handleError } from '../../_utils/errorHandler';

export async function handleGetHubSpotContactByEmail(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const emailEntity = entities?.email;
    if (
      !emailEntity ||
      typeof emailEntity !== 'string' ||
      emailEntity.trim() === ''
    ) {
      return 'Email is required and must be a non-empty string to get a HubSpot contact by email.';
    } else {
      const contact: HubSpotContact | null = await getByEmail(
        userId,
        emailEntity
      );
      if (contact) {
        const name =
          `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();
        let responseString = `HubSpot Contact Found:\nID: ${contact.id}\nName: ${name || 'N/A'}\nEmail: ${contact.properties.email || 'N/A'}\nCompany: ${contact.properties.company || 'N/A'}`;
        if (contact.properties.createdate)
          responseString += `\nCreated: ${new Date(contact.properties.createdate).toLocaleString()}`;
        if (contact.properties.lastmodifieddate)
          responseString += `\nLast Modified: ${new Date(contact.properties.lastmodifieddate).toLocaleString()}`;
        if (ATOM_HUBSPOT_PORTAL_ID && contact.id)
          responseString += `\nView in HubSpot: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${contact.id}`;
        return responseString;
      } else {
        return `No HubSpot contact found with email: ${emailEntity}.`;
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      'Sorry, an error occurred while trying to retrieve the HubSpot contact.'
    );
  }
}

export async function handleCreateHubSpotContact(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const { email, first_name, last_name, contact_name, company_name } =
      entities;
    if (!email || typeof email !== 'string') {
      return 'Email is required (and must be a string) to create a HubSpot contact via NLU.';
    } else {
      let finalFirstName = first_name;
      let finalLastName = last_name;
      if (
        !finalFirstName &&
        !finalLastName &&
        contact_name &&
        typeof contact_name === 'string'
      ) {
        const nameParts = contact_name.split(' ');
        finalFirstName = nameParts[0];
        if (nameParts.length > 1) finalLastName = nameParts.slice(1).join(' ');
      }
      const contactDetails: HubSpotContactProperties = {
        email,
        firstname:
          typeof finalFirstName === 'string' ? finalFirstName : undefined,
        lastname: typeof finalLastName === 'string' ? finalLastName : undefined,
        company: typeof company_name === 'string' ? company_name : undefined,
      };
      const hubspotResponse: CreateHubSpotContactResponse = await create(
        userId,
        contactDetails
      );
      if (
        hubspotResponse.success &&
        hubspotResponse.contactId &&
        hubspotResponse.hubSpotContact
      ) {
        const contact = hubspotResponse.hubSpotContact;
        const name =
          `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim() ||
          'N/A';
        return `HubSpot contact created via NLU! ID: ${hubspotResponse.contactId}. Name: ${name}. Email: ${contact.properties.email}.`;
      } else {
        return `Failed to create HubSpot contact via NLU: ${hubspotResponse.message || 'Unknown HubSpot error.'}`;
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      'Sorry, there was an issue creating the HubSpot contact based on your request.'
    );
  }
}
