"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const Star_1 = __importDefault(require("@pages/Calendar/Rating/Star"));
const Stars = (props) => {
    return ((0, jsx_runtime_1.jsx)(jsx_runtime_1.Fragment, { children: Array.from({ length: props.maxStars || 5 }).map((_, i) => {
            return ((0, jsx_runtime_1.jsx)(Star_1.default, { size: props.starSize, distance: props.distance, offset: props.offset - i }, i));
        }) }));
};
exports.default = Stars;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiU3RhcnMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJTdGFycy50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQ0EsdUVBQThEO0FBTzlELE1BQU0sS0FBSyxHQUFHLENBQUMsS0FBa0IsRUFBRSxFQUFFO0lBQ25DLE9BQU8sQ0FDTCwyREFDRyxLQUFLLENBQUMsSUFBSSxDQUFDLEVBQUUsTUFBTSxFQUFFLEtBQUssQ0FBQyxRQUFRLElBQUksQ0FBQyxFQUFFLENBQUMsQ0FBQyxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsQ0FBQyxFQUFFLEVBQUU7WUFDeEQsT0FBTyxDQUNMLHVCQUFDLGNBQUksSUFFSCxJQUFJLEVBQUUsS0FBSyxDQUFDLFFBQVEsRUFDcEIsUUFBUSxFQUFFLEtBQUssQ0FBQyxRQUFRLEVBQ3hCLE1BQU0sRUFBRSxLQUFLLENBQUMsTUFBTSxHQUFHLENBQUMsSUFIbkIsQ0FBQyxDQUlOLENBQ0gsQ0FBQztRQUNKLENBQUMsQ0FBQyxHQUNELENBQ0osQ0FBQztBQUNKLENBQUMsQ0FBQztBQUVGLGtCQUFlLEtBQUssQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCBmcm9tICdyZWFjdCc7XG5pbXBvcnQgU3RhciwgeyBJU3RhclByb3BzIH0gZnJvbSAnQHBhZ2VzL0NhbGVuZGFyL1JhdGluZy9TdGFyJ1xuXG5pbnRlcmZhY2UgSVN0YXJzUHJvcHMgZXh0ZW5kcyBJU3RhclByb3BzIHtcbiAgbWF4U3RhcnM6IG51bWJlcjtcbiAgc3RhclNpemU6IG51bWJlcjtcbn1cblxuY29uc3QgU3RhcnMgPSAocHJvcHM6IElTdGFyc1Byb3BzKSA9PiB7XG4gIHJldHVybiAoXG4gICAgPD5cbiAgICAgIHtBcnJheS5mcm9tKHsgbGVuZ3RoOiBwcm9wcy5tYXhTdGFycyB8fCA1IH0pLm1hcCgoXywgaSkgPT4ge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxTdGFyXG4gICAgICAgICAgICBrZXk9e2l9XG4gICAgICAgICAgICBzaXplPXtwcm9wcy5zdGFyU2l6ZX1cbiAgICAgICAgICAgIGRpc3RhbmNlPXtwcm9wcy5kaXN0YW5jZX1cbiAgICAgICAgICAgIG9mZnNldD17cHJvcHMub2Zmc2V0IC0gaX1cbiAgICAgICAgICAvPlxuICAgICAgICApO1xuICAgICAgfSl9XG4gICAgPC8+XG4gICk7XG59O1xuXG5leHBvcnQgZGVmYXVsdCBTdGFycztcbiJdfQ==