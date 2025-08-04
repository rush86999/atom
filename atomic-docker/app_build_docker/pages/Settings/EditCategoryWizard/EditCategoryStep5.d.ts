import { Dispatch, SetStateAction } from 'react';
import { DefaultRemindersType } from '@lib/dataTypes/CategoryType';
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
    defaultReminders: DefaultRemindersType;
    setParentDefaultReminders: Dispatch<SetStateAction<DefaultRemindersType>>;
};
declare function EditCategoryStep5(props: Props): JSX.Element;
export default EditCategoryStep5;
