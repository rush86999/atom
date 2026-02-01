import React from 'react';
import {
    FileText,
    TrendingUp,
    Receipt,
    Calculator
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription
} from "@/components/ui/card";

export const XeroReports: React.FC = () => {
    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold tracking-tight">Financial Reports</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="hover:shadow-md transition-all cursor-pointer">
                    <CardHeader>
                        <div className="flex items-center gap-4">
                            <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                                <FileText className="h-8 w-8 text-blue-600 dark:text-blue-400" />
                            </div>
                            <div>
                                <CardTitle>Profit & Loss</CardTitle>
                                <CardDescription>
                                    View detailed profit and loss statement for your business
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <Button className="w-full">Generate Report</Button>
                    </CardContent>
                </Card>

                <Card className="hover:shadow-md transition-all cursor-pointer">
                    <CardHeader>
                        <div className="flex items-center gap-4">
                            <div className="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
                                <TrendingUp className="h-8 w-8 text-green-600 dark:text-green-400" />
                            </div>
                            <div>
                                <CardTitle>Balance Sheet</CardTitle>
                                <CardDescription>
                                    Comprehensive view of your assets, liabilities, and equity
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <Button className="w-full">Generate Report</Button>
                    </CardContent>
                </Card>

                <Card className="hover:shadow-md transition-all cursor-pointer">
                    <CardHeader>
                        <div className="flex items-center gap-4">
                            <div className="p-2 bg-orange-100 dark:bg-orange-900 rounded-lg">
                                <Receipt className="h-8 w-8 text-orange-600 dark:text-orange-400" />
                            </div>
                            <div>
                                <CardTitle>Cash Flow</CardTitle>
                                <CardDescription>
                                    Track cash inflows and outflows over time
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <Button className="w-full">Generate Report</Button>
                    </CardContent>
                </Card>

                <Card className="hover:shadow-md transition-all cursor-pointer">
                    <CardHeader>
                        <div className="flex items-center gap-4">
                            <div className="p-2 bg-purple-100 dark:bg-purple-900 rounded-lg">
                                <Calculator className="h-8 w-8 text-purple-600 dark:text-purple-400" />
                            </div>
                            <div>
                                <CardTitle>Aged Receivables</CardTitle>
                                <CardDescription>
                                    Monitor outstanding invoices and overdue payments
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <Button className="w-full">Generate Report</Button>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};
