"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const styles_1 = require("@mui/material/styles");
const colors_1 = require("@mui/material/colors");
const theme_1 = require("@lib/theme/theme");
// Create a theme instance.
const theme = (0, styles_1.createTheme)({
    palette: {
        primary: {
            main: theme_1.palette.purplePrimary,
        },
        secondary: {
            main: theme_1.palette.pinkPrimary,
        },
        error: {
            main: colors_1.red.A400,
        },
    },
});
exports.default = theme;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGhlbWUuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ0aGVtZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLGlEQUFtRDtBQUNuRCxpREFBMkM7QUFDM0MsNENBQTJDO0FBRTNDLDJCQUEyQjtBQUMzQixNQUFNLEtBQUssR0FBRyxJQUFBLG9CQUFXLEVBQUM7SUFDeEIsT0FBTyxFQUFFO1FBQ1AsT0FBTyxFQUFFO1lBQ1AsSUFBSSxFQUFFLGVBQU8sQ0FBQyxhQUFhO1NBQzVCO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLGVBQU8sQ0FBQyxXQUFXO1NBQzFCO1FBQ0QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLFlBQUcsQ0FBQyxJQUFJO1NBQ2Y7S0FDRjtDQUNGLENBQUMsQ0FBQztBQUVILGtCQUFlLEtBQUssQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGNyZWF0ZVRoZW1lIH0gZnJvbSAnQG11aS9tYXRlcmlhbC9zdHlsZXMnO1xuaW1wb3J0IHsgcmVkIH0gZnJvbSAnQG11aS9tYXRlcmlhbC9jb2xvcnMnO1xuaW1wb3J0IHsgcGFsZXR0ZSB9IGZyb20gJ0BsaWIvdGhlbWUvdGhlbWUnO1xuXG4vLyBDcmVhdGUgYSB0aGVtZSBpbnN0YW5jZS5cbmNvbnN0IHRoZW1lID0gY3JlYXRlVGhlbWUoe1xuICBwYWxldHRlOiB7XG4gICAgcHJpbWFyeToge1xuICAgICAgbWFpbjogcGFsZXR0ZS5wdXJwbGVQcmltYXJ5LFxuICAgIH0sXG4gICAgc2Vjb25kYXJ5OiB7XG4gICAgICBtYWluOiBwYWxldHRlLnBpbmtQcmltYXJ5LFxuICAgIH0sXG4gICAgZXJyb3I6IHtcbiAgICAgIG1haW46IHJlZC5BNDAwLFxuICAgIH0sXG4gIH0sXG59KTtcblxuZXhwb3J0IGRlZmF1bHQgdGhlbWU7XG4iXX0=