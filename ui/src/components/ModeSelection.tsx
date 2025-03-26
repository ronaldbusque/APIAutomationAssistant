import React, { useState } from 'react';
import { useAppContext } from '../context/AppContext';
import { useGenerateBlueprint } from '../hooks/useApi';

interface Props {
  onBack: () => void;
  onNext: () => void;
}

const ModeSelection: React.FC<Props> = ({ onBack, onNext }) => {
  const { 
    state,
    setMode,
    setBusinessRules,
    setTestData,
    setTestFlow,
    setBlueprintJobId
  } = useAppContext();
  
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const generateBlueprintMutation = useGenerateBlueprint();
  
  const handleModeChange = (mode: 'basic' | 'advanced') => {
    setMode(mode);
  };
  
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    
    try {
      // Build request based on mode
      const request = {
        spec: state.openApiSpec,
        mode: state.mode as 'basic' | 'advanced',
      };
      
      if (state.mode === 'advanced') {
        Object.assign(request, {
          business_rules: state.businessRules || undefined,
          test_data: state.testData || undefined,
          test_flow: state.testFlow || undefined
        });
      }
      
      // Generate blueprint
      const result = await generateBlueprintMutation.mutateAsync(request);
      
      // Store job ID for status polling
      setBlueprintJobId(result.job_id);
      
      // Move to next step
      onNext();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate blueprint');
      setIsGenerating(false);
    }
  };
  
  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Blueprint Generation Settings</h2>
      
      {/* Mode Selection */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
          Select Generation Mode
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            type="button"
            onClick={() => handleModeChange('basic')}
            className={`block w-full text-left p-4 rounded-lg border transition-colors ${
              state.mode === 'basic'
                ? 'bg-primary-50 dark:bg-gray-700 border-primary-500 dark:border-primary-400 ring-1 ring-primary-500 dark:ring-primary-400'
                : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
            }`}
          >
            <div className="font-semibold text-gray-900 dark:text-white">Basic Mode</div>
            <div className="text-sm mt-1 text-gray-600 dark:text-gray-400">
              Focus on endpoint contracts, status codes, and schema validation.
            </div>
          </button>
          
          <button
            type="button"
            onClick={() => handleModeChange('advanced')}
            className={`block w-full text-left p-4 rounded-lg border transition-colors ${
              state.mode === 'advanced'
                ? 'bg-primary-50 dark:bg-gray-700 border-primary-500 dark:border-primary-400 ring-1 ring-primary-500 dark:ring-primary-400'
                : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
            }`}
          >
            <div className="font-semibold text-gray-900 dark:text-white">Advanced Mode</div>
            <div className="text-sm mt-1 text-gray-600 dark:text-gray-400">
              Includes business rules, test data, and test flow configuration.
            </div>
          </button>
        </div>
      </div>
      
      {/* Advanced Options */}
      {state.mode === 'advanced' && (
        <div className="border border-gray-300 dark:border-gray-600 rounded-lg p-5 space-y-5 bg-white dark:bg-gray-800 shadow-sm animate-fade-in">
          <h3 className="font-medium text-base text-gray-900 dark:text-white mb-2">
            Advanced Configuration
          </h3>
          
          <div>
            <label htmlFor="business-rules" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Business Rules
            </label>
            <textarea
              id="business-rules"
              value={state.businessRules}
              onChange={(e) => setBusinessRules(e.target.value)}
              placeholder="e.g., Invalid tokens must return 401"
              className="w-full h-24 p-2 rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-primary-500 focus:border-primary-500"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Describe business rules that should be validated through testing.
            </p>
          </div>
          
          <div>
            <label htmlFor="test-data" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Test Data Setup <span className="text-xs text-gray-500 dark:text-gray-400">(Optional)</span>
            </label>
            <textarea
              id="test-data"
              value={state.testData}
              onChange={(e) => setTestData(e.target.value)}
              placeholder="e.g., POST /users to create a resource"
              className="w-full h-24 p-2 rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-primary-500 focus:border-primary-500"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              If left empty, the test planner will automatically create appropriate test data based on the API specification.
            </p>
          </div>
          
          <div>
            <label htmlFor="test-flow" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Test Flow <span className="text-xs text-gray-500 dark:text-gray-400">(Optional)</span>
            </label>
            <textarea
              id="test-flow"
              value={state.testFlow}
              onChange={(e) => setTestFlow(e.target.value)}
              placeholder="e.g., Create -> Read -> Update -> Delete"
              className="w-full h-24 p-2 rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-primary-500 focus:border-primary-500"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              If left empty, the test planner will automatically determine an appropriate test sequence based on API dependencies.
            </p>
          </div>
        </div>
      )}
      
      {/* Error Display */}
      {error && (
        <div className="p-4 mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md text-red-700 dark:text-red-300">
          <div className="flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        </div>
      )}
      
      {/* Action Buttons */}
      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
        >
          Back
        </button>
        
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
        >
          {isGenerating ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Generating...
            </>
          ) : (
            'Generate Blueprint'
          )}
        </button>
      </div>
    </div>
  );
};

export default ModeSelection; 