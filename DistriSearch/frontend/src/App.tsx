import { Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout';
import {
  Dashboard,
  SearchPage,
  Documents,
  Cluster,
  Monitoring,
  Settings,
} from './pages';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="documents" element={<Documents />} />
          <Route path="documents/:id" element={<Documents />} />
          <Route path="cluster" element={<Cluster />} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </QueryClientProvider>
  );
}

export default App;
