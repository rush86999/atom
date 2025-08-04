import { createHubSpotContact as create, getHubSpotContactByEmail as getByEmail, } from './hubspotSkills';
import { ATOM_HUBSPOT_PORTAL_ID } from '../../_libs/constants';
import { handleError } from '../../_utils/errorHandler';
export async function handleGetHubSpotContactByEmail(userId, entities) {
    try {
        const emailEntity = entities?.email;
        if (!emailEntity ||
            typeof emailEntity !== 'string' ||
            emailEntity.trim() === '') {
            return 'Email is required and must be a non-empty string to get a HubSpot contact by email.';
        }
        else {
            const contact = await getByEmail(userId, emailEntity);
            if (contact) {
                const name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();
                let responseString = `HubSpot Contact Found:\nID: ${contact.id}\nName: ${name || 'N/A'}\nEmail: ${contact.properties.email || 'N/A'}\nCompany: ${contact.properties.company || 'N/A'}`;
                if (contact.properties.createdate)
                    responseString += `\nCreated: ${new Date(contact.properties.createdate).toLocaleString()}`;
                if (contact.properties.lastmodifieddate)
                    responseString += `\nLast Modified: ${new Date(contact.properties.lastmodifieddate).toLocaleString()}`;
                if (ATOM_HUBSPOT_PORTAL_ID && contact.id)
                    responseString += `\nView in HubSpot: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${contact.id}`;
                return responseString;
            }
            else {
                return `No HubSpot contact found with email: ${emailEntity}.`;
            }
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, an error occurred while trying to retrieve the HubSpot contact.');
    }
}
export async function handleCreateHubSpotContact(userId, entities) {
    try {
        const { email, first_name, last_name, contact_name, company_name } = entities;
        if (!email || typeof email !== 'string') {
            return 'Email is required (and must be a string) to create a HubSpot contact via NLU.';
        }
        else {
            let finalFirstName = first_name;
            let finalLastName = last_name;
            if (!finalFirstName &&
                !finalLastName &&
                contact_name &&
                typeof contact_name === 'string') {
                const nameParts = contact_name.split(' ');
                finalFirstName = nameParts[0];
                if (nameParts.length > 1)
                    finalLastName = nameParts.slice(1).join(' ');
            }
            const contactDetails = {
                email,
                firstname: typeof finalFirstName === 'string' ? finalFirstName : undefined,
                lastname: typeof finalLastName === 'string' ? finalLastName : undefined,
                company: typeof company_name === 'string' ? company_name : undefined,
            };
            const hubspotResponse = await create(userId, contactDetails);
            if (hubspotResponse.success &&
                hubspotResponse.contactId &&
                hubspotResponse.hubSpotContact) {
                const contact = hubspotResponse.hubSpotContact;
                const name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim() ||
                    'N/A';
                return `HubSpot contact created via NLU! ID: ${hubspotResponse.contactId}. Name: ${name}. Email: ${contact.properties.email}.`;
            }
            else {
                return `Failed to create HubSpot contact via NLU: ${hubspotResponse.message || 'Unknown HubSpot error.'}`;
            }
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, there was an issue creating the HubSpot contact based on your request.');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaHVic3BvdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImh1YnNwb3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBS0EsT0FBTyxFQUNMLG9CQUFvQixJQUFJLE1BQU0sRUFDOUIsd0JBQXdCLElBQUksVUFBVSxHQUN2QyxNQUFNLGlCQUFpQixDQUFDO0FBQ3pCLE9BQU8sRUFBRSxzQkFBc0IsRUFBRSxNQUFNLHVCQUF1QixDQUFDO0FBQy9ELE9BQU8sRUFBRSxXQUFXLEVBQUUsTUFBTSwyQkFBMkIsQ0FBQztBQUV4RCxNQUFNLENBQUMsS0FBSyxVQUFVLDhCQUE4QixDQUNsRCxNQUFjLEVBQ2QsUUFBYTtJQUViLElBQUksQ0FBQztRQUNILE1BQU0sV0FBVyxHQUFHLFFBQVEsRUFBRSxLQUFLLENBQUM7UUFDcEMsSUFDRSxDQUFDLFdBQVc7WUFDWixPQUFPLFdBQVcsS0FBSyxRQUFRO1lBQy9CLFdBQVcsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLEVBQ3pCLENBQUM7WUFDRCxPQUFPLHFGQUFxRixDQUFDO1FBQy9GLENBQUM7YUFBTSxDQUFDO1lBQ04sTUFBTSxPQUFPLEdBQTBCLE1BQU0sVUFBVSxDQUNyRCxNQUFNLEVBQ04sV0FBVyxDQUNaLENBQUM7WUFDRixJQUFJLE9BQU8sRUFBRSxDQUFDO2dCQUNaLE1BQU0sSUFBSSxHQUNSLEdBQUcsT0FBTyxDQUFDLFVBQVUsQ0FBQyxTQUFTLElBQUksRUFBRSxJQUFJLE9BQU8sQ0FBQyxVQUFVLENBQUMsUUFBUSxJQUFJLEVBQUUsRUFBRSxDQUFDLElBQUksRUFBRSxDQUFDO2dCQUN0RixJQUFJLGNBQWMsR0FBRywrQkFBK0IsT0FBTyxDQUFDLEVBQUUsV0FBVyxJQUFJLElBQUksS0FBSyxZQUFZLE9BQU8sQ0FBQyxVQUFVLENBQUMsS0FBSyxJQUFJLEtBQUssY0FBYyxPQUFPLENBQUMsVUFBVSxDQUFDLE9BQU8sSUFBSSxLQUFLLEVBQUUsQ0FBQztnQkFDdkwsSUFBSSxPQUFPLENBQUMsVUFB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WSxPQUFPLENBQUMsVUFBVSxDQUFDLEtBQUssR0FBRyxDQUFDO1lBQ2pJLENBQUM7aUJBQU0sQ0FBQztnQkFDTixPQUFPLDZDQUE2QyxlQUFlLENBQUMsT0FBTyxJQUFJLHdCQUF3QixFQUFFLENBQUM7WUFDNUcsQ0FBQztRQUNILENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixPQUFPLFdBQVcsQ0FDaEIsS0FBSyxFQUNMLCtFQUErRSxDQUNoRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBIdWJTcG90Q29udGFjdFByb3BlcnRpZXMsXG4gIENyZWF0ZUh1YlNwb3RDb250YWN0UmVzcG9uc2UsXG4gIEh1YlNwb3RDb250YWN0LFxufSBmcm9tICcuLi8uLi90eXBlcyc7XG5pbXBvcnQge1xuICBjcmVhdGVIdWJTcG90Q29udGFjdCBhcyBjcmVhdGUsXG4gIGdldEh1YlNwb3RDb250YWN0QnlFbWFpbCBhcyBnZXRCeUVtYWlsLFxufSBmcm9tICcuL2h1YnNwb3RTa2lsbHMnO1xuaW1wb3J0IHsgQVRPTV9IVUJTUE9UX1BPUlRBTF9JRCB9IGZyb20gJy4uLy4uL19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBoYW5kbGVFcnJvciB9IGZyb20gJy4uLy4uL191dGlscy9lcnJvckhhbmRsZXInO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlR2V0SHViU3BvdENvbnRhY3RCeUVtYWlsKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBlbWFpbEVudGl0eSA9IGVudGl0aWVzPy5lbWFpbDtcbiAgICBpZiAoXG4gICAgICAhZW1haWxFbnRpdHkgfHxcbiAgICAgIHR5cGVvZiBlbWFpbEVudGl0eSAhPT0gJ3N0cmluZycgfHxcbiAgICAgIGVtYWlsRW50aXR5LnRyaW0oKSA9PT0gJydcbiAgICApIHtcbiAgICAgIHJldHVybiAnRW1haWwgaXMgcmVxdWlyZWQgYW5kIG11c3QgYmUgYSBub24tZW1wdHkgc3RyaW5nIHRvIGdldCBhIEh1YlNwb3QgY29udGFjdCBieSBlbWFpbC4nO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBjb250YWN0OiBIdWJTcG90Q29udGFjdCB8IG51bGwgPSBhd2FpdCBnZXRCeUVtYWlsKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGVtYWlsRW50aXR5XG4gICAgICApO1xuICAgICAgaWYgKGNvbnRhY3QpIHtcbiAgICAgICAgY29uc3QgbmFtZSA9XG4gICAgICAgICAgYCR7Y29udGFjdC5wcm9wZXJ0aWVzLmZpcnN0bmFtZSB8fCAnJ30gJHtjb250YWN0LnByb3BlcnRpZXMubGFzdG5hbWUgfHwgJyd9YC50cmltKCk7XG4gICAgICAgIGxldCByZXNwb25zZVN0cmluZyA9IGBIdWJTcG90IENvbnRhY3QgRm91bmQ6XFxuSUQ6ICR7Y29udGFjdC5pZH1cXG5OYW1lOiAke25hbWUgfHwgJ04vQSd9XFxuRW1haWw6ICR7Y29udGFjdC5wcm9wZXJ0aWVzLmVtYWlsIHx8ICdOL0EnfVxcbkNvbXBhbnk6ICR7Y29udGFjdC5wcm9wZXJ0aWVzLmNvbXBhbnkgfHwgJ04vQSd9YDtcbiAgICAgICAgaWYgKGNvbnRhY3QucHJvcGVydGllcy5jcmVhdGVkYXRlKVxuICAgICAgICAgIHJlc3BvbnNlU3RyaW5nICs9IGBcXG5DcmVhdGVkOiAke25ldyBEYXRlKGNvbnRhY3QucHJvcGVydGllcy5jcmVhdGVkYXRlKS50b0xvY2FsZVN0cmluZygpfWA7XG4gICAgICAgIGlmIChjb250YWN0LnByb3BlcnRpZXMubGFzdG1vZGlmaWVkZGF0ZSlcbiAgICAgICAgICByZXNwb25zZVN0cmluZyArPSBgXFxuTGFzdCBNb2RpZmllZDogJHtuZXcgRGF0ZShjb250YWN0LnByb3BlcnRpZXMubGFzdG1vZGlmaWVkZGF0ZSkudG9Mb2NhbGVTdHJpbmcoKX1gO1xuICAgICAgICBpZiAoQVRPTV9IVUJTUE9UX1BPUlRBTF9JRCAmJiBjb250YWN0LmlkKVxuICAgICAgICAgIHJlc3BvbnNlU3RyaW5nICs9IGBcXG5WaWV3IGluIEh1YlNwb3Q6IGh0dHBzOi8vYXBwLmh1YnNwb3QuY29tL2NvbnRhY3RzLyR7QVRPTV9IVUJTUE9UX1BPUlRBTF9JRH0vY29udGFjdC8ke2NvbnRhY3QuaWR9YDtcbiAgICAgICAgcmV0dXJuIHJlc3BvbnNlU3RyaW5nO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgcmV0dXJuIGBObyBIdWJTcG90IGNvbnRhY3QgZm91bmQgd2l0aCBlbWFpbDogJHtlbWFpbEVudGl0eX0uYDtcbiAgICAgIH1cbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICByZXR1cm4gaGFuZGxlRXJyb3IoXG4gICAgICBlcnJvcixcbiAgICAgICdTb3JyeSwgYW4gZXJyb3Igb2NjdXJyZWQgd2hpbGUgdHJ5aW5nIHRvIHJldHJpZXZlIHRoZSBIdWJTcG90IGNvbnRhY3QuJ1xuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZUNyZWF0ZUh1YlNwb3RDb250YWN0KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGVtYWlsLCBmaXJzdF9uYW1lLCBsYXN0X25hbWUsIGNvbnRhY3RfbmFtZSwgY29tcGFueV9uYW1lIH0gPVxuICAgICAgZW50aXRpZXM7XG4gICAgaWYgKCFlbWFpbCB8fCB0eXBlb2YgZW1haWwgIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm4gJ0VtYWlsIGlzIHJlcXVpcmVkIChhbmQgbXVzdCBiZSBhIHN0cmluZykgdG8gY3JlYXRlIGEgSHViU3BvdCBjb250YWN0IHZpYSBOTFUuJztcbiAgICB9IGVsc2Uge1xuICAgICAgbGV0IGZpbmFsRmlyc3ROYW1lID0gZmlyc3RfbmFtZTtcbiAgICAgIGxldCBmaW5hbExhc3ROYW1lID0gbGFzdF9uYW1lO1xuICAgICAgaWYgKFxuICAgICAgICAhZmluYWxGaXJzdE5hbWUgJiZcbiAgICAgICAgIWZpbmFsTGFzdE5hbWUgJiZcbiAgICAgICAgY29udGFjdF9uYW1lICYmXG4gICAgICAgIHR5cGVvZiBjb250YWN0X25hbWUgPT09ICdzdHJpbmcnXG4gICAgICApIHtcbiAgICAgICAgY29uc3QgbmFtZVBhcnRzID0gY29udGFjdF9uYW1lLnNwbGl0KCcgJyk7XG4gICAgICAgIGZpbmFsRmlyc3ROYW1lID0gbmFtZVBhcnRzWzBdO1xuICAgICAgICBpZiAobmFtZVBhcnRzLmxlbmd0aCA+IDEpIGZpbmFsTGFzdE5hbWUgPSBuYW1lUGFydHMuc2xpY2UoMSkuam9pbignICcpO1xuICAgICAgfVxuICAgICAgY29uc3QgY29udGFjdERldGFpbHM6IEh1YlNwb3RDb250YWN0UHJvcGVydGllcyA9IHtcbiAgICAgICAgZW1haWwsXG4gICAgICAgIGZpcnN0bmFtZTpcbiAgICAgICAgICB0eXBlb2YgZmluYWxGaXJzdE5hbWUgPT09ICdzdHJpbmcnID8gZmluYWxGaXJzdE5hbWUgOiB1bmRlZmluZWQsXG4gICAgICAgIGxhc3RuYW1lOiB0eXBlb2YgZmluYWxMYXN0TmFtZSA9PT0gJ3N0cmluZycgPyBmaW5hbExhc3ROYW1lIDogdW5kZWZpbmVkLFxuICAgICAgICBjb21wYW55OiB0eXBlb2YgY29tcGFueV9uYW1lID09PSAnc3RyaW5nJyA/IGNvbXBhbnlfbmFtZSA6IHVuZGVmaW5lZCxcbiAgICAgIH07XG4gICAgICBjb25zdCBodWJzcG90UmVzcG9uc2U6IENyZWF0ZUh1YlNwb3RDb250YWN0UmVzcG9uc2UgPSBhd2FpdCBjcmVhdGUoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgY29udGFjdERldGFpbHNcbiAgICAgICk7XG4gICAgICBpZiAoXG4gICAgICAgIGh1YnNwb3RSZXNwb25zZS5zdWNjZXNzICYmXG4gICAgICAgIGh1YnNwb3RSZXNwb25zZS5jb250YWN0SWQgJiZcbiAgICAgICAgaHVic3BvdFJlc3BvbnNlLmh1YlNwb3RDb250YWN0XG4gICAgICApIHtcbiAgICAgICAgY29uc3QgY29udGFjdCA9IGh1YnNwb3RSZXNwb25zZS5odWJTcG90Q29udGFjdDtcbiAgICAgICAgY29uc3QgbmFtZSA9XG4gICAgICAgICAgYCR7Y29udGFjdC5wcm9wZXJ0aWVzLmZpcnN0bmFtZSB8fCAnJ30gJHtjb250YWN0LnByb3BlcnRpZXMubGFzdG5hbWUgfHwgJyd9YC50cmltKCkgfHxcbiAgICAgICAgICAnTi9BJztcbiAgICAgICAgcmV0dXJuIGBIdWJTcG90IGNvbnRhY3QgY3JlYXRlZCB2aWEgTkxVISBJRDogJHtodWJzcG90UmVzcG9uc2UuY29udGFjdElkfS4gTmFtZTogJHtuYW1lfS4gRW1haWw6ICR7Y29udGFjdC5wcm9wZXJ0aWVzLmVtYWlsfS5gO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgcmV0dXJuIGBGYWlsZWQgdG8gY3JlYXRlIEh1YlNwb3QgY29udGFjdCB2aWEgTkxVOiAke2h1YnNwb3RSZXNwb25zZS5tZXNzYWdlIHx8ICdVbmtub3duIEh1YlNwb3QgZXJyb3IuJ31gO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgJ1NvcnJ5LCB0aGVyZSB3YXMgYW4gaXNzdWUgY3JlYXRpbmcgdGhlIEh1YlNwb3QgY29udGFjdCBiYXNlZCBvbiB5b3VyIHJlcXVlc3QuJ1xuICAgICk7XG4gIH1cbn1cbiJdfQ==