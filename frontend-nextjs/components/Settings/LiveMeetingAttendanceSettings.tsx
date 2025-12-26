import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

const LiveMeetingAttendanceSettings: React.FC = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;
    const { toast } = useToast();

    const [isAutoAttendanceEnabled, setIsAutoAttendanceEnabled] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchSettings = async () => {
            if (!userId) return;
            try {
                const response = await fetch(`/api/users/${userId}/settings/meeting-attendance`);
                const data = await response.json();
                if (data.success) {
                    setIsAutoAttendanceEnabled(data.enabled);
                }
            } catch (error) {
                console.error('Error fetching meeting settings:', error);
            } finally {
                setIsLoading(false);
            }
        };
        fetchSettings();
    }, [userId]);

    const handleToggleAutoAttendance = async () => {
        if (!userId) return;
        const newValue = !isAutoAttendanceEnabled;
        setIsAutoAttendanceEnabled(newValue);

        try {
            const response = await fetch(`/api/users/${userId}/settings/meeting-attendance`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: newValue }),
            });
            if (response.ok) {
                toast({
                    title: `Auto-attendance ${newValue ? 'enabled' : 'disabled'}`,
                    variant: 'success'
                });
            } else {
                throw new Error('Failed to update');
            }
        } catch (error) {
            setIsAutoAttendanceEnabled(!newValue);
            toast({ title: 'Error updating meeting attendance settings', variant: 'error' });
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                    <Label htmlFor="auto-attendance">Auto-attend Meetings</Label>
                    <p className="text-sm text-muted-foreground">Automatically join calendar meetings and take notes.</p>
                </div>
                <Switch
                    id="auto-attendance"
                    checked={isAutoAttendanceEnabled}
                    onCheckedChange={handleToggleAutoAttendance}
                    disabled={isLoading}
                />
            </div>

            {isAutoAttendanceEnabled && (
                <div className="p-3 bg-blue-50 text-blue-700 rounded-md border border-blue-200 text-sm">
                    ATOM will join upcoming Zoom and Teams meetings detected in your Google Calendar.
                </div>
            )}
        </div>
    );
};

export default LiveMeetingAttendanceSettings;
