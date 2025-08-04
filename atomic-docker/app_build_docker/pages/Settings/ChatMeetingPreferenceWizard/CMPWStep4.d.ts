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
    isBufferTime: boolean;
    beforeEventMinutes: number;
    afterEventMinutes: number;
    setParentIsBufferTime: Dispatch<SetStateAction<boolean>>;
    setParentBeforeEventMinutes: Dispatch<SetStateAction<number>>;
    setParentAfterEventMinutes: Dispatch<SetStateAction<number>>;
};
declare function CMPWStep4(props: Props): JSX.Element;
export default CMPWStep4;
