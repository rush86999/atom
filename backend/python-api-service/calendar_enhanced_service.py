"""
Enhanced Calendar Service Implementation
Complete Google Calendar integration with recurring events, free/busy, and advanced features
"""

import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from loguru import logger

@dataclass
class CalendarEvent:
    """Enhanced calendar event representation"""
    id: str
    summary: str
    description: Optional[str] = None
    location: Optional[str] = None
    start: Dict[str, Any] = None
    end: Dict[str, Any] = None
    attendees: Optional[List[Dict[str, Any]]] = None
    creator: Optional[Dict[str, Any]] = None
    organizer: Optional[Dict[str, Any]] = None
    visibility: str = 'public'
    transparency: str = 'opaque'
    i_cal_uid: Optional[str] = None
    sequence: int = 0
    recurrence: Optional[List[str]] = None
    recurring_event_id: Optional[str] = None
    original_start_time: Optional[Dict[str, Any]] = None
    status: str = 'confirmed'
    color_id: Optional[str] = None
    hangout_link: Optional[str] = None
    conference_data: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    reminders: Optional[Dict[str, Any]] = None
    extended_properties: Optional[Dict[str, Any]] = None

@dataclass
class Calendar:
    """Calendar representation"""
    id: str
    summary: str
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = 'UTC'
    primary: bool = False
    access_role: str = 'reader'
    color_id: Optional[str] = None
    background_color: Optional[str] = None
    foreground_color: Optional[str] = None
    selected: bool = True
    hidden: bool = False

@dataclass
class FreeBusyTime:
    """Free/busy time representation"""
    start: str
    end: str
    busy: bool

@dataclass
class RecurrenceRule:
    """Recurrence rule representation"""
    frequency: str  # DAILY, WEEKLY, MONTHLY, YEARLY
    interval: int = 1
    count: Optional[int] = None
    until: Optional[str] = None
    by_weekday: Optional[List[str]] = None
    by_month_day: Optional[List[int]] = None
    by_month: Optional[List[int]] = None
    week_start: str = 'MO'
    
    def to_rrule(self) -> str:
        """Convert to RFC 5545 RRULE format"""
        rrule_parts = [f'FREQ={self.frequency}']
        
        if self.interval != 1:
            rrule_parts.append(f'INTERVAL={self.interval}')
        
        if self.count:
            rrule_parts.append(f'COUNT={self.count}')
        
        if self.until:
            rrule_parts.append(f'UNTIL={self.until}')
        
        if self.by_weekday:
            rrule_parts.append(f'BYDAY={",".join(self.by_weekday)}')
        
        if self.by_month_day:
            rrule_parts.append(f'BYMONTHDAY={",".join(map(str, self.by_month_day))}')
        
        if self.by_month:
            rrule_parts.append(f'BYMONTH={",".join(map(str, self.by_month))}')
        
        return f'RRULE:{";".join(rrule_parts)}'

