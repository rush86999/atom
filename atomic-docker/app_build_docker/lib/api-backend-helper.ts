import got from "got"
import { dayjs } from '@lib/date-utils'
import _ from "lodash"
import { googleClientIdAtomicWeb, googleClientSecretAtomicWeb, googleOAuthAtomicWebRedirectUrl, googleTokenUrl, hasuraAdminSecret, hasuraGraphUrl, zoomIVForPass, zoomPassKey, zoomSaltForPass } from "@lib/constants"
import { ZoomWebhookRequestType, ZoomWebhookValidationRequestType } from "@lib/types"
import { google } from 'googleapis'
import type { NextApiRequest, NextApiResponse } from 'next'
import crypto, { BinaryLike } from 'crypto'
import { CalendarIntegrationType, colorType } from "./dataTypes/Calendar_IntegrationType"
import { googleColorUrl } from "./calendarLib/constants"
import { colorResponseType } from "./calendarLib/types"
import { type Credentials } from 'google-auth-library/build/src/auth/credentials'
import { googlePeopleSyncUrl } from "./contactLib/constants"
import { ScheduleMeetingRequestType } from "./dataTypes/ScheduleMeetingRequestType"
import { SCHEDULER_API_URL } from "./constants"


const oauth2Client = new google.auth.OAuth2(
    googleClientIdAtomicWeb,
    googleClientSecretAtomicWeb,
    googleOAuthAtomicWebRedirectUrl,
)


export const exchangeCodeForTokens = async (code: string): Promise<Credentials> => {
    try {
        let { tokens } = await oauth2Client.getToken(code);
        oauth2Client.setCredentials(tokens)
        return tokens
    } catch (e) {
        console.log(e, ' unable to exchange code for tokens')
    }
}

export const generateGoogleAuthUrl = (state?: string) => {


    // Access scopes for read-only Drive activity.
    const scopes = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/contacts.readonly'
    ]

    const config: any = {
        // 'online' (default) or 'offline' (gets refresh_token)
        access_type: 'offline',
        /** Pass in the scopes array defined above.
          * Alternatively, if only one scope is needed, you can pass a scope URL as a string */
        scope: scopes,
        // Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes: true,
    }

    if (state) {
        config.state = state
    }
    // Generate a url that asks permissions for the Calendar activity scope
    const authorizationUrl = oauth2Client.generateAuthUrl(config)

    // console.log(authorizationUrl, ' authorizationUrl')

    return authorizationUrl
}

export const getMinimalCalendarIntegrationByResource = async (
    userId: string,
    resource: string,
) => {
    try {
        const operationName = 'getCalendarIntegration'
        const query = `
      query getCalendarIntegration($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
            appAccountId
            appEmail
            appId
            clientType
            colors
            contactEmail
            contactFirstName
            contactLastName
            contactName
            createdDate
            deleted
            enabled
            expiresAt
            id
            name
            pageToken
            password
            phoneCountry
            phoneNumber
            refreshToken
            resource
            syncEnabled
            syncToken
            token
            updatedAt
            userId
            username
        }
      }
    `
        const variables = {
            userId,
            resource,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0]
        }
    } catch (e) {
        console.log(e, ' unable to get calendar integration')
    }
}

export const updateAccessTokenCalendarIntegration = async (
    id: string,
    token: string | null,
    expiresIn: number | null,
    enabled?: boolean,
    refreshToken?: string | null,
) => {
    try {
        const operationName = 'updateCalendarIntegration'
        const query = `
      mutation updateCalendarIntegration($id: uuid!,${token !== undefined ? ' $token: String,' : ''}${refreshToken !== undefined ? ' $refreshToken: String,' : ''}${expiresIn !== undefined ? ' $expiresAt: timestamptz,' : ''}${enabled !== undefined ? ' $enabled: Boolean,' : ''}) {
        update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {${token !== undefined ? 'token: $token,' : ''}${refreshToken !== undefined ? ' refreshToken: $refreshToken,' : ''}${expiresIn !== undefined ? ' expiresAt: $expiresAt,' : ''}${enabled !== undefined ? ' enabled: $enabled,' : ''}}) {
          id
          name
          refreshToken
          token
          clientType
          userId
          updatedAt
        }
      }
    `
        let variables: any = {
            id,
            token,
            expiresAt: expiresIn ? dayjs().add(expiresIn, 'seconds').toISOString() : null,

        }

        if (enabled !== undefined) {
            variables.enabled = enabled
        }

        if (refreshToken !== undefined) {
            variables.refreshToken = refreshToken
        }

        const res: { data: { update_Calendar_Integration_by_pk: CalendarIntegrationType } } = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside updateCalendarIntegration')
    } catch (e) {
        console.log(e, ' unable to update calendar integration')
    }
}

