// SuperTokens configuration for functions backend
import ThirdPartyEmailPassword from "supertokens-node/recipe/thirdpartyemailpassword";
import Session from "supertokens-node/recipe/session";
import { TypeInput } from "supertokens-node/types";

export const supertokensConfig = () => {
  return {
    framework: "express",
    supertokens: {
      connectionURI: process.env.SUPERTOKENS_CONNECTION_URI || "https://try.supertokens.com",
      apiKey: process.env.SUPERTOKENS_API_KEY,
    },
    appInfo: {
      appName: "atom-functions",
      apiDomain: process.env.API_DOMAIN || "http://localhost:8000",
      websiteDomain: process.env.WEBSITE_DOMAIN || "http://localhost:3000",
      apiBasePath: "/api/auth",
    },
    recipeList: [
      Session.init({
        cookieSecure: process.env.NODE_ENV === "production",
        cookieSameSite: process.env.NODE_ENV === "production" ? "none" : "lax",
        antiCsrf: process.env.NODE_ENV === "production" ? "VIA_TOKEN" : "NONE",
        sessionRequiredForSignUp: true,
      }),
      ThirdPartyEmailPassword.init({
        override: {
          apis: (originalImplementation) => {
            return {
              ...originalImplementation,
              // Custom email verification
              emailVerifyPOST: async (input) => {
                let response = await originalImplementation.emailVerifyPOST(input);
                if (response.status === "OK") {
                  // User verification completed
                  console.log("User verified:", response.user);
                }
                return response;
              },
              // Custom sign in response
              signInPOST: async (input) => {
                let response = await originalImplementation.signInPOST(input);
                if (response.status === "OK") {
                  console.log("User signed in:", response.user.id);
                }
                return response;
              },
            };
          },
          functions: (originalImplementation) => {
            return {
              ...originalImplementation,
              // Custom user creation handling
              signUp: async (input) => {
                let response = await originalImplementation.signUp(input);
                if (response.status === "OK") {
                  // User created successfully
                  console.log("User created:", response.user.id);
                }
                return response;
              },
            };
          },
        },
        providers: [
          ThirdPartyEmailPassword.Google({
            clientId: process.env.GOOGLE_CLIENT_ID,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET,
          }),
          ThirdPartyEmailPassword.Github({
            clientId: process.env.GITHUB_CLIENT_ID,
            clientSecret: process.env.GITHUB_CLIENT_SECRET,
          }),
        ],
      }),
    ],
    isInServerlessEnv: true,
  };
};
