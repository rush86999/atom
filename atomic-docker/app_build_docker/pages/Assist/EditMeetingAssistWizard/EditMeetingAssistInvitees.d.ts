import { Dispatch, SetStateAction } from 'react';
import { ContactType } from '@lib/dataTypes/ContactType';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { MeetingAssistInviteType } from '@lib/dataTypes/MeetingAssistInviteType';
export type SelectedContactType = ContactType & {
    selected: boolean;
};
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
type Props = {
    invitees: MeetingAssistInviteType[];
    setParentInvitees: Dispatch<SetStateAction<MeetingAssistInviteType[]>>;
    userId: string;
    client: ApolloClient<NormalizedCacheObject>;
    hostName: string;
    meetingId: string;
};
declare function EditMeetingAssistInvitees(props: Props): JSX.Element;
export default EditMeetingAssistInvitees;
