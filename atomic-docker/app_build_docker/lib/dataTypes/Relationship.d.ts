declare const Relationship: {
    title: string;
    version: number;
    description: string;
    primaryKey: string;
    type: string;
    properties: {
        id: {
            type: string;
        };
        contactId: {
            type: string;
        };
        name: {
            type: string;
        };
        label: {
            type: string;
        };
        updatedAt: {
            type: string;
        };
        createdDate: {
            type: string;
        };
    };
    required: string[];
    indexes: string[];
};
export default Relationship;
