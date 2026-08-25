import React from "react";
import AuditTrailExplorer from "../../components/Audit/AuditTrailExplorer";

const AuditTrailPage = () => {
    return (
        <div className="h-[calc(100vh-2rem)] w-full bg-background overflow-hidden rounded-lg border border-border shadow-sm flex flex-col p-4">
            <AuditTrailExplorer />
        </div>
    );
};

export default AuditTrailPage;
