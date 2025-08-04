import React from "react";
export interface Article {
    id: string;
    title: string;
    content: string;
    category: "HR" | "IT" | "Engineering";
    lastUpdated: string;
}
/**
 * Internal Support Agent component for the desktop application.
 * It provides a searchable interface for a mock knowledge base.
 */
declare const Support: React.FC;
export default Support;
