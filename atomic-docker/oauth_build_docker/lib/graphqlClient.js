"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.executeGraphQLMutation = executeGraphQLMutation;
const got_1 = __importDefault(require("got"));
const constants_1 = require("./constants");
async function executeGraphQLMutation(mutation, variables, operationName, userId) {
    const response = await got_1.default
        .post(constants_1.hasuraGraphUrl, {
        json: {
            query: mutation,
            variables,
            operationName,
        },
        headers: {
            'X-Hasura-Admin-Secret': constants_1.hasuraAdminSecret,
            'Content-Type': 'application/json',
            'X-Hasura-Role': 'user',
            'X-Hasura-User-Id': userId,
        },
    })
        .json();
    return response;
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ3JhcGhxbENsaWVudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImdyYXBocWxDbGllbnQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFHQSx3REFzQkM7QUF6QkQsOENBQXNCO0FBQ3RCLDJDQUFnRTtBQUV6RCxLQUFLLFVBQVUsc0JBQXNCLENBQzFDLFFBQWdCLEVBQ2hCLFNBQWMsRUFDZCxhQUFxQixFQUNyQixNQUFjO0lBRWQsTUFBTSxRQUFRLEdBQUcsTUFBTSxhQUFHO1NBQ3ZCLElBQUksQ0FBQywwQkFBYyxFQUFFO1FBQ3BCLElBQUksRUFBRTtZQUNKLEtBQUssRUFBRSxRQUFRO1lBQ2YsU0FBUztZQUNULGFBQWE7U0FDZDtRQUNELE9BQU8sRUFBRTtZQUNQLHVCQUF1QixFQUFFLDZCQUFpQjtZQUMxQyxjQUFjLEVBQUUsa0JBQWtCO1lBQ2xDLGVBQWUsRUFBRSxNQUFNO1lBQ3ZCLGtCQUFrQixFQUFFLE1BQU07U0FDM0I7S0FDRixDQUFDO1NBQ0QsSUFBSSxFQUFFLENBQUM7SUFDVixPQUFPLFFBQWEsQ0FBQztBQUN2QixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IHsgaGFzdXJhQWRtaW5TZWNyZXQsIGhhc3VyYUdyYXBoVXJsIH0gZnJvbSAnLi9jb25zdGFudHMnO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZXhlY3V0ZUdyYXBoUUxNdXRhdGlvbjxUPihcbiAgbXV0YXRpb246IHN0cmluZyxcbiAgdmFyaWFibGVzOiBhbnksXG4gIG9wZXJhdGlvbk5hbWU6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmdcbik6IFByb21pc2U8VD4ge1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdFxuICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICBqc29uOiB7XG4gICAgICAgIHF1ZXJ5OiBtdXRhdGlvbixcbiAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgfSxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICd1c2VyJyxcbiAgICAgICAgJ1gtSGFzdXJhLVVzZXItSWQnOiB1c2VySWQsXG4gICAgICB9LFxuICAgIH0pXG4gICAgLmpzb24oKTtcbiAgcmV0dXJuIHJlc3BvbnNlIGFzIFQ7XG59XG4iXX0=