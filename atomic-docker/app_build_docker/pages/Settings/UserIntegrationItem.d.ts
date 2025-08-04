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
    index: number;
    token?: string;
    resource?: string;
    resourceId?: string;
    name?: string;
    tableName?: string;
    updateParentTokenValue: (index: number, value: string) => void;
    updateParentResourceValue: (index: number, value: string) => void;
    updateParentResourceIdValue: (index: number, value: string) => void;
    updateParentNameValue: (index: number, value: string) => void;
    updateParentTableNameValue: (index: number, value: string) => void;
    removeParentIntegration: (index: number) => Promise<void>;
};
declare function UserIntegrationItem(props: Props): JSX.Element;
export default UserIntegrationItem;
