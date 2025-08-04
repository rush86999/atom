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
    copyModifiable: boolean;
    setParentCopyModifiable: Dispatch<SetStateAction<boolean>>;
    copyCategories: boolean;
    setParentCopyCategories: Dispatch<SetStateAction<boolean>>;
    copyIsBreak: boolean;
    setParentCopyIsBreak: Dispatch<SetStateAction<boolean>>;
};
declare function TrainEventBaseStep2(props: Props): JSX.Element;
export default TrainEventBaseStep2;
