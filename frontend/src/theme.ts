import { extendTheme, ThemeConfig } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'dark',
  useSystemColorMode: false,
};

const theme = extendTheme({
  config,
  colors: {
    brand: {
      50: '#dcefff',
      100: '#add5f5',
      200: '#7fbce8',
      300: '#52a2db',
      400: '#2689cf',
      500: '#0b6fb6',
      600: '#085891',
      700: '#05416b',
      800: '#032a46',
      900: '#011320',
    },
  },
  fonts: {
    heading: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif',
    body: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif',
  },
  components: {
    Button: {
      defaultProps: {
        colorScheme: 'brand',
      },
    },
  },
});

export default theme;
