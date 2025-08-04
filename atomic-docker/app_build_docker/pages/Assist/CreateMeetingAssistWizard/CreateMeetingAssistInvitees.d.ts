import { Dispatch, SetStateAction } from 'react';
import { ContactType } from '@lib/dataTypes/ContactType';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { MeetingAssistInviteType } from '@lib/dataTypes/MeetingAssistInviteType';
import { NextApiRequest, NextApiResponse } from 'next';
export declare function getServerSideProps({ req, res }: {
    req: NextApiRequest;
    res: NextApiResponse;
}): Promise<{
    props: {
        fromSupertokens: string;
        sub?: undefined;
    };
    redirect?: undefined;
} | {
    redirect: {
        destination: string;
        permanent: boolean;
    };
    props?: undefined;
} | {
    props: {
        sub: any;
        fromSupertokens?: undefined;
    };
    redirect?: undefined;
}>;
export type SelectedContactType = ContactType & {
    selected: boolean;
};
type Props = {
    invitees: MeetingAssistInviteType[];
    setParentInvitees: Dispatch<SetStateAction<MeetingAssistInviteType[]>>;
    userId: string;
    client: ApolloClient<NormalizedCacheObject>;
    hostName: string;
    meetingId: string;
};
declare function CreateMeetingAssistInvitees(props: Props): JSX.Element;
export default CreateMeetingAssistInvitees;
