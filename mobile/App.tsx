/**
 * Atom Mobile App - Root Component
 *
 * Main entry point for the React Native mobile application.
 * Sets up navigation, state providers, and global styles.
 */

import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { PaperProvider, MD3DarkTheme, MD3LightTheme } from 'react-native-paper';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { AppNavigator } from './src/navigation/AppNavigator';
import { AuthProvider } from './src/contexts/AuthContext';
import { WebSocketProvider } from './src/contexts/WebSocketContext';
import { useColorScheme } from './src/hooks/useColorScheme';

export default function App() {
  const colorScheme = useColorScheme();
  const theme = colorScheme === 'dark' ? MD3DarkTheme : MD3LightTheme;

  // Customize theme
  const customTheme = {
    ...theme,
    colors: {
      ...theme.colors,
      primary: '#6366f1',
      secondary: '#8b5cf6',
      tertiary: '#ec4899',
    },
  };

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <PaperProvider theme={customTheme}>
          <AuthProvider>
            <WebSocketProvider>
              <NavigationContainer>
                <AppNavigator />
                <StatusBar style="auto" />
              </NavigationContainer>
            </WebSocketProvider>
          </AuthProvider>
        </PaperProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
