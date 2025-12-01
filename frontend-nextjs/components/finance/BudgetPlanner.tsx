import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Progress } from "../ui/progress";
import { Button } from "../ui/button";
import { Plus } from "lucide-react";

const BudgetPlanner = () => {
    const budgets = [
        { category: "Infrastructure", spent: 142, limit: 200, color: "bg-blue-500" },
        { category: "Software Subscriptions", spent: 345, limit: 500, color: "bg-purple-500" },
        { category: "Marketing", spent: 850, limit: 1000, color: "bg-green-500" },
        { category: "Office & Rent", spent: 450, limit: 450, color: "bg-yellow-500" },
        { category: "Travel", spent: 1200, limit: 800, color: "bg-red-500" },
    ];

    return (
        <div className="grid gap-4 md:grid-cols-2">
            <Card className="col-span-2">
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>Monthly Budget</CardTitle>
                        <CardDescription>Track your spending against your targets.</CardDescription>
                    </div>
                    <Button>
                        <Plus className="mr-2 h-4 w-4" /> Add Budget
                    </Button>
                </CardHeader>
                <CardContent>
                    <div className="space-y-8">
                        {budgets.map((budget) => {
                            const percentage = Math.min((budget.spent / budget.limit) * 100, 100);
                            const isOverBudget = budget.spent > budget.limit;

                            return (
                                <div key={budget.category} className="space-y-2">
                                    <div className="flex items-center justify-between text-sm">
                                        <div className="font-medium">{budget.category}</div>
                                        <div className="text-muted-foreground">
                                            <span className={isOverBudget ? "text-red-500 font-bold" : ""}>
                                                ${budget.spent}
                                            </span>{" "}
                                            / ${budget.limit}
                                        </div>
                                    </div>
                                    <Progress value={percentage} className="h-2" indicatorClassName={isOverBudget ? "bg-red-500" : budget.color} />
                                    <p className="text-xs text-muted-foreground text-right">
                                        {percentage.toFixed(0)}% used
                                    </p>
                                </div>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default BudgetPlanner;
