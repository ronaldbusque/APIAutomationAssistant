import React from 'react';
import { AppProvider } from './context/AppContext';
import Layout from './components/Layout';

const App: React.FC = () => {
  return (
    <AppProvider>
      <Layout />
    </AppProvider>
  );
};

export default App; 