import React, { useState, useEffect, useRef } from 'react';
import { useAppContext } from '../context/AppContext';
import { useJobStatus } from '../hooks/useApi';

interface Props {
  onBack: () => void;
  onNext: () => void;
}

const BlueprintView: React.FC<Props> = ({ onBack, onNext }) => {
  const { 
    state, 
    setBlueprint, 
    setBlueprintIsValid,
  } = useAppContext();
  
  const [isEditing, setIsEditing] = useState(false);
  const [editedBlueprint, setEditedBlueprint] = useState('');
  const [error, setError] = useState<string | null>(null);
  const processedJobRef = useRef<string | null>(null);
  
  // Poll job status
  const jobStatus = useJobStatus(state.blueprintJobId);
  
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
  
  // Render progress indicator
  const renderProgress = () => {
    if (jobStatus.isLoading) {
      return <div className="text-center p-8">Loading job status...</div>;
    }
    
    const progress = jobStatus.data?.progress;
    
    if (jobStatus.data?.status === 'queued') {
      return (
        <div className="text-center p-8">
          <div className="animate-pulse text-primary-600 dark:text-primary-400">Job queued...</div>
        </div>
      );
    }
    
    if (jobStatus.data?.status === 'processing' && progress) {
      return (
        <div className="p-8">
          <div className="mb-2 flex justify-between">
            <div className="text-sm font-medium">{progress.stage}</div>
            <div className="text-sm text-gray-600 dark:text-gray-400">{progress.percent}%</div>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
            <div 
              className="bg-primary-600 h-2.5 rounded-full transition-all duration-300" 
              style={{ width: `${progress.percent}%` }}
            ></div>
          </div>
          <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">{progress.message}</div>
        </div>
      );
    }
    
    return null;
  };
  
  // Render error message
  const renderError = () => {
    if (error || jobStatus.error) {
      return (
        <div className="p-4 mb-4 bg-red-100 border border-red-400 text-red-700 rounded-md">
          <div className="font-medium">Error</div>
          <div>{error || (jobStatus.error instanceof Error ? jobStatus.error.message : 'An error occurred')}</div>
        </div>
      );
    }
    
    return null;
  };
  
  // Render blueprint viewer/editor
  const renderBlueprint = () => {
    if (isEditing) {
      return (
        <div>
          <textarea
            value={editedBlueprint}
            onChange={(e) => setEditedBlueprint(e.target.value)}
            className="w-full h-96 p-2 font-mono text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-800 rounded-md resize-y"
          />
          <div className="flex mt-4 space-x-2">
            <button
              onClick={handleSave}
              className="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded-md"
            >
              Save Changes
            </button>
            <button
              onClick={handleCancel}
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
            >
              Cancel
            </button>
          </div>
        </div>
      );
    }
    
    if (state.blueprint) {
      return (
        <div>
          <div className="flex justify-end mb-2">
            <button
              onClick={handleEdit}
              className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md flex items-center"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit Blueprint
            </button>
          </div>
          <pre className="w-full h-96 p-4 bg-gray-100 dark:bg-gray-800 rounded-md overflow-auto font-mono text-sm">
            {JSON.stringify(state.blueprint, null, 2)}
          </pre>
        </div>
      );
    }
    
    return null;
  };
  
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Review Test Blueprint</h2>
      
      {renderProgress()}
      {renderError()}
      
      {jobStatus.data?.status === 'completed' && renderBlueprint()}
      
      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
        >
          Back
        </button>
        
        <button
          onClick={onNext}
          disabled={!state.blueprintIsValid || jobStatus.data?.status !== 'completed'}
          className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
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