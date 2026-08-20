import { Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import DashboardPage from './pages/DashboardPage';
import AccountsPage from './pages/AccountsPage';
import ConfigPage from './pages/ConfigPage';
import StatisticsPage from './pages/StatisticsPage';
import FleetsPage from './pages/FleetsPage';
import HistoryPage from './pages/HistoryPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/accounts" element={<AccountsPage />} />
        <Route path="/stats" element={<StatisticsPage />} />
        <Route path="/fleets" element={<FleetsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/config" element={<ConfigPage />} />
      </Routes>
    </Layout>
  );
}
