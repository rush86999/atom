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
    color: string;
    setParentColor: Dispatch<SetStateAction<string>>;
    copyIsMeeting: boolean;
    setParentCopyIsMeeting: Dispatch<SetStateAction<boolean>>;
    copyIsExternalMeeting: boolean;
    setParentCopyIsExternalMeeting: Dispatch<SetStateAction<boolean>>;
    defaultIsMeeting: boolean;
    setParentDefaultIsMeeting: Dispatch<SetStateAction<boolean>>;
    defaultIsExternalMeeting: boolean;
    setParentDefaultIsExternalMeeting: Dispatch<SetStateAction<boolean>>;
    defaultMeetingModifiable: boolean;
    setParentDefaultMeetingModifiable: Dispatch<SetStateAction<boolean>>;
    defaultExternalMeetingModifiable: boolean;
    setParentDefaultExternalMeetingModifiable: Dispatch<SetStateAction<boolean>>;
};
declare function EditCategoryStep6(props: Props): JSX.Element;
export default EditCategoryStep6;
