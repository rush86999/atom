import ThirdPartyEmailPasswordReact from 'supertokens-auth-react/recipe/thirdpartyemailpassword';
export declare const frontendConfig: () => {
    appInfo: {
        appName: string;
        apiDomain: string;
        websiteDomain: string;
        apiBasePath: string;
        websiteBasePath: string;
    };
    recipeList: (import("supertokens-auth-react/lib/build/types").RecipeInitResult<ThirdPartyEmailPasswordReact.GetRedirectionURLContext, import("supertokens-auth-react/lib/build/recipe/thirdpartyemailpassword/types").PreAndPostAPIHookAction, ThirdPartyEmailPasswordReact.OnHandleEventContext, import("supertokens-auth-react/lib/build/recipe/thirdpartyemailpassword/types").NormalisedConfig> | import("supertokens-auth-react/lib/build/types").RecipeInitResult<unknown, unknown, unknown, any>)[];
    windowHandler: (oI: any) => any;
};
