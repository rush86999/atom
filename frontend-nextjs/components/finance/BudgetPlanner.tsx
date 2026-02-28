import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Progress } from "../ui/progress";
import { Button } from "../ui/button";
import { Plus } from "lucide-react";
import { useToast } from "../ui/use-toast";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { Input } from "../ui/input";
import { Label } from "../ui/label";

const BudgetPlanner = () => {
    const { toast } = useToast();
    const [budgets, setBudgets] = React.useState([
        { category: "Infrastructure", spent: 142, limit: 200, color: "bg-blue-500" },
        { category: "Software Subscriptions", spent: 345, limit: 500, color: "bg-purple-500" },
        { category: "Marketing", spent: 850, limit: 1000, color: "bg-green-500" },
        { category: "Office & Rent", spent: 450, limit: 450, color: "bg-yellow-500" },
        { category: "Travel", spent: 1200, limit: 800, color: "bg-red-500" },
    ]);
    const [isAddOpen, setIsAddOpen] = React.useState(false);
    const [newBudget, setNewBudget] = React.useState({ category: "", limit: "" });

    const handleAddBudget = (e: React.FormEvent) => {
        e.preventDefault();
        if (!newBudget.category || !newBudget.limit) return;

        const limitNum = parseFloat(newBudget.limit);
        if (isNaN(limitNum) || limitNum <= 0) {
            toast({ title: "Invalid Limit", description: "Please enter a valid number for the budget limit.", variant: "error" });
            return;
        }

        const colors = ["bg-blue-500", "bg-purple-500", "bg-green-500", "bg-yellow-500", "bg-red-500", "bg-cyan-500", "bg-pink-500"];
        const randomColor = colors[Math.floor(Math.random() * colors.length)];

        setBudgets(prev => [...prev, {
            category: newBudget.category,
            spent: 0,
            limit: limitNum,
            color: randomColor
        }]);

        toast({ title: "Budget Added", description: `Created new budget for ${newBudget.category}` });
        setNewBudget({ category: "", limit: "" });
        setIsAddOpen(false);
    };

    return (
        <div className="grid gap-4 md:grid-cols-2">
            <Card className="col-span-2">
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>Monthly Budget</CardTitle>
                        <CardDescription>Track your spending against your targets.</CardDescription>
                    </div>
                    <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
                        <DialogTrigger asChild>
                            <Button>
                                <Plus className="mr-2 h-4 w-4" /> Add Budget
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[425px]">
                            <DialogHeader>
                                <DialogTitle>Add New Budget</DialogTitle>
                                <DialogDescription>
                                    Create a new budget category to track expenses.
                                </DialogDescription>
                            </DialogHeader>
                            <form onSubmit={handleAddBudget} className="space-y-4 pt-4">
                                <div className="space-y-2">
                                    <Label htmlFor="category">Category Name</Label>
                                    <Input
                                        id="category"
                                        value={newBudget.category}
                                        onChange={(e) => setNewBudget({ ...newBudget, category: e.target.value })}
                                        placeholder="e.g. Legal Fees"
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="limit">Monthly Limit ($)</Label>
                                    <Input
                                        id="limit"
                                        type="number"
                                        step="0.01"
                                        value={newBudget.limit}
                                        onChange={(e) => setNewBudget({ ...newBudget, limit: e.target.value })}
                                        placeholder="500.00"
                                        required
                                    />
                                </div>
                                <DialogFooter className="pt-4">
                                    <Button type="submit">Create Budget</Button>
                                </DialogFooter>
                            </form>
                        </DialogContent>
                    </Dialog>
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
