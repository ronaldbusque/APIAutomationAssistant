import React, { useState } from 'react';
import { useAppContext } from '../context/AppContext';
import { useGenerateBlueprint } from '../hooks/useApi';
import { Switch } from '@headlessui/react';

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
    setBlueprintJobId,
    setMaxIterations
  } = useAppContext();
  
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const generateBlueprintMutation = useGenerateBlueprint();
  
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    
    try {
      const request: any = {
        spec: state.openApiSpec,
        max_iterations: state.maxIterations
      };
      
      if (state.businessRules) request.business_rules = state.businessRules;
      if (state.testData) request.test_data = state.testData;
      if (state.testFlow) request.test_flow = state.testFlow;
      
      const result = await generateBlueprintMutation.mutateAsync(request);
      
      setBlueprintJobId(result.job_id);
      
      onNext();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate blueprint');
      setIsGenerating(false);
    }
  };
  
  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Blueprint Generation Settings</h2>
      
      {/* Advanced Options - Now Always Visible */}
      <div className="border border-gray-300 dark:border-gray-600 rounded-lg p-5 space-y-5 bg-white dark:bg-gray-800 shadow-sm">
        <h3 className="font-medium text-base text-gray-900 dark:text-white mb-2">
          Advanced Configuration
        </h3>
        <div>
          <label htmlFor="business-rules" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Business Rules (Optional)
          </label>
          <textarea
            id="business-rules"
            value={state.businessRules}
            onChange={(e) => setBusinessRules(e.target.value)}
            placeholder="e.g., - Users under 18 cannot create orders.
                 - Invalid API keys must return a 401 Unauthorized error.
                 - GET /products should support sorting by 'price' and 'name'."
            className="w-full h-32 p-2 rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-primary-500 focus:border-primary-500"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Describe business rules that should be validated through testing.
          </p>
        </div>
        
        <div>
          <label htmlFor="test-data" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Test Data Setup Guidance (Optional)
          </label>
          <textarea
            id="test-data"
            value={state.testData}
            onChange={(e) => setTestData(e.target.value)}
            placeholder="e.g., - Ensure a user with ID '123' exists before running GET /users/123.
                 - Need products in 'electronics' and 'clothing' categories.
                 - Pre-populate the system with at least 5 orders."
            className="w-full h-24 p-2 rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-primary-500 focus:border-primary-500"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Provide guidance on specific data needed for tests. If empty, the AI will infer setup needs from the spec.
          </p>
        </div>
        
        <div>
          <label htmlFor="test-flow" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Test Flow Guidance (Optional)
          </label>
          <textarea
            id="test-flow"
            value={state.testFlow}
            onChange={(e) => setTestFlow(e.target.value)}
            placeholder="e.g., - Test the Login endpoint before any other authenticated endpoints.
                 - Verify the Create -> Read -> Update -> Delete sequence for '/items'.
                 - Run all GET requests before POST/PUT/DELETE requests."
            className="w-full h-24 p-2 rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-primary-500 focus:border-primary-500"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Describe desired test execution order or dependencies. If empty, the AI will determine a sequence.
          </p>
        </div>
      </div>
      
      {/* Generation Options */}
      <div className="p-4 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700/30">
        <div className="mt-2">
           <label htmlFor="max-iterations" className="block text-sm font-medium text-gray-900 dark:text-white mb-1">
            Maximum Refinement Iterations
          </label>
          <div className="flex items-center">
            <input
              id="max-iterations"
              type="range"
              min="1"
              max="10"
              value={state.maxIterations}
              onChange={(e) => setMaxIterations(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
            />
            <span className="ml-3 text-gray-900 dark:text-white font-medium">{state.maxIterations}</span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Higher values may produce better results but take longer to complete. The AI will automatically refine the blueprint, improving quality with each iteration.
          </p>
        </div>
      </div>
      
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
          disabled={isGenerating || !state.openApiSpec}
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