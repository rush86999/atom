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
    setParentCopyAvailability: Dispatch<SetStateAction<boolean>>;
    copyTimeBlocking: boolean;
    setParentCopyTimeBlocking: Dispatch<SetStateAction<boolean>>;
    copyTimePreference: boolean;
    setParentCopyTimePreference: Dispatch<SetStateAction<boolean>>;
};
declare function TrainEventBaseStep(props: Props): JSX.Element;
export default TrainEventBaseStep;
