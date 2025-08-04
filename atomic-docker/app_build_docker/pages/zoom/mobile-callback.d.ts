import { NextPage, NextApiRequest, NextApiResponse } from "next";
import { ZoomJSONUserResponseType } from "@lib/types";
export declare function getServerSideProps({ req, res }: {
    req: NextApiRequest;
    res: NextApiResponse;
}): Promise<{
    props: {
        zoomUser: ZoomJSONUserResponseType;
        userId: string;
    };
} | {
    props: {
        zoomUser?: undefined;
        userId?: undefined;
    };
}>;
type Props = {
    zoomUser: ZoomJSONUserResponseType;
    userId: string;
    path: string;
};
declare const ZoomWebCallback: NextPage<Props>;
export default ZoomWebCallback;
