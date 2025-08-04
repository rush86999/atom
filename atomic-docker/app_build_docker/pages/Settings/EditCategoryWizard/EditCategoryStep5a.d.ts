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
    copyIsBreak: boolean;
    setParentCopyIsBreak: Dispatch<SetStateAction<boolean>>;
    defaultIsBreak: boolean;
    setParentDefaultIsBreak: Dispatch<SetStateAction<boolean>>;
};
declare function EditCategoryStep5a(props: Props): JSX.Element;
export default EditCategoryStep5a;
