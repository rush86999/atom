/**
 * User Presence List Component
 * Shows active users in the workflow with their cursor colors
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface Participant {
  user_id: string;
  user_name: string;
  user_color: string;
  role: string;
  can_edit: boolean;
  cursor_position?: {
    x: number;
    y: number;
    viewport?: {
      width: number;
      height: number;
    };
  };
  selected_node?: string;
  last_heartbeat: string;
}

interface UserPresenceListProps {
  workflowId: string;
  sessionId?: string;
  currentUserId?: string;
}

export const UserPresenceList: React.FC<UserPresenceListProps> = ({
  workflowId,
  sessionId,
  currentUserId,
}) => {
  const { toast } = useToast();
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch participants
  const fetchParticipants = useCallback(async () => {
    if (!sessionId) return;

    try {
      const response = await fetch(`/api/collaboration/sessions/${sessionId}`);
      if (!response.ok) throw new Error('Failed to fetch participants');

      const data = await response.json();
      setParticipants(data.participants || []);
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching participants:', error);
      setIsLoading(false);
    }
  }, [sessionId]);

  // Initial load
  useEffect(() => {
    fetchParticipants();
  }, [fetchParticipants]);

  // Poll for updates
  useEffect(() => {
    if (!sessionId) return;

    const interval = setInterval(fetchParticipants, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [sessionId, fetchParticipants]);

  // Get user initials
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  // Get role badge color
  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'owner':
        return 'default';
      case 'editor':
        return 'secondary';
      case 'viewer':
        return 'outline';
      case 'commenter':
        return 'outline';
      default:
        return 'outline';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Users className="h-4 w-4" />
            Active Users
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-4">
            <div className="h-2 w-2 bg-gray-200 rounded-full animate-pulse mr-2" />
            <div className="h-2 w-24 bg-gray-200 rounded-full animate-pulse" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Users className="h-4 w-4" />
          Active Users ({participants.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        {participants.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            No active collaborators
          </p>
        ) : (
          <div className="space-y-3">
            {participants.map((participant) => (
              <div
                key={participant.user_id}
                className="flex items-center justify-between group"
              >
                <div className="flex items-center gap-3 flex-1">
                  {/* User Avatar with Color */}
                  <Avatar
                    className="h-8 w-8"
                    style={{
                      border: `2px solid ${participant.user_color}`,
                    }}
                  >
                    <AvatarFallback
                      style={{
                        backgroundColor: `${participant.user_color}20`,
                        color: participant.user_color,
                      }}
                    >
                      {getInitials(participant.user_name)}
                    </AvatarFallback>
                  </Avatar>

                  {/* User Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium truncate">
                        {participant.user_name}
                      </p>
                      {participant.user_id === currentUserId && (
                        <Badge variant="outline" className="text-xs">
                          You
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={getRoleBadgeVariant(participant.role) as any} className="text-xs">
                        {participant.role}
                      </Badge>
                      {!participant.can_edit && (
                        <span className="text-xs text-muted-foreground">
                          View only
                        </span>
                      )}
                      {participant.selected_node && (
                        <span className="text-xs text-muted-foreground truncate" title={`Selected: ${participant.selected_node}`}>
                          🔍 {participant.selected_node}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Status Indicator */}
                <div
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: participant.user_color }}
                  title={`Last active: ${new Date(participant.last_heartbeat).toLocaleTimeString()}`}
                />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default UserPresenceList;
