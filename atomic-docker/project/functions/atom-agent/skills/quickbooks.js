import { getAuthUri, listQuickBooksInvoices as listInvoices, getQuickBooksInvoiceDetails as getInvoiceDetails, } from './quickbooksSkills';
import { ATOM_QB_TOKEN_FILE_PATH } from '../../_libs/constants';
import { handleError } from '../../_utils/errorHandler';
export async function handleGetQuickBooksAuthUrl(userId, entities) {
    try {
        const authUri = getAuthUri();
        if (authUri) {
            return `To authorize QuickBooks Online (via NLU), please visit this URL in your browser: ${authUri}\nAfter authorization, the agent will need the resulting tokens and realmId to be stored in its configured token file path (${ATOM_QB_TOKEN_FILE_PATH}). This step typically requires manual intervention or a separate callback handler not part of this command.`;
        }
        else {
            return 'Could not generate QuickBooks authorization URL (via NLU). Please check server configuration.';
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, an error occurred while generating the QuickBooks authorization URL (NLU path).');
    }
}
export async function handleListQuickBooksInvoices(userId, entities) {
    try {
        const { customer_id, status, limit: nluLimit, offset: nluOffset, } = entities;
        const options = {};
        if (nluLimit) {
            if (typeof nluLimit === 'number')
                options.limit = nluLimit;
            else if (typeof nluLimit === 'string') {
                const parsed = parseInt(nluLimit, 10);
                if (!isNaN(parsed))
                    options.limit = parsed;
            }
        }
        if (nluOffset) {
            if (typeof nluOffset === 'number')
                options.offset = nluOffset;
            else if (typeof nluOffset === 'string') {
                const parsed = parseInt(nluOffset, 10);
                if (!isNaN(parsed))
                    options.offset = parsed;
            }
        }
        if (customer_id && typeof customer_id === 'string')
            options.customerId = customer_id;
        if (status && typeof status === 'string')
            console.log(`[handleListQuickBooksInvoices] NLU: received status filter: ${status}. Currently illustrative, skill may not filter by it.`);
        const response = await listInvoices(options);
        if (response.ok && response.invoices && response.invoices.length > 0) {
            let output = 'QuickBooks Invoices (via NLU):\n';
            for (const inv of response.invoices) {
                output += `- ID: ${inv.Id}, Num: ${inv.DocNumber || 'N/A'}, Cust: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}, Total: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\n`;
            }
            if (response.queryResponse)
                output += `Showing results. Max per page: ${response.queryResponse.maxResults || options.limit}\n`;
            return output;
        }
        else if (response.ok) {
            return 'No QuickBooks invoices found via NLU matching your criteria.';
        }
        else {
            return `Error fetching QuickBooks invoices via NLU: ${response.error || 'Unknown error'}. Ensure QuickBooks is connected and authorized.`;
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, an error occurred while fetching QuickBooks invoices via NLU.');
    }
}
export async function handleGetQuickBooksInvoiceDetails(userId, entities) {
    try {
        const { invoice_id } = entities;
        if (!invoice_id || typeof invoice_id !== 'string') {
            return 'Invoice ID is required to get QuickBooks invoice details via NLU.';
        }
        else {
            const response = await getInvoiceDetails(invoice_id);
            if (response.ok && response.invoice) {
                const inv = response.invoice;
                return `QuickBooks Invoice (ID: ${inv.Id}):\nDoc #: ${inv.DocNumber || 'N/A'}\nCustomer: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}\nTotal: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\nBalance: ${inv.Balance !== undefined ? inv.Balance.toFixed(2) : 'N/A'}`;
            }
            else {
                return `Error fetching QuickBooks invoice details via NLU: ${response.error || 'Invoice not found or error occurred.'}`;
            }
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, an error occurred while fetching QuickBooks invoice details via NLU.');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicXVpY2tib29rcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInF1aWNrYm9va3MudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBSUEsT0FBTyxFQUNMLFVBQVUsRUFDVixzQkFBc0IsSUFBSSxZQUFZLEVBQ3RDLDJCQUEyQixJQUFJLGlCQUFpQixHQUNqRCxNQUFNLG9CQUFvQixDQUFDO0FBQzVCLE9BQU8sRUFBRSx1QkFBdUIsRUFBRSxNQUFNLHVCQUF1QixDQUFDO0FBQ2hFLE9BQU8sRUFBRSxXQUFXLEVBQUUsTUFBTSwyQkFBMkIsQ0FBQztBQUV4RCxNQUFNLENBQUMsS0FBSyxVQUFVLDBCQUEwQixDQUM5QyxNQUFjLEVBQ2QsUUFBYTtJQUViLElBQUksQ0FBQztRQUNILE1BQU0sT0FBTyxHQUFHLFVBQVUsRUFBRSxDQUFDO1FBQzdCLElBQUksT0FBTyxFQUFFLENBQUM7WUFDWixPQUFPLG9GQUFvRixPQUFPLCtIQUErSCx1QkFBdUIsOEdBQThHLENBQUM7UUFDelcsQ0FBQzthQUFNLENBQUM7WUFDTixPQUFPLCtGQUErRixDQUFDO1FBQ3pHLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixPQUFPLFdBQVcsQ0FDaEIsS0FBSyxFQUNMLHdGQUF3RixDQUN6RixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLDRCQUE0QixDQUNoRCxNQUFjLEVBQ2QsUUFBYTtJQUViLElBQUksQ0FBQztRQUNILE1BQU0sRUFDSixXQUFXLEVBQ1gsTUFBTSxFQUNOLEtBQUssRUFBRSxRQUFRLEVBQ2YsTUFBTSxFQUFFLFNBQVMsR0FDbEIsR0FBRyxRQUFRLENBQUM7UUFDYixNQUFNLE9BQU8sR0FLVCxFQUFFLENBQUM7UUFDUCxJQUFJLFFBQVEsRUFBRSxDQUFDO1lBQ2IsSUFBSSxPQUFPLFFBQVEsS0FBSyxRQUFRO2dCQUFFLE9BQU8sQ0FBQyxLQUFLLEdBQUcsUUFBUSxDQUFDO2lC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QkFBaUIsQ0FBQyxVQUFVLENBQUMsQ0FBQztZQUN0QyxJQUFJLFFBQVEsQ0FBQyxFQUFFLElBQUksUUFBUSxDQUFDLE9BQU8sRUFBRSxDQUFDO2dCQUNwQyxNQUFNLEdBQUcsR0FBRyxRQUFRLENBQUMsT0FBTyxDQUFDO2dCQUM3QixPQUFPLDJCQUEyQixHQUFHLENBQUMsRUFBRSxjQUFjLEdBQUcsQ0FBQyxTQUFTLElBQUksS0FBSyxlQUFlLEdBQUcsQ0FBQyxXQUFXLEVBQUUsSUFBSSxJQUFJLEdBQUcsQ0FBQyxXQUFXLEVBQUUsS0FBSyxJQUFJLEtBQUssWUFBWSxHQUFHLENBQUMsUUFBUSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsR0FBRyxDQUFDLFFBQVEsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLEtBQUssSUFBSSxHQUFHLENBQUMsV0FBVyxFQUFFLEtBQUssSUFBSSxFQUFFLGNBQWMsR0FBRyxDQUFDLE9BQU8sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxPQUFPLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUN4VSxDQUFDO2lCQUFNLENBQUM7Z0JBQ04sT0FBTyxzREFBc0QsUUFBUSxDQUFDLEtBQUssSUFBSSxzQ0FBc0MsRUFBRSxDQUFDO1lBQzFILENBQUM7UUFDSCxDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsT0FBTyxXQUFXLENBQ2hCLEtBQUssRUFDTCw2RUFBNkUsQ0FDOUUsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgTGlzdFF1aWNrQm9va3NJbnZvaWNlc1Jlc3BvbnNlLFxuICBHZXRRdWlja0Jvb2tzSW52b2ljZURldGFpbHNSZXNwb25zZSxcbn0gZnJvbSAnLi4vLi4vdHlwZXMnO1xuaW1wb3J0IHtcbiAgZ2V0QXV0aFVyaSxcbiAgbGlzdFF1aWNrQm9va3NJbnZvaWNlcyBhcyBsaXN0SW52b2ljZXMsXG4gIGdldFF1aWNrQm9va3NJbnZvaWNlRGV0YWlscyBhcyBnZXRJbnZvaWNlRGV0YWlscyxcbn0gZnJvbSAnLi9xdWlja2Jvb2tzU2tpbGxzJztcbmltcG9ydCB7IEFUT01fUUJfVE9LRU5fRklMRV9QQVRIIH0gZnJvbSAnLi4vLi4vX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGhhbmRsZUVycm9yIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2Vycm9ySGFuZGxlcic7XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVHZXRRdWlja0Jvb2tzQXV0aFVybChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVudGl0aWVzOiBhbnlcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIHRyeSB7XG4gICAgY29uc3QgYXV0aFVyaSA9IGdldEF1dGhVcmkoKTtcbiAgICBpZiAoYXV0aFVyaSkge1xuICAgICAgcmV0dXJuIGBUbyBhdXRob3JpemUgUXVpY2tCb29rcyBPbmxpbmUgKHZpYSBOTFUpLCBwbGVhc2UgdmlzaXQgdGhpcyBVUkwgaW4geW91ciBicm93c2VyOiAke2F1dGhVcml9XFxuQWZ0ZXIgYXV0aG9yaXphdGlvbiwgdGhlIGFnZW50IHdpbGwgbmVlZCB0aGUgcmVzdWx0aW5nIHRva2VucyBhbmQgcmVhbG1JZCB0byBiZSBzdG9yZWQgaW4gaXRzIGNvbmZpZ3VyZWQgdG9rZW4gZmlsZSBwYXRoICgke0FUT01fUUJfVE9LRU5fRklMRV9QQVRIfSkuIFRoaXMgc3RlcCB0eXBpY2FsbHkgcmVxdWlyZXMgbWFudWFsIGludGVydmVudGlvbiBvciBhIHNlcGFyYXRlIGNhbGxiYWNrIGhhbmRsZXIgbm90IHBhcnQgb2YgdGhpcyBjb21tYW5kLmA7XG4gICAgfSBlbHNlIHtcbiAgICAgIHJldHVybiAnQ291bGQgbm90IGdlbmVyYXRlIFF1aWNrQm9va3MgYXV0aG9yaXphdGlvbiBVUkwgKHZpYSBOTFUpLiBQbGVhc2UgY2hlY2sgc2VydmVyIGNvbmZpZ3VyYXRpb24uJztcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICByZXR1cm4gaGFuZGxlRXJyb3IoXG4gICAgICBlcnJvcixcbiAgICAgICdTb3JyeSwgYW4gZXJyb3Igb2NjdXJyZWQgd2hpbGUgZ2VuZXJhdGluZyB0aGUgUXVpY2tCb29rcyBhdXRob3JpemF0aW9uIFVSTCAoTkxVIHBhdGgpLidcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVMaXN0UXVpY2tCb29rc0ludm9pY2VzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7XG4gICAgICBjdXN0b21lcl9pZCxcbiAgICAgIHN0YXR1cyxcbiAgICAgIGxpbWl0OiBubHVMaW1pdCxcbiAgICAgIG9mZnNldDogbmx1T2Zmc2V0LFxuICAgIH0gPSBlbnRpdGllcztcbiAgICBjb25zdCBvcHRpb25zOiB7XG4gICAgICBsaW1pdD86IG51bWJlcjtcbiAgICAgIG9mZnNldD86IG51bWJlcjtcbiAgICAgIGN1c3RvbWVySWQ/OiBzdHJpbmc7XG4gICAgICBzdGF0dXM/OiBzdHJpbmc7XG4gICAgfSA9IHt9O1xuICAgIGlmIChubHVMaW1pdCkge1xuICAgICAgaWYgKHR5cGVvZiBubHVMaW1pdCA9PT0gJ251bWJlcicpIG9wdGlvbnMubGltaXQgPSBubHVMaW1pdDtcbiAgICAgIGVsc2UgaWYgKHR5cGVvZiBubHVMaW1pdCA9PT0gJ3N0cmluZycpIHtcbiAgICAgICAgY29uc3QgcGFyc2VkID0gcGFyc2VJbnQobmx1TGltaXQsIDEwKTtcbiAgICAgICAgaWYgKCFpc05hTihwYXJzZWQpKSBvcHRpb25zLmxpbWl0ID0gcGFyc2VkO1xuICAgICAgfVxuICAgIH1cbiAgICBpZiAobmx1T2Zmc2V0KSB7XG4gICAgICBpZiAodHlwZW9mIG5sdU9mZnNldCA9PT0gJ251bWJlcicpIG9wdGlvbnMub2Zmc2V0ID0gbmx1T2Zmc2V0O1xuICAgICAgZWxzZSBpZiAodHlwZW9mIG5sdU9mZnNldCA9PT0gJ3N0cmluZycpIHtcbiAgICAgICAgY29uc3QgcGFyc2VkID0gcGFyc2VJbnQobmx1T2Zmc2V0LCAxMCk7XG4gICAgICAgIGlmICghaXNOYU4ocGFyc2VkKSkgb3B0aW9ucy5vZmZzZXQgPSBwYXJzZWQ7XG4gICAgICB9XG4gICAgfVxuICAgIGlmIChjdXN0b21lcl9pZCAmJiB0eXBlb2YgY3VzdG9tZXJfaWQgPT09ICdzdHJpbmcnKVxuICAgICAgb3B0aW9ucy5jdXN0b21lcklkID0gY3VzdG9tZXJfaWQ7XG4gICAgaWYgKHN0YXR1cyAmJiB0eXBlb2Ygc3RhdHVzID09PSAnc3RyaW5nJylcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgW2hhbmRsZUxpc3RRdWlja0Jvb2tzSW52b2ljZXNdIE5MVTogcmVjZWl2ZWQgc3RhdHVzIGZpbHRlcjogJHtzdGF0dXN9LiBDdXJyZW50bHkgaWxsdXN0cmF0aXZlLCBza2lsbCBtYXkgbm90IGZpbHRlciBieSBpdC5gXG4gICAgICApO1xuICAgIGNvbnN0IHJlc3BvbnNlOiBMaXN0UXVpY2tCb29rc0ludm9pY2VzUmVzcG9uc2UgPVxuICAgICAgYXdhaXQgbGlzdEludm9pY2VzKG9wdGlvbnMpO1xuICAgIGlmIChyZXNwb25zZS5vayAmJiByZXNwb25zZS5pbnZvaWNlcyAmJiByZXNwb25zZS5pbnZvaWNlcy5sZW5ndGggPiAwKSB7XG4gICAgICBsZXQgb3V0cHV0ID0gJ1F1aWNrQm9va3MgSW52b2ljZXMgKHZpYSBOTFUpOlxcbic7XG4gICAgICBmb3IgKGNvbnN0IGludiBvZiByZXNwb25zZS5pbnZvaWNlcykge1xuICAgICAgICBvdXRwdXQgKz0gYC0gSUQ6ICR7aW52LklkfSwgTnVtOiAke2ludi5Eb2NOdW1iZXIgfHwgJ04vQSd9LCBDdXN0OiAke2ludi5DdXN0b21lclJlZj8ubmFtZSB8fCBpbnYuQ3VzdG9tZXJSZWY/LnZhbHVlIHx8ICdOL0EnfSwgVG90YWw6ICR7aW52LlRvdGFsQW10ICE9PSB1bmRlZmluZWQgPyBpbnYuVG90YWxBbXQudG9GaXhlZCgyKSA6ICdOL0EnfSAke2ludi5DdXJyZW5jeVJlZj8udmFsdWUgfHwgJyd9XFxuYDtcbiAgICAgIH1cbiAgICAgIGlmIChyZXNwb25zZS5xdWVyeVJlc3BvbnNlKVxuICAgICAgICBvdXRwdXQgKz0gYFNob3dpbmcgcmVzdWx0cy4gTWF4IHBlciBwYWdlOiAke3Jlc3BvbnNlLnF1ZXJ5UmVzcG9uc2UubWF4UmVzdWx0cyB8fCBvcHRpb25zLmxpbWl0fVxcbmA7XG4gICAgICByZXR1cm4gb3V0cHV0O1xuICAgIH0gZWxzZSBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgIHJldHVybiAnTm8gUXVpY2tCb29rcyBpbnZvaWNlcyBmb3VuZCB2aWEgTkxVIG1hdGNoaW5nIHlvdXIgY3JpdGVyaWEuJztcbiAgICB9IGVsc2Uge1xuICAgICAgcmV0dXJuIGBFcnJvciBmZXRjaGluZyBRdWlja0Jvb2tzIGludm9pY2VzIHZpYSBOTFU6ICR7cmVzcG9uc2UuZXJyb3IgfHwgJ1Vua25vd24gZXJyb3InfS4gRW5zdXJlIFF1aWNrQm9va3MgaXMgY29ubmVjdGVkIGFuZCBhdXRob3JpemVkLmA7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIGhhbmRsZUVycm9yKFxuICAgICAgZXJyb3IsXG4gICAgICAnU29ycnksIGFuIGVycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIFF1aWNrQm9va3MgaW52b2ljZXMgdmlhIE5MVS4nXG4gICAgKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlR2V0UXVpY2tCb29rc0ludm9pY2VEZXRhaWxzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGludm9pY2VfaWQgfSA9IGVudGl0aWVzO1xuICAgIGlmICghaW52b2ljZV9pZCB8fCB0eXBlb2YgaW52b2ljZV9pZCAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnSW52b2ljZSBJRCBpcyByZXF1aXJlZCB0byBnZXQgUXVpY2tCb29rcyBpbnZvaWNlIGRldGFpbHMgdmlhIE5MVS4nO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCByZXNwb25zZTogR2V0UXVpY2tCb29rc0ludm9pY2VEZXRhaWxzUmVzcG9uc2UgPVxuICAgICAgICBhd2FpdCBnZXRJbnZvaWNlRGV0YWlscyhpbnZvaWNlX2lkKTtcbiAgICAgIGlmIChyZXNwb25zZS5vayAmJiByZXNwb25zZS5pbnZvaWNlKSB7XG4gICAgICAgIGNvbnN0IGludiA9IHJlc3BvbnNlLmludm9pY2U7XG4gICAgICAgIHJldHVybiBgUXVpY2tCb29rcyBJbnZvaWNlIChJRDogJHtpbnYuSWR9KTpcXG5Eb2MgIzogJHtpbnYuRG9jTnVtYmVyIHx8ICdOL0EnfVxcbkN1c3RvbWVyOiAke2ludi5DdXN0b21lclJlZj8ubmFtZSB8fCBpbnYuQ3VzdG9tZXJSZWY/LnZhbHVlIHx8ICdOL0EnfVxcblRvdGFsOiAke2ludi5Ub3RhbEFtdCAhPT0gdW5kZWZpbmVkID8gaW52LlRvdGFsQW10LnRvRml4ZWQoMikgOiAnTi9BJ30gJHtpbnYuQ3VycmVuY3lSZWY/LnZhbHVlIHx8ICcnfVxcbkJhbGFuY2U6ICR7aW52LkJhbGFuY2UgIT09IHVuZGVmaW5lZCA/IGludi5CYWxhbmNlLnRvRml4ZWQoMikgOiAnTi9BJ31gO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgcmV0dXJuIGBFcnJvciBmZXRjaGluZyBRdWlja0Jvb2tzIGludm9pY2UgZGV0YWlscyB2aWEgTkxVOiAke3Jlc3BvbnNlLmVycm9yIHx8ICdJbnZvaWNlIG5vdCBmb3VuZCBvciBlcnJvciBvY2N1cnJlZC4nfWA7XG4gICAgICB9XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIGhhbmRsZUVycm9yKFxuICAgICAgZXJyb3IsXG4gICAgICAnU29ycnksIGFuIGVycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIFF1aWNrQm9va3MgaW52b2ljZSBkZXRhaWxzIHZpYSBOTFUuJ1xuICAgICk7XG4gIH1cbn1cbiJdfQ==