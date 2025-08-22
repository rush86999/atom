import { useState, useCallback } from "react";

export interface FinanceSuggestion {
  id: string;
  text: string;
  category: string;
  relevance: number;
}

export function useFinanceAgent() {
  const [suggestions, setSuggestions] = useState<FinanceSuggestion[]>([]);

  const generateSuggestions = useCallback((input: string) => {
    const filtered = [
      {
        id: "1",
        text: "What is my net worth?",
        category: "net-worth",
        relevance: 0.9,
      },
      { id: "2", text: "Show my budget", category: "budget", relevance: 0.8 },
      {
        id: "3",
        text: "Where did I spend money?",
        category: "spending",
        relevance: 0.7,
      },
      {
        id: "4",
        text: "Create a savings goal",
        category: "goals",
        relevance: 0.6,
      },
      {
        id: "5",
        text: "Portfolio overview",
        category: "investments",
        relevance: 0.5,
      },
      {
        id: "6",
        text: "Financial recommendations",
        category: "recommendations",
        relevance: 0.4,
      },
    ].filter(
      (suggestion) =>
        suggestion.text.toLowerCase().includes(input.toLowerCase()) ||
        suggestion.category.toLowerCase().includes(input.toLowerCase()),
    );

    setSuggestions(filtered);
  }, []);

  const getPopularCommands = useCallback(() => {
    return [
      "net worth",
      "budget",
      "spending",
      "goals",
      "investments",
      "recommendations",
    ];
  }, []);

  return {
    suggestions,
    generateSuggestions,
    getPopularCommands,
    allSuggestions: [
      "What is my net worth?",
      "Show my budget",
      "Where did I spend money?",
      "Create a savings goal",
      "Portfolio overview",
    ],
  };
}

// Hook for tracking finance-related events
export function useFinanceEvents() {
  const [events, setEvents] = useState<
    Array<{
      type: string;
      message: string;
      timestamp: Date;
    }>
  >([]);

  const addEvent = useCallback((type: string, message: string) => {
    const newEvent = {
      type,
      message,
      timestamp: new Date(),
    };
    setEvents((prev) => [...prev, newEvent]);
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return {
    events,
    addEvent,
    clearEvents,
  };
}
