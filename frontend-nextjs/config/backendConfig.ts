import SuperTokens from "supertokens-node";
import Session from "supertokens-node/recipe/session";

export function backendConfig() {
  return {
    framework: "express",
    supertokens: {
      connectionURI:
        process.env.SUPERTOKENS_CONNECTION_URI || "https://try.supertokens.io",
    },
    appInfo: {
      appName: process.env.APP_NAME || "Atomic App",
      apiDomain: process.env.API_DOMAIN || "http://localhost:3000",
      websiteDomain: process.env.WEBSITE_DOMAIN || "http://localhost:3000",
      apiBasePath: "/api/auth",
      websiteBasePath: "/auth",
    },
    recipeList: [Session.init()],
  };
}

export default backendConfig;
