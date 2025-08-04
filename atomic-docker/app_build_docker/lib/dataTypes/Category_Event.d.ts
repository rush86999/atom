declare const Category_Event: {
    title: string;
    version: number;
    description: string;
    primaryKey: string;
    type: string;
    properties: {
        id: {
            type: string;
        };
        userId: {
            type: string;
        };
        categoryId: {
            type: string;
        };
        eventId: {
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
    indexes: string[][];
};
export default Category_Event;
