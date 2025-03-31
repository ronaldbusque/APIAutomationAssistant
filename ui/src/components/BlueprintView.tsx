import React, { useState, useEffect, useRef } from 'react';
import { useAppContext } from '../context/AppContext';
import { useGenerateScripts, useJobStatus, useWebSocket } from '../hooks/useApi';

interface Props {
  onBack: () => void;
  onNext: () => void;
}

const BlueprintView: React.FC<Props> = ({ onBack, onNext }) => {
  const { 
    state, 
    setBlueprint, 
    setBlueprintIsValid,
    setScriptJobId
  } = useAppContext();
  
  const [isEditing, setIsEditing] = useState(false);
  const [editedBlueprint, setEditedBlueprint] = useState('');
  const [error, setError] = useState<string | null>(null);
  const processedJobRef = useRef<string | null>(null);
  const wsRef = useRef<any>(null);
  
  // Poll job status
  const jobStatus = useJobStatus(state.blueprintJobId);
  
  // Set up WebSocket for real-time updates
  const { connect } = useWebSocket(state.blueprintJobId, (data) => {
    console.log('WebSocket update received:', data);
    
    // Handle different message types
    if (data.type === 'progress' && data.progress) {
      console.log('Progress update:', data.progress);
      // Progress updates are automatically handled by job status refreshes
      // This just ensures we get more frequent UI updates
      jobStatus.refetch();
    } else if (data.type === 'completed' && data.result) {
      console.log('Completed message received:', data.result);
      jobStatus.refetch();
    } else if (data.type === 'error') {
      console.error('Error message received:', data.error);
      setError(data.error || 'An error occurred during blueprint generation');
      jobStatus.refetch();
    }
  });
  
  // Generate scripts hook
  const generateScriptsMutation = useGenerateScripts();
  
  // Update blueprint when job completes
  useEffect(() => {
    // Skip if no data or we're still loading
    if (!jobStatus.data || jobStatus.isLoading) return;
    
    // Skip if job is still processing
    if (jobStatus.data.status === 'queued' || jobStatus.data.status === 'processing') return;
    
    // Skip if we've already processed this job result
    const jobId = jobStatus.data.job_id;
    if (processedJobRef.current === jobId) {
      console.log(`Job ${jobId} already processed, skipping`);
      return;
    }
    
    console.log(`Processing job ${jobId} with status ${jobStatus.data.status}`);
    
    // Mark this job as processed - do this first to prevent multiple processing
    processedJobRef.current = jobId;
    
    if (jobStatus.data.status === 'completed' && jobStatus.data.result?.blueprint) {
      const blueprintData = jobStatus.data.result.blueprint;
      
      // If the blueprint is a string, parse it
      if (typeof blueprintData === 'string') {
        try {
          const parsedBlueprint = JSON.parse(blueprintData);
          setBlueprint(parsedBlueprint);
          setBlueprintIsValid(true);
        } catch (err) {
          console.error('Failed to parse blueprint:', err);
          setError('The generated blueprint is not valid JSON.');
          setBlueprintIsValid(false);
        }
      } else {
        // Already an object
        setBlueprint(blueprintData);
        setBlueprintIsValid(true);
      }
    } else if (jobStatus.data.status === 'failed') {
      setError(jobStatus.data.error || 'Blueprint generation failed.');
      setBlueprintIsValid(false);
    }
  }, [jobStatus.data, jobStatus.isLoading, setBlueprint, setBlueprintIsValid]);
  
  // Connect to WebSocket when job ID changes
  useEffect(() => {
    if (state.blueprintJobId) {
      console.log('Connecting to WebSocket for blueprint updates...');
      
      // Disconnect previous connection if exists
      if (wsRef.current) {
        console.log('Disconnecting previous WebSocket connection');
        wsRef.current.disconnect();
      }
      
      // Create new connection
      const connection = connect();
      if (connection) {
        wsRef.current = connection;
      }
    }
    
    // Cleanup function
    return () => {
      if (wsRef.current) {
        console.log('Cleaning up WebSocket connection');
        wsRef.current.disconnect();
        wsRef.current = null;
      }
    };
  }, [state.blueprintJobId, connect]);
  
  // Handle editing the blueprint
  const handleEdit = () => {
    setEditedBlueprint(JSON.stringify(state.blueprint, null, 2));
    setIsEditing(true);
  };
  
  const handleSave = () => {
    try {
      const parsedBlueprint = JSON.parse(editedBlueprint);
      setBlueprint(parsedBlueprint);
      setBlueprintIsValid(true);
      setIsEditing(false);
      setError(null);
    } catch (err) {
      setError('Invalid JSON format. Please correct the errors before saving.');
    }
  };
  
  const handleCancel = () => {
    setIsEditing(false);
    setError(null);
  };
  
  // Handle continue to script generation
  const handleContinue = async () => {
    if (!state.blueprintIsValid || !state.blueprint) {
      return;
    }
    
    // Simply move to the next step
    // Script generation will be handled in the ScriptOutput component
    onNext();
  };
  
  // Render progress indicator
  const renderProgress = () => {
    if (jobStatus.isLoading) {
      return (
        <div className="text-center p-8">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] text-primary-500 motion-reduce:animate-[spin_1.5s_linear_infinite]"></div>
          <div className="mt-2 text-gray-600 dark:text-gray-400">Loading job status...</div>
        </div>
      );
    }
    
    const progress = jobStatus.data?.progress;
    
    if (jobStatus.data?.status === 'queued') {
      return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 text-center">
          <div className="inline-block h-12 w-12 text-primary-500 mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">Job Queued</h3>
          <p className="text-gray-600 dark:text-gray-400">Your request is in the queue and will be processed shortly.</p>
          <div className="mt-4 h-1.5 w-full bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div className="animate-pulse-indeterminate h-full bg-primary-500"></div>
          </div>
        </div>
      );
    }
    
    if (jobStatus.data?.status === 'processing' && progress) {
      // Get more descriptive stage name
      const getStageName = (stage: string, autonomousStage?: string) => {
        // Check if we have an autonomous-specific stage to display
        if (autonomousStage) {
          switch (autonomousStage) {
            case "spec_analysis": return "Analyzing Specification";
            case "blueprint_authoring": return "Creating Blueprint";
            case "blueprint_reviewing": return "Reviewing Blueprint";
            case "blueprint_complete": return "Blueprint Complete";
            default: return autonomousStage.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
          }
        }
        
        // Standard stage names
        switch (stage) {
          case "planning": return 'Planning Blueprint Structure';
          case "initializing": return 'Initializing';
          case "completed": return 'Completed';
          case "failed": return 'Failed';
          default: return stage.charAt(0).toUpperCase() + stage.slice(1);
        }
      };

      return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">Blueprint Generation</h3>
            <div className="flex space-x-2">
              <div className="text-xs px-3 py-1 bg-primary-100 text-primary-800 dark:bg-primary-900/30 dark:text-primary-300 rounded-full capitalize font-medium">
                {jobStatus.data.status}
              </div>
              <button 
                onClick={() => jobStatus.refetch()}
                className="text-xs px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full flex items-center transition-colors"
                title="Manually refresh status"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </button>
            </div>
          </div>
          
          <div className="mb-6">
            <div className="flex items-center mb-4">
              <div className="font-medium text-gray-800 dark:text-gray-200">
                {getStageName(progress.stage, progress.autonomous_stage)}
              </div>
            </div>
            
            {/* Visual animated indicator */}
            <div className="relative h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              {jobStatus.data.status === 'processing' || jobStatus.data.status === 'queued' ? (
                <div className="animate-progress-indeterminate absolute top-0 h-full w-full bg-primary-500 dark:bg-primary-400"></div>
              ) : jobStatus.data.status === 'completed' ? (
                <div className="absolute h-full w-full bg-green-500 dark:bg-green-400"></div>
              ) : jobStatus.data.status === 'failed' ? (
                <div className="absolute h-full w-full bg-red-500 dark:bg-red-400"></div>
              ) : (
                <div className="absolute h-full w-1/4 bg-primary-500 dark:bg-primary-400"></div>
              )}
            </div>
            
            <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-md">
              <div className="flex">
                <div className="flex-shrink-0 mr-3">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div className="text-sm text-gray-700 dark:text-gray-300">{progress.message}</div>
              </div>
            </div>
          </div>
        </div>
      );
    }
    
    return null;
  };
  
  // Render error message
  const renderError = () => {
    if (error || jobStatus.error) {
      return (
        <div className="p-4 mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md text-red-700 dark:text-red-300">
          <div className="flex items-start">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 mt-0.5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <div className="font-medium">Error</div>
              <div className="text-sm mt-1">{error || (jobStatus.error instanceof Error ? jobStatus.error.message : 'An error occurred')}</div>
            </div>
          </div>
        </div>
      );
    }
    
    return null;
  };
  
  // Render blueprint viewer/editor
  const renderBlueprint = () => {
    if (isEditing) {
      return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">Edit Blueprint</h3>
          <textarea
            value={editedBlueprint}
            onChange={(e) => setEditedBlueprint(e.target.value)}
            className="w-full h-96 p-4 font-mono text-sm bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md resize-y text-gray-800 dark:text-gray-200 focus:ring-primary-500 focus:border-primary-500"
            spellCheck="false"
          />
          <div className="flex mt-4 space-x-2 justify-end">
            <button
              onClick={handleCancel}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md transition-colors"
            >
              Save Changes
            </button>
          </div>
        </div>
      );
    }
    
    if (state.blueprint) {
      return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">Generated Blueprint</h3>
            <button
              onClick={handleEdit}
              className="px-3 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md flex items-center transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit
            </button>
          </div>
          <pre className="w-full h-96 p-4 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md overflow-auto font-mono text-sm text-gray-800 dark:text-gray-200">
            {JSON.stringify(state.blueprint, null, 2)}
          </pre>
          <div className="mt-4 p-3 bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800 rounded-md">
            <div className="flex items-center text-primary-700 dark:text-primary-300 text-sm">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>This blueprint will be used to generate test scripts in the next step. You can edit it if needed.</span>
            </div>
          </div>
        </div>
      );
    }
    
    return null;
  };
  
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Review Test Blueprint</h2>
      
      {renderProgress()}
      {renderError()}
      
      {jobStatus.data?.status === 'completed' && renderBlueprint()}
      
      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
        >
          Back
        </button>
        
        <button
          onClick={handleContinue}
          disabled={!state.blueprintIsValid || jobStatus.data?.status !== 'completed'}
          className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center transition-colors"
        >
          <span>Continue to Script Generation</span>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default BlueprintView; 