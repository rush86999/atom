import { Dispatch, SetStateAction } from 'react';
import { CategoryType } from '@lib/dataTypes/CategoryType';
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
    setParentSelectedCategories: Dispatch<SetStateAction<CategoryType[]>>;
    selectedCategories: CategoryType[];
    categories: CategoryType[];
};
export type OptionType = {
    label: string;
    value: string;
};
declare function EditEventUpdateCategories(props: Props): JSX.Element;
export default EditEventUpdateCategories;
