import { SkillResponse } from 'atomic-docker/project/functions/atom-agent/types';
import { decrypt } from 'atomic-docker/project/functions/_libs/crypto';
import { executeGraphQLQuery } from 'atomic-docker/project/functions/atom-agent/_libs/graphqlClient';
import { handleError } from 'atomic-docker/project/functions/_utils/errorHandler';
import axios from 'axios';

const MIRO_API_BASE_URL = 'https://api.miro.com/v2';

interface MiroItem {
    id: string;
    data: {
        content?: string;
    };
    type: string;
}

async function getMiroAccessToken(userId: string): Promise<string | null> {
    const query = `
        query GetUserCredential($userId: String!, $serviceName: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                encrypted_secret
            }
        }
    `;
    const variables = {
        userId,
        serviceName: 'miro_access_token',
    };
    const response = await executeGraphQLQuery<{
        user_credentials: { encrypted_secret: string }[];
    }>(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
    }
    return null;
}

export async function getStickyNotesFromFrame(
    userId: string,
    boardId: string,
    frameId: string
): Promise<SkillResponse<MiroItem[]>> {
    try {
        const accessToken = await getMiroAccessToken(userId);
        if (!accessToken) {
            return {
                ok: false,
                error: {
                    code: 'CONFIG_ERROR',
                    message: 'Miro access token not configured for this user.',
                },
            };
        }

        const response = await axios.get(
            `${MIRO_API_BASE_URL}/boards/${boardId}/frames/${frameId}/items`,
            {
                headers: {
                    Authorization: `Bearer ${accessToken}`,
                },
            }
        );

        const items: MiroItem[] = response.data.data;
        const stickyNotes = items.filter(item => item.type === 'sticky_note');

        return { ok: true, data: stickyNotes };
    } catch (error: any) {
        return {
            ok: false,
            error: {
                code: 'MIRO_API_ERROR',
                message: "Sorry, I couldn't get the sticky notes from the Miro frame due to an error.",
                details: error,
            },
        };
    }
}