export const refreshGoogleToken = async (
    refreshToken: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web'
): Promise<{
    access_token: string,
    expires_in: number, // add seconds to now
    scope: string,
    token_type: string
} | undefined> => {
    try {
        // console.log('refreshGoogleToken called', refreshToken)
        console.log('clientType', clientType)
        switch (clientType) {
            case 'atomic-web':
                return got.post(
                    googleTokenUrl,
                    {
                        form: {
                            grant_type: 'refresh_token',
                            refresh_token: refreshToken,
                            client_id: googleClientIdAtomicWeb,
                            client_secret: googleClientSecretAtomicWeb,
                        },
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                    },
                ).json()
            default:
                console.log('no case found inside refresh google tken')
                break
        }

        /*  
        {
          "access_token": "1/fFAGRNJru1FTz70BzhT3Zg",
          "expires_in": 3920, // add seconds to now
          "scope": "https://www.googleapis.com/auth/drive.metadata.readonly",
          "token_type": "Bearer"
        }
        */
    } catch (e) {
        console.log(e, ' unable to refresh google token')
    }
}

export const getGoogleAPIToken = async (
    userId: string,
    resource: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    let integrationId = ''
    try {
        const res = await getMinimalCalendarIntegrationByResource(userId, resource)
        if (!res) {
            console.log(' unabl eto get calendar integration')
            throw new Error('no calendar integration available')
        }

        const { id, token, expiresAt, refreshToken } = res
        if (!refreshToken) {
            throw new Error('no refresh token provided from calendar integration')
        }
        integrationId = id
        // console.log(id, token, expiresAt, refreshToken, ' id, token, expiresAt, refreshToken')
        if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
            const res = await refreshGoogleToken(refreshToken, clientType)
            // console.log(res, ' res from refreshGoogleToken')
            if (res) {
                await updateAccessTokenCalendarIntegration(id, res.access_token, res.expires_in)
                return res.access_token
            }
        }
        return token
    } catch (e) {
        console.log(e, ' unable to get api token')
        await updateAccessTokenCalendarIntegration(integrationId, null, null, false)
    }
}


export const decryptZoomTokens = (
    encryptedToken: string,
    encryptedRefreshToken?: string,
) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64')
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64')

    const key = crypto.pbkdf2Sync(zoomPassKey as string, saltBuffer, 10000, 32, 'sha256')

    const decipherToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer)
    let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8')
    decryptedToken += decipherToken.final('utf8')

    if (encryptedRefreshToken) {
        const decipherRefreshToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer)
        let decryptedRefreshToken = decipherRefreshToken.update(encryptedRefreshToken, 'base64', 'utf8')
        decryptedRefreshToken += decipherRefreshToken.final('utf8')

        return {
            token: decryptedToken,
            refreshToken: decryptedRefreshToken,
        }
    }

    return {
        token: decryptedToken,
    }

}


export const encryptZoomTokens = (
    token: string,
    refreshToken?: string,
) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64')
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64')

    const key = crypto.pbkdf2Sync(zoomPassKey as string, saltBuffer, 10000, 32, 'sha256')
    const cipherToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer)
    let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
    encryptedToken += cipherToken.final('base64')

    let encryptedRefreshToken = ''

    if (refreshToken) {
        const cipherRefreshToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer)
        encryptedRefreshToken = cipherRefreshToken.update(refreshToken, 'utf8', 'base64');
        encryptedRefreshToken += cipherRefreshToken.final('base64')
    }

    if (encryptedRefreshToken) {
        return {
            encryptedToken,
            encryptedRefreshToken
        }
    } else {
        return { encryptedToken }
    }
}

