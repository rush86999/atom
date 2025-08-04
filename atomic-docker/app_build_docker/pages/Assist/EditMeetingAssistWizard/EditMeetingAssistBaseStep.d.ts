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
    notes: string;
    windowStartDate: Date;
    windowEndDate: Date;
    location: string | undefined;
    cancel: boolean;
    summary: string;
    setParentNotes: Dispatch<SetStateAction<string>>;
    setParentSummary: Dispatch<SetStateAction<string>>;
    setParentWindowStartDate: Dispatch<SetStateAction<Date>>;
    setParentWindowEndDate: Dispatch<SetStateAction<Date>>;
    setParentLocation: Dispatch<SetStateAction<string>>;
    setParentCancel: Dispatch<SetStateAction<boolean>>;
};
declare function EditMeetingAssistBaseStep(props: Props): JSX.Element;
export default EditMeetingAssistBaseStep;
