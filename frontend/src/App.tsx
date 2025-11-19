import { Box, Divider } from '@chakra-ui/react';
import { Route, Routes } from 'react-router-dom';

import NavBar from './components/NavBar';
import LandingPage from './pages/LandingPage';
import ActionQuickReference from './pages/ActionQuickReference';
import PreflopShoveExplorer from './pages/PreflopShoveExplorer';
import OpponentCountPerformance from './pages/OpponentCountPerformance';
import PerformanceOverview from './pages/PerformanceOverview';
import PreflopResponseCurves from './pages/PreflopResponseCurves';
import FlopResponseMatrix from './pages/FlopResponseMatrix';
import LineExplorer from './pages/LineExplorer';
import TurnResponseMatrix from './pages/TurnResponseMatrix';
import RiverResponseMatrix from './pages/RiverResponseMatrix';
import { DataSourceProvider } from './hooks/useActiveDataSource';

const App = () => (
  <DataSourceProvider>
    <Box minH="100vh" bgGradient="linear(to-b, gray.900, gray.800)">
      <Box
        position="sticky"
        top={0}
        zIndex="sticky"
        bgGradient="linear(to-b, gray.900, gray.800)"
      >
        <NavBar />
        <Divider opacity={0.2} />
      </Box>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/actions/quick-reference" element={<ActionQuickReference />} />
        <Route path="/flop/response-matrix" element={<FlopResponseMatrix />} />
        <Route path="/turn/response-matrix" element={<TurnResponseMatrix />} />
        <Route path="/river/response-matrix" element={<RiverResponseMatrix />} />
        <Route path="/preflop-shove-explorer" element={<PreflopShoveExplorer />} />
        <Route path="/preflop/response-curves" element={<PreflopResponseCurves />} />
        <Route path="/performance/opponent-count" element={<OpponentCountPerformance />} />
        <Route path="/performance/overview" element={<PerformanceOverview />} />
        <Route path="/lines/explorer" element={<LineExplorer />} />
      </Routes>
    </Box>
  </DataSourceProvider>
);

export default App;
