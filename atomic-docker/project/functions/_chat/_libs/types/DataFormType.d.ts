type DataType = {
    type: 'select' | 'input' | 'multi-select' | 'date-time';
    value: string;
    name: string;
};
export type FormDataResponseType = DataType[];
export {};
