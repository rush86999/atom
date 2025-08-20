import ThirdPartyEmailPasswordNode from "supertokens-node/recipe/thirdpartyemailpassword";
import SessionNode from "supertokens-node/recipe/session";
import { appInfo } from "./appInfo";
import { TypeInput } from "supertokens-node/types";

export const backendConfig = (): TypeInput => {
  return {
    framework: "express",
    supertokens: {
      connectionURI:
        process.env.SUPERTOKENS_CONNECTION_URI || "http://supertokens:3567",
      // apiKey: process.env.SUPERTOKENS_API_KEY, // Optional: Add if using API key authentication
    },
    appInfo,
    recipeList: [
      ThirdPartyEmailPasswordNode.init({
        providers: [
          {
            config: {
              thirdPartyId: "google",
              clients: [
                {
                  clientId: process.env.GOOGLE_CLIENT_ID || "",
                  clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
                },
              ],
            },
          },
          {
            config: {
              thirdPartyId: "github",
              clients: [
                {
                  clientId: process.env.GITHUB_CLIENT_ID || "",
                  clientSecret: process.env.GITHUB_CLIENT_SECRET || "",
                },
              ],
            },
          },
          {
            config: {
              thirdPartyId: "apple",
              clients: [
                {
                  clientId: process.env.APPLE_CLIENT_ID || "",
                  additionalConfig: {
                    keyId: process.env.APPLE_KEY_ID || "",
                    privateKey: process.env.APPLE_PRIVATE_KEY || "",
                    teamId: process.env.APPLE_TEAM_ID || "",
                  },
                },
              ],
            },
          },
        ],
      }),
      SessionNode.init({
        exposeAccessTokenToFrontendInCookieBasedAuth: true,
        override: {
          functions: function (originalImplementation) {
            return {
              ...originalImplementation,
              createNewSession: async function (input) {
                input.accessTokenPayload = {
                  ...input.accessTokenPayload,
                  "https://hasura.io/jwt/claims": {
                    "x-hasura-user-id": input.userId,
                    "x-hasura-default-role": "user",
                    "x-hasura-allowed-roles": ["user"],
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
