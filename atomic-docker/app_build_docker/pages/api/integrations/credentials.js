"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const nextjs_1 = require("supertokens-node/nextjs");
const graphqlClient_1 = require("../../../../project/functions/_libs/graphqlClient");
const crypto_1 = require("../../../../project/functions/_libs/crypto"); // Assuming crypto utils exist
async function saveCredential(userId, service, secret) {
    const encryptedSecret = (0, crypto_1.encrypt)(secret);
    const mutation = `
        mutation InsertUserCredential($userId: String!, $serviceName: String!, $secret: String!) {
            insert_user_credentials_one(object: {user_id: $userId, service_name: $serviceName, encrypted_secret: $secret}, on_conflict: {constraint: user_credentials_pkey, update_columns: encrypted_secret}) {
                user_id
            }
        }
    `;
    const variables = {
        userId,
        serviceName: service,
        secret: encryptedSecret,
    };
    await (0, graphqlClient_1.executeGraphQLMutation)(mutation, variables, 'InsertUserCredential', userId);
}
async function getCredential(userId, service) {
    const query = `
        query GetUserSetting($userId: String!, $key: String!) {
            user_settings(where: {user_id: {_eq: $userId}, key: {_eq: $key}}) {
                value
            }
        }
    `;
    const variables = {
        userId,
        key: service,
    };
    const response = await (0, graphqlClient_1.executeGraphQLQuery)(query, variables, 'GetUserSetting', userId);
    if (response.user_settings && response.user_settings.length > 0) {
        return { isConnected: true, value: response.user_settings[0].value };
    }
    return { isConnected: false };
}
async function handler(req, res) {
    let session;
    try {
        session = await (0, nextjs_1.getSession)(req, res, {
            overrideGlobalClaimValidators: () => [],
        });
    }
    catch (err) {
        return res.status(401).json({ message: 'Unauthorized' });
    }
    const userId = session.getUserId();
    if (req.method === 'POST') {
        const { service, secret } = req.body;
        if (!service || !secret) {
            return res
                .status(400)
                .json({ message: 'Service and secret are required' });
        }
        try {
            await saveCredential(userId, service, secret);
            return res
                .status(200)
                .json({ message: `${service} credentials saved successfully` });
        }
        catch (error) {
            console.error(`Error saving ${service} credentials:`, error);
            return res
                .status(500)
                .json({ message: `Failed to save ${service} credentials` });
        }
    }
    else if (req.method === 'GET') {
        const { service } = req.query;
        if (!service) {
            return res.status(400).json({ message: 'Service is required' });
        }
        try {
            const credential = await getCredential(userId, service);
            return res.status(200).json(credential);
        }
        catch (error) {
            console.error(`Error checking ${service} credentials:`, error);
            return res
                .status(500)
                .json({ message: `Failed to check ${service} credentials` });
        }
    }
    else {
        res.setHeader('Allow', ['POST', 'GET']);
        res.status(405).end(`Method ${req.method} Not Allowed`);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY3JlZGVudGlhbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjcmVkZW50aWFscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQXVEQSwwQkFtREM7QUF6R0Qsb0RBQXFEO0FBRXJELHFGQUcyRDtBQUMzRCx1RUFBOEUsQ0FBQyw4QkFBOEI7QUFFN0csS0FBSyxVQUFVLGNBQWMsQ0FBQyxNQUFjLEVBQUUsT0FBZSxFQUFFLE1BQWM7SUFDM0UsTUFBTSxlQUFlLEdBQUcsSUFBQSxnQkFBTyxFQUFDLE1BQU0sQ0FBQyxDQUFDO0lBQ3hDLE1BQU0sUUFBUSxHQUFHOzs7Ozs7S0FNZCxDQUFDO0lBQ0osTUFBTSxTQUFTLEdBQUc7UUFDaEIsTUFBTTtRQUNOLFdBQVcsRUFBRSxPQUFPO1FBQ3BCLE1BQU0sRUFBRSxlQUFlO0tBQ3hCLENBQUM7SUFDRixNQUFNLElBQUEsc0NBQXNCLEVBQzFCLFFBQVEsRUFDUixTQUFTLEVBQ1Qsc0JBQXNCLEVBQ3RCLE1BQU0sQ0FDUCxDQUFDO0FBQ0osQ0FBQztBQUVELEtBQUssVUFBVSxhQUFhLENBQzFCLE1BQWMsRUFDZCxPQUFlO0lBRWYsTUFBTSxLQUFLLEdBQUc7Ozs7OztLQU1YLENBQUM7SUFDSixNQUFNLFNBQVMsR0FBRztRQUNoQixNQUFNO1FBQ04sR0FBRyxFQUFFLE9BQU87S0FDYixDQUFDO0lBQ0YsTUFBTSxRQUFRLEdBQUcsTUFBTSxJQUFBLG1DQUFtQixFQUV2QyxLQUFLLEVBQUUsU0FBUyxFQUFFLGdCQUFnQixFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQy9DLElBQUksUUFBUSxDQUFDLGFBQWEsSUFBSSxRQUFRLENBQUMsYUFBYSxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztRQUNoRSxPQUFPLEVBQUUsV0FBVyxFQUFFLElBQUksRUFBRSxLQUFLLEVBQUUsUUFBUSxDQUFDLGFBQWEsQ0FBQyxDQUFDLENBQUMsQ0FBQyxLQUFLLEVBQUUsQ0FBQztJQUN2RSxDQUFDO0lBQ0QsT0FBTyxF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QUMsVUFBVSxHQUFHLENBQUMsTUFBTSxjQUFjLENBQUMsQ0FBQztJQUMxRCxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7IGdldFNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL25leHRqcyc7XG5pbXBvcnQgeyBTZXNzaW9uQ29udGFpbmVyIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQge1xuICBleGVjdXRlR3JhcGhRTE11dGF0aW9uLFxuICBleGVjdXRlR3JhcGhRTFF1ZXJ5LFxufSBmcm9tICcuLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9fbGlicy9ncmFwaHFsQ2xpZW50JztcbmltcG9ydCB7IGVuY3J5cHQsIGRlY3J5cHQgfSBmcm9tICcuLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9fbGlicy9jcnlwdG8nOyAvLyBBc3N1bWluZyBjcnlwdG8gdXRpbHMgZXhpc3RcblxuYXN5bmMgZnVuY3Rpb24gc2F2ZUNyZWRlbnRpYWwodXNlcklkOiBzdHJpbmcsIHNlcnZpY2U6IHN0cmluZywgc2VjcmV0OiBzdHJpbmcpIHtcbiAgY29uc3QgZW5jcnlwdGVkU2VjcmV0ID0gZW5jcnlwdChzZWNyZXQpO1xuICBjb25zdCBtdXRhdGlvbiA9IGBcbiAgICAgICAgbXV0YXRpb24gSW5zZXJ0VXNlckNyZWRlbnRpYWwoJHVzZXJJZDogU3RyaW5nISwgJHNlcnZpY2VOYW1lOiBTdHJpbmchLCAkc2VjcmV0OiBTdHJpbmchKSB7XG4gICAgICAgICAgICBpbnNlcnRfdXNlcl9jcmVkZW50aWFsc19vbmUob2JqZWN0OiB7dXNlcl9pZDogJHVzZXJJZCwgc2VydmljZV9uYW1lOiAkc2VydmljZU5hbWUsIGVuY3J5cHRlZF9zZWNyZXQ6ICRzZWNyZXR9LCBvbl9jb25mbGljdDoge2NvbnN0cmFpbnQ6IHVzZXJfY3JlZGVudGlhbHNfcGtleSwgdXBkYXRlX2NvbHVtbnM6IGVuY3J5cHRlZF9zZWNyZXR9KSB7XG4gICAgICAgICAgICAgICAgdXNlcl9pZFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgIHVzZXJJZCxcbiAgICBzZXJ2aWNlTmFtZTogc2VydmljZSxcbiAgICBzZWNyZXQ6IGVuY3J5cHRlZFNlY3JldCxcbiAgfTtcbiAgYXdhaXQgZXhlY3V0ZUdyYXBoUUxNdXRhdGlvbihcbiAgICBtdXRhdGlvbixcbiAgICB2YXJpYWJsZXMsXG4gICAgJ0luc2VydFVzZXJDcmVkZW50aWFsJyxcbiAgICB1c2VySWRcbiAgKTtcbn1cblxuYXN5bmMgZnVuY3Rpb24gZ2V0Q3JlZGVudGlhbChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHNlcnZpY2U6IHN0cmluZ1xuKTogUHJvbWlzZTx7IGlzQ29ubmVjdGVkOiBib29sZWFuOyB2YWx1ZT86IHN0cmluZyB8IG51bGwgfT4ge1xuICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgR2V0VXNlclNldHRpbmcoJHVzZXJJZDogU3RyaW5nISwgJGtleTogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl9zZXR0aW5ncyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9LCBrZXk6IHtfZXE6ICRrZXl9fSkge1xuICAgICAgICAgICAgICAgIHZhbHVlXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgO1xuICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgdXNlcklkLFxuICAgIGtleTogc2VydmljZSxcbiAgfTtcbiAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICB1c2VyX3NldHRpbmdzOiB7IHZhbHVlOiBzdHJpbmcgfVtdO1xuICB9PihxdWVyeSwgdmFyaWFibGVzLCAnR2V0VXNlclNldHRpbmcnLCB1c2VySWQpO1xuICBpZiAocmVzcG9uc2UudXNlcl9zZXR0aW5ncyAmJiByZXNwb25zZS51c2VyX3NldHRpbmdzLmxlbmd0aCA+IDApIHtcbiAgICByZXR1cm4geyBpc0Nvbm5lY3RlZDogdHJ1ZSwgdmFsdWU6IHJlc3BvbnNlLnVzZXJfc2V0dGluZ3NbMF0udmFsdWUgfTtcbiAgfVxuICByZXR1cm4geyBpc0Nvbm5lY3RlZDogZmFsc2UgfTtcbn1cblxuZXhwb3J0IGRlZmF1bHQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlcihcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2Vcbikge1xuICBsZXQgc2Vzc2lvbjogU2Vzc2lvbkNvbnRhaW5lcjtcbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6ICgpID0+IFtdLFxuICAgIH0pO1xuICB9IGNhdGNoIChlcnIpIHtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDEpLmpzb24oeyBtZXNzYWdlOiAnVW5hdXRob3JpemVkJyB9KTtcbiAgfVxuXG4gIGNvbnN0IHVzZXJJZCA9IHNlc3Npb24uZ2V0VXNlcklkKCk7XG5cbiAgaWYgKHJlcS5tZXRob2QgPT09ICdQT1NUJykge1xuICAgIGNvbnN0IHsgc2VydmljZSwgc2VjcmV0IH0gPSByZXEuYm9keTtcbiAgICBpZiAoIXNlcnZpY2UgfHwgIXNlY3JldCkge1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgLmpzb24oeyBtZXNzYWdlOiAnU2VydmljZSBhbmQgc2VjcmV0IGFyZSByZXF1aXJlZCcgfSk7XG4gICAgfVxuICAgIHRyeSB7XG4gICAgICBhd2FpdCBzYXZlQ3JlZGVudGlhbCh1c2VySWQsIHNlcnZpY2UsIHNlY3JldCk7XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoMjAwKVxuICAgICAgICAuanNvbih7IG1lc3NhZ2U6IGAke3NlcnZpY2V9IGNyZWRlbnRpYWxzIHNhdmVkIHN1Y2Nlc3NmdWxseWAgfSk7XG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoYEVycm9yIHNhdmluZyAke3NlcnZpY2V9IGNyZWRlbnRpYWxzOmAsIGVycm9yKTtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHsgbWVzc2FnZTogYEZhaWxlZCB0byBzYXZlICR7c2VydmljZX0gY3JlZGVudGlhbHNgIH0pO1xuICAgIH1cbiAgfSBlbHNlIGlmIChyZXEubWV0aG9kID09PSAnR0VUJykge1xuICAgIGNvbnN0IHsgc2VydmljZSB9ID0gcmVxLnF1ZXJ5O1xuICAgIGlmICghc2VydmljZSkge1xuICAgICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAwKS5qc29uKHsgbWVzc2FnZTogJ1NlcnZpY2UgaXMgcmVxdWlyZWQnIH0pO1xuICAgIH1cbiAgICB0cnkge1xuICAgICAgY29uc3QgY3JlZGVudGlhbCA9IGF3YWl0IGdldENyZWRlbnRpYWwodXNlcklkLCBzZXJ2aWNlIGFzIHN0cmluZyk7XG4gICAgICByZXR1cm4gcmVzLnN0YXR1cygyMDApLmpzb24oY3JlZGVudGlhbCk7XG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoYEVycm9yIGNoZWNraW5nICR7c2VydmljZX0gY3JlZGVudGlhbHM6YCwgZXJyb3IpO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oeyBtZXNzYWdlOiBgRmFpbGVkIHRvIGNoZWNrICR7c2VydmljZX0gY3JlZGVudGlhbHNgIH0pO1xuICAgIH1cbiAgfSBlbHNlIHtcbiAgICByZXMuc2V0SGVhZGVyKCdBbGxvdycsIFsnUE9TVCcsICdHRVQnXSk7XG4gICAgcmVzLnN0YXR1cyg0MDUpLmVuZChgTWV0aG9kICR7cmVxLm1ldGhvZH0gTm90IEFsbG93ZWRgKTtcbiAgfVxufVxuIl19