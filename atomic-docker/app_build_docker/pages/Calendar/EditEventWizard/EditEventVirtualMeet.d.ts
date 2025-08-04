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
    isZoomAvailable: boolean;
    isGoogleMeetAvailable: boolean;
    zoomMeet: boolean;
    googleMeet: boolean;
    setParentZoomMeet: Dispatch<SetStateAction<boolean>>;
    setParentGoogleMeet: Dispatch<SetStateAction<boolean>>;
    zoomPrivateMeeting: boolean;
    setParentZoomPrivateMeeting: Dispatch<SetStateAction<boolean>>;
};
declare function EditEventVirtualMeet(props: Props): JSX.Element;
export default EditEventVirtualMeet;
/** end */
