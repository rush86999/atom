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
    copyCategories: boolean;
    copyIsBreak: boolean;
    maxWorkLoadPercent: number;
    minNumberOfBreaks: number;
    breakLength: number;
    setParentCopyCategories: Dispatch<SetStateAction<boolean>>;
    setParentCopyIsBreak: Dispatch<SetStateAction<boolean>>;
    setParentMaxWorkLoadPercent: Dispatch<SetStateAction<number>>;
    setParentMinNumberOfBreaks: Dispatch<SetStateAction<number>>;
    setParentBreakLength: Dispatch<SetStateAction<number>>;
};
declare function EditPreferenceStep5(props: Props): JSX.Element;
export default EditPreferenceStep5;
