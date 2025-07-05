import React from 'react';
import {
    AggregatedPrepResults,
    PrepResultSourceEntry,
    GmailMessageSnippet,
    SlackMessageSnippet,
    NotionPageSummary,
    CalendarEventSummary
} from '@lib/dataTypes/Messaging/MessagingTypes'; // Adjust path as necessary

// Define interfaces for the item props if they are not already globally available
// For now, assuming they are imported or will be defined alongside their components.

// --- Item Sub-Components (Conceptual, will be separate files) ---

const GmailResultItem: React.FC<{ item: GmailMessageSnippet }> = ({ item }) => (
    <div className="p-2 mb-2 border rounded-lg shadow-sm hover:shadow-md transition-shadow">
        <p className="text-sm font-semibold text-blue-600">{item.subject || 'No Subject'}</p>
        <p className="text-xs text-gray-600">From: {item.from || 'N/A'} | Date: {item.date ? new Date(item.date).toLocaleDateString() : 'N/A'}</p>
        <p className="text-xs text-gray-700 mt-1 truncate">{item.snippet || 'No snippet'}</p>
        {item.link && <a href={item.link} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline">View Email</a>}
    </div>
);

const SlackResultItem: React.FC<{ item: SlackMessageSnippet }> = ({ item }) => (
    <div className="p-2 mb-2 border rounded-lg shadow-sm hover:shadow-md transition-shadow">
        <p className="text-sm font-semibold text-purple-600">Slack Message</p>
        <p className="text-xs text-gray-600">
            Channel: {item.channel?.name || item.channel?.id || 'N/A'} | User: {item.user?.name || item.user?.id || 'N/A'}
        </p>
        <p className="text-xs text-gray-700 mt-1">{item.text || 'No text'}</p>
        {item.permalink && <a href={item.permalink} target="_blank" rel="noopener noreferrer" className="text-xs text-purple-500 hover:underline">View Message</a>}
    </div>
);

const NotionResultItem: React.FC<{ item: NotionPageSummary }> = ({ item }) => (
    <div className="p-2 mb-2 border rounded-lg shadow-sm hover:shadow-md transition-shadow">
        <p className="text-sm font-semibold text-green-600">{item.title || 'Untitled Page'}</p>
        <p className="text-xs text-gray-600">
            Last Edited: {item.last_edited_time ? new Date(item.last_edited_time).toLocaleDateString() : 'N/A'}
        </p>
        {item.preview_text && <p className="text-xs text-gray-700 mt-1 truncate">{item.preview_text}</p>}
        {item.url && <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-xs text-green-500 hover:underline">View Page</a>}
    </div>
);

const RelatedCalendarEventItem: React.FC<{ item: CalendarEventSummary }> = ({ item }) => (
    <div className="p-2 mb-2 border rounded-lg shadow-sm hover:shadow-md transition-shadow">
        <p className="text-sm font-semibold text-orange-600">{item.summary || 'Untitled Event'}</p>
        <p className="text-xs text-gray-600">
            Starts: {item.start ? new Date(item.start).toLocaleString() : 'N/A'}
        </p>
        <p className="text-xs text-gray-600">
            Ends: {item.end ? new Date(item.end).toLocaleString() : 'N/A'}
        </p>
        {item.htmlLink && <a href={item.htmlLink} target="_blank" rel="noopener noreferrer" className="text-xs text-orange-500 hover:underline">View Event</a>}
    </div>
);

// --- Main Display Component ---

interface MeetingPrepDisplayProps {
    briefing: AggregatedPrepResults;
}

const MeetingPrepDisplay: React.FC<MeetingPrepDisplayProps> = ({ briefing }) => {
    if (!briefing) {
        return <div className="p-3 text-sm text-gray-700">No meeting preparation data available.</div>;
    }

    return (
        <div className="p-4 my-2 bg-gray-50 border border-gray-200 rounded-lg shadow">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">
                Meeting Prep: {briefing.meeting_reference_identified}
            </h2>

            {briefing.identified_calendar_event && (
                <div className="mb-3 p-3 bg-indigo-50 border border-indigo-200 rounded">
                    <h3 className="text-md font-medium text-indigo-700">Identified Event:</h3>
                    <p className="text-sm text-indigo-600">{briefing.identified_calendar_event.summary}</p>
                    <p className="text-xs text-indigo-500">
                        {new Date(briefing.identified_calendar_event.start || '').toLocaleString()} -
                        {new Date(briefing.identified_calendar_event.end || '').toLocaleString()}
                    </p>
                    {/* Consider adding attendees or other details if needed */}
                </div>
            )}

            {briefing.overall_summary_notes && (
                <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded">
                    <h3 className="text-md font-medium text-green-700">Overall Summary:</h3>
                    <p className="text-sm text-green-600 whitespace-pre-wrap">{briefing.overall_summary_notes}</p>
                </div>
            )}

            {briefing.results_by_source && briefing.results_by_source.length > 0 && (
                <div className="mb-2">
                    <h3 className="text-md font-medium text-gray-700 mb-1">Information Found:</h3>
                    {briefing.results_by_source.map((sourceEntry, index) => (
                        <div key={index} className="mb-3 pl-2 border-l-4 border-gray-300">
                            <h4 className="text-sm font-semibold text-gray-600">
                                From {sourceEntry.source} ({sourceEntry.count} item(s))
                            </h4>
                            {sourceEntry.error_message && (
                                <p className="text-xs text-red-500">Error: {sourceEntry.error_message}</p>
                            )}
                            <div className="mt-1 max-h-60 overflow-y-auto pr-2"> {/* Scrollable area for results */}
                                {sourceEntry.results.map((item, itemIndex) => {
                                    switch (sourceEntry.source) {
                                        case 'gmail':
                                            return <GmailResultItem key={itemIndex} item={item as GmailMessageSnippet} />;
                                        case 'slack':
                                            return <SlackResultItem key={itemIndex} item={item as SlackMessageSnippet} />;
                                        case 'notion':
                                            return <NotionResultItem key={itemIndex} item={item as NotionPageSummary} />;
                                        case 'calendar_events':
                                            return <RelatedCalendarEventItem key={itemIndex} item={item as CalendarEventSummary} />;
                                        default:
                                            return <p key={itemIndex} className="text-xs">Unsupported item type</p>;
                                    }
                                })}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {briefing.errors_encountered && briefing.errors_encountered.length > 0 && (
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded">
                    <h3 className="text-md font-medium text-red-700">Errors Encountered:</h3>
                    <ul className="list-disc list-inside pl-2">
                        {briefing.errors_encountered.map((error, index) => (
                            <li key={index} className="text-xs text-red-600">
                                Source: {error.source_attempted || 'Overall'} - {error.message}
                                {error.details && <span className="block text-xxs text-red-400 truncate">Details: {error.details}</span>}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

export default MeetingPrepDisplay;
