import { ReactNode } from "react";
interface Opportunity {
    id: string;
    name: string;
    stage: string;
    value: number;
}
interface Contact {
    id: string;
    name: string;
    opportunityId: string;
}
interface Task {
    id: string;
    description: string;
    dueDate: string;
}
interface SalesData {
    opportunities: Opportunity[];
    contacts: Contact[];
    tasks: Task[];
}
interface SalesContextType {
    salesData: SalesData | null;
    loading: boolean;
    error: Error | null;
    fetchSalesData: () => Promise<void>;
}
export declare const useSales: () => SalesContextType;
export declare const SalesProvider: ({ children }: {
    children: ReactNode;
}) => JSX.Element;
export {};
