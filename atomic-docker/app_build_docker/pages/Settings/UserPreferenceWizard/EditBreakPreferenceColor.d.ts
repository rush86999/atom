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
interface Props {
    breakColor: string;
    setParentBreakColor: (color: string) => void;
    setParentEnableSelectColor: Dispatch<SetStateAction<boolean>>;
}
declare function EditBreakPreferenceColor(props: Props): JSX.Element;
export default EditBreakPreferenceColor;
