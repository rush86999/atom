/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useState, useEffect, useMemo } from 'react';
import { Transaction, Budget } from '../types';
import { TRANSACTIONS_DATA, BUDGETS_DATA } from '../data';

const COLORS: Record<string, string> = {
    groceries: 'var(--accent-blue)',
    entertainment: 'var(--accent-purple)',
    utilities: 'var(--accent-orange)',
    income: 'var(--accent-green)',
    other: 'var(--text-muted-dark)',
};

const ExpenseDoughnutChart: React.FC<{ transactions: Transaction[] }> = ({ transactions }) => {
    const expenseByCategory = useMemo(() => {
        return transactions
            .filter(t => t.type === 'debit')
            .reduce((acc, t) => {
                acc[t.category] = (acc[t.category] || 0) + t.amount;
                return acc;
            }, {} as Record<string, number>);
    }, [transactions]);
    
    const totalExpenses = Object.values(expenseByCategory).reduce((sum, amount) => sum + amount, 0);

    const chartData = useMemo(() => {
        let cumulativePercent = 0;
        return Object.entries(expenseByCategory).map(([category, amount]) => {
            const percent = (amount / totalExpenses) * 100;
            const startAngle = (cumulativePercent / 100) * 360;
            cumulativePercent += percent;
            return { category, amount, percent, startAngle, endAngle: (cumulativePercent / 100) * 360 };
        });
    }, [expenseByCategory, totalExpenses]);

    const getArcPath = (startAngle: number, endAngle: number, radius: number, cutout: number) => {
        const polarToCartesian = (r: number, angle: number) => {
            const rad = (angle - 90) * Math.PI / 180.0;
            return { x: 50 + (r * Math.cos(rad)), y: 50 + (r * Math.sin(rad)) };
        };
        const start = polarToCartesian(radius, startAngle);
        const end = polarToCartesian(radius, endAngle);
        const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
        const cutoutStart = polarToCartesian(cutout, startAngle);
        const cutoutEnd = polarToCartesian(cutout, endAngle);

        return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${end.x} ${end.y} L ${cutoutEnd.x} ${cutoutEnd.y} A ${cutout} ${cutout} 0 ${largeArcFlag} 0 ${cutoutStart.x} ${cutoutStart.y} Z`;
    };

    return (
        <div className="doughnut-chart-container">
            <svg viewBox="0 0 100 100">
                {chartData.map(slice => <path key={slice.category} d={getArcPath(slice.startAngle, slice.endAngle, 45, 30)} fill={COLORS[slice.category] || COLORS.other} />)}
                <text x="50" y="48" textAnchor="middle" className="doughnut-center-text-label">Total Spent</text>
                <text x="50" y="60" textAnchor="middle" className="doughnut-center-text-amount">${totalExpenses.toFixed(2)}</text>
            </svg>
            <div className="doughnut-legend">
                {chartData.map(slice => (
                     <div key={slice.category} className="legend-item">
                        <span className="legend-dot" style={{ backgroundColor: COLORS[slice.category] || COLORS.other }}></span>
                        <span className="legend-label">{slice.category.charAt(0).toUpperCase() + slice.category.slice(1)}</span>
                        <span className="legend-percent">{slice.percent.toFixed(1)}%</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

const WeeklyCashFlowChart: React.FC<{ transactions: Transaction[] }> = ({ transactions }) => {
    const chartData = useMemo(() => {
        const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - i); return d; }).reverse();
        return days.map(day => ({
            day: day.toLocaleDateString('en-US', { weekday: 'short' }),
            income: transactions.filter(t => t.type === 'credit' && new Date(t.date).toDateString() === day.toDateString()).reduce((s, t) => s + t.amount, 0),
            expense: transactions.filter(t => t.type === 'debit' && new Date(t.date).toDateString() === day.toDateString()).reduce((s, t) => s + t.amount, 0),
        }));
    }, [transactions]);

    const maxAmount = Math.max(...chartData.flatMap(d => [d.income, d.expense]), 1);

    return (
        <div className="bar-chart-container">
            <svg width="100%" height="200">
                {chartData.map((data, index) => {
                    const x = (index / chartData.length) * 100 + (100 / chartData.length / 2);
                    const incomeHeight = (data.income / maxAmount) * 80;
                    const expenseHeight = (data.expense / maxAmount) * 80;
                    return (
                        <g key={data.day}>
                            <rect x={`${x - 5}%`} y={`${90 - incomeHeight}%`} width="4%" height={`${incomeHeight}%`} fill="var(--accent-green)" />
                            <rect x={`${x + 1}%`} y={`${90 - expenseHeight}%`} width="4%" height={`${expenseHeight}%`} fill="var(--accent-red)" />
                            <text x={`${x}%`} y="98%" textAnchor="middle" className="bar-chart-label">{data.day}</text>
                        </g>
                    );
                })}
            </svg>
            <div className="bar-chart-legend">
                <div className="legend-item"><span className="legend-dot" style={{backgroundColor: 'var(--accent-green)'}}></span>Income</div>
                <div className="legend-item"><span className="legend-dot" style={{backgroundColor: 'var(--accent-red)'}}></span>Expense</div>
            </div>
        </div>
    );
};

export const FinancesView = () => {
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [budgets, setBudgets] = useState<Budget[]>([]);
    const [filter, setFilter] = useState('');

    useEffect(() => {
        // In a real app, you'd fetch this data.
        setTransactions(TRANSACTIONS_DATA);
        setBudgets(BUDGETS_DATA);
    }, []);

    const filteredTransactions = transactions.filter(t =>
        t.description.toLowerCase().includes(filter.toLowerCase())
    ).sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    const {totalIncome, totalSpending, netChange} = useMemo(() => {
        const income = transactions.filter(t => t.type === 'credit').reduce((acc, t) => acc + t.amount, 0);
        const spending = transactions.filter(t => t.type === 'debit').reduce((acc, t) => acc + t.amount, 0);
        return { totalIncome: income, totalSpending: spending, netChange: income - spending };
    }, [transactions]);
    
    return (
        <div className="finances-view">
            <header className="view-header"><h1>Financial Dashboard</h1><p>Your complete financial overview.</p></header>
            
            <div className="finances-dashboard-grid">
                <div className="finance-summary-cards">
                    <div className="summary-card"><h3>Total Spending (30d)</h3><p>${totalSpending.toFixed(2)}</p></div>
                    <div className="summary-card"><h3>Total Income (30d)</h3><p>${totalIncome.toFixed(2)}</p></div>
                    <div className="summary-card"><h3>Net Change (30d)</h3><p className={netChange >= 0 ? 'positive' : 'negative'}>${netChange.toFixed(2)}</p></div>
                </div>

                <div className="dashboard-card chart-card">
                    <h3>Weekly Cash Flow</h3>
                    <WeeklyCashFlowChart transactions={transactions} />
                </div>

                <div className="dashboard-card chart-card">
                    <h3>Expense Breakdown</h3>
                    <ExpenseDoughnutChart transactions={transactions} />
                </div>

                <div className="dashboard-card full-width budgets-section">
                    <h3>Budgets</h3>
                    <div className="budgets-grid">
                        {budgets.map(budget => {
                            const percentage = Math.min((budget.spent / budget.amount) * 100, 100);
                            const status = percentage > 90 ? 'over' : percentage > 70 ? 'warning' : 'good';
                            return (
                                <div key={budget.id} className="budget-card">
                                    <div className="budget-card-header">
                                        <span>{budget.category}</span>
                                        <span className="budget-summary">${budget.spent.toFixed(0)} / ${budget.amount.toFixed(0)} ({((budget.spent / budget.amount) * 100).toFixed(0)}%)</span>
                                    </div>
                                    <div className="budget-progress-bar-container"><div className={`budget-progress-bar ${status}`} style={{ width: `${percentage}%` }}></div></div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                <div className="dashboard-card full-width transactions-section">
                     <div className="transactions-header">
                        <h3>Recent Transactions</h3>
                        <input type="text" placeholder="Filter transactions..." value={filter} onChange={e => setFilter(e.target.value)} className="transaction-filter-input" />
                    </div>
                    <div className="transactions-list">
                        {filteredTransactions.map(t => (
                            <div key={t.id} className="transaction-row">
                                <div>
                                    <p className="transaction-description">{t.description}</p>
                                    <p className="transaction-date">{new Date(t.date).toLocaleDateString()}</p>
                                </div>
                                <p className={`transaction-amount ${t.type === 'credit' ? 'positive' : 'negative'}`}>
                                    {t.type === 'credit' ? '+' : '-'}${t.amount.toFixed(2)}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};
