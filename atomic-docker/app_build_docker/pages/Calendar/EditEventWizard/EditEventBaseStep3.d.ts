import { Dispatch, SetStateAction } from 'react';
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
    modifiable: boolean;
    isMeeting: boolean;
    isExternalMeeting: boolean;
    transparency: TransparencyType;
    setParentModifiable: Dispatch<SetStateAction<boolean>>;
    setParentIsMeeting: Dispatch<SetStateAction<boolean>>;
    setParentIsExternalMeeting: Dispatch<SetStateAction<boolean>>;
    setParentTransparency: Dispatch<SetStateAction<TransparencyType>>;
};
declare function EditEventBaseStep3(props: Props): JSX.Element;
export default EditEventBaseStep3;
