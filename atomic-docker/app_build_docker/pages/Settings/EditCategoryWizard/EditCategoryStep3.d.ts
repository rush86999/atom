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
    defaultPriorityLevel: number;
    setParentDefaultPriorityLevel: Dispatch<SetStateAction<number>>;
    defaultModifiable: boolean;
    setParentDefaultModifiable: Dispatch<SetStateAction<boolean>>;
};
declare function EditCategoryStep3(props: Props): JSX.Element;
export default EditCategoryStep3;
