/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./src/App";

const container = document.getElementById("app-container");
if (container) {
  const root = createRoot(container);
  root.render(<App />);
}
