import React from "react";

const Automations = () => {
  return (
    <div style={{ padding: "20px" }}>
      <h2>Automations</h2>
      <p>
        Workflow automation features are currently available in the web version.
      </p>
      <div
        style={{
          border: "2px dashed #ccc",
          padding: "40px",
          textAlign: "center",
          borderRadius: "8px",
          marginTop: "20px",
        }}
      >
        <h3>Workflow Editor</h3>
        <p>
          This feature requires integration with the main application's workflow
          system.
        </p>
        <button
          style={{
            padding: "10px 20px",
            backgroundColor: "#007bff",
            color: "white",
            border: "none",
            borderRadius: "4px",
            marginTop: "10px",
          }}
          onClick={() =>
            window.open("http://localhost:3000/automations", "_blank")
          }
        >
          Open in Web App
        </button>
      </div>
    </div>
  );
};

export default Automations;
