import { ReactNode } from "react";
interface Account {
    id: string;
    account_name: string;
    account_type: string;
    balance: number;
}
interface Holding {
    id: string;
    ticker: string;
    shares: number;
    purchase_price: number;
    current_price: number;
}
interface Investment {
    id: string;
    investment_name: string;
    investment_type: string;
    holdings: Holding[];
}
interface FinanceData {
    netWorth: number;
    accounts: Account[];
    investments: Investment[];
}
interface FinanceContextType {
    financeData: FinanceData | null;
    loading: boolean;
    error: Error | null;
    fetchFinanceData: () => Promise<void>;
}
export declare const useFinance: () => FinanceContextType;
export declare const FinanceProvider: ({ children }: {
    children: ReactNode;
}) => JSX.Element;
export {};
