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
    copyAvailability: boolean;
    copyTimeBlocking: boolean;
    copyTimePreference: boolean;
    copyReminders: boolean;
    copyPriorityLevel: boolean;
    copyModifiable: boolean;
    setParentCopyAvailability: Dispatch<SetStateAction<boolean>>;
    setParentCopyTimeBlocking: Dispatch<SetStateAction<boolean>>;
    setParentCopyTimePreference: Dispatch<SetStateAction<boolean>>;
    setParentCopyReminders: Dispatch<SetStateAction<boolean>>;
    setParentCopyPriorityLevel: Dispatch<SetStateAction<boolean>>;
    setParentCopyModifiable: Dispatch<SetStateAction<boolean>>;
};
declare function EditPreferenceStep3(props: Props): JSX.Element;
export default EditPreferenceStep3;
