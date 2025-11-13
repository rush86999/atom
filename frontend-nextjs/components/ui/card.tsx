import React from "react";

export const Card = ({ className, children, ...props }) => (
  <div className={`rounded-lg border border-gray-200 bg-white p-4 ${className || ""}`} {...props}>
    {children}
  </div>
);

export const CardHeader = ({ className, children, ...props }) => (
  <div className={`border-b border-gray-200 pb-3 mb-4 ${className || ""}`} {...props}>
    {children}
  </div>
);

export const CardTitle = ({ className, children, ...props }) => (
  <h3 className={`text-lg font-semibold ${className || ""}`} {...props}>
    {children}
  </h3>
);

export const CardContent = ({ className, children, ...props }) => (
  <div className={className || ""} {...props}>
    {children}
  </div>
);
