import React, { useState } from 'react';
import { AppProvider } from './context/AppContext';
import Layout from './components/Layout';
import ApiTest from './components/ApiTest';

const App: React.FC = () => {
  const [showApiTest, setShowApiTest] = useState(false);

  return (
    <AppProvider>
      <Layout>
        <div className="mt-4 flex justify-end">
          <button
            onClick={() => setShowApiTest(!showApiTest)}
            className="text-sm px-3 py-1 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded border border-blue-300 flex items-center"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            {showApiTest ? 'Hide API Test' : 'Debug: Test API Connection'}
          </button>
        </div>
        
        {showApiTest && (
          <div className="mt-4">
            <ApiTest />
          </div>
        )}
      </Layout>
    </AppProvider>
  );
};

export default App; 