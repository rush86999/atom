import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Calendar, CreditCard, AlertCircle } from "lucide-react";
import { useToast } from "../ui/use-toast";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";

const SubscriptionTracker = () => {
    const { toast } = useToast();
    const [subscriptions, setSubscriptions] = React.useState([
        { id: 1, name: "AWS", plan: "Pro", cost: 142.00, cycle: "Monthly", nextBill: "2025-12-01", status: "Active" },
        { id: 2, name: "Adobe Creative Cloud", plan: "All Apps", cost: 54.99, cycle: "Monthly", nextBill: "2025-12-05", status: "Active" },
        { id: 3, name: "Slack", plan: "Business", cost: 12.50, cycle: "Monthly/User", nextBill: "2025-12-10", status: "Active" },
        { id: 4, name: "GitHub", plan: "Team", cost: 40.00, cycle: "Monthly", nextBill: "2025-12-15", status: "Active" },
        { id: 5, name: "Vercel", plan: "Pro", cost: 20.00, cycle: "Monthly", nextBill: "2025-12-01", status: "Active" },
        { id: 6, name: "Notion", plan: "Team", cost: 8.00, cycle: "Monthly/User", nextBill: "2025-12-03", status: "Active" },
    ]);
    const [isManageOpen, setIsManageOpen] = React.useState(false);
    const [selectedSub, setSelectedSub] = React.useState<any>(null);

    const handleCancel = () => {
        if (!selectedSub) return;
        setSubscriptions(prev => prev.map(sub =>
            sub.id === selectedSub.id ? { ...sub, status: "Cancelled" } : sub
        ));
        toast({ title: "Subscription Cancelled", description: `${selectedSub.name} has been cancelled successfully.` });
        setIsManageOpen(false);
    };

    const activeSubs = subscriptions.filter(s => s.status === "Active");
    const totalMonthly = activeSubs.reduce((acc, sub) => acc + sub.cost, 0);

    return (
        <>
            <div className="space-y-6">
                <div className="grid gap-4 md:grid-cols-3">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Monthly Recurring</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">${totalMonthly.toFixed(2)}</div>
                            <p className="text-xs text-muted-foreground">Estimated for next month</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Active Subscriptions</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{activeSubs.length}</div>
                            <p className="text-xs text-muted-foreground">Services connected</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Total Tracked</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{subscriptions.length}</div>
                            <p className="text-xs text-muted-foreground">Historical & active</p>
                        </CardContent>
                    </Card>
                </div>

                <Card>
                    <CardHeader>
                        <CardTitle>Subscriptions</CardTitle>
                        <CardDescription>Manage your recurring software and service payments.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {subscriptions.map((sub) => (
                                <div key={sub.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-secondary/50 transition-colors">
                                    <div className="flex items-center gap-4">
                                        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                                            <CreditCard className="h-5 w-5 text-primary" />
                                        </div>
                                        <div>
                                            <h4 className="font-semibold">{sub.name}</h4>
                                            <p className="text-sm text-muted-foreground">{sub.plan} • {sub.cycle}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-6">
                                        <div className="text-right">
                                            <div className="font-bold">${sub.cost.toFixed(2)}</div>
                                            <div className="text-xs text-muted-foreground flex items-center gap-1 justify-end">
                                                <Calendar className="h-3 w-3" /> {sub.nextBill}
                                            </div>
                                        </div>
                                        <Badge variant="outline" className={sub.status === 'Active' ? "bg-green-500/10 text-green-500 border-green-500/20" : "bg-red-500/10 text-red-500 border-red-500/20"}>
                                            {sub.status}
                                        </Badge>
                                        <Button variant="ghost" size="sm" onClick={() => {
                                            setSelectedSub(sub);
                                            setIsManageOpen(true);
                                        }}>Manage</Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>

            <Dialog open={isManageOpen} onOpenChange={setIsManageOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Manage Subscription</DialogTitle>
                        <DialogDescription>
                            Review or cancel your {selectedSub?.name} subscription.
                        </DialogDescription>
                    </DialogHeader>
                    {selectedSub && (
                        <div className="space-y-4 py-4">
                            <div className="flex justify-between items-center text-sm border-b pb-2">
                                <span className="text-muted-foreground">Plan</span>
                                <span className="font-medium">{selectedSub.plan}</span>
                            </div>
                            <div className="flex justify-between items-center text-sm border-b pb-2">
                                <span className="text-muted-foreground">Cost</span>
                                <span className="font-medium">${selectedSub.cost.toFixed(2)} ({selectedSub.cycle})</span>
                            </div>
                            <div className="flex justify-between items-center text-sm border-b pb-2">
                                <span className="text-muted-foreground">Status</span>
                                <Badge variant="outline" className={selectedSub.status === 'Active' ? "bg-green-500/10 text-green-500 border-green-500/20" : "bg-red-500/10 text-red-500 border-red-500/20"}>
                                    {selectedSub.status}
                                </Badge>
                            </div>
                            <div className="flex justify-between items-center text-sm">
                                <span className="text-muted-foreground">Billing Cycle</span>
                                <span className="font-medium">Renews {selectedSub.nextBill}</span>
                            </div>
                        </div>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsManageOpen(false)}>Close</Button>
                        {selectedSub?.status === 'Active' && (
                            <Button variant="destructive" onClick={handleCancel}>Cancel Subscription</Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
};

export default SubscriptionTracker;
