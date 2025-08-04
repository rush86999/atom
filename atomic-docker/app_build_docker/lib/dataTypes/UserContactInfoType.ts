export type UserContactInfoType = {
  createdDate: string;
  id: string;
  name?: string;
  primary: boolean;
  type: 'email' | 'phone';
  updatedAt: string;
  userId: string;
};
