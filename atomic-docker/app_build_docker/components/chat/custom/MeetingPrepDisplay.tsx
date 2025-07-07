import React from 'react';
import {
    AggregatedPrepResults,
    PrepResultSourceEntry,
    GmailMessageSnippet,
    SlackMessageSnippet,
    NotionPageSummary,
    CalendarEventSummary
} from '@lib/dataTypes/Messaging/MessagingTypes';
import { cn } from '@lib/Chat/utils';

const ItemCard: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
    <div className={cn(
        "p-3 mb-2 border rounded-lg shadow-sm transition-shadow hover:shadow-md",
        "bg-white dark:bg-gray-800",
        "border-gray-200 dark:border-gray-600",
        className
    )}>
        {children}
    </div>
);

const ItemLink: React.FC<{ href: string; children: React.ReactNode; className?: string }> = ({ href, children, className }) => (
    <a href={href} target="_blank" rel="noopener noreferrer"
       className={cn("text-xs hover:underline focus:outline-none focus:ring-1 focus:ring-sky-500 rounded", className)}>
        {children}
    </a>
);

const GmailResultItem: React.FC<{ item: GmailMessageSnippet }> = ({ item }) => (
    <ItemCard>
        <p className="text-sm font-semibold text-sky-700 dark:text-sky-400">{item.subject || 'No Subject'}</p>
        <p className="text-xs text-gray-600 dark:text-gray-400">
            From: {item.from || 'N/A'} | Date: {item.date ? new Date(item.date).toLocaleDateString() : 'N/A'}
        </p>
        <p className="text-xs text-gray-700 dark:text-gray-300 mt-1 truncate">{item.snippet || 'No snippet'}</p>
        {item.link && <ItemLink href={item.link} className="text-sky-600 dark:text-sky-500">View Email</ItemLink>}
    </ItemCard>
);

const SlackResultItem: React.FC<{ item: SlackMessageSnippet }> = ({ item }) => (
    <ItemCard>
        <p className="text-sm font-semibold text-purple-600 dark:text-purple-400">Slack Message</p>
        <p className="text-xs text-gray-600 dark:text-gray-400">
            Channel: {item.channel?.name || item.channel?.id || 'N/A'} | User: {item.user?.name || item.user?.id || 'N/A'}
        </p>
        <p className="text-xs text-gray-700 dark:text-gray-300 mt-1 whitespace-pre-wrap">{item.text || 'No text'}</p>
        {item.permalink && <ItemLink href={item.permalink} className="text-purple-500 dark:text-purple-400">View Message</ItemLink>}
    </ItemCard>
);

const NotionResultItem: React.FC<{ item: NotionPageSummary }> = ({ item }) => (
    <ItemCard>
        <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">{item.title || 'Untitled Page'}</p>
        <p className="text-xs text-gray-600 dark:text-gray-400">
            Last Edited: {item.last_edited_time ? new Date(item.last_edited_time).toLocaleDateString() : 'N/A'}
        </p>
        {item.preview_text && <p className="text-xs text-gray-700 dark:text-gray-300 mt-1 truncate">{item.preview_text}</p>}
        {item.url && <ItemLink href={item.url} className="text-emerald-500 dark:text-emerald-400">View Page</ItemLink>}
    </ItemCard>
);

const RelatedCalendarEventItem: React.FC<{ item: CalendarEventSummary }> = ({ item }) => (
    <ItemCard>
        <p className="text-sm font-semibold text-amber-600 dark:text-amber-400">{item.summary || 'Untitled Event'}</p>
        <p className="text-xs text-gray-600 dark:text-gray-400">
            Starts: {item.start ? new Date(item.start).toLocaleString() : 'N/A'}
        </p>
        <p className="text-xs text-gray-600 dark:text-gray-400">
            Ends: {item.end ? new Date(item.end).toLocaleString() : 'N/A'}
        </p>
        {item.htmlLink && <ItemLink href={item.htmlLink} className="text-amber-500 dark:text-amber-400">View Event</ItemLink>}
    </ItemCard>
);

interface MeetingPrepDisplayProps {
    briefing: AggregatedPrepResults;
}

