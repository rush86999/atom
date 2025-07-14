import React from 'react';
import { DailyBriefingData, BriefingItem } from '@lib/dataTypes/Messaging/MessagingTypes'; // Adjust path as needed
import { cn } from '@lib/Chat/utils';
import { Button } from '../ui/button'; // Assuming a generic Button component is available
import { IconArrowRight, IconCalendar, IconCheck, IconMail, IconMessage, IconMessage2 } from '../ui/icons'; // Assuming icons are available

const getIconForType = (type: BriefingItem['type']) => {
  const iconProps = { className: "mr-2 h-4 w-4" };
  switch (type) {
    case 'meeting':
      return <IconCalendar {...iconProps} />;
    case 'task':
      return <IconCheck {...iconProps} />;
    case 'email':
      return <IconMail {...iconProps} />;
    case 'slack_message':
      return <IconMessage {...iconProps} />; // Assuming IconMessage for Slack
    case 'teams_message':
      return <IconMessage2 {...iconProps} />; // Assuming IconMessage2 for Teams
    default:
      return null;
  }
};

const getButtonTextForType = (type: BriefingItem['type']): string => {
    switch (type) {
        case 'meeting': return "View Event";
        case 'task': return "Open Task";
        case 'email': return "View Email";
        case 'slack_message': return "View Message";
        case 'teams_message': return "View Message";
        default: return "Open Link";
    }
};

const BriefingItemCard: React.FC<{ item: BriefingItem }> = ({ item }) => {
  const icon = getIconForType(item.type);
  const buttonText = getButtonTextForType(item.type);

  return (
    <div className={cn(
      "p-3 mb-3 border rounded-lg shadow-sm transition-shadow hover:shadow-md",
      "bg-white dark:bg-gray-800",
      "border-gray-200 dark:border-gray-700"
    )}>
      <div className="flex items-center mb-1">
        {icon}
        <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-100">{item.title}</h4>
      </div>
      <p className="text-xs text-gray-600 dark:text-gray-400 pl-6 mb-2">{item.details}</p>

      {item.link && (
        <div className="pl-6 mt-2">
            <a
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                    buttonVariants({ variant: 'outline', size: 'sm' }),
                    "h-8 text-xs"
                )}
            >
                {buttonText} <IconArrowRight className="ml-1 h-3 w-3" />
            </a>
        </div>
      )}
    </div>
  );
};


const DailyBriefingDisplay: React.FC<{ briefing: DailyBriefingData }> = ({ briefing }) => {
  if (!briefing) {
    return <div className="p-3 text-sm text-gray-600 dark:text-gray-400 font-sans">No briefing data available.</div>;
  }

  return (
    <div className={cn(
      "p-4 my-2 rounded-lg shadow font-sans",
      "bg-gray-50 dark:bg-gray-800/50",
      "border border-gray-200 dark:border-gray-700"
    )}>
      {briefing.overall_summary_message && (
        <p className="text-sm text-gray-800 dark:text-gray-200 mb-4 whitespace-pre-wrap">
          {briefing.overall_summary_message}
        </p>
      )}

      <div className="max-h-96 overflow-y-auto custom-scrollbar pr-2">
        {briefing.priority_items.length > 0 ? (
          briefing.priority_items.map((item, index) => (
            <BriefingItemCard key={item.source_id || `item-${index}`} item={item} />
          ))
        ) : (
          <p className="text-sm text-gray-500 dark:text-gray-400">You have no priority items for this day.</p>
        )}
      </div>

      {briefing.errors_encountered && briefing.errors_encountered.length > 0 && (
        <div className="mt-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/50">
           <h4 className="text-sm font-semibold mb-1 text-red-800 dark:text-red-200">Data Retrieval Issues</h4>
           <ul className="list-disc list-inside pl-2 space-y-1">
                {briefing.errors_encountered.map((error, index) => (
                    <li key={index} className="text-xs text-red-700 dark:text-red-300">
                        <span className="font-medium">{error.source_area}:</span> {error.message}
                    </li>
                ))}
            </ul>
        </div>
      )}
    </div>
  );
};

export default DailyBriefingDisplay;
