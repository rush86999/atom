import { Dispatch, SetStateAction } from 'react';
import { SendUpdatesType, VisibilityType } from '@lib/calendarLib/types';
import { TransparencyType } from '@lib/calendarLib/types';
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
    sendUpdates: SendUpdatesType;
    guestsCanInviteOthers: boolean;
    transparency: TransparencyType;
    visibility: VisibilityType;
    name: string;
    setParentSendUpdates: Dispatch<SetStateAction<SendUpdatesType>>;
    setParentGuestsCanInviteOthers: Dispatch<SetStateAction<boolean>>;
    setParentTransparency: Dispatch<SetStateAction<TransparencyType>>;
    setParentVisibility: Dispatch<SetStateAction<VisibilityType>>;
    setParentName: Dispatch<SetStateAction<string>>;
};
declare function CMPWStep1(props: Props): JSX.Element;
export default CMPWStep1;
