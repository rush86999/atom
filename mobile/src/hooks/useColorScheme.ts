/**
 * Color scheme hook.
 *
 * Round 82: App.tsx imported './src/hooks/useColorScheme' but the hooks
 * directory did not exist (phantom import broke bundling). This restores the
 * hook as a thin re-export of React Native's own.
 */

import { useColorScheme as useRNColorScheme } from 'react-native';

export function useColorScheme(): string | null | undefined {
  return useRNColorScheme();
}

export default useColorScheme;