export const updateZoomIntegration = async (
    id: string,
    appAccountId: string,
    appEmail: string,
    appId: string,
    token: string | null,
    expiresIn: number | null,
    refreshToken?: string,
    contactFirstName?: string,
    contactLastName?: string,
    phoneCountry?: string, // 'US'
    phoneNumber?: string, // '+1 1234567891'
    enabled?: boolean,
) => {
    try {
        //${token !== undefined ? ' $token: String,' : ''}
        // 
        const operationName = 'updateCalendarIntegrationById'
        const query = `
            mutation updateCalendarIntegrationById(
                    $id: uuid!,
                    $appAccountId: String!,
                    $appEmail: String!,
                    $appId: String!,
                    ${token !== undefined ? ' $token: String,' : ''}
                    ${refreshToken !== undefined ? ' $refreshToken: String,' : ''}
                    ${expiresIn !== undefined ? ' $expiresAt: timestamptz,' : ''}
                    ${enabled !== undefined ? ' $enabled: Boolean,' : ''}
                    ${contactFirstName !== undefined ? ' $contactFirstName: String,' : ''}
                    ${contactLastName !== undefined ? ' $contactLastName: String,' : ''}
                    ${phoneCountry !== undefined ? ' $phoneCountry: String,' : ''}
                    ${phoneNumber !== undefined ? ' $phoneNumber: String,' : ''}
                ) {
                update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {
                    appAccountId: $appAccountId,
                    appEmail: $appEmail,
                    appId: $appId,
                    ${token !== undefined ? 'token: $token,' : ''}
                    ${expiresIn !== undefined ? ' expiresAt: $expiresAt,' : ''}
                    ${refreshToken !== undefined ? 'refreshToken: $refreshToken,' : ''}
                    ${contactFirstName !== undefined ? 'contactFirstName: $contactFirstName,' : ''}
                    ${contactLastName !== undefined ? 'contactLastName: $contactLastName,' : ''}
                    ${phoneCountry !== undefined ? 'phoneCountry: $phoneCountry,' : ''}
                    ${phoneNumber !== undefined ? 'phoneNumber: $phoneNumber,' : ''}
                    ${enabled !== undefined ? ' enabled: $enabled,' : ''}
                }) {
                    appAccountId
                    appEmail
                    appId
                    clientType
                    colors
                    contactEmail
                    contactFirstName
                    contactLastName
                    contactName
                    createdDate
                    deleted
                    enabled
                    expiresAt
                    id
                    name
                    pageToken
                    password
                    phoneCountry
                    phoneNumber
                    refreshToken
                    resource
                    syncEnabled
                    syncToken
                    token
                    updatedAt
                    userId
                    username
                }
            }
        `

        let encryptedValues = null

        if (token) {
            encryptedValues = encryptZoomTokens(token, refreshToken)
        }

        const variables = {
            id,
            appAccountId,
            appEmail,
            appId,
            token: encryptedValues?.encryptedToken,
            expiresAt: expiresIn ? dayjs().add(expiresIn, 'seconds').toISOString() : null,
            refreshToken: refreshToken === undefined ? undefined : encryptedValues?.encryptedRefreshToken,
            contactFirstName,
            contactLastName,
            phoneCountry,
            phoneNumber,
            enabled,
        }

        const res = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside updateCalendarIntegration')

    } catch (e) {
        console.log(e, ' unable to update zoom integration')
    }
}

export const getMinimalCalendarIntegrationByName = async (
    userId: string,
    name: string,
) => {
    try {
        const operationName = 'getCalendarIntegration'
        const query = `
      query getCalendarIntegration($userId: uuid!, $name: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, name: {_eq: $name}}) {
            appAccountId
            appEmail
            appId
            clientType
            colors
            contactEmail
            contactFirstName
            contactLastName
            contactName
            createdDate
            deleted
            enabled
            expiresAt
            id
            name
            pageToken
            password
            phoneCountry
            phoneNumber
            refreshToken
            resource
            syncEnabled
            syncToken
            token
            updatedAt
            userId
            username
        }
      }
    `
        const variables = {
            userId,
            name,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0]
        }
    } catch (e) {
        console.log(e, ' unable to get calendar integration by name')
    }
}

