import { NextApiRequest } from 'next/types';
export type ColorType = {
    id: string;
    background: string;
    foreground: string;
    itemType: 'calendar' | 'event';
};
export type ZoomJSONResponseType = {
    access_token: string;
    token_type: 'bearer';
    refresh_token: string;
    expires_in: number;
    scope: string;
};
export type ZoomJSONUserResponseType = {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
    type: number;
    role_name: string;
    pmi: number;
    use_pmi: false;
    vanity_url: string;
    personal_meeting_url: string;
    timezone: string;
    verified: number;
    dept: string;
    created_at: string;
    last_login_time: string;
    last_client_version: string;
    pic_url: string;
    host_key: string;
    jid: string;
    group_ids: string[];
    im_group_ids: string[];
    account_id: string;
    language: string;
    phone_country: string;
    phone_number: string;
    status: string;
};
export interface ZoomWebhookRequestType extends NextApiRequest {
    headers: {
        [key: string]: string;
        'x-zm-request-timestamp': string;
    };
    body: {
        event: string;
        payload: {
            account_id: string;
            object: {
                start_time: string;
                id: string;
            };
        };
        event_ts: number;
    };
}
export interface ZoomWebhookValidationRequestType extends NextApiRequest {
    headers: {
        [key: string]: string;
        'x-zm-request-timestamp': string;
    };
    body: {
        event: string;
        payload: {
            plainToken: string;
        };
        event_ts: number;
    };
}
export interface ZoomWebhookDeAuthRequestType extends NextApiRequest {
    headers: {
        [key: string]: string;
        'x-zm-request-timestamp': string;
    };
    body: {
        event: 'app_deauthorized';
        payload: {
            account_id: string;
            user_id: string;
            signature: string;
            deauthorization_time: string;
            client_id: string;
        };
    };
}
