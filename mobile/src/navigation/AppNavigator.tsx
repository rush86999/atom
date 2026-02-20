/**
 * Mobile App Navigation Structure
 * Defines all navigation routes and tab navigation for authenticated users
 */

import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

// Screen Imports
import { WorkflowsListScreen } from '../screens/workflows/WorkflowsListScreen';
import { WorkflowDetailScreen } from '../screens/workflows/WorkflowDetailScreen';
import { WorkflowTriggerScreen } from '../screens/workflows/WorkflowTriggerScreen';
import { ExecutionProgressScreen } from '../screens/workflows/ExecutionProgressScreen';
import { WorkflowLogsScreen } from '../screens/workflows/WorkflowLogsScreen';
import { AnalyticsDashboardScreen } from '../screens/analytics/AnalyticsDashboardScreen';
import { AgentListScreen } from '../screens/agent/AgentListScreen';
import { AgentChatScreen } from '../screens/agent/AgentChatScreen';
import { ChatTabScreen } from '../screens/chat';
import { SettingsScreen } from '../screens/settings/SettingsScreen';

// Stack Navigator for Workflows
const WorkflowStack = createNativeStackNavigator();

function WorkflowStackNavigator() {
  return (
    <WorkflowStack.Navigator
      initialRouteName="WorkflowsList"
      screenOptions={{
        headerStyle: {
          backgroundColor: '#2196F3',
        },
        headerTintColor: '#fff',
        headerTitleStyle: {
          fontWeight: 'bold',
        },
      }}
    >
      <WorkflowStack.Screen
        name="WorkflowsList"
        component={WorkflowsListScreen}
        options={{
          title: 'Workflows',
          headerShown: false,
        }}
      />
      <WorkflowStack.Screen
        name="WorkflowDetail"
        component={WorkflowDetailScreen}
        options={{
          title: 'Workflow Details',
        }}
      />
      <WorkflowStack.Screen
        name="WorkflowTrigger"
        component={WorkflowTriggerScreen}
        options={{
          title: 'Trigger Workflow',
          presentation: 'modal',
        }}
      />
      <WorkflowStack.Screen
        name="ExecutionProgress"
        component={ExecutionProgressScreen}
        options={{
          title: 'Execution Progress',
        }}
      />
      <WorkflowStack.Screen
        name="WorkflowLogs"
        component={WorkflowLogsScreen}
        options={{
          title: 'Execution Logs',
        }}
      />
    </WorkflowStack.Navigator>
  );
}

// Stack Navigator for Analytics
const AnalyticsStack = createNativeStackNavigator();

function AnalyticsStackNavigator() {
  return (
    <AnalyticsStack.Navigator
      initialRouteName="AnalyticsDashboard"
      screenOptions={{
        headerStyle: {
          backgroundColor: '#2196F3',
        },
        headerTintColor: '#fff',
        headerTitleStyle: {
          fontWeight: 'bold',
        },
      }}
    >
      <AnalyticsStack.Screen
        name="AnalyticsDashboard"
        component={AnalyticsDashboardScreen}
        options={{
          title: 'Dashboard',
          headerShown: false,
        }}
      />
    </AnalyticsStack.Navigator>
  );
}

// Stack Navigator for Agents
const AgentStack = createNativeStackNavigator();

function AgentStackNavigator() {
  return (
    <AgentStack.Navigator
      initialRouteName="AgentList"
      screenOptions={{
        headerStyle: {
          backgroundColor: '#2196F3',
        },
        headerTintColor: '#fff',
        headerTitleStyle: {
          fontWeight: 'bold',
        },
      }}
    >
      <AgentStack.Screen
        name="AgentList"
        component={AgentListScreen}
        options={{
          title: 'Agents',
          headerShown: false,
        }}
      />
      <AgentStack.Screen
        name="AgentChat"
        component={AgentChatScreen}
        options={{
          title: 'Chat',
        }}
      />
    </AgentStack.Navigator>
  );
}

// Stack Navigator for Chat
const ChatStack = createNativeStackNavigator();

function ChatStackNavigator() {
  return (
    <ChatStack.Navigator
      initialRouteName="ChatTab"
      screenOptions={{
        headerStyle: {
          backgroundColor: '#2196F3',
        },
        headerTintColor: '#fff',
        headerTitleStyle: {
          fontWeight: 'bold',
        },
      }}
    >
      <ChatStack.Screen
        name="ChatTab"
        component={ChatTabScreen}
        options={{
          title: 'Chat',
          headerShown: false,
        }}
      />
      <ChatStack.Screen
        name="AgentChat"
        component={AgentChatScreen}
        options={{
          title: 'Chat',
        }}
      />
    </ChatStack.Navigator>
  );
}

// Bottom Tab Navigator
const Tab = createBottomTabNavigator();

export function AppNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused, color, size }) => {
            let iconName: string;

            if (route.name === 'WorkflowsTab') {
              iconName = focused ? 'flash' : 'flash-outline';
            } else if (route.name === 'AnalyticsTab') {
              iconName = focused ? 'stats-chart' : 'stats-chart-outline';
            } else if (route.name === 'AgentsTab') {
              iconName = focused ? 'people' : 'people-outline';
            } else if (route.name === 'ChatTab') {
              iconName = focused ? 'chatbubbles' : 'chatbubbles-outline';
            } else if (route.name === 'SettingsTab') {
              iconName = focused ? 'settings' : 'settings-outline';
            } else {
              iconName = 'ellipse';
            }

            return <Ionicons name={iconName as any} size={size} color={color} />;
          },
          tabBarActiveTintColor: '#2196F3',
          tabBarInactiveTintColor: '#999',
          tabBarStyle: {
            paddingBottom: 5,
            paddingTop: 5,
            height: 60,
          },
          tabBarLabelStyle: {
            fontSize: 12,
            fontWeight: '500',
          },
        })}
      >
        <Tab.Screen
          name="WorkflowsTab"
          component={WorkflowStackNavigator}
          options={{
            tabBarLabel: 'Workflows',
          }}
        />
        <Tab.Screen
          name="AnalyticsTab"
          component={AnalyticsStackNavigator}
          options={{
            tabBarLabel: 'Analytics',
          }}
        />
        <Tab.Screen
          name="AgentsTab"
          component={AgentStackNavigator}
          options={{
            tabBarLabel: 'Agents',
          }}
        />
        <Tab.Screen
          name="ChatTab"
          component={ChatStackNavigator}
          options={{
            tabBarLabel: 'Chat',
          }}
        />
        <Tab.Screen
          name="SettingsTab"
          component={SettingsScreen}
          options={{
            tabBarLabel: 'Settings',
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

// Export navigation types
export type RootStackParamList = {
  WorkflowsTab: undefined;
  AnalyticsTab: undefined;
  AgentsTab: undefined;
  ChatTab: undefined;
  SettingsTab: undefined;
};

export type WorkflowStackParamList = {
  WorkflowsList: undefined;
  WorkflowDetail: { workflowId: string };
  WorkflowTrigger: { workflowId: string; workflowName: string };
  ExecutionProgress: { executionId: string };
  WorkflowLogs: { executionId: string };
};

export type AnalyticsStackParamList = {
  AnalyticsDashboard: undefined;
};

export type AgentStackParamList = {
  AgentList: undefined;
  AgentChat: { agentId: string; agentName?: string };
};

export type ChatStackParamList = {
  ChatTab: undefined;
  AgentChat: { agentId: string; conversationId?: string };
};

export default AppNavigator;
