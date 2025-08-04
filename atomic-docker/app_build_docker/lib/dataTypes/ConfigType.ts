export type ConfigType =
  | {
      issuer: string;
      clientId: string;
      redirectUrl: string;
      scopes: string[];
    }
  | {
      clientId: string;
      redirectUrl: string;
      scopes: string[];
      serviceConfiguration: {
        authorizationEndpoint: string;
        tokenEndpoint: string;
      };
    };
