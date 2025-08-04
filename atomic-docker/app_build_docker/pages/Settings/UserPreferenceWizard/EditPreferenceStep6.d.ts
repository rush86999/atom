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
    copyIsExternalMeeting: boolean;
    copyColor: boolean;
    backToBackMeetings: boolean;
    breakColor: string;
    setParentCopyIsMeeting: Dispatch<SetStateAction<boolean>>;
    setParentCopyIsExternalMeeting: Dispatch<SetStateAction<boolean>>;
    setParentCopyColor: Dispatch<SetStateAction<boolean>>;
    setParentBackToBackMeetings: Dispatch<SetStateAction<boolean>>;
    setParentBreakColor: Dispatch<SetStateAction<string>>;
};
declare function EditPreferenceStep6(props: Props): JSX.Element;
export default EditPreferenceStep6;
