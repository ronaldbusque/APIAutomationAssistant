import React, { useState, useEffect } from 'react';
import { useAppContext } from '../context/AppContext';

const AuthInput: React.FC = () => {
  const { state, setAccessToken } = useAppContext();
  const [localToken, setLocalToken] = useState<string>(state.accessToken || '');
  const [showFeedback, setShowFeedback] = useState<boolean>(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string>('');

  // Show feedback for 3 seconds
  const showTemporaryFeedback = (message: string) => {
    setFeedbackMessage(message);
    setShowFeedback(true);
    setTimeout(() => {
      setShowFeedback(false);
    }, 3000);
  };

  const handleSaveToken = () => {
    setAccessToken(localToken.trim());
    showTemporaryFeedback('Access token saved');
  };

  const handleClearToken = () => {
    setLocalToken('');
    setAccessToken(null);
    showTemporaryFeedback('Access token cleared');
  };

  return (
    <div className="flex flex-col sm:flex-row items-center space-y-2 sm:space-y-0 sm:space-x-2 bg-gray-50 dark:bg-gray-800 p-2 rounded-md border border-gray-200 dark:border-gray-700">
      <label htmlFor="access-token" className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
        Access Token
      </label>
      <div className="flex-grow relative">
        <input
          id="access-token"
          type="password"
          value={localToken}
          onChange={(e) => setLocalToken(e.target.value)}
          placeholder="Enter your API access token"
          className="w-full py-1 px-2 text-sm border rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        {showFeedback && (
          <div className="absolute -bottom-6 left-0 right-0 text-xs text-green-600 dark:text-green-400 mt-1">
            {feedbackMessage}
          </div>
        )}
      </div>
      <div className="flex space-x-2">
        <button
          onClick={handleSaveToken}
          disabled={!localToken}
          className="py-1 px-3 text-sm rounded-md bg-primary-600 hover:bg-primary-700 text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          Save
        </button>
        <button
          onClick={handleClearToken}
          disabled={!localToken && !state.accessToken}
          className="py-1 px-3 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
        >
          Clear
        </button>
      </div>
    </div>
  );
};

export default AuthInput; 