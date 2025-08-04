declare const Feedback: {
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
        question1_A: {
            type: string;
        };
        question1_B: {
            type: string;
        };
        question1_C: {
            type: string;
        };
        question2: {
            type: string[];
        };
        question3: {
            type: string[];
        };
        question4: {
            type: string[];
        };
        lastSeen: {
            type: string;
        };
        count: {
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
export default Feedback;
