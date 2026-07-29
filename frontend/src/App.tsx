import { Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import DashboardPage from './pages/DashboardPage';
import AccountsPage from './pages/AccountsPage';
import ConfigPage from './pages/ConfigPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/accounts" element={<AccountsPage />} />
        <Route path="/config" element={<ConfigPage />} />
      </Routes>
    </Layout>
  );
}
