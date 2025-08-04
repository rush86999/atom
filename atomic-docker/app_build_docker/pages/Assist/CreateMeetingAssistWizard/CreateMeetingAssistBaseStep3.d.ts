import { Dispatch, SetStateAction } from 'react';
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
    sendUpdates: 'all' | 'externalOnly';
    guestsCanInviteOthers: boolean;
    transparency: 'opaque' | 'transparent';
    visibility: 'default' | 'public' | 'private';
    hostName: string;
    setParentSendUpdates: Dispatch<SetStateAction<'all' | 'externalOnly'>>;
    setParentGuestsCanInviteOthers: Dispatch<SetStateAction<boolean>>;
    setParentTransparency: Dispatch<SetStateAction<'opaque' | 'transparent'>>;
    setParentVisibility: Dispatch<SetStateAction<'default' | 'public' | 'private'>>;
    setParentHostName: Dispatch<SetStateAction<string>>;
};
declare function CreateMeetingAssistBaseStep3(props: Props): JSX.Element;
export default CreateMeetingAssistBaseStep3;
