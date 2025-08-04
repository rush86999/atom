export type enabledCalendarType = {
    id: string;
    name: string;
    enabled: boolean;
};
export type AndroidGoogleCalendarCredentials = {
    /**
     * This field is only present if the access_type parameter was set to offline in the authentication request. For details, see Refresh tokens.
     */
    refresh_token?: string | null;
    /**
     * The time in ms at which this token is thought to expire.
     */
    expiry_date?: number | null;
    /**
     * A token that can be sent to a Google API.
     */
    access_token?: string | null;
    /**
     * Identifies the type of token returned. At this time, this field always has the value Bearer.
     */
    token_type?: string | null;
    /**
     * A JWT that contains identity information about the user that is digitally signed by Google.
     */
    id_token?: string | null;
    /**
     * The scopes of access granted by the access_token expressed as a list of space-delimited, case-sensitive strings.
     */
    scope?: string;
};
