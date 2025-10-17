import { Box, Divider } from '@chakra-ui/react';
import { Route, Routes } from 'react-router-dom';

import NavBar from './components/NavBar';
import LandingPage from './pages/LandingPage';
import PreflopShoveExplorer from './pages/PreflopShoveExplorer';
import OpponentCountPerformance from './pages/OpponentCountPerformance';
import PerformanceOverview from './pages/PerformanceOverview';
import PreflopResponseCurves from './pages/PreflopResponseCurves';

const App = () => (
  <Box minH="100vh" bgGradient="linear(to-b, gray.900, gray.800)">
    <NavBar />
    <Divider opacity={0.2} />
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/preflop-shove-explorer" element={<PreflopShoveExplorer />} />
      <Route path="/preflop/response-curves" element={<PreflopResponseCurves />} />
      <Route path="/performance/opponent-count" element={<OpponentCountPerformance />} />
      <Route path="/performance/overview" element={<PerformanceOverview />} />
    </Routes>
  </Box>
);

export default App;
