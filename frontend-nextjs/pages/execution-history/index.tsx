import React from "react";
import AgentHistoryTable from "../../components/Agents/AgentHistoryTable";

const ExecutionHistoryPage = () => {
    return (
        <div className="h-[calc(100vh-2rem)] w-full bg-background overflow-hidden rounded-lg border border-border shadow-sm flex flex-col p-4">
            <AgentHistoryTable />
        </div>
    );
};

export default ExecutionHistoryPage;
