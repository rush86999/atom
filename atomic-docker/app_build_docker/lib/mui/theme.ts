import { createTheme } from '@mui/material/styles';
import { red } from '@mui/material/colors';
import { palette } from '@lib/theme/theme';

// Create a theme instance.
const theme = createTheme({
  palette: {
    primary: {
      main: palette.purplePrimary,
    },
    secondary: {
      main: palette.pinkPrimary,
    },
    error: {
      main: red.A400,
    },
  },
});

export default theme;
