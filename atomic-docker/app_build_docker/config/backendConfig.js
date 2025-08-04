"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.backendConfig = void 0;
const thirdpartyemailpassword_1 = __importDefault(require("supertokens-node/recipe/thirdpartyemailpassword"));
const session_1 = __importDefault(require("supertokens-node/recipe/session"));
const appInfo_1 = require("./appInfo");
const backendConfig = () => {
    return {
        framework: 'express',
        supertokens: {
            // https://try.supertokens.com is for demo purposes. Replace this with the address of your core instance (sign up on supertokens.com), or self host a core.
            connectionURI: 'http://supertokens:3567',
            // apiKey: <API_KEY(if configured)>,
        },
        appInfo: appInfo_1.appInfo,
        recipeList: [
            thirdpartyemailpassword_1.default.init({
                // We have provided you with development keys which you can use for testing.
                // IMPORTANT: Please replace them with your own OAuth keys for production use.
                providers: [
                    {
                        config: {
                            thirdPartyId: 'google',
                            clients: [
                                {
                                    clientId: '1060725074195-kmeum4crr01uirfl2op9kd5acmi9jutn.apps.googleusercontent.com',
                                    clientSecret: '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',
                                },
                            ],
                        },
                    },
                    {
                        config: {
                            thirdPartyId: 'github',
                            clients: [
                                {
                                    clientId: '467101b197249757c71f',
                                    clientSecret: 'e97051221f4b6426e8fe8d51486396703012f5bd',
                                },
                            ],
                        },
                    },
                    {
                        config: {
                            thirdPartyId: 'apple',
                            clients: [
                                {
                                    clientId: '4398792-io.supertokens.example.service',
                                    additionalConfig: {
                                        keyId: '7M48Y4RYDL',
                                        privateKey: '-----BEGIN PRIVATE KEY-----\nMIGTAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBHkwdwIBAQQgu8gXs+XYkqXD6Ala9Sf/iJXzhbwcoG5dMh1OonpdJUmgCgYIKoZIzj0DAQehRANCAASfrvlFbFCYqn3I2zeknYXLwtH30JuOKestDbSfZYxZNMqhF/OzdZFTV0zc5u5s3eN+oCWbnvl0hM+9IW0UlkdA\n-----END PRIVATE KEY-----',
                                        teamId: 'YWQCXGJRJL',
                                    },
                                },
                            ],
                        },
                    },
                ],
            }),
            session_1.default.init({
                exposeAccessTokenToFrontendInCookieBasedAuth: true,
                override: {
                    functions: function (originalImplementation) {
                        return {
                            ...originalImplementation,
                            createNewSession: async function (input) {
                                input.accessTokenPayload = {
                                    ...input.accessTokenPayload,
                                    'https://hasura.io/jwt/claims': {
                                        'x-hasura-user-id': input.userId,
                                        'x-hasura-default-role': 'user',
                                        'x-hasura-allowed-roles': ['user'],
                                    },
                                };
                                return originalImplementation.createNewSession(input);
                            },
                        };
                    },
                },
            }),
        ],
        // isInServerlessEnv: true,
    };
};
exports.backendConfig = backendConfig;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYmFja2VuZENvbmZpZy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImJhY2tlbmRDb25maWcudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsOEdBQTBGO0FBQzFGLDhFQUEwRDtBQUMxRCx1Q0FBb0M7QUFHN0IsTUFBTSxhQUFhLEdBQUcsR0FBYyxFQUFFO0lBQzNDLE9BQU87UUFDTCxTQUFTLEVBQUUsU0FBUztRQUNwQixXQUFXLEVBQUU7WUFDWCwySkFBMko7WUFDM0osYUFBYSxFQUFFLHlCQUF5QjtZQUN4QyxvQ0FBb0M7U0FDckM7UUFDRCxPQUFPLEVBQVAsaUJBQU87UUFDUCxVQUFVLEVBQUU7WUFDVixpQ0FBMkIsQ0FBQyxJQUFJLENBQUM7Z0JBQy9CLDRFQUE0RTtnQkFDNUUsOEVBQThFO2dCQUM5RSxTQUFTLEVBQUU7b0JBQ1Q7d0JBQ0UsTUFBTSxFQUFFOzRCQUNOLFlBQVksRUFBRSxRQUFROzRCQUN0QixPQUFPLEVBQUU7Z0NBQ1A7b0NBQ0UsUUFBUSxFQUNOLDJFQUEyRTtvQ0FDN0UsWUFBWSxFQUFFLHFDQUFxQztpQ0FDcEQ7NkJBQ0Y7eUJBQ0Y7cUJBQ0Y7b0JBQ0Q7d0JBQ0UsTUFBTSxFQUFFOzRCQUNOLFlBQVksRUFBRSxRQUFROzRCQUN0QixPQUFPLEVBQUU7Z0NBQ1A7b0NBQ0UsUUFBUSxFQUFFLHNCQUFzQjtvQ0FDaEMsWUFBWSxFQUFFLDBDQUEwQztpQ0FDekQ7NkJBQ0Y7eUJBQ0Y7cUJBQ0Y7b0JBQ0Q7d0JBQ0UsTUFBTSxFQUFFOzRCQUNOLFlBQVksRUFBRSxPQUFPOzRCQUNyQixPQUFPLEVBQUU7Z0NBQ1A7b0NBQ0UsUUFBUSxFQUFFLHdDQUF3QztvQ0FDbEQsZ0JBQWdCLEVBQUU7d0NBQ2hCLEtBQUssRUFBRSxZQUFZO3dDQUNuQixVQUFVLEVBQ1Isa1FBQWtRO3dDQUNwUSxNQUFNLEVBQUUsWUFBWTtxQ0FDckI7aUNBQ0Y7NkJBQ0Y7eUJBQ0Y7cUJBQ0Y7aUJBQ0Y7YUFDRixDQUFDO1lBQ0YsaUJBQVcsQ0FBQyxJQUFJLENBQUM7Z0JBQ2YsNENBQTRDLEVBQUUsSUFBSTtnQkFDbEQsUUFBUSxFQUFFO29CQUNSLFNBQVMsRUFBRSxVQUFVLHNCQUFzQjt3QkFDekMsT0FBTzs0QkFDTCxHQUFHLHNCQUFzQjs0QkFDekIsZ0JBQWdCLEVBQUUsS0FBSyxXQUFXLEtBQUs7Z0NBQ3JDLEtBQUssQ0FBQyxrQkFBa0IsR0FBRztvQ0FDekIsR0FBRyxLQUFLLENBQUMsa0JBQWtCO29DQUMzQiw4QkFBOEIsRUFBRTt3Q0FDOUIsa0JBQWtCLEVBQUUsS0FBSyxDQUFDLE1BQU07d0NBQ2hDLHVCQUF1QixFQUFFLE1BQU07d0NBQy9CLHdCQUF3QixFQUFFLENBQUMsTUFBTSxDQUFDO3FDQUNuQztpQ0FDRixDQUFDO2dDQUVGLE9BQU8sc0JBQXNCLENBQUMsZ0JBQWdCLENBQUMsS0FBSyxDQUFDLENBQUM7NEJBQ3hELENBQUM7eUJBQ0YsQ0FBQztvQkFDSixDQUFDO2lCQUNGO2FBQ0YsQ0FBQztTQUNIO1FBQ0QsMkJBQTJCO0tBQzVCLENBQUM7QUFDSixDQUFDLENBQUM7QUFoRlcsUUFBQSxhQUFhLGlCQWdGeEIiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgVGhpcmRQYXJ0eUVtYWlsUGFzc3dvcmROb2RlIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvcmVjaXBlL3RoaXJkcGFydHllbWFpbHBhc3N3b3JkJztcbmltcG9ydCBTZXNzaW9uTm9kZSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJztcbmltcG9ydCB7IGFwcEluZm8gfSBmcm9tICcuL2FwcEluZm8nO1xuaW1wb3J0IHsgVHlwZUlucHV0IH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS90eXBlcyc7XG5cbmV4cG9ydCBjb25zdCBiYWNrZW5kQ29uZmlnID0gKCk6IFR5cGVJbnB1dCA9PiB7XG4gIHJldHVybiB7XG4gICAgZnJhbWV3b3JrOiAnZXhwcmVzcycsXG4gICAgc3VwZXJ0b2tlbnM6IHtcbiAgICAgIC8vIGh0dHBzOi8vdHJ5LnN1cGVydG9rZW5zLmNvbSBpcyBmb3IgZGVtbyBwdXJwb3Nlcy4gUmVwbGFjZSB0aGlzIHdpdGggdGhlIGFkZHJlc3Mgb2YgeW91ciBjb3JlIGluc3RhbmNlIChzaWduIHVwIG9uIHN1cGVydG9rZW5zLmNvbSksIG9yIHNlbGYgaG9zdCBhIGNvcmUuXG4gICAgICBjb25uZWN0aW9uVVJJOiAnaHR0cDovL3N1cGVydG9rZW5zOjM1NjcnLFxuICAgICAgLy8gYXBpS2V5OiA8QVBJX0tFWShpZiBjb25maWd1cmVkKT4sXG4gICAgfSxcbiAgICBhcHBJbmZvLFxuICAgIHJlY2lwZUxpc3Q6IFtcbiAgICAgIFRoaXJkUGFydHlFbWFpbFBhc3N3b3JkTm9kZS5pbml0KHtcbiAgICAgICAgLy8gV2UgaGF2ZSBwcm92aWRlZCB5b3Ugd2l0aCBkZXZlbG9wbWVudCBrZXlzIHdoaWNoIHlvdSBjYW4gdXNlIGZvciB0ZXN0aW5nLlxuICAgICAgICAvLyBJTVBPUlRBTlQ6IFBsZWFzZSByZXBsYWNlIHRoZW0gd2l0aCB5b3VyIG93biBPQXV0aCBrZXlzIGZvciBwcm9kdWN0aW9uIHVzZS5cbiAgICAgICAgcHJvdmlkZXJzOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgY29uZmlnOiB7XG4gICAgICAgICAgICAgIHRoaXJkUGFydHlJZDogJ2dvb2dsZScsXG4gICAgICAgICAgICAgIGNsaWVudHM6IFtcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBjbGllbnRJZDpcbiAgICAgICAgICAgICAgICAgICAgJzEwNjA3MjUwNzQxOTUta21ldW00Y3JyMDF1aXJmbDJvcDlrZDVhY21pOWp1dG4uYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20nLFxuICAgICAgICAgICAgICAgICAgY2xpZW50U2VjcmV0OiAnR09DU1BYLTFyMGFOY0c4Z2RkV3lFZ1I2UldhQWlKS3IyU1cnLFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIF0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgICAge1xuICAgICAgICAgICAgY29uZmlnOiB7XG4gICAgICAgICAgICAgIHRoaXJkUGFydHlJZDogJ2dpdGh1YicsXG4gICAgICAgICAgICAgIGNsaWVudHM6IFtcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBjbGllbnRJZDogJzQ2NzEwMWIxOTcyNDk3NTdjNzFmJyxcbiAgICAgICAgICAgICAgICAgIGNsaWVudFNlY3JldDogJ2U5NzA1MTIyMWY0YjY0MjZlOGZlOGQ1MTQ4NjM5NjcwMzAxMmY1YmQnLFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIF0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgICAge1xuICAgICAgICAgICAgY29uZmlnOiB7XG4gICAgICAgICAgICAgIHRoaXJkUGFydHlJZDogJ2FwcGxlJyxcbiAgICAgICAgICAgICAgY2xpZW50czogW1xuICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgIGNsaWVudElkOiAnNDM5ODc5Mi1pby5zdXBlcnRva2Vucy5leGFtcGxlLnNlcnZpY2UnLFxuICAgICAgICAgICAgICAgICAgYWRkaXRpb25hbENvbmZpZzoge1xuICAgICAgICAgICAgICAgICAgICBrZXlJZDogJzdNNDhZNFJZREwnLFxuICAgICAgICAgICAgICAgICAgICBwcml2YXRlS2V5OlxuICAgICAgICAgICAgICAgICAgICAgICctLS0tLUJFR0lOIFBSSVZBVEUgS0VZLS0tLS1cXG5NSUdUQWdFQU1CTUdCeXFHU000OUFnRUdDQ3FHU000OUF3RUhCSGt3ZHdJQkFRUWd1OGdYcytYWWtxWEQ2QWxhOVNmL2lKWHpoYndjb0c1ZE1oMU9vbnBkSlVtZ0NnWUlLb1pJemowREFRZWhSQU5DQUFTZnJ2bEZiRkNZcW4zSTJ6ZWtuWVhMd3RIMzBKdU9LZXN0RGJTZlpZeFpOTXFoRi9PemRaRlRWMHpjNXU1czNlTitvQ1dibnZsMGhNKzlJVzBVbGtkQVxcbi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS0nLFxuICAgICAgICAgICAgICAgICAgICB0ZWFtSWQ6ICdZV1FDWEdKUkpMJyxcbiAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgXSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSxcbiAgICAgICAgXSxcbiAgICAgIH0pLFxuICAgICAgU2Vzc2lvbk5vZGUuaW5pdCh7XG4gICAgICAgIGV4cG9zZUFjY2Vzc1Rva2VuVG9Gcm9udGVuZEluQ29va2llQmFzZWRBdXRoOiB0cnVlLFxuICAgICAgICBvdmVycmlkZToge1xuICAgICAgICAgIGZ1bmN0aW9uczogZnVuY3Rpb24gKG9yaWdpbmFsSW1wbGVtZW50YXRpb24pIHtcbiAgICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICAgIC4uLm9yaWdpbmFsSW1wbGVtZW50YXRpb24sXG4gICAgICAgICAgICAgIGNyZWF0ZU5ld1Nlc3Npb246IGFzeW5jIGZ1bmN0aW9uIChpbnB1dCkge1xuICAgICAgICAgICAgICAgIGlucHV0LmFjY2Vzc1Rva2VuUGF5bG9hZCA9IHtcbiAgICAgICAgICAgICAgICAgIC4uLmlucHV0LmFjY2Vzc1Rva2VuUGF5bG9hZCxcbiAgICAgICAgICAgICAgICAgICdodHRwczovL2hhc3VyYS5pby9qd3QvY2xhaW1zJzoge1xuICAgICAgICAgICAgICAgICAgICAneC1oYXN1cmEtdXNlci1pZCc6IGlucHV0LnVzZXJJZCxcbiAgICAgICAgICAgICAgICAgICAgJ3gtaGFzdXJhLWRlZmF1bHQtcm9sZSc6ICd1c2VyJyxcbiAgICAgICAgICAgICAgICAgICAgJ3gtaGFzdXJhLWFsbG93ZWQtcm9sZXMnOiBbJ3VzZXInXSxcbiAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgfTtcblxuICAgICAgICAgICAgICAgIHJldHVybiBvcmlnaW5hbEltcGxlbWVudGF0aW9uLmNyZWF0ZU5ld1Nlc3Npb24oaW5wdXQpO1xuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgfTtcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSksXG4gICAgXSxcbiAgICAvLyBpc0luU2VydmVybGVzc0VudjogdHJ1ZSxcbiAgfTtcbn07XG4iXX0=