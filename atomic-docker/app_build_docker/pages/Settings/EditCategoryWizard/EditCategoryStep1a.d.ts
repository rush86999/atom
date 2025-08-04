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
    copyPriorityLevel: boolean;
    setParentCopyPriorityLevel: Dispatch<SetStateAction<boolean>>;
    copyTimePreference: boolean;
    setParentCopyTimePreference: Dispatch<SetStateAction<boolean>>;
    copyReminders: boolean;
    setParentCopyReminders: Dispatch<SetStateAction<boolean>>;
};
declare function EditCategoryStep2(props: Props): JSX.Element;
export default EditCategoryStep2;