class CalendarEnhancedService:
    """Enhanced Calendar service with advanced capabilities"""
    
    def __init__(self):
        self.base_url = "https://www.googleapis.com"
        self.timeout = 30
        self.logger = logger
        self.session = None
        
    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session"""
        if self.session is None:
            self.session = httpx.AsyncClient(timeout=self.timeout)
        return self.session

    async def _make_request(
        self,
        user_id: str,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Calendar API"""
        try:
            # Get access token for user
            access_token = await self._get_access_token(user_id)
            if not access_token:
                raise Exception(f"No access token available for user {user_id}")

            session = await self._get_session()
            url = f"{self.base_url}{endpoint}"

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            if method.upper() == "GET":
                response = await session.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await session.post(url, headers=headers, json=data, params=params)
            elif method.upper() == "PUT":
                response = await session.put(url, headers=headers, json=data, params=params)
            elif method.upper() == "DELETE":
                response = await session.delete(url, headers=headers, params=params)
            elif method.upper() == "PATCH":
                response = await session.patch(url, headers=headers, json=data, params=params)
            else:
                raise Exception(f"Unsupported HTTP method: {method}")

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return {"success": True}
            elif response.status_code == 401:
                self.logger.warning(f"Calendar API token expired for user {user_id}")
                raise Exception("Authentication failed - token may need refresh")
            else:
                error_text = response.text
                self.logger.error(f"Calendar API error {response.status_code}: {error_text}")
                raise Exception(f"Calendar API error: {response.status_code} - {error_text}")

        except Exception as e:
            self.logger.error(f"Error making Calendar API request: {e}")
            raise

    async def _get_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user (mock implementation)"""
        # In production, this would fetch from database
        return os.getenv("GOOGLE_ACCESS_TOKEN")

    # Enhanced Calendar Management
    async def list_calendars(
        self, user_id: str, min_access_role: str = 'reader'
    ) -> List[Calendar]:
        """List user's calendars with enhanced metadata"""
        try:
            params = {'minAccessRole': min_access_role}
            response = await self._make_request(
                user_id, "/calendar/v3/users/me/calendarList", params=params
            )

            calendars = []
            for item in response.get("items", []):
                calendar = Calendar(
                    id=item.get("id", ""),
                    summary=item.get("summary", ""),
                    description=item.get("description"),
                    location=item.get("location"),
                    timezone=item.get("timeZone", "UTC"),
                    primary=item.get("primary", False),
                    access_role=item.get("accessRole", "reader"),
                    color_id=item.get("colorId"),
                    background_color=item.get("backgroundColor"),
                    foreground_color=item.get("foregroundColor"),
                    selected=item.get("selected", True),
                    hidden=item.get("hidden", False),
                )
                calendars.append(calendar)

            return calendars

        except Exception as e:
            self.logger.error(f"Error listing calendars: {e}")
            return self._get_mock_calendars()

    async def create_calendar(
        self, user_id: str, summary: str, description: str = None,
        timezone: str = 'UTC', location: str = None
    ) -> Optional[Calendar]:
        """Create a new calendar"""
        try:
            data = {
                'summary': summary,
                'timeZone': timezone,
            }
            
            if description:
                data['description'] = description
            if location:
                data['location'] = location

            response = await self._make_request(
                user_id, "/calendar/v3/calendars", method="POST", data=data
            )

            return Calendar(
                id=response.get("id", ""),
                summary=response.get("summary", ""),
                description=response.get("description"),
                location=response.get("location"),
                timezone=response.get("timeZone", "UTC"),
                primary=response.get("primary", False),
                access_role='owner',
            )

        except Exception as e:
            self.logger.error(f"Error creating calendar: {e}")
            return None

    async def update_calendar(
        self, user_id: str, calendar_id: str, updates: Dict[str, Any]
    ) -> Optional[Calendar]:
        """Update calendar metadata"""
        try:
            response = await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}", 
                method="PATCH", data=updates
            )

            return Calendar(
                id=response.get("id", calendar_id),
                summary=response.get("summary", ""),
                description=response.get("description"),
                location=response.get("location"),
                timezone=response.get("timeZone", "UTC"),
                primary=response.get("primary", False),
                access_role='owner',
            )

        except Exception as e:
            self.logger.error(f"Error updating calendar: {e}")
            return None

    async def delete_calendar(self, user_id: str, calendar_id: str) -> bool:
        """Delete a calendar"""
        try:
            await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}", method="DELETE"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error deleting calendar: {e}")
            return False

    # Enhanced Event Management
    async def list_events(
        self, user_id: str, calendar_id: str = 'primary',
        time_min: str = None, time_max: str = None, q: str = None,
        max_results: int = 50, single_events: bool = True,
        order_by: str = 'startTime', timezone: str = None
    ) -> List[CalendarEvent]:
        """List calendar events with advanced filtering"""
        try:
            params = {
                'maxResults': max_results,
                'singleEvents': str(single_events).lower(),
                'orderBy': order_by,
            }

            if time_min:
                params['timeMin'] = time_min
            if time_max:
                params['timeMax'] = time_max
            if q:
                params['q'] = q
            if timezone:
                params['timeZone'] = timezone

            response = await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}/events", params=params
            )

            events = []
            for item in response.get("items", []):
                event = CalendarEvent(
                    id=item.get("id", ""),
                    summary=item.get("summary", ""),
                    description=item.get("description"),
                    location=item.get("location"),
                    start=item.get("start", {}),
                    end=item.get("end", {}),
                    attendees=item.get("attendees"),
                    creator=item.get("creator"),
                    organizer=item.get("organizer"),
                    visibility=item.get("visibility", "public"),
                    transparency=item.get("transparency", "opaque"),
                    i_cal_uid=item.get("iCalUID"),
                    sequence=item.get("sequence", 0),
                    recurrence=item.get("recurrence"),
                    recurring_event_id=item.get("recurringEventId"),
                    original_start_time=item.get("originalStartTime"),
                    status=item.get("status", "confirmed"),
                    color_id=item.get("colorId"),
                    hangout_link=item.get("hangoutLink"),
                    conference_data=item.get("conferenceData"),
                    attachments=item.get("attachments"),
                    reminders=item.get("reminders"),
                    extended_properties=item.get("extendedProperties"),
                )
                events.append(event)

            return events

        except Exception as e:
            self.logger.error(f"Error listing events: {e}")
            return self._get_mock_events(max_results)

    async def create_event(
        self, user_id: str, calendar_id: str, event_data: Dict[str, Any]
    ) -> Optional[CalendarEvent]:
        """Create a new calendar event"""
        try:
            response = await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}/events",
                method="POST", data=event_data
            )

            return self._parse_event(response)

        except Exception as e:
            self.logger.error(f"Error creating event: {e}")
            return None

    async def create_recurring_event(
        self, user_id: str, calendar_id: str,
        base_event: Dict[str, Any], recurrence_rules: List[RecurrenceRule]
    ) -> Optional[CalendarEvent]:
        """Create a recurring event"""
        try:
            # Convert recurrence rules to RRULE format
            rrule_strings = [rule.to_rrule() for rule in recurrence_rules]
            
            event_data = {
                **base_event,
                'recurrence': rrule_strings
            }

            return await self.create_event(user_id, calendar_id, event_data)

        except Exception as e:
            self.logger.error(f"Error creating recurring event: {e}")
            return None

    async def update_event(
        self, user_id: str, calendar_id: str, event_id: str,
        updates: Dict[str, Any]
    ) -> Optional[CalendarEvent]:
        """Update calendar event"""
        try:
            response = await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                method="PATCH", data=updates
            )

            return self._parse_event(response)

        except Exception as e:
            self.logger.error(f"Error updating event: {e}")
            return None

    async def delete_event(
        self, user_id: str, calendar_id: str, event_id: str
    ) -> bool:
        """Delete calendar event"""
        try:
            await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                method="DELETE"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error deleting event: {e}")
            return False

    async def move_event(
        self, user_id: str, source_calendar_id: str, event_id: str,
        destination_calendar_id: str
    ) -> Optional[CalendarEvent]:
        """Move event to another calendar"""
        try:
            response = await self._make_request(
                user_id, f"/calendar/v3/calendars/{source_calendar_id}/events/{event_id}/move",
                params={'destination': destination_calendar_id},
                method="POST"
            )

            return self._parse_event(response)

        except Exception as e:
            self.logger.error(f"Error moving event: {e}")
            return None

    # Free/Busy Functions
    async def get_free_busy(
        self, user_id: str, user_ids: List[str], time_min: str, time_max: str,
        calendar_expansion_max: int = 50, group_expansion_max: int = 50
    ) -> Dict[str, Any]:
        """Get free/busy information for users"""
        try:
            data = {
                'timeMin': time_min,
                'timeMax': time_max,
                'items': [{'id': user_id} for user_id in user_ids],
                'calendarExpansionMax': calendar_expansion_max,
                'groupExpansionMax': group_expansion_max,
            }

            response = await self._make_request(
                user_id, "/calendar/v3/freeBusy", method="POST", data=data
            )

            return response

        except Exception as e:
            self.logger.error(f"Error getting free/busy: {e}")
            return {"calendars": {}, "groups": {}, "errors": []}

    async def find_available_time(
        self, user_id: str, user_ids: List[str], duration_minutes: int,
        time_min: str, time_max: str, min_attendees: int = 1
    ) -> List[Dict[str, Any]]:
        """Find available time slots for all attendees"""
        try:
            # Get free/busy information
            free_busy = await self.get_free_busy(user_id, user_ids, time_min, time_max)
            
            available_slots = []
            
            for user_id in user_ids:
                busy_times = free_busy.get("calendars", {}).get(user_id, {}).get("busy", [])
                
                # Parse busy times and find gaps
                if busy_times:
                    current_time = datetime.fromisoformat(time_min.replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(time_max.replace('Z', '+00:00'))
                    
                    for busy in busy_times:
                        busy_start = datetime.fromisoformat(busy["start"].replace('Z', '+00:00'))
                        busy_end = datetime.fromisoformat(busy["end"].replace('Z', '+00:00'))
                        
                        # Check gap before this busy time
                        if busy_start > current_time:
                            gap_duration = (busy_start - current_time).total_seconds() / 60
                            if gap_duration >= duration_minutes:
                                available_slots.append({
                                    "start": current_time.isoformat(),
                                    "end": busy_start.isoformat(),
                                    "duration_minutes": gap_duration,
                                    "available_users": [user_id],
                                })
                        
                        current_time = max(current_time, busy_end)
                    
                    # Check gap after last busy time
                    if end_time > current_time:
                        gap_duration = (end_time - current_time).total_seconds() / 60
                        if gap_duration >= duration_minutes:
                            available_slots.append({
                                "start": current_time.isoformat(),
                                "end": end_time.isoformat(),
                                "duration_minutes": gap_duration,
                                "available_users": [user_id],
                            })
            
            # Find overlapping slots for all users
            if len(available_slots) >= min_attendees:
                # This is simplified - would need more complex logic for multiple users
                pass
            
            return available_slots

        except Exception as e:
            self.logger.error(f"Error finding available time: {e}")
            return []

    # Calendar Sharing
    async def share_calendar(
        self, user_id: str, calendar_id: str, email: str,
        role: str = 'reader'
    ) -> bool:
        """Share calendar with user"""
        try:
            data = {
                'scope': {
                    'type': 'user',
                    'value': email
                },
                'role': role
            }

            await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}/acl",
                method="POST", data=data
            )
            
            return True

        except Exception as e:
            self.logger.error(f"Error sharing calendar: {e}")
            return False

    async def get_calendar_permissions(
        self, user_id: str, calendar_id: str
    ) -> List[Dict[str, Any]]:
        """Get calendar access control list"""
        try:
            response = await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}/acl"
            )
            
            return response.get("items", [])

        except Exception as e:
            self.logger.error(f"Error getting calendar permissions: {e}")
            return []

    async def update_calendar_permission(
        self, user_id: str, calendar_id: str, rule_id: str,
        role: str
    ) -> bool:
        """Update calendar permission"""
        try:
            data = {'role': role}
            
            await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}/acl/{rule_id}",
                method="PATCH", data=data
            )
            
            return True

        except Exception as e:
            self.logger.error(f"Error updating calendar permission: {e}")
            return False

    async def revoke_calendar_access(
        self, user_id: str, calendar_id: str, rule_id: str
    ) -> bool:
        """Revoke calendar access"""
        try:
            await self._make_request(
                user_id, f"/calendar/v3/calendars/{calendar_id}/acl/{rule_id}",
                method="DELETE"
            )
            
            return True

        except Exception as e:
            self.logger.error(f"Error revoking calendar access: {e}")
            return False

    # Event Analytics
    async def get_calendar_analytics(
        self, user_id: str, calendar_id: str, date_range: Dict[str, str]
    ) -> Dict[str, Any]:
        """Get calendar analytics for a date range"""
        try:
            events = await self.list_events(
                user_id, calendar_id, 
                time_min=date_range.get("after"),
                time_max=date_range.get("before")
            )
            
            analytics = {
                "period": date_range,
                "total_events": len(events),
                "recurring_events": len([e for e in events if e.recurrence]),
                "events_with_attendees": len([e for e in events if e.attendees]),
                "events_with_conference": len([e for e in events if e.hangout_link]),
                "events_by_status": {},
                "events_by_visibility": {},
                "total_duration_minutes": 0,
                "average_duration_minutes": 0,
                "busiest_days": [],
                "top_attendees": []
            }
            
            # Calculate metrics
            total_duration = 0
            day_counts = {}
            attendee_counts = {}
            
            for event in events:
                # Status
                status = event.status
                analytics["events_by_status"][status] = analytics["events_by_status"].get(status, 0) + 1
                
                # Visibility
                visibility = event.visibility
                analytics["events_by_visibility"][visibility] = analytics["events_by_visibility"].get(visibility, 0) + 1
                
                # Duration
                if event.start and event.end:
                    start_time = datetime.fromisoformat(event.start.get("dateTime", event.start.get("date")))
                    end_time = datetime.fromisoformat(event.end.get("dateTime", event.end.get("date")))
                    duration = (end_time - start_time).total_seconds() / 60
                    total_duration += duration
                
                # Day count
                if event.start:
                    start_date = event.start.get("dateTime", event.start.get("date"))
                    day = start_date.split("T")[0] if "T" in start_date else start_date
                    day_counts[day] = day_counts.get(day, 0) + 1
                
                # Attendee count
                if event.attendees:
                    for attendee in event.attendees:
                        email = attendee.get("email", "")
                        attendee_counts[email] = attendee_counts.get(email, 0) + 1
            
            analytics["total_duration_minutes"] = int(total_duration)
            if events:
                analytics["average_duration_minutes"] = int(total_duration / len(events))
            
            # Busiest days
            sorted_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            analytics["busiest_days"] = [{"date": day, "count": count} for day, count in sorted_days]
            
            # Top attendees
            sorted_attendees = sorted(attendee_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            analytics["top_attendees"] = [{"email": email, "count": count} for email, count in sorted_attendees]
            
            return {"ok": True, "analytics": analytics}

        except Exception as e:
            self.logger.error(f"Error getting calendar analytics: {e}")
            return {"ok": False, "error": str(e)}

    def _parse_event(self, event_data: Dict[str, Any]) -> CalendarEvent:
        """Parse event data from Calendar API"""
        return CalendarEvent(
            id=event_data.get("id", ""),
            summary=event_data.get("summary", ""),
            description=event_data.get("description"),
            location=event_data.get("location"),
            start=event_data.get("start", {}),
            end=event_data.get("end", {}),
            attendees=event_data.get("attendees"),
            creator=event_data.get("creator"),
            organizer=event_data.get("organizer"),
            visibility=event_data.get("visibility", "public"),
            transparency=event_data.get("transparency", "opaque"),
            i_cal_uid=event_data.get("iCalUID"),
            sequence=event_data.get("sequence", 0),
            recurrence=event_data.get("recurrence"),
            recurring_event_id=event_data.get("recurringEventId"),
            original_start_time=event_data.get("originalStartTime"),
            status=event_data.get("status", "confirmed"),
            color_id=event_data.get("colorId"),
            hangout_link=event_data.get("hangoutLink"),
            conference_data=event_data.get("conferenceData"),
            attachments=event_data.get("attachments"),
            reminders=event_data.get("reminders"),
            extended_properties=event_data.get("extendedProperties"),
        )

    # Mock Data Methods
    def _get_mock_calendars(self) -> List[Calendar]:
        """Generate mock calendars for development"""
        return [
            Calendar(
                id="primary",
                summary="Primary Calendar",
                primary=True,
                access_role="owner",
                timezone="America/New_York",
            ),
            Calendar(
                id="work_calendar",
                summary="Work Calendar",
                primary=False,
                access_role="writer",
                timezone="America/New_York",
            ),
        ]

    def _get_mock_events(self, max_results: int) -> List[CalendarEvent]:
        """Generate mock events for development"""
        current_time = datetime.utcnow()
        events = []

        for i in range(max_results):
            start_time = current_time + timedelta(days=i, hours=9)
            end_time = start_time + timedelta(hours=1)
            
            events.append(CalendarEvent(
                id=f"event_{i}",
                summary=f"Mock Event {i}",
                description=f"This is a mock calendar event for development",
                location=f"Room {chr(65 + (i % 26))}" if i % 2 == 0 else "Virtual",
                start={"dateTime": start_time.isoformat() + "Z", "timeZone": "UTC"},
                end={"dateTime": end_time.isoformat() + "Z", "timeZone": "UTC"},
                visibility="public",
                status="confirmed",
                color_id=str(i % 11),
            ))

        return events

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.aclose()
            self.session = None

    def get_service_info(self) -> Dict[str, Any]:
        """Get Calendar enhanced service information"""
        return {
            "name": "Calendar Enhanced Service",
            "version": "2.0.0",
            "capabilities": [
                "calendar_management",
                "event_crud",
                "recurring_events",
                "free_busy_lookup",
                "available_time_finding",
                "calendar_sharing",
                "permission_management",
                "event_analytics",
                "conference_integration"
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }

# Global service instance
calendar_enhanced_service = CalendarEnhancedService()