const Section: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className }) => (
    <div className={cn("mb-4 p-3 rounded-lg", className)}>
        <h3 className="text-base font-semibold mb-2 text-gray-700 dark:text-gray-200">{title}</h3>
        {children}
    </div>
);


const MeetingPrepDisplay: React.FC<MeetingPrepDisplayProps> = ({ briefing }) => {
    if (!briefing) {
        return <div className="p-3 text-sm text-gray-600 dark:text-gray-400 font-sans">No meeting preparation data available.</div>;
    }

    return (
        <div className={cn(
            "p-4 my-2 rounded-lg shadow font-sans",
            "bg-gray-50 dark:bg-gray-800/50", // Slightly more transparent dark bg
            "border border-gray-200 dark:border-gray-700"
        )}>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-3">
                Meeting Prep: {briefing.meeting_reference_identified || "General Briefing"}
            </h2>

            {briefing.identified_calendar_event && (
                <Section title="Identified Event" className="bg-sky-50 dark:bg-sky-900/30 border border-sky-200 dark:border-sky-700/50">
                    <p className="text-sm text-sky-800 dark:text-sky-200">{briefing.identified_calendar_event.summary}</p>
                    <p className="text-xs text-sky-600 dark:text-sky-400">
                        {new Date(briefing.identified_calendar_event.start || '').toLocaleString()} - {new Date(briefing.identified_calendar_event.end || '').toLocaleString()}
                    </p>
                </Section>
            )}

            {briefing.overall_summary_notes && (
                <Section title="Overall Summary" className="bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-700/50">
                    <p className="text-sm text-emerald-800 dark:text-emerald-200 whitespace-pre-wrap">{briefing.overall_summary_notes}</p>
                </Section>
            )}

            {briefing.results_by_source && briefing.results_by_source.length > 0 && (
                <Section title="Information Found" className="bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700/50">
                    {briefing.results_by_source.map((sourceEntry, index) => (
                        <div key={index} className="mb-4 last:mb-0">
                            <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-300 mb-1">
                                From {sourceEntry.source} ({sourceEntry.count} item(s))
                            </h4>
                            {sourceEntry.error_message && (
                                <p className="text-xs text-red-600 dark:text-red-400 py-1 px-2 bg-red-50 dark:bg-red-900/50 border border-red-200 dark:border-red-700/50 rounded-md">Error: {sourceEntry.error_message}</p>
                            )}
                            <div className="mt-1 max-h-72 overflow-y-auto pr-2 custom-scrollbar space-y-2">
                                {sourceEntry.results.map((item, itemIndex) => {
                                    const key = `${sourceEntry.source}-${itemIndex}`;
                                    switch (sourceEntry.source) {
                                        case 'gmail':
                                            return <GmailResultItem key={key} item={item as GmailMessageSnippet} />;
                                        case 'slack':
                                            return <SlackResultItem key={key} item={item as SlackMessageSnippet} />;
                                        case 'notion':
                                            return <NotionResultItem key={key} item={item as NotionPageSummary} />;
                                        case 'calendar_events':
                                            return <RelatedCalendarEventItem key={key} item={item as CalendarEventSummary} />;
                                        default:
                                            return <p key={key} className="text-xs text-gray-500 dark:text-gray-400">Unsupported item type</p>;
                                    }
                                })}
                            </div>
                        </div>
                    ))}
                </Section>
            )}

            {briefing.errors_encountered && briefing.errors_encountered.length > 0 && (
                 <Section title="Errors Encountered During Prep" className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/50">
                    <ul className="list-disc list-inside pl-2 space-y-1">
                        {briefing.errors_encountered.map((error, index) => (
                            <li key={index} className="text-xs text-red-700 dark:text-red-300">
                                <span className="font-medium">{error.source_attempted || 'Overall'}:</span> {error.message}
                                {error.details && <span className="block text-xxs text-red-500 dark:text-red-400 truncate">Details: {error.details}</span>}
                            </li>
                        ))}
                    </ul>
                </Section>
            )}
        </div>
    );
};

export default MeetingPrepDisplay;
