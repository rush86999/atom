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
    isAttendees: boolean;
    allDay: boolean;
    isRecurring: boolean;
    isBreak: boolean;
    setParentAllDay: Dispatch<SetStateAction<boolean>>;
    setParentIsRecurring: Dispatch<SetStateAction<boolean>>;
    setParentIsAttendees: Dispatch<SetStateAction<boolean>>;
    setParentIsBreak: Dispatch<SetStateAction<boolean>>;
};
declare function EditEventBaseStep2(props: Props): JSX.Element;
export default EditEventBaseStep2;
