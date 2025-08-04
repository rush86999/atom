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
    anyoneCanAddSelf: boolean;
    guestsCanSeeOtherGuests: boolean;
    lockAfter: boolean;
    primaryEmail: string;
    setParentAnyoneCanAddSelf: Dispatch<SetStateAction<boolean>>;
    setParentGuestsCanSeeOtherGuests: Dispatch<SetStateAction<boolean>>;
    setParentPrimaryEmail: Dispatch<SetStateAction<string>>;
    setParentLockAfter: Dispatch<SetStateAction<boolean>>;
};
declare function CMPWStep5(props: Props): JSX.Element;
export default CMPWStep5;
