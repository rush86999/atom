/**
 * Pull-to-refresh hook for FlatList/ScrollView refreshControl props.
 *
 * Manages the refreshing state and renders a RefreshControl wired to the
 * provided onRefresh callback.
 */

import { useCallback, useRef, useState } from 'react';
import { RefreshControl } from 'react-native';

interface UseRefreshControlOptions {
  onRefresh: () => void | Promise<void>;
  colors?: string[];
}

export const useRefreshControl = ({ onRefresh, colors }: UseRefreshControlOptions) => {
  const [refreshing, setRefreshing] = useState(false);
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await onRefreshRef.current();
    } finally {
      setRefreshing(false);
    }
  }, []);

  const refreshControl = (
    <RefreshControl
      refreshing={refreshing}
      onRefresh={handleRefresh}
      colors={colors || ['#2196F3']}
    />
  );

  return { refreshControl, refreshing };
};
