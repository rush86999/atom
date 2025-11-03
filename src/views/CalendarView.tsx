
import React, { useState, useEffect } from 'react';
import { CalendarEvent } from '../types';
import { getCalendarEventsForMonth } from '../data';

export const CalendarView = () => {
    const [currentDate, setCurrentDate] = useState(new Date());
    const [selectedDate, setSelectedDate] = useState(new Date());
    const [events, setEvents] = useState<CalendarEvent[]>([]);
    useEffect(() => { setEvents(getCalendarEventsForMonth(currentDate.getFullYear(), currentDate.getMonth())); }, [currentDate]);

    const startOfMonth = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const daysInMonth = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0).getDate();
    const startOfWeek = startOfMonth.getDay();
    const days = Array.from({ length: startOfWeek }, () => null).concat(Array.from({ length: daysInMonth }, (_, i) => new Date(currentDate.getFullYear(), currentDate.getMonth(), i + 1)));
    const today = new Date();
    const isSameDay = (d1: Date, d2: Date) => d1.getFullYear() === d2.getFullYear() && d1.getMonth() === d2.getMonth() && d1.getDate() === d2.getDate();
    const formatTime = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const selectedDayEvents = events.filter(e => isSameDay(new Date(e.startTime), selectedDate)).sort((a,b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());

    return (
        <div className="calendar-view">
            <header className="view-header"><h1>Calendar</h1><p>Manage your schedule and events.</p></header>
            <div className="calendar-main">
                <div className="calendar-grid-container">
                    <div className="calendar-controls">
                        <button onClick={() => setCurrentDate(new Date(currentDate.setMonth(currentDate.getMonth() - 1)))}>&lt;</button>
                        <h2>{currentDate.toLocaleString('default', { month: 'long', year: 'numeric' })}</h2>
                        <button onClick={() => setCurrentDate(new Date(currentDate.setMonth(currentDate.getMonth() + 1)))}>&gt;</button>
                    </div>
                    <div className="calendar-weekdays">{['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => <div key={d}>{d}</div>)}</div>
                    <div className="calendar-grid">
                        {days.map((day, i) => day ? (
                            <div key={i} className={`calendar-day ${isSameDay(day, today) ? 'is-today' : ''} ${isSameDay(day, selectedDate) ? 'is-selected' : ''}`} onClick={() => setSelectedDate(day)}>
                                <span className="day-number">{day.getDate()}</span>
                                <div className="events-container">
                                    {events.filter(e => isSameDay(new Date(e.startTime), day)).slice(0, 2).map(e => <div key={e.id} className={`event-pill ${e.color}`}>{e.title}</div>)}
                                    {events.filter(e => isSameDay(new Date(e.startTime), day)).length > 2 && <div className="event-pill more">+{events.filter(e => isSameDay(new Date(e.startTime), day)).length - 2} more</div>}
                                </div>
                            </div>
                        ) : <div key={i} className="calendar-day empty"></div>)}
                    </div>
                </div>
                <aside className="day-details">
                    <h3 className="day-details-header">{selectedDate.toLocaleDateString('default', { weekday: 'long', month: 'long', day: 'numeric' })}</h3>
                    <div className="day-events-list">
                        {selectedDayEvents.length > 0 ? selectedDayEvents.map(e => (
                            <div key={e.id} className="event-detail-item">
                                <div className={`event-color-bar ${e.color}`}></div>
                                <div className="event-info"><p className="event-title">{e.title}</p><p className="event-time">{formatTime(e.startTime)} - {formatTime(e.endTime)}</p></div>
                            </div>
                        )) : <p className="no-events">No events scheduled.</p>}
                    </div>
                </aside>
            </div>
        </div>
    );
};
