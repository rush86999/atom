import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";
import { FileText, MessageSquare, ClipboardCheck, ArrowRight, Play, CheckCircle2, AlertTriangle } from "lucide-react";

interface Meeting {
    id: string;
    title: string;
    date: string;
    summary: string;
    objections: string[];
    action_items: string[];
    deal_name: string;
}

const MeetingAutomation = () => {
    const [meetings, setMeetings] = useState<Meeting[]>([]);
    const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null);

    useEffect(() => {
        fetchMeetings();
    }, []);

    const fetchMeetings = async () => {
        try {
            const response = await fetch("/api/sales/calls?workspace_id=temp_ws");
            const data = await response.json();
            setMeetings(data);
            if (data.length > 0) {
                setSelectedMeeting(data[0]);
            }
        } catch (error) {
            console.error("Error fetching meetings:", error);
        }
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 h-[600px]">
            <div className="md:col-span-4 border rounded-lg overflow-hidden flex flex-col">
                <div className="p-4 border-b bg-muted/50">
                    <h3 className="font-semibold flex items-center gap-2">
                        <MessageSquare className="h-4 w-4" /> Recent Calls
                    </h3>
                </div>
                <ScrollArea className="flex-1">
                    <div className="p-2 space-y-2">
                        {meetings.map((meeting) => (
                            <button
                                key={meeting.id}
                                onClick={() => setSelectedMeeting(meeting)}
                                className={`w-full text-left p-3 rounded-md transition-colors ${selectedMeeting?.id === meeting.id
                                    ? "bg-primary/10 border-primary border"
                                    : "hover:bg-muted border border-transparent"
                                    }`}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <span className="font-medium text-sm truncate">{meeting.title}</span>
                                    <Badge variant="outline" className="text-[10px] h-4">
                                        {new Date(meeting.date).toLocaleDateString()}
                                    </Badge>
                                </div>
                                <div className="text-xs text-muted-foreground truncate">{meeting.deal_name}</div>
                            </button>
                        ))}
                    </div>
                </ScrollArea>
            </div>

            <div className="md:col-span-8 space-y-4">
                {selectedMeeting ? (
                    <>
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <CardTitle>{selectedMeeting.title}</CardTitle>
                                        <CardDescription>{selectedMeeting.deal_name}</CardDescription>
                                    </div>
                                    <Button size="sm" variant="outline">
                                        <Play className="h-3 w-3 mr-2" /> Play Recording
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="space-y-2">
                                    <h4 className="text-sm font-semibold flex items-center gap-2 text-primary">
                                        <FileText className="h-4 w-4" /> AI Summary
                                    </h4>
                                    <p className="text-sm text-balance leading-relaxed">
                                        {selectedMeeting.summary}
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
                                    <div className="space-y-3">
                                        <h4 className="text-sm font-semibold flex items-center gap-2 text-orange-500">
                                            <AlertTriangle className="h-4 w-4" /> Objections Found
                                        </h4>
                                        <div className="flex flex-wrap gap-2 text-xs">
                                            {selectedMeeting.objections.map((obj, idx) => (
                                                <Badge key={idx} variant="warning" className="bg-orange-100 text-orange-700 hover:bg-orange-100">
                                                    {obj}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        <h4 className="text-sm font-semibold flex items-center gap-2 text-green-500">
                                            <ClipboardCheck className="h-4 w-4" /> Extracted Tasks
                                        </h4>
                                        <ul className="space-y-2">
                                            {selectedMeeting.action_items.map((item, idx) => (
                                                <li key={idx} className="text-xs flex items-center gap-2">
                                                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                                                    <span>{item}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>

                                <div className="pt-4 flex justify-end">
                                    <Button>
                                        Sync to CRM <ArrowRight className="h-4 w-4 ml-2" />
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    </>
                ) : (
                    <div className="h-full flex items-center justify-center border-2 border-dashed rounded-lg text-muted-foreground">
                        Select a meeting to view intelligence
                    </div>
                )}
            </div>
        </div>
    );
};

export default MeetingAutomation;
