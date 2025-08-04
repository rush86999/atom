import { Dispatch, SetStateAction } from 'react';
import { DefaultTimeBlockingType } from '@lib/dataTypes/CategoryType';
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
    defaultAvailability: boolean;
    setParentDefaultAvailability: Dispatch<SetStateAction<boolean>>;
    defaultTimeBlocking: DefaultTimeBlockingType;
    setParentDefaultTimeBlocking?: Dispatch<SetStateAction<DefaultTimeBlockingType>>;
};
declare function EditCategoryStep2(props: Props): JSX.Element;
export default EditCategoryStep2;