/**
 * query getCalendarIntegration($userId: uuid!, $resource: String!, $clientType: String!) {
  Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, clientType: {_eq: $clientType}}) {
    appAccountId
    appEmail
    appId
    clientType
    colors
    contactEmail
    contactFirstName
    contactLastName
    contactName
    createdDate
    deleted
    enabled
    expiresAt
    id
    name
    pageToken
    password
    phoneCountry
    phoneNumber
    refreshToken
    resource
    syncEnabled
    syncToken
    token
    updatedAt
    userId
    username
  }
}

 */

export const getAllCalendarIntegratonsByResourceAndClientType = async (
    userId: string,
    resource: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web'
) => {
    try {
        const operationName = 'getCalendarIntegrationByResourceAndClientType'

        const query = `
            query getCalendarIntegrationByResourceAndClientType($userId: uuid!, $resource: String!, $clientType: String!) {
                Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, clientType: {_eq: $clientType}}) {
                appAccountId
                appEmail
                appId
                clientType
                colors
                contactEmail
                contactFirstName
                contactLastName
                contactName
                createdDate
                deleted
                enabled
                expiresAt
                id
                name
                pageToken
                password
                phoneCountry
                phoneNumber
                refreshToken
                resource
                syncEnabled
                syncToken
                token
                updatedAt
                userId
                username
                }
            }
        `

        const variables = {
            userId,
            resource,
            clientType,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration
        }
    } catch (e) {
        console.log(e, ' unable to get all calendar integrations by resource and client type')
    }
}

export const getAllCalendarIntegrationsByResource = async (
    userId: string,
    resource: string,
) => {
    try {
        const operationName = 'getCalendarIntegrationByResource'
        const query = `
      query getCalendarIntegrationByResource($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
            appAccountId
            appEmail
            appId
            clientType
            colors
            contactEmail
            contactFirstName
            contactLastName
            contactName
            createdDate
            deleted
            enabled
            expiresAt
            id
            name
            pageToken
            password
            phoneCountry
            phoneNumber
            refreshToken
            resource
            syncEnabled
            syncToken
            token
            updatedAt
            userId
            username
        }
      }
    `
        const variables = {
            userId,
            resource,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration
        }
    } catch (e) {
        console.log(e, ' unable to get calendar all integrations by resource')
    }
}

export const getGoogleColors = async (
    token: string,
) => {
    try {
        const url = googleColorUrl
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        }

        const data: colorResponseType = await got.get(url, config).json()
        console.log(data, ' data for get colors')
        return data
    } catch (e) {
        console.log(e, ' unable to get google colors')
    }
}

