"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const config_json_1 = __importDefault(require("@config/config.json"));
const menu_json_1 = __importDefault(require("@config/menu.json"));
const router_1 = require("next/router");
const react_1 = require("react");
const Header = () => {
    //router
    const router = (0, router_1.useRouter)();
    // distructuring the main menu from menu object
    const { main } = menu_json_1.default;
    // states declaration
    const [navOpen, setNavOpen] = (0, react_1.useState)(false);
    // logo source
    const { logo } = config_json_1.default.site;
    const { enable, link } = config_json_1.default.nav_button;
    return ((0, jsx_runtime_1.jsx)("header", { className: "", children: (0, jsx_runtime_1.jsx)("nav", { className: "" }) }));
};
exports.default = Header;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiSGVhZGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiSGVhZGVyLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFDQSxzRUFBeUM7QUFDekMsa0VBQXFDO0FBRXJDLHdDQUF3QztBQUN4QyxpQ0FBd0M7QUFHeEMsTUFBTSxNQUFNLEdBQUcsR0FBRyxFQUFFO0lBQ2xCLFFBQVE7SUFDUixNQUFNLE1BQU0sR0FBRyxJQUFBLGtCQUFTLEdBQUUsQ0FBQztJQUUzQiwrQ0FBK0M7SUFDL0MsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLG1CQUFXLENBQUM7SUFFN0IscUJBQXFCO0lBQ3JCLE1BQU0sQ0FBQyxPQUFPLEVBQUUsVUFBVSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEtBQUssQ0FBQyxDQUFDO0lBRTlDLGNBQWM7SUFDZCxNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcscUJBQU0sQ0FBQyxJQUFJLENBQUM7SUFDN0IsTUFBTSxFQUFFLE1BQU0sRUFBRSxJQUFJLEVBQUUsR0FBRyxxQkFBTSxDQUFDLFVBQVUsQ0FBQztJQUUzQyxPQUFPLENBQ0wsbUNBQVEsU0FBUyxFQUFDLEVBQUUsWUFDbEIsZ0NBQUssU0FBUyxFQUFDLEVBQUUsR0FDWCxHQUNDLENBQ1YsQ0FBQztBQUNKLENBQUMsQ0FBQztBQUVGLGtCQUFlLE1BQU0sQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBMb2dvIGZyb20gXCJAY29tcG9uZW50cy9Mb2dvXCI7XG5pbXBvcnQgY29uZmlnIGZyb20gXCJAY29uZmlnL2NvbmZpZy5qc29uXCI7XG5pbXBvcnQgbWVudSBmcm9tIFwiQGNvbmZpZy9tZW51Lmpzb25cIjtcbmltcG9ydCBMaW5rIGZyb20gXCJuZXh0L2xpbmtcIjtcbmltcG9ydCB7IHVzZVJvdXRlciB9IGZyb20gXCJuZXh0L3JvdXRlclwiO1xuaW1wb3J0IFJlYWN0LCB7IHVzZVN0YXRlIH0gZnJvbSBcInJlYWN0XCI7XG5pbXBvcnQgeyB0eXBlIFVybE9iamVjdCB9IGZyb20gXCJ1cmxcIjtcblxuY29uc3QgSGVhZGVyID0gKCkgPT4ge1xuICAvL3JvdXRlclxuICBjb25zdCByb3V0ZXIgPSB1c2VSb3V0ZXIoKTtcblxuICAvLyBkaXN0cnVjdHVyaW5nIHRoZSBtYWluIG1lbnUgZnJvbSBtZW51IG9iamVjdFxuICBjb25zdCB7IG1haW4gfSA9IG1lbnUgYXMgYW55O1xuXG4gIC8vIHN0YXRlcyBkZWNsYXJhdGlvblxuICBjb25zdCBbbmF2T3Blbiwgc2V0TmF2T3Blbl0gPSB1c2VTdGF0ZShmYWxzZSk7XG5cbiAgLy8gbG9nbyBzb3VyY2VcbiAgY29uc3QgeyBsb2dvIH0gPSBjb25maWcuc2l0ZTtcbiAgY29uc3QgeyBlbmFibGUsIGxpbmsgfSA9IGNvbmZpZy5uYXZfYnV0dG9uO1xuXG4gIHJldHVybiAoXG4gICAgPGhlYWRlciBjbGFzc05hbWU9XCJcIj5cbiAgICAgIDxuYXYgY2xhc3NOYW1lPVwiXCI+XG4gICAgICA8L25hdj5cbiAgICA8L2hlYWRlcj5cbiAgKTtcbn07XG5cbmV4cG9ydCBkZWZhdWx0IEhlYWRlcjtcbiJdfQ==