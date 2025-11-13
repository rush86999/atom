import React, { useCallback, useMemo } from 'react';
import { FixedSizeList as List } from 'react-window';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store';

interface VirtualizedListProps<T> {
  items: T[];
  itemHeight: number;
  containerHeight: number;
  renderItem: (item: T, index: number) => React.ReactNode;
  className?: string;
  overscanCount?: number;
  onItemClick?: (item: T, index: number) => void;
  selectedIndex?: number;
  emptyMessage?: string;
  loading?: boolean;
  loadingComponent?: React.ReactNode;
}

export function VirtualizedList<T>({
  items,
  itemHeight,
  containerHeight,
  renderItem,
  className = '',
  overscanCount = 5,
  onItemClick,
  selectedIndex,
  emptyMessage = 'No items to display',
  loading = false,
  loadingComponent,
}: VirtualizedListProps<T>) {
  const { searchQuery } = useAppStore();

  // Filter items based on search query if provided
  const filteredItems = useMemo(() => {
    if (!searchQuery) return items;

    return items.filter((item, index) => {
      // If renderItem provides searchable text, we could enhance this
      // For now, assume items have a 'title' or 'name' property
      const searchableText = (item as any).title || (item as any).name || '';
      return searchableText.toLowerCase().includes(searchQuery.toLowerCase());
    });
  }, [items, searchQuery]);

  const ItemWrapper = useCallback(
    ({ index, style }: { index: number; style: React.CSSProperties }) => {
      const item = filteredItems[index];

      return (
        <motion.div
          style={style}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.2, delay: index * 0.05 }}
          className={`cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
            selectedIndex === index ? 'bg-blue-50 dark:bg-blue-900/20' : ''
          }`}
          onClick={() => onItemClick?.(item, index)}
        >
          {renderItem(item, index)}
        </motion.div>
      );
    },
    [filteredItems, renderItem, onItemClick, selectedIndex]
  );

  if (loading) {
    return (
      <div
        className={`flex items-center justify-center ${className}`}
        style={{ height: containerHeight }}
      >
        {loadingComponent || (
          <div className="flex items-center space-x-2">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
            <span className="text-gray-500 dark:text-gray-400">Loading...</span>
          </div>
        )}
      </div>
    );
  }

  if (filteredItems.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-gray-500 dark:text-gray-400 ${className}`}
        style={{ height: containerHeight }}
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={className}>
      <List
        height={containerHeight}
        itemCount={filteredItems.length}
        itemSize={itemHeight}
        overscanCount={overscanCount}
        className="scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600 scrollbar-track-transparent"
      >
        {ItemWrapper}
      </List>
    </div>
  );
}

// Specialized virtualized components for common use cases
export const VirtualizedTaskList: React.FC<{
  tasks: any[];
  onTaskClick?: (task: any, index: number) => void;
  selectedTaskId?: string;
  containerHeight?: number;
}> = ({ tasks, onTaskClick, selectedTaskId, containerHeight = 400 }) => {
  return (
    <VirtualizedList
      items={tasks}
      itemHeight={80}
      containerHeight={containerHeight}
      renderItem={(task, index) => (
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={task.status === 'completed'}
                onChange={() => {}} // Handle in parent
                className="rounded"
              />
              <div>
                <h4 className={`font-medium ${task.status === 'completed' ? 'line-through text-gray-500' : ''}`}>
                  {task.title}
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Due: {new Date(task.dueDate).toLocaleDateString()}
                </p>
              </div>
            </div>
            <span className={`px-2 py-1 text-xs rounded-full ${
              task.priority === 'high' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
              task.priority === 'medium' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
              'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
            }`}>
              {task.priority}
            </span>
          </div>
        </div>
      )}
      onItemClick={onTaskClick}
      selectedIndex={tasks.findIndex(task => task.id === selectedTaskId)}
      emptyMessage="No tasks found"
    />
  );
};

export const VirtualizedMessageList: React.FC<{
  messages: any[];
  onMessageClick?: (message: any, index: number) => void;
  selectedMessageId?: string;
  containerHeight?: number;
}> = ({ messages, onMessageClick, selectedMessageId, containerHeight = 400 }) => {
  return (
    <VirtualizedList
      items={messages}
      itemHeight={100}
      containerHeight={containerHeight}
      renderItem={(message, index) => (
        <div className={`p-4 border-b border-gray-200 dark:border-gray-700 ${message.unread ? 'bg-blue-50 dark:bg-blue-900/10' : ''}`}>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-2">
                <h4 className="font-medium">{message.from.name}</h4>
                {message.unread && (
                  <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                )}
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-white mt-1">
                {message.subject}
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                {message.preview}
              </p>
            </div>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {new Date(message.timestamp).toLocaleDateString()}
            </span>
          </div>
        </div>
      )}
      onItemClick={onMessageClick}
      selectedIndex={messages.findIndex(message => message.id === selectedMessageId)}
      emptyMessage="No messages found"
    />
  );
};

export const VirtualizedAgentList: React.FC<{
  agents: any[];
  onAgentClick?: (agent: any, index: number) => void;
  selectedAgentId?: string;
  containerHeight?: number;
}> = ({ agents, onAgentClick, selectedAgentId, containerHeight = 400 }) => {
  return (
    <VirtualizedList
      items={agents}
      itemHeight={120}
      containerHeight={containerHeight}
      renderItem={(agent, index) => (
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className={`w-3 h-3 rounded-full ${
                agent.status === 'online' ? 'bg-green-500' :
                agent.status === 'busy' ? 'bg-yellow-500' : 'bg-gray-500'
              }`}></div>
              <div>
                <h4 className="font-medium">{agent.name}</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">{agent.role}</p>
                <div className="flex items-center space-x-4 mt-2">
                  <span className="text-xs text-gray-500">
                    Tasks: {agent.performance.tasksCompleted}
                  </span>
                  <span className="text-xs text-gray-500">
                    Success: {agent.performance.successRate}%
                  </span>
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium">
                {agent.performance.avgResponseTime}ms
              </div>
              <div className="text-xs text-gray-500">avg response</div>
            </div>
          </div>
        </div>
      )}
      onItemClick={onAgentClick}
      selectedIndex={agents.findIndex(agent => agent.id === selectedAgentId)}
      emptyMessage="No agents found"
    />
  );
};
