"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useFinance = exports.FinanceProvider = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const FinanceContext = (0, react_1.createContext)(null);
const FinanceProvider = ({ children }) => {
    const [accounts, setAccounts] = (0, react_1.useState)([]);
    const [transactions, setTransactions] = (0, react_1.useState)([]);
    const value = {
        accounts,
        setAccounts,
        transactions,
        setTransactions,
    };
    return ((0, jsx_runtime_1.jsx)(FinanceContext.Provider, { value: value, children: children }));
};
exports.FinanceProvider = FinanceProvider;
const useFinance = () => {
    return (0, react_1.useContext)(FinanceContext);
};
exports.useFinance = useFinance;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7OztBQUFBLGlDQUFtRTtBQUVuRSxNQUFNLGNBQWMsR0FBRyxJQUFBLHFCQUFhLEVBQUMsSUFBSSxDQUFDLENBQUM7QUFFcEMsTUFBTSxlQUFlLEdBQUcsQ0FBQyxFQUFFLFFBQVEsRUFBRSxFQUFFLEVBQUU7SUFDOUMsTUFBTSxDQUFDLFFBQVEsRUFBRSxXQUFXLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFDN0MsTUFBTSxDQUFDLFlBQVksRUFBRSxlQUFlLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFFckQsTUFBTSxLQUFLLEdBQUc7UUFDWixRQUFRO1FBQ1IsV0FBVztRQUNYLFlBQVk7UUFDWixlQUFlO0tBQ2hCLENBQUM7SUFFRixPQUFPLENBQ0wsdUJBQUMsY0FBYyxDQUFDLFFBQVEsSUFBQyxLQUFLLEVBQUUsS0FBSyxZQUFHLFFBQVEsR0FBMkIsQ0FDNUUsQ0FBQztBQUNKLENBQUMsQ0FBQztBQWRXLFFBQUEsZUFBZSxtQkFjMUI7QUFFSyxNQUFNLFVBQVUsR0FBRyxHQUFHLEVBQUU7SUFDN0IsT0FBTyxJQUFBLGtCQUFVLEVBQUMsY0FBYyxDQUFDLENBQUM7QUFDcEMsQ0FBQyxDQUFDO0FBRlcsUUFBQSxVQUFVLGNBRXJCIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IGNyZWF0ZUNvbnRleHQsIHVzZUNvbnRleHQsIHVzZVN0YXRlIH0gZnJvbSAncmVhY3QnO1xuXG5jb25zdCBGaW5hbmNlQ29udGV4dCA9IGNyZWF0ZUNvbnRleHQobnVsbCk7XG5cbmV4cG9ydCBjb25zdCBGaW5hbmNlUHJvdmlkZXIgPSAoeyBjaGlsZHJlbiB9KSA9PiB7XG4gIGNvbnN0IFthY2NvdW50cywgc2V0QWNjb3VudHNdID0gdXNlU3RhdGUoW10pO1xuICBjb25zdCBbdHJhbnNhY3Rpb25zLCBzZXRUcmFuc2FjdGlvbnNdID0gdXNlU3RhdGUoW10pO1xuXG4gIGNvbnN0IHZhbHVlID0ge1xuICAgIGFjY291bnRzLFxuICAgIHNldEFjY291bnRzLFxuICAgIHRyYW5zYWN0aW9ucyxcbiAgICBzZXRUcmFuc2FjdGlvbnMsXG4gIH07XG5cbiAgcmV0dXJuIChcbiAgICA8RmluYW5jZUNvbnRleHQuUHJvdmlkZXIgdmFsdWU9e3ZhbHVlfT57Y2hpbGRyZW59PC9GaW5hbmNlQ29udGV4dC5Qcm92aWRlcj5cbiAgKTtcbn07XG5cbmV4cG9ydCBjb25zdCB1c2VGaW5hbmNlID0gKCkgPT4ge1xuICByZXR1cm4gdXNlQ29udGV4dChGaW5hbmNlQ29udGV4dCk7XG59O1xuIl19