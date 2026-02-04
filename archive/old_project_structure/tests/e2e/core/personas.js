"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAllPersonas = exports.getPersona = exports.personas = void 0;
exports.personas = {
  alex: {
    id: "alex-chen",
    name: "Alex Chen",
    email: "alex.chen@example.com",
    characteristics: [
      "growth-minded professional",
      "data-driven decision maker",
      "focuses on productivity metrics",
      "collaborative team leader",
    ],
    goals: [
      "increase personal productivity by 30%",
      "automate repetitive tasks",
      "better team collaboration",
      "data-driven insights for meetings",
    ],
    integrations: ["notion", "toggl", "google-calendar", "github"],
  },
  maria: {
    id: "maria-garcia",
    name: "Maria Garcia",
    email: "maria.garcia@example.com",
    characteristics: [
      "busy parent with career",
      "values family time",
      "efficiency-focused",
      "organized and systematic",
      "health-conscious",
    ],
    goals: [
      "work-life balance",
      "schedule optimization",
      "family coordination",
      "stress reduction",
    ],
    integrations: ["google-calendar", "todoist", "fitbit", "monzo"],
  },
  ben: {
    id: "ben-williams",
    name: "Ben Williams",
    email: "ben.williams@example.com",
    characteristics: [
      "creative professional",
      "startup founder",
      "collaborative networker",
      "innovation focused",
    ],
    goals: [
      "startup growth",
      "team productivity",
      "investor relationship management",
      "creative project management",
    ],
    integrations: ["linkedin", "asana", "zoom", "figma"],
  },
};
const getPersona = (name) => {
  const normalizedName = name.toLowerCase();
  if (!exports.personas[normalizedName]) {
    throw new Error(
      `Unknown persona: ${name}. Available: ${Object.keys(exports.personas).join(", ")}`,
    );
  }
  return exports.personas[normalizedName];
};
exports.getPersona = getPersona;
const getAllPersonas = () => {
  return Object.values(exports.personas);
};
exports.getAllPersonas = getAllPersonas;
//# sourceMappingURL=personas.js.map
