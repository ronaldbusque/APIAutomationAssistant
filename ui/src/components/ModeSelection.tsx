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
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Blueprint Generation Settings</h2>
      
      {/* Mode Selection */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Generation Mode
        </label>
        <div className="flex space-x-4">
          <button
            type="button"
            onClick={() => handleModeChange('basic')}
            className={`px-4 py-2 rounded-md ${
              state.mode === 'basic'
                ? 'bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 border border-primary-500'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600'
            }`}
          >
            <div className="font-medium">Basic Mode</div>
            <div className="text-xs mt-1 text-gray-500 dark:text-gray-400">
              Focus on endpoint contracts, status codes, and schema validation
            </div>
          </button>
          
          <button
            type="button"
            onClick={() => handleModeChange('advanced')}
            className={`px-4 py-2 rounded-md ${
              state.mode === 'advanced'
                ? 'bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 border border-primary-500'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600'
            }`}
          >
            <div className="font-medium">Advanced Mode</div>
            <div className="text-xs mt-1 text-gray-500 dark:text-gray-400">
              Includes business rules, test data, and test flow configuration
            </div>
          </button>
        </div>
      </div>
      
      {/* Advanced Options */}
      {state.mode === 'advanced' && (
        <div className="space-y-4">
          <div>
            <label htmlFor="business-rules" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Business Rules
            </label>
            <textarea
              id="business-rules"
              value={state.businessRules}
              onChange={(e) => setBusinessRules(e.target.value)}
              placeholder="e.g., Invalid tokens must return 401"
              className="w-full h-24 p-2 border border-gray-300 rounded-md dark:border-gray-600 dark:bg-gray-800"
            />
          </div>
          
          <div>
            <label htmlFor="test-data" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Test Data Setup <span className="text-xs text-gray-500">(Optional)</span>
            </label>
            <textarea
              id="test-data"
              value={state.testData}
              onChange={(e) => setTestData(e.target.value)}
              placeholder="e.g., POST /users to create a resource"
              className="w-full h-24 p-2 border border-gray-300 rounded-md dark:border-gray-600 dark:bg-gray-800"
            />
            <p className="text-xs text-gray-500 mt-1">
              If left empty, the test planner will automatically create appropriate test data based on the API specification.
            </p>
          </div>
          
          <div>
            <label htmlFor="test-flow" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Test Flow <span className="text-xs text-gray-500">(Optional)</span>
            </label>
            <textarea
              id="test-flow"
              value={state.testFlow}
              onChange={(e) => setTestFlow(e.target.value)}
              placeholder="e.g., Create -> Read -> Update -> Delete"
              className="w-full h-24 p-2 border border-gray-300 rounded-md dark:border-gray-600 dark:bg-gray-800"
            />
            <p className="text-xs text-gray-500 mt-1">
              If left empty, the test planner will automatically determine an appropriate test sequence based on API dependencies.
            </p>
          </div>
        </div>
      )}
      
      {/* Error Display */}
      {error && (
        <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded-md">
          {error}
        </div>
      )}
      
      {/* Action Buttons */}
      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
        >
          Back
        </button>
        
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? 'Generating...' : 'Generate Blueprint'}
        </button>
      </div>
    </div>
  );
};

export default ModeSelection; 