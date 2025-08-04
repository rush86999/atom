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
    title: string;
    notes: string;
    location: string;
    startDate: Date;
    endDate: Date;
    setParentTitle: Dispatch<SetStateAction<string>>;
    setParentNotes: Dispatch<SetStateAction<string>>;
    setParentLocation: Dispatch<SetStateAction<string>>;
    setParentStartDate: Dispatch<SetStateAction<Date>>;
    setParentEndDate: Dispatch<SetStateAction<Date>>;
};
declare function EditEventBaseStep(props: Props): JSX.Element;
export default EditEventBaseStep;
