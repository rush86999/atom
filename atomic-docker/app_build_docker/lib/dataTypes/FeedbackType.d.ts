export type FeedbackType = {
    id: string;
    userId: string;
    question1_A: boolean;
    question1_B: boolean;
    question1_C: boolean;
    question2?: string;
    question3?: string;
    question4?: string;
    lastSeen: string;
    count: number;
    updatedAt: string;
    createdDate: string;
    deleted: boolean;
};
