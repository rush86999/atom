import React, { useState, useEffect } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { Badge } from "../ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Search, Filter, RefreshCw, UserPlus, ShieldAlert, CheckCircle2 } from "lucide-react";
import { Progress } from "../ui/progress";

interface Lead {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    company: string;
    source: string;
    status: string;
    ai_score: number;
    ai_qualification_summary: string;
    is_spam: boolean;
    created_at: string;
}

const LeadManagement = () => {
    const [leads, setLeads] = useState<Lead[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");

    useEffect(() => {
        fetchLeads();
    }, []);

    const fetchLeads = async () => {
        setIsLoading(true);
        try {
            const response = await fetch("/api/sales/leads?workspace_id=temp_ws");
            const data = await response.json();
            setLeads(data);
        } catch (error) {
            console.error("Error fetching leads:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const filteredLeads = leads.filter(lead =>
        lead.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (lead.company && lead.company.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    const getScoreColor = (score: number) => {
        if (score >= 80) return "bg-green-500";
        if (score >= 50) return "bg-yellow-500";
        return "bg-red-500";
    };

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search leads or companies..."
                        className="pl-8"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={fetchLeads} disabled={isLoading}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                        Sync CRM
                    </Button>
                    <Button>
                        <UserPlus className="h-4 w-4 mr-2" />
                        Add Lead
                    </Button>
                </div>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>AI-Scored Leads</CardTitle>
                    <CardDescription>
                        Leads are automatically evaluated and scored based on intent, firmographics, and source.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Lead</TableHead>
                                <TableHead>Company</TableHead>
                                <TableHead>Source</TableHead>
                                <TableHead>AI Score</TableHead>
                                <TableHead>Qualification Summary</TableHead>
                                <TableHead>Status</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredLeads.map((lead) => (
                                <TableRow key={lead.id}>
                                    <TableCell>
                                        <div className="flex flex-col">
                                            <span className="font-medium">{lead.first_name} {lead.last_name}</span>
                                            <span className="text-xs text-muted-foreground">{lead.email}</span>
                                        </div>
                                    </TableCell>
                                    <TableCell>{lead.company}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline">{lead.source}</Badge>
                                    </TableCell>
                                    <TableCell>
                                        <div className="w-[100px] space-y-1">
                                            <div className="flex justify-between text-xs">
                                                <span>{lead.ai_score}%</span>
                                            </div>
                                            <Progress value={lead.ai_score} className={`h-1.5 ${getScoreColor(lead.ai_score)}`} />
                                        </div>
                                    </TableCell>
                                    <TableCell className="max-w-md">
                                        <p className="text-sm truncate" title={lead.ai_qualification_summary}>
                                            {lead.ai_qualification_summary}
                                        </p>
                                    </TableCell>
                                    <TableCell>
                                        {lead.is_spam ? (
                                            <Badge variant="destructive" className="flex w-fit gap-1">
                                                <ShieldAlert className="h-3 w-3" /> Spam
                                            </Badge>
                                        ) : (
                                            <Badge variant="success" className="flex w-fit gap-1">
                                                <CheckCircle2 className="h-3 w-3" /> {lead.status}
                                            </Badge>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                            {filteredLeads.length === 0 && !isLoading && (
                                <TableRow>
                                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                                        No leads found matching your criteria.
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    );
};

export default LeadManagement;