export const triggerGooglePeopleSync = async (
    calendarIntegrationId: string,
    userId: string,
    req: NextApiRequest,
) => {
    try {
        console.log('triggerGooglePeopleSyn called')
        if (!calendarIntegrationId) {
            console.log(' no calendarINtegrationid')
            return
        }

        if (!userId) {
            console.log('no userId')
            return
        }
        const token = req.session.getAccessTokenPayload()

        const data = {
            calendarIntegrationId,
            userId,
            isInitialSync: true,
        }

        const url = googlePeopleSyncUrl

        const results = await got.post(url, {
            json: data,
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        }).json()

        console.log(results, ' successfully triggered google people sync')
    } catch (e: any) {
        console.log(e, ' unable to trigger google people sync')
        console.log(e?.response?.data?.message, ' error message')
        console.log(e?.response?.data?.code, ' error code')
        console.log(e?.code, ' error code')
        console.log(e?.message, ' error message')
    }
}
export const updateGoogleIntegration = async (
    id: string,
    enabled?: boolean,
    token?: string,
    refreshToken?: string,
    expiresAt?: string,
    syncEnabled?: boolean,
    colors?: colorType[],
    pageToken?: string,
    syncToken?: string,
    clientType?: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    try {
        const operationName = 'UpdateCalendarIntegrationById'
        const query = `
            mutation UpdateCalendarIntegrationById($id: uuid!, 
                ${enabled !== undefined ? '$enabled: Boolean,' : ''} 
                ${expiresAt !== undefined ? '$expiresAt: timestamptz,' : ''} 
                ${refreshToken !== undefined ? '$refreshToken: String,' : ''} 
                ${token !== undefined ? '$token: String,' : ''}
                ${syncEnabled !== undefined ? '$syncEnabled: Boolean,' : ''}
                ${colors !== undefined ? '$colors: jsonb,' : ''}
                ${pageToken !== undefined ? '$pageToken: String,' : ''}
                ${syncToken !== undefined ? '$syncToken: String,' : ''}
                ${clientType !== undefined ? '$clientType: String,' : ''}
                $updatedAt: timestamptz) {
                update_Calendar_Integration_by_pk(_set: {
                    ${enabled !== undefined ? 'enabled: $enabled,' : ''} 
                    ${expiresAt !== undefined ? 'expiresAt: $expiresAt,' : ''} 
                    ${refreshToken !== undefined ? 'refreshToken: $refreshToken,' : ''} 
                    ${token !== undefined ? 'token: $token,' : ''}
                    ${syncEnabled !== undefined ? 'syncEnabled: $syncEnabled,' : ''}
                    ${colors !== undefined ? 'colors: $colors,' : ''}
                    ${pageToken !== undefined ? 'pageToken: $pageToken,' : ''}
                    ${syncToken !== undefined ? 'syncToken: $syncToken,' : ''}
                    ${clientType !== undefined ? 'clientType: $clientType,' : ''}
                    updatedAt: $updatedAt}, pk_columns: {id: $id}) {
                    appAccountId
                    appEmail
                    appId
                    colors
                    contactEmail
                    contactName
                    createdDate
                    deleted
                    enabled
                    expiresAt
                    id
                    name
                    pageToken
                    password
                    refreshToken
                    syncEnabled
                    resource
                    token
                    syncToken
                    updatedAt
                    userId
                    username
                }
            }
        `

        let variables: any = {
            id,
            updatedAt: dayjs().format(),
        }

        if (enabled !== undefined) {
            variables.enabled = enabled
        }

        if (expiresAt !== undefined) {
            if (expiresAt === null) {
                variables.expiresAt = null
            } else {
                variables.expiresAt = dayjs(expiresAt).format()
            }
        }

        if (refreshToken !== undefined) {
            variables.refreshToken = refreshToken
        }

        if (token !== undefined) {
            variables.token = token
        }

        if (syncEnabled !== undefined) {
            variables.syncEnabled = syncEnabled
        }

        if (colors !== undefined) {
            variables.colors = colors
        }

        if (pageToken !== undefined) {
            variables.pageToken = pageToken
        }

        if (syncToken !== undefined) {
            variables.syncToken = syncToken
        }

        if (clientType !== undefined) {
            variables.clientType = clientType
        }

        const res: { data: { update_Calendar_Integration_by_pk: CalendarIntegrationType } } = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        console.log(res?.data?.update_Calendar_Integration_by_pk, ' successfully update calendar integration')

        return res?.data?.update_Calendar_Integration_by_pk
    } catch (e) {
        console.log(e, ' unable to update google integration')
    }
}

export const scheduleMeeting = async (
    payload: ScheduleMeetingRequestType,
    // TODO: Add userId and token once auth is figured out for this endpoint
): Promise<any> => { // eslint-disable-line @typescript-eslint/no-explicit-any
    try {
        const url = `${SCHEDULER_API_URL}/timeTable/user/scheduleMeeting`;
        console.log('scheduleMeeting called with url: ', url, ' and payload: ', payload);

        const response = await got.post(url, {
            json: payload,
            headers: {
                'Content-Type': 'application/json',
                // TODO: Add Authorization header if required by the scheduler API
                // 'Authorization': `Bearer ${token}`,
            },
        }).json();

        console.log('scheduleMeeting response: ', response);
        return response;
    } catch (e: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
        console.error('Error calling scheduleMeeting API:', e?.response?.body || e?.message || e);
        // It's good practice to throw the error or return a structured error response
        // For now, rethrowing the error or a processed version of it.
        if (e?.response?.body) {
            try {
                const errorBody = JSON.parse(e.response.body);
                throw new Error(`API Error: ${errorBody.message || e.response.body}`);
            } catch (parseError) {
                // If parsing fails, throw the original body content
                throw new Error(`API Error: ${e.response.body}`);
            }
        }
        throw new Error(e.message || 'Failed to schedule meeting due to an unknown error');
    }
};
