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
    copyIsMeeting: boolean;
    setParentCopyIsMeeting: Dispatch<SetStateAction<boolean>>;
    copyIsExternalMeeting: boolean;
    setParentCopyIsExternalMeeting: Dispatch<SetStateAction<boolean>>;
    copyDuration: boolean;
    setParentCopyDuration: Dispatch<SetStateAction<boolean>>;
    copyColor: boolean;
    setParentCopyColor: Dispatch<SetStateAction<boolean>>;
};
declare function TrainEventBaseStep3(props: Props): JSX.Element;
export default TrainEventBaseStep3;
