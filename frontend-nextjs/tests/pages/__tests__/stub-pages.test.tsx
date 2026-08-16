import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import VoicePage from "@/pages/voice";
import TasksPage from "@/pages/tasks";
import CalendarPage from "@/pages/calendar";
import CommunicationPage from "@/pages/communication";
import Scheduling from "@/pages/scheduling";
import SystemStatusPage from "@/pages/system-status";
import TeamChatPage from "@/pages/team-chat";
import GoogleDrivePage from "@/pages/google-drive";
import OneDrivePage from "@/pages/onedrive";

jest.mock("next/head", () => {
  return function Head({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
  };
});

jest.mock("@/components/Voice/WakeWordDetector", () => {
  return function MockWakeWordDetector(props: any) {
    return (
      <button
        data-testid="wakeword"
        onClick={() => props.onDetection?.({ word: "atom" })}
      >
        Mock Wake Word
      </button>
    );
  };
});

jest.mock("@/components/Voice/VoiceCommands", () => {
  return function MockVoiceCommands(props: any) {
    return (
      <button
        data-testid="voice-commands"
        onClick={() => {
          props.onCommandRecognized?.("hello");
          props.onCommandExecute?.("open", { target: "tasks" });
        }}
      >
        Mock Voice Commands
      </button>
    );
  };
});

jest.mock("@/components/TaskManagement", () => {
  return function MockTaskManagement() {
    return <div data-testid="mock-tasks">Task Management</div>;
  };
});

jest.mock("@/components/CalendarManagement", () => {
  return function MockCalendarManagement() {
    return <div data-testid="mock-calendar">Calendar Management</div>;
  };
});

jest.mock("@/components/dashboards/CommunicationCommandCenter", () => {
  return function MockCommunication() {
    return <div data-testid="mock-communication">Communication Center</div>;
  };
});

jest.mock("@/components/Calendar/CalendarView", () => {
  return function MockCalendarView() {
    return <div data-testid="mock-calendar-view">Calendar View</div>;
  };
});

jest.mock("@/components/SystemStatusDashboard", () => {
  return function MockSystemStatus() {
    return <div data-testid="mock-system-status">System Status</div>;
  };
});

jest.mock("@/components/integrations/GoogleDriveIntegration", () => {
  return function MockGoogleDrive() {
    return <div data-testid="mock-google-drive">Google Drive</div>;
  };
});

jest.mock("@/components/integrations/OneDriveIntegration", () => {
  return function MockOneDrive() {
    return <div data-testid="mock-onedrive">OneDrive</div>;
  };
});

describe("stub pages", () => {
  it("renders the voice page with all three tabs", () => {
    render(<VoicePage />);
    expect(
      screen.getByRole("heading", { name: "Voice & AI Features" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI Chat" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Voice Commands" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Wake Word Detection" }),
    ).toBeInTheDocument();
    expect(screen.getByText("AI Chat is now Global!")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Voice Commands" }));
    expect(screen.getByTestId("voice-commands")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("voice-commands"));
    expect(screen.getByText("Mock Voice Commands")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Wake Word Detection" }),
    );
    expect(screen.getByTestId("wakeword")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("wakeword"));
  });

  it("renders the tasks page with the task management child", () => {
    render(<TasksPage />);
    expect(screen.getByTestId("new-task-btn")).toBeInTheDocument();
    expect(screen.getByTestId("mock-tasks")).toBeInTheDocument();
  });

  it("renders the calendar page with the calendar management child", () => {
    render(<CalendarPage />);
    expect(screen.getByTestId("calendar-view")).toBeInTheDocument();
    expect(screen.getByTestId("mock-calendar")).toBeInTheDocument();
  });

  it("renders the communication page", () => {
    render(<CommunicationPage />);
    expect(screen.getByTestId("mock-communication")).toBeInTheDocument();
  });

  it("renders the scheduling page", () => {
    render(<Scheduling />);
    expect(screen.getByTestId("mock-calendar-view")).toBeInTheDocument();
  });

  it("renders the system-status page", () => {
    render(<SystemStatusPage />);
    expect(screen.getByTestId("mock-system-status")).toBeInTheDocument();
  });

  it("renders the team-chat maintenance page", () => {
    render(<TeamChatPage />);
    expect(
      screen.getByRole("heading", { name: "Team Chat" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("This feature is currently under maintenance."),
    ).toBeInTheDocument();
  });

  it("renders the google-drive page with title and child", () => {
    render(<GoogleDrivePage />);
    expect(
      screen.getByRole("heading", { name: /Google Drive Integration/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("mock-google-drive")).toBeInTheDocument();
  });

  it("renders the onedrive page with title and child", () => {
    render(<OneDrivePage />);
    expect(
      screen.getByRole("heading", { name: /OneDrive Integration/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("mock-onedrive")).toBeInTheDocument();
  });
});
