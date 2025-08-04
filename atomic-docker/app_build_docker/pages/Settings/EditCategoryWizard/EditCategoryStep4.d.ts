import { Dispatch, SetStateAction } from 'react';
import { DefaultTimePreferenceTypes } from '@lib/dataTypes/CategoryType';
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
    defaultTimePreferences: DefaultTimePreferenceTypes;
    setParentDefaultTimePreference: Dispatch<SetStateAction<DefaultTimePreferenceTypes>>;
};
declare function EditCategoryStep4(props: Props): JSX.Element;
export default EditCategoryStep4;
