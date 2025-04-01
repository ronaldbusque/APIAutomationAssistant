import React, { useState, useEffect, useRef } from 'react';
import { useAppContext } from '../context/AppContext';
import { useGenerateScripts, useJobStatus, useWebSocket } from '../hooks/useApi';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Switch } from '@headlessui/react';

interface Props {
  onBack: () => void;
}

// Define interface for JSON validation errors
interface JsonError {
  message: string;
  // We might add line/column later if we use a better parser, but keep it simple for now
}

const ScriptOutput: React.FC<Props> = ({ onBack }) => {
  const { 
    state, 
    setScriptJobId, 
    setScripts, 
    setBlueprint, 
    setBlueprintIsValid,
    setCurrentStep,
    setMaxIterations,
    setTarget, // Add setTarget here
    setSpec,
    setSpecFormat
  } = useAppContext();
  
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [blueprintInput, setBlueprintInput] = useState<string>('');
  const [showBlueprintInput, setShowBlueprintInput] = useState<boolean>(false);
  const [showErrorDetails, setShowErrorDetails] = useState<boolean>(false);
  const [jsonErrors, setJsonErrors] = useState<Record<string, JsonError | null>>({});
  
  const generateScriptsMutation = useGenerateScripts();
  const jobStatus = useJobStatus(state.scriptJobId);
  
  const processedJobRef = useRef<string | null>(null);
  const wsRef = useRef<any>(null);
  
  // After the useState declarations at the top of the component, add a new state for tracking expanded directories
  const [expandedDirs, setExpandedDirs] = useState<Record<string, boolean>>({});
  
  // Add validation useEffect for JSON files
  useEffect(() => {
    const currentTargetScripts = state.target ? state.scripts[state.target] : null;
    const errors: Record<string, JsonError | null> = {};

    if (currentTargetScripts) {
      Object.entries(currentTargetScripts).forEach(([filename, content]) => {
        if (filename.endsWith('.json')) { // Only validate .json files
          try {
            if (content && typeof content === 'string') { // Ensure content is a non-empty string
              JSON.parse(content);
              errors[filename] = null; // No error
            } else {
               errors[filename] = null; // Treat empty/non-string content as not-an-error for now
            }
          } catch (e) {
            if (e instanceof Error) {
              // Store the error message
              errors[filename] = { message: e.message };
            } else {
              // Fallback for unknown error types
              errors[filename] = { message: 'Unknown JSON parsing error' };
            }
            console.warn(`JSON validation failed for file: ${filename}`, e);
          }
        } else {
           errors[filename] = null; // Not a JSON file, no error
        }
      });
    }
    setJsonErrors(errors); // Update the state with errors for the current target

  }, [state.target, state.scripts]); // Re-run when target or scripts change
  
  // Set up WebSocket for real-time updates
  const { connect } = useWebSocket(state.scriptJobId, (data) => {
    console.log('WebSocket update received in ScriptOutput:', data);
    
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
      setError(data.error || 'An error occurred during script generation');
      jobStatus.refetch();
    }
  });
  
  // Connect to WebSocket when job ID changes
  useEffect(() => {
    if (state.scriptJobId) {
      console.log('Connecting to WebSocket for script generation updates...');
      
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
  }, [state.scriptJobId, connect]);
  
  // Update scripts when job completes
  useEffect(() => {
    // Skip if no data or we're still loading
    if (!jobStatus.data || jobStatus.isLoading) return;
    
    // Skip if job is still processing
    if (jobStatus.data.status === 'queued' || jobStatus.data.status === 'processing') return;
    
    // Skip if we've already processed this job result
    const jobId = jobStatus.data.job_id;
    if (processedJobRef.current === jobId) {
      console.log(`Script job ${jobId} already processed, skipping`);
      return;
    }
    
    console.log(`Processing script job ${jobId} with status ${jobStatus.data.status}`);
    
    // Mark this job as processed - do this first to prevent multiple processing
    processedJobRef.current = jobId;
    
    if (jobStatus.data.status === 'completed' && jobStatus.data.result) {
      console.log('Received job result data:', jobStatus.data.result);
      
      // Extract scripts from result
      const scriptsData = processScriptsData(jobStatus.data.result);
      
      // Update state with the processed scripts
      if (scriptsData && Object.keys(scriptsData).length > 0) {
        console.log('Setting scripts data in state:', scriptsData);
        setScripts(scriptsData);
        
        // Get available targets from the response (should only be one)
        const availableTargets = Object.keys(scriptsData);
        
        // Select the first file of the single target if available
        if (availableTargets.length > 0) {
          const currentTarget = availableTargets[0]; // Should match state.target
          if (scriptsData[currentTarget]) {
            const fileNames = Object.keys(scriptsData[currentTarget]);
            if (fileNames.length > 0 && !selectedFile) { // Only set if no file is selected
              setSelectedFile(fileNames[0]);
            }
          }
        }
      } else {
        console.error('No valid scripts data found in the server response');
        setError('No valid scripts data found in the server response');
      }
      
      setGenerating(false);
    } else if (jobStatus.data.status === 'failed') {
      console.error('Script generation failed:', jobStatus.data.error);
      setError(jobStatus.data.error || 'Script generation failed.');
      setGenerating(false);
    }
  }, [jobStatus.data, jobStatus.isLoading, setScripts, selectedFile, state.target]);
  
  // Process scripts data from API response
  const processScriptsData = (result: any) => {
    // Check if result exists
    if (!result) {
      console.error('Empty result received');
      return null;
    }
    
    console.log('Processing scripts data, result structure:', Object.keys(result));
    
    // Try to extract scripts from the result
    let scriptsData = result.scripts;
    
    // If scripts property doesn't exist or is empty, check if the result itself might be the scripts data
    if (!scriptsData || Object.keys(scriptsData).length === 0) {
      console.log('No scripts property found or it\'s empty, checking alternative structures');
      
      // Check for specific target properties like 'playwright', 'postman', etc.
      const commonTargets = ['playwright', 'postman', 'python', 'typescript', 'java', 'rust', 'go'];
      const hasTargets = commonTargets.some(target => result[target] && typeof result[target] === 'object');
      
      if (hasTargets) {
        console.log('Result appears to contain target properties directly');
        scriptsData = {};
        
        // Copy only the valid target properties
        commonTargets.forEach(target => {
          if (result[target] && typeof result[target] === 'object') {
            scriptsData[target] = result[target];
          }
        });
      }
      
      // If still no valid data, see if the result itself is a map of targets to files
      if (Object.keys(scriptsData).length === 0) {
        // Check if the result looks like a map of targets to files
        const possibleTargets = Object.keys(result);
        for (const target of possibleTargets) {
          if (typeof result[target] === 'object' && !Array.isArray(result[target])) {
            // Check if the target's value looks like a file map (string values or filename-like keys)
            const targetObj = result[target];
            const fileKeys = Object.keys(targetObj);
            
            if (fileKeys.length > 0) {
              const looksLikeFiles = fileKeys.some(key => 
                key.includes('.') ||  // Has file extension
                key.includes('/') ||  // Has path separator
                typeof targetObj[key] === 'string' // Value is string content
              );
              
              if (looksLikeFiles) {
                console.log(`Found target ${target} with file-like structure`);
                if (!scriptsData) scriptsData = {};
                scriptsData[target] = targetObj;
              }
            }
          }
        }
      }
    }
    
    // Additional fix: If the data is in array format like ["file1", "file2"] instead of {file1: content, file2: content}
    // Try to convert it to a more usable format
    if (scriptsData) {
      for (const target in scriptsData) {
        const targetData = scriptsData[target];
        
        // If targetData is an array, assume it's a list of filenames without content
        if (Array.isArray(targetData)) {
          console.log(`Target ${target} data is in array format, converting to object`);
          const fileObj: Record<string, string> = {};
          
          // Convert array to object with filenames as keys
          targetData.forEach(filename => {
            if (typeof filename === 'string') {
              // Use placeholder content
              fileObj[filename] = `// Content for ${filename} will be loaded when selected`;
            }
          });
          
          // Replace array with object
          scriptsData[target] = fileObj;
        }
      }
    }
    
    // Validate scripts data structure
    if (!scriptsData || typeof scriptsData !== 'object' || Object.keys(scriptsData).length === 0) {
      console.error('Invalid scripts data format or empty after processing:', scriptsData);
      return null;
    }
    
    // Log the structure of the processed data
    console.log('Processed scripts data structure:', Object.keys(scriptsData));
    for (const target in scriptsData) {
      const fileCount = Object.keys(scriptsData[target]).length;
      console.log(`- ${target}: ${fileCount} files`);
      if (fileCount > 0) {
        console.log(`  First few files:`, Object.keys(scriptsData[target]).slice(0, 3));
      }
    }
    
    return scriptsData;
  };
  
  // Handle blueprint input
  const handleBlueprintSubmit = () => {
    try {
      const parsedBlueprint = JSON.parse(blueprintInput);
      setBlueprint(parsedBlueprint);
      setBlueprintIsValid(true);
      setShowBlueprintInput(false);
      setError(null);
    } catch (err) {
      setError('Invalid JSON format. Please ensure your blueprint is a valid JSON object.');
    }
  };
  
  // Handle blueprint file upload
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    // Check if it's a JSON file
    if (!file.name.endsWith('.json')) {
      setError('Please upload a JSON file.');
      return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const parsedBlueprint = JSON.parse(content);
        setBlueprint(parsedBlueprint);
        setBlueprintIsValid(true);
        setShowBlueprintInput(false);
        setError(null);
      } catch (err) {
        setError('Invalid JSON blueprint file. Please ensure the file contains a valid JSON object.');
      }
    };
    reader.onerror = () => {
      setError('Error reading the file. Please try again.');
    };
    reader.readAsText(file);
  };
  
  // Function to handle script generation
  const handleGenerateScripts = async () => {
    setGenerating(true);
    setError(null);
    
    // Reset script-related state when generating new scripts
    setScripts({});
    setScriptJobId(null);
    setSelectedFile(null);
    processedJobRef.current = null;

    if (!state.target) { // Check if a target is selected
        setError('Please select a target framework before generating scripts.');
        setGenerating(false);
        return;
    }

    try {
      const request = {
        blueprint: state.blueprint,
        targets: [state.target], // Send the single target in an array
        max_iterations: state.maxIterations
      };
      
      const result = await generateScriptsMutation.mutateAsync(request);
      setScriptJobId(result.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate scripts');
      setGenerating(false);
    }
  };
  
  // Handle file selection
  const handleFileSelect = async (file: string) => {
    setSelectedFile(file);
    
    // If we have a file list without content, try to fetch the content
    if (state.target && 
        state.scripts[state.target] && 
        state.scripts[state.target][file] && 
        (state.scripts[state.target][file].startsWith('// Content for') || 
         state.scripts[state.target][file].length < 100)
       ) {
      await fetchFileContent(state.target, file);
    }
  };
  
  // Fetch file content if needed
  const fetchFileContent = async (target: string, filename: string) => {
    // Use target argument directly
    if (!state.scriptJobId) return;
    
    try {
      console.log(`Fetching content for ${target}/${filename}`);
      
      // Create a temporary loading message
      const newScripts = {...state.scripts};
      newScripts[target][filename] = `// Loading content for ${filename}...`;
      setScripts(newScripts);
      
      // Use the API to fetch the specific file content
      const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/file-content/${state.scriptJobId}/${target}/${filename}`);
      
      if (!response.ok) {
        throw new Error(`Failed to load file content: ${response.status}`);
      }
      
      const content = await response.text();
      
      // Update the scripts state with the fetched content
      const updatedScripts = {...state.scripts};
      updatedScripts[target][filename] = content;
      setScripts(updatedScripts);
      
      console.log(`Successfully loaded content for ${target}/${filename}`);
    } catch (error) {
      console.error('Error fetching file content:', error);
      // Show error in the file content
      const errorScripts = {...state.scripts};
      errorScripts[target][filename] = `// Error loading content: ${error instanceof Error ? error.message : 'Unknown error'}`;
      setScripts(errorScripts);
    }
  };
  
  // Handle copy to clipboard
  const handleCopy = () => {
    if (state.target && selectedFile && state.scripts[state.target]?.[selectedFile]) {
      navigator.clipboard.writeText(state.scripts[state.target][selectedFile]);
    }
  };
  
  // Handle download
  const handleDownload = () => {
    if (state.target && selectedFile && state.scripts[state.target]?.[selectedFile]) {
      const content = state.scripts[state.target][selectedFile];
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      
      const a = document.createElement('a');
      a.href = url;
      a.download = selectedFile;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };
  
  // Handle downloading all files as ZIP
  const handleDownloadAllFiles = async () => {
    if (!state.target || !state.scripts[state.target]) return;
    
    try {
      // Dynamically import JSZip (with type assertion to avoid TypeScript errors)
      const JSZipModule = await import('jszip');
      const JSZip = JSZipModule.default;
      const zip = new JSZip();
      
      // Add all files to the ZIP
      const files = state.scripts[state.target];
      for (const [filename, content] of Object.entries(files)) {
        // Create directory structure in the ZIP
        zip.file(filename, content);
      }
      
      // Generate ZIP and trigger download
      const zipBlob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(zipBlob);
      
      const a = document.createElement('a');
      a.href = url;
      a.download = `${state.target}_scripts.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error creating ZIP file:', error);
      setError('Failed to download files as ZIP. Please try downloading individual files.');
    }
  };
  
  // Render progress
  const renderProgress = () => {
    if (jobStatus.isLoading) {
      return (
        <div className="text-center p-8">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] text-primary-500 motion-reduce:animate-[spin_1.5s_linear_infinite]"></div>
          <div className="mt-2 text-gray-600 dark:text-gray-400">Loading job status...</div>
        </div>
      );
    }
    
    const progress = jobStatus.data?.progress || state.scriptProgress;
    const status = jobStatus.data?.status || 'processing';
    const message = progress?.message || 'Processing...';
    const stage = progress?.stage || 'initializing';
    
    // Get more descriptive stage name
    const getStageName = (stage: string, autonomousStage?: string) => {
      // Check if we have an autonomous-specific stage to display
      if (autonomousStage) {
        switch (autonomousStage) {
          case "spec_analysis": return "Analyzing Specification";
          case "blueprint_authoring": return "Creating Blueprint";
          case "blueprint_reviewing": return "Reviewing Blueprint";
          case "script_target_start": return "Initializing Script Generation";
          case "script_coding": return "Coding Tests";
          case "script_reviewing": return "Reviewing Tests";
          case "script_target_complete": return "Target Complete";
          default: return autonomousStage.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
        }
      }
      
      // Standard stage names
      switch (stage) {
        case "planning": return 'Planning Test Structure';
        case "coding": return 'Generating Test Scripts';
        case "initializing": return 'Initializing';
        case "waiting_for_review": return 'Waiting for Review';
        case "completed": return 'Completed';
        case "failed": return 'Failed';
        default: return stage.charAt(0).toUpperCase() + stage.slice(1);
      }
    };
    
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-6">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">Script Generation</h3>
          <div className="flex space-x-2">
            <div className="text-xs px-3 py-1 bg-primary-100 text-primary-800 dark:bg-primary-900/30 dark:text-primary-300 rounded-full capitalize font-medium">
              {status}
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
              {getStageName(stage, progress?.autonomous_stage)}
            </div>
            <div className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 text-xs rounded-full">
              Autonomous Pipeline
            </div>
          </div>
          
          {/* Visual animated indicator */}
          <div className="relative h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            {status === 'processing' || status === 'queued' ? (
              <div className="animate-progress-indeterminate absolute top-0 h-full w-full bg-primary-500 dark:bg-primary-400"></div>
            ) : status === 'completed' ? (
              <div className="absolute h-full w-full bg-green-500 dark:bg-green-400"></div>
            ) : status === 'failed' ? (
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
              <div className="text-sm text-gray-700 dark:text-gray-300">{message}</div>
            </div>
          </div>
        </div>
        
        {/* Show job details for debugging */}
        <div className="mt-4 flex justify-end">
          <button
            onClick={() => setShowBlueprintInput(!showBlueprintInput)}
            className="text-xs px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full flex items-center transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {showBlueprintInput ? 'Hide Details' : 'Show Details'}
          </button>
        </div>
        
        {showBlueprintInput && jobStatus.data && (
          <div className="mt-3 p-4 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md text-xs font-mono overflow-auto max-h-48">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div>
                <span className="font-semibold text-gray-700 dark:text-gray-300">Job ID:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">{jobStatus.data.job_id}</span>
              </div>
              <div>
                <span className="font-semibold text-gray-700 dark:text-gray-300">Status:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">{jobStatus.data.status}</span>
              </div>
              <div>
                <span className="font-semibold text-gray-700 dark:text-gray-300">Stage:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">{progress?.stage || 'N/A'}</span>
              </div>
              <div>
                <span className="font-semibold text-gray-700 dark:text-gray-300">Trace ID:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">{jobStatus.data.result?.trace_id || 'N/A'}</span>
              </div>
              <div>
                <span className="font-semibold text-gray-700 dark:text-gray-300">Last Updated:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">{new Date().toLocaleTimeString()}</span>
              </div>
              <div>
                <span className="font-semibold text-gray-700 dark:text-gray-300">Message:</span>{' '}
                <span className="text-gray-600 dark:text-gray-400">{message}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };
  
  // Render error message
  const renderError = () => {
    if (!error) return null;
    
    return (
      <div className="p-4 mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md text-red-700 dark:text-red-300">
        <div className="flex items-start">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 mt-0.5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <div className="font-medium">Error</div>
            <div className="text-sm mt-1">{error}</div>
          </div>
        </div>
        
        {/* Debug button to show job result data */}
        {jobStatus.data && (
          <div className="mt-4 border-t border-red-200 dark:border-red-800 pt-3">
            <button
              onClick={() => setShowErrorDetails(!showErrorDetails)}
              className="text-xs px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full flex items-center transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {showErrorDetails ? 'Hide Error Details' : 'Show Error Details'}
            </button>
            
            {showErrorDetails && (
              <div className="mt-3 overflow-auto max-h-64 p-3 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md text-xs font-mono">
                <pre className="text-gray-700 dark:text-gray-300">
                  {JSON.stringify(jobStatus.data, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };
  
  // Render script output
  const renderOutput = () => {
    // Add debugging for state
    console.log('Render output - state.scripts:', state.scripts);
    console.log('Render output - selectedTarget:', state.target);
    
    if (state.target) {
      console.log('Render output - files for selected target:', 
        state.scripts[state.target] ? Object.keys(state.scripts[state.target]) : 'No files');
    }
    
    // Check if scripts are empty or undefined
    const hasScripts = state.scripts && Object.keys(state.scripts).length > 0;
    console.log('Render output - has scripts:', hasScripts);
    
    if (!hasScripts) {
      return (
        <div className="space-y-6">
          {!showBlueprintInput && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">Use Blueprint</h3>
                <div className="flex space-x-2">
                  <label className="px-3 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md flex items-center text-sm cursor-pointer transition-colors">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    Upload Blueprint
                    <input 
                      type="file" 
                      accept=".json" 
                      onChange={handleFileUpload} 
                      className="hidden" 
                    />
                  </label>
                  <button
                    onClick={() => setShowBlueprintInput(true)}
                    className="px-3 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md flex items-center text-sm transition-colors"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Paste Blueprint
                  </button>
                </div>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                If you have a previously saved test blueprint, you can upload a JSON file or paste it directly to generate scripts without going through the specification and blueprint generation steps.
              </p>
            </div>
          )}

          {showBlueprintInput && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">Paste Your Blueprint</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Paste a valid JSON test blueprint to generate scripts:
              </p>
              <textarea
                value={blueprintInput}
                onChange={(e) => setBlueprintInput(e.target.value)}
                className="w-full h-64 p-4 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md font-mono text-sm resize-y text-gray-800 dark:text-gray-200 focus:ring-primary-500 focus:border-primary-500"
                placeholder='{
  "apiName": "Example API",
  "version": "1.0.0",
  "groups": [
    {
      "name": "Example Group",
      "tests": [
        {
          "id": "test1",
          "name": "Test Example",
          "endpoint": "/example",
          "method": "GET",
          "expectedStatus": 200
        }
      ]
    }
  ]
}'
                spellCheck="false"
              ></textarea>
              <div className="flex mt-4 space-x-2 justify-end">
                <button
                  onClick={() => setShowBlueprintInput(false)}
                  className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleBlueprintSubmit}
                  className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md transition-colors"
                >
                  Use Blueprint
                </button>
              </div>
            </div>
          )}

          {/* Show blueprint status - whether loaded or not */}
          {!showBlueprintInput && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">Blueprint Status</h3>
                {state.blueprint ? (
                  <div className="flex space-x-2 items-center">
                    <div className="text-xs px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 rounded-full font-medium">Ready for Script Generation</div>
                    <button 
                      onClick={() => {
                        setBlueprint(null);
                        setBlueprintIsValid(false);
                      }}
                      className="text-xs px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full flex items-center transition-colors"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Clear
                    </button>
                  </div>
                ) : (
                  <div className="text-xs px-3 py-1 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 rounded-full font-medium">No Blueprint Loaded</div>
                )}
              </div>
              {state.blueprint ? (
                <>
                  <div className="p-4 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-md">
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      Blueprint for <span className="font-medium">{state.blueprint.apiName || 'Unknown API'}</span> has been loaded successfully.
                    </p>
                    <div className="mt-2 text-sm text-gray-600 dark:text-gray-400 flex items-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                      <span>
                        Contains: <span className="font-medium">{state.blueprint.groups?.length || 0}</span> test groups with{' '}
                        <span className="font-medium">{state.blueprint.groups?.reduce((total: number, group: any) => total + (group.tests?.length || 0), 0) || 0}</span> tests
                      </span>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Please upload or paste a blueprint, or navigate back to generate one from your API specification.
                </p>
              )}
            </div>
          )}

          {/* ADD Target Framework Selection Here */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <label className="block text-lg font-medium text-gray-900 dark:text-white mb-4">
              Target Framework
            </label>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Select the framework you want to generate test scripts for:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {['postman', 'playwright', 'python', 'typescript', 'java'].map((target) => (
                <label 
                  key={target}
                  className={`flex items-center p-3 rounded-md border transition-colors cursor-pointer ${ 
                    state.target === target 
                      ? 'border-primary-500 bg-primary-50 dark:bg-gray-700 dark:border-primary-400 ring-1 ring-primary-500 dark:ring-primary-400' 
                      : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500' 
                  }`}
                >
                  <input
                    type="radio"
                    name="target-framework-script"
                    value={target}
                    checked={state.target === target}
                    onChange={() => setTarget(target)}
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 dark:border-gray-600 dark:bg-gray-900 dark:checked:bg-primary-600 dark:focus:ring-offset-gray-800"
                  />
                  <span className="ml-2 capitalize text-gray-800 dark:text-gray-200">{target}</span>
                </label>
              ))}
            </div>
          </div>
          
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex flex-col">
              <div className="mb-4">
                <span className="font-medium text-gray-900 dark:text-white">Generation Options</span>
                <p className="text-sm text-gray-600 dark:text-gray-400">Configure how your test scripts are generated.</p>
              </div>
              
              <div className="mt-2">
                <label htmlFor="script-max-iterations" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Maximum Refinement Iterations
                </label>
                <div className="flex items-center">
                  <input
                    id="script-max-iterations"
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
                  Higher values may produce better results but take longer to complete. The AI will automatically refine the scripts, improving quality with each iteration.
                </p>
              </div>
            </div>
          </div>
          
          <div className="text-center pt-4">
            <button 
              onClick={handleGenerateScripts}
              disabled={generating || !state.target || !state.blueprint} // Check for state.target instead of state.targets.length
              className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center mx-auto shadow-sm transition-colors"
            >
              {generating ? (
                <span className="flex items-center font-medium">
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Generating Scripts...
                </span>
              ) : (
                <span className="flex items-center font-medium">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  Generate Scripts
                </span>
              )}
            </button>
            {/* Update error messages */}
            {!state.target && (
              <p className="mt-2 text-sm text-amber-500 dark:text-amber-400">Please go back and select a target framework</p>
            )}
            {!state.blueprint && (
              <p className="mt-2 text-sm text-amber-500 dark:text-amber-400">Please upload/paste a blueprint or navigate back to create one</p>
            )}
          </div>
        </div>
      );
    }
    
    // Calculate if the current target has any JSON errors
    const hasAnyJsonError = state.target ? Object.values(jsonErrors).some(error => error !== null) : false;

    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="flex flex-col md:flex-row h-[calc(100vh-280px)]">
          {/* File List Column - Fixed width, independent scrolling */}
          <div className="w-full md:w-72 flex-shrink-0 border-r border-gray-200 dark:border-gray-700 flex flex-col min-h-0">
            {state.target && (
              <div className="flex-1 flex flex-col min-h-0">
                {/* Sticky Header */}
                <div className="flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 z-10 flex-shrink-0">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center">
                    Files for <span className="capitalize font-semibold mx-1">{state.target}</span>
                    {/* Global Error Indicator for Target */}
                    {hasAnyJsonError && (
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1 text-amber-500 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                        <title>Contains files with JSON errors</title>
                        <path fillRule="evenodd" d="M8.257 3.099c.636-1.178 2.364-1.178 3.001 0l5.142 9.496c.61 1.124-.17 2.573-1.5 2.573H4.614c-1.33 0-2.11-1.449-1.5-2.573l5.142-9.496zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                      </svg>
                    )}
                  </h3>
                  {/* ... (Download All button) ... */}
                  <button
                    onClick={handleDownloadAllFiles}
                    className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                    title="Download all files as ZIP"
                  >
                    Download All
                  </button>
                </div>
                {/* File List - Scrollable area */}
                <div className="file-list-container p-4 overflow-y-auto overflow-x-auto flex-grow min-h-0">
                  {(() => {
                    // ... (existing logic for filesByDir, rootFiles, rootDirs) ...
                    // Logic to organize files into directories
                    const filesByDir: Record<string, string[]> = {};
                    const rootFiles: string[] = [];
                    const rootDirs = new Set<string>();
                    
                    if (state.target && state.scripts[state.target]) {
                      // Process each file path
                      Object.keys(state.scripts[state.target]).forEach(filePath => {
                        const parts = filePath.split('/');
                        
                        if (parts.length === 1) {
                          // Root-level file
                          rootFiles.push(filePath);
                        } else {
                          // File in a directory
                          const dirPath = parts.slice(0, -1).join('/');
                          
                          // Create directory entry if it doesn't exist
                          if (!filesByDir[dirPath]) {
                            filesByDir[dirPath] = [];
                            
                            // Also add parent directories
                            let currentDir = '';
                            parts.slice(0, -1).forEach(part => {
                              currentDir = currentDir ? `${currentDir}/${part}` : part;
                              rootDirs.add(currentDir);
                            });
                          }
                          
                          // Add file to its directory
                          filesByDir[dirPath].push(filePath);
                        }
                      });
                    }
                    
                    const renderFileButton = (filePath: string, indent: number) => {
                      const fileName = filePath.split('/').pop() || filePath;
                      const fileError = jsonErrors[filePath]; // Check for error
                      const isJsonFile = filePath.endsWith('.json');

                      return (
                        <button
                          key={filePath}
                          onClick={() => handleFileSelect(filePath)}
                          className={`block w-full text-left px-3 py-2 text-sm border-b border-gray-200 dark:border-gray-700 last:border-b-0 ${
                            selectedFile === filePath
                              ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 font-medium'
                              : fileError && isJsonFile
                              ? 'hover:bg-red-50 dark:hover:bg-red-900/20 text-red-800 dark:text-red-300' // Error style
                              : 'hover:bg-gray-50 dark:hover:bg-gray-800/80 text-gray-700 dark:text-gray-300'
                          } transition-colors`}
                          style={{ paddingLeft: `${indent}px` }}
                        >
                          <span className="flex items-center">
                            {getFileIcon(fileName)}
                            <span className="truncate mr-1">{fileName}</span>
                            {/* Per-File Error Indicator */}
                            {fileError && isJsonFile && (
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-auto flex-shrink-0 text-amber-500" viewBox="0 0 20 20" fill="currentColor">
                                <title>{`Invalid JSON: ${fileError.message}`}</title>
                                <path fillRule="evenodd" d="M8.257 3.099c.636-1.178 2.364-1.178 3.001 0l5.142 9.496c.61 1.124-.17 2.573-1.5 2.573H4.614c-1.33 0-2.11-1.449-1.5-2.573l5.142-9.496zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                              </svg>
                            )}
                          </span>
                        </button>
                      );
                    };

                    const renderDir = (dirPath: string, level: number) => {
                      // ... (existing directory rendering logic) ...
                      // Compute directory display name
                      const dirName = dirPath.split('/').pop() || dirPath;
                      const indent = level * 12;
                      const isExpanded = expandedDirs[dirPath] !== false; // Default to expanded
                      
                      // Check if this directory contains any files
                      const hasFiles = filesByDir[dirPath] && filesByDir[dirPath].length > 0;
                      
                      // Find subdirectories of this directory
                      const subDirs = Array.from(rootDirs).filter(dir => {
                        const parts = dir.split('/');
                        const parentDir = parts.slice(0, -1).join('/');
                        return parentDir === dirPath;
                      });
                      
                      return (
                        <div key={dirPath} className="mb-1">
                          {/* Directory header/button */}
                          <button
                            onClick={() => {
                              setExpandedDirs({
                                ...expandedDirs,
                                [dirPath]: !isExpanded
                              });
                            }}
                            className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800/80 text-gray-800 dark:text-gray-200 font-medium flex items-center"
                            style={{ paddingLeft: `${indent}px` }}
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              className={`h-4 w-4 mr-1 transition-transform ${isExpanded ? 'transform rotate-90' : ''}`}
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1 text-yellow-500" viewBox="0 0 20 20" fill="currentColor">
                              <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                            </svg>
                            <span className="truncate">{dirName}</span>
                          </button>
                          
                          {/* Directory contents (conditionally rendered) */}
                          {isExpanded && (
                            <div className="ml-4">
                              {/* Render subdirectories */}
                              {subDirs.map(subDir => renderDir(subDir, level + 1))}
                              
                              {/* Render files in this directory */}
                              {hasFiles && filesByDir[dirPath].map(item => {
                                // If this is a file in this exact directory (not a sub-subdirectory)
                                const fileName = item.split('/').pop();
                                if (fileName) {
                                  return renderFileButton(item, indent + 20);
                                }
                              })}
                            </div>
                          )}
                        </div>
                      );
                    };
                    
                    // Build full directory structure
                    return (
                      <>
                        {/* Root directories */}
                        {Array.from(rootDirs).filter(dir => !dir.includes('/')).map(dir => renderDir(dir, 0))}
                        
                        {/* Root files */}
                        {rootFiles.map(file => {
                          const fileName = file.split('/').pop() || file;
                          const fileError = jsonErrors[file]; // Check for error
                          const isJsonFile = file.endsWith('.json');

                          return (
                            <button
                              key={file}
                              onClick={() => handleFileSelect(file)}
                              className={`block w-full text-left px-3 py-2 text-sm border-b border-gray-200 dark:border-gray-700 last:border-b-0 ${
                                selectedFile === file
                                  ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 font-medium'
                                  : fileError && isJsonFile
                                  ? 'hover:bg-red-50 dark:hover:bg-red-900/20 text-red-800 dark:text-red-300' // Error style
                                  : 'hover:bg-gray-50 dark:hover:bg-gray-800/80 text-gray-700 dark:text-gray-300'
                              } transition-colors`}
                              style={{ paddingLeft: '12px' }}
                            >
                              <span className="flex items-center">
                                {getFileIcon(file)}
                                <span className="truncate mr-1">{fileName}</span>
                                {/* Per-File Error Indicator */}
                                {fileError && isJsonFile && (
                                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-auto flex-shrink-0 text-amber-500" viewBox="0 0 20 20" fill="currentColor">
                                    <title>{`Invalid JSON: ${fileError.message}`}</title>
                                    <path fillRule="evenodd" d="M8.257 3.099c.636-1.178 2.364-1.178 3.001 0l5.142 9.496c.61 1.124-.17 2.573-1.5 2.573H4.614c-1.33 0-2.11-1.449-1.5-2.573l5.142-9.496zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                                  </svg>
                                )}
                              </span>
                            </button>
                          );
                        })}
                      </>
                    );
                  })()}
                </div>
              </div>
            )}
          </div>
          
          {/* Content View Column - Flexible width, independent scrolling */}
          <div className="flex-grow min-w-0 min-h-0 flex flex-col">
            {renderFileContent()} 
          </div>
        </div>
      </div>
    );
  };
  
  const renderFileContent = () => {
    if (!selectedFile || !state.target || !state.scripts[state.target]) {
      return (
        <div className="flex-1 flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-900">
          <p className="text-gray-500 dark:text-gray-400">Select a file to view its content</p>
        </div>
      );
    }

    const content = state.scripts[state.target][selectedFile];
    const fileError = jsonErrors[selectedFile];
    const isJsonFile = selectedFile.endsWith('.json');

    return (
      <div className="flex-1 flex flex-col min-h-0">
        {/* File header with actions */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex-shrink-0">
          <div className="flex items-center space-x-2">
            {getFileIcon(selectedFile)}
            <span className="font-medium text-gray-900 dark:text-white">{selectedFile}</span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleCopyContent(content)}
              className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              title="Copy content"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>
            <button
              onClick={() => handleDownloadFile(selectedFile, content)}
              className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              title="Download file"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </button>
          </div>
        </div>

        {/* JSON Error Warning Banner */}
        {fileError && isJsonFile && (
          <div className="bg-amber-50 dark:bg-amber-900/20 border-l-4 border-amber-500 p-4 flex-shrink-0">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-amber-500" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.636-1.178 2.364-1.178 3.001 0l5.142 9.496c.61 1.124-.17 2.573-1.5 2.573H4.614c-1.33 0-2.11-1.449-1.5-2.573l5.142-9.496zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  Invalid JSON: {fileError.message}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Content area with syntax highlighting */}
        <div className="flex-1 overflow-x-auto min-h-0 min-w-0 bg-gray-50 dark:bg-gray-900">
          <SyntaxHighlighter
            language={getLanguageFromFileName(selectedFile)}
            style={document.documentElement.classList.contains('dark') ? oneDark : oneLight}
            customStyle={{
              margin: 0,
              padding: '1rem',
              minWidth: 'max-content',
              fontSize: '0.875rem',
              lineHeight: '1.5',
              backgroundColor: document.documentElement.classList.contains('dark') ? '#111827' : '#f9fafb',
              height: '100%',
              overflowY: 'auto'
            }}
            wrapLongLines={false}
            showLineNumbers={true}
            lineNumberStyle={{
              minWidth: '3em',
              paddingRight: '1em',
              textAlign: 'right',
              userSelect: 'none',
              position: 'sticky',
              left: 0,
              zIndex: 10,
              backgroundColor: document.documentElement.classList.contains('dark') ? '#111827' : '#f9fafb'
            }}
          >
            {content}
          </SyntaxHighlighter>
        </div>
      </div>
    );
  };
  
  // Add a function to get file icon based on extension
  const getFileIcon = (fileName: string) => {
    const extension = fileName.split('.').pop()?.toLowerCase();
    
    // Return different SVG paths based on file type
    switch (extension) {
      case 'ts':
      case 'tsx':
        return (
          <svg className="h-4 w-4 mr-1.5 text-blue-500 dark:text-blue-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 3H21V21H3V3Z" fill="currentColor" fillOpacity="0.2" />
            <path d="M13 6.5V8H17V18H19V6.5H13Z" fill="currentColor" />
            <path d="M11 18V16.5H7V13H11V11.5H5V18H11Z" fill="currentColor" />
          </svg>
        );
      case 'js':
      case 'jsx':
        return (
          <svg className="h-4 w-4 mr-1.5 text-yellow-500 dark:text-yellow-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 3H21V21H3V3Z" fill="currentColor" fillOpacity="0.2" />
            <path d="M16 12.5C16.2761 12.5 16.5 12.7239 16.5 13V15.5C16.5 16.6046 17.3954 17.5 18.5 17.5V16C18.5 15.4477 18.0523 15 17.5 15V13C17.5 12.1716 16.8284 11.5 16 11.5C15.1716 11.5 14.5 12.1716 14.5 13V15.5C14.5 16.6046 15.3954 17.5 16.5 17.5V16C16.5 15.4477 16.0523 15 15.5 15V13C15.5 12.7239 15.7239 12.5 16 12.5Z" fill="currentColor" />
            <path d="M8 11.5C7.17157 11.5 6.5 12.1716 6.5 13V16C6.5 17.1046 7.39543 18 8.5 18V16.5C7.40228 16.5 7 16 7 16V13.5V13C7 12.7239 7.22386 12.5 7.5 12.5H8.5C8.77614 12.5 9 12.7239 9 13V13.5H10V13C10 12.1716 9.32843 11.5 8.5 11.5H7.5Z" fill="currentColor" />
          </svg>
        );
      case 'py':
        return (
          <svg className="h-4 w-4 mr-1.5 text-green-500 dark:text-green-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8.11426 2C7.40934 2 6.83008 2.57926 6.83008 3.28418V5.71582H12.542C13.2469 5.71582 13.8262 6.29508 13.8262 7V9.78418H16.542C17.2469 9.78418 17.8262 10.3634 17.8262 11.0684V18.7158C17.8262 19.4208 17.2469 20 16.542 20H11.1143C10.4093 20 9.83008 19.4208 9.83008 18.7158V16.2842H4.11426C3.40934 16.2842 2.83008 15.7049 2.83008 15V7.28418C2.83008 6.57926 3.40934 6 4.11426 6H5.83008V3.28418C5.83008 2.01253 6.84261 1 8.11426 1H13.542C14.8137 1 15.8262 2.01253 15.8262 3.28418V5H14.1143V3.28418C14.1143 2.94039 13.8858 2.71582 13.542 2.71582H8.11426C7.77047 2.71582 7.54492 2.94137 7.54492 3.28418V4.28516H8.11426C8.80317 4.28516 9.36523 4.82136 9.36523 5.47656V6H13.8262V7.71582H9.36523V8.24023C9.36523 8.89544 8.80416 9.43164 8.11523 9.43164H7.54492V14.5684H8.11426C8.80317 14.5684 9.36523 15.1046 9.36523 15.7598V16.2842H13.8262V18H9.36523V18.5244C9.36523 19.1796 8.80317 19.7158 8.11426 19.7158H7.54492V16.2842H4.11426C3.77047 16.2842 3.54492 16.0586 3.54492 15.7158V7.28418C3.54492 6.94039 3.77047 6.71582 4.11426 6.71582H5.83008V5.71582H4.11426C3.77047 5.71582 3.54492 5.94137 3.54492 6.28418V14.5684H6.83008V12.8506V11.1348V7.28418C6.83008 6.57926 7.40934 6 8.11426 6H13.1143V7.71582H8.11426C7.77047 7.71582 7.54492 7.94137 7.54492 8.28418V11.1348V12.8506V14.7158C7.54492 15.0586 7.77047 15.2842 8.11426 15.2842H11.1143C11.4581 15.2842 11.6836 15.0586 11.6836 14.7158V11.0684C11.6836 10.7246 11.9092 10.5 12.2529 10.5H16.542C16.8858 10.5 17.1113 10.7246 17.1113 11.0684V18.7158C17.1113 19.0596 16.8858 19.2842 16.542 19.2842H11.1143C10.7705 19.2842 10.5449 19.0596 10.5449 18.7158V17.7148H11.1143C11.8032 17.7148 12.3652 17.1786 12.3652 16.5234V16H16.8262V14.2842H12.3652V13.7598C12.3652 13.1046 11.8042 12.5684 11.1152 12.5684H10.5449V7.43164H11.1143C11.8032 7.43164 12.3652 6.89544 12.3652 6.24023V5.71582H16.8262V4H12.3652V3.47559C12.3652 2.82039 11.8042 2.28418 11.1152 2.28418H10.5449V5.71582H8.11426C7.77047 5.71582 7.54492 5.94137 7.54492 6.28418V9H8.11426C8.45804 9 8.68359 8.77446 8.68359 8.43164V6.71582H11.1143C11.4581 6.71582 11.6836 6.49024 11.6836 6.14746V3.28418C11.6836 2.94141 11.4581 2.71582 11.1143 2.71582H8.11426V2Z" fill="currentColor" />
          </svg>
        );
      case 'json':
        return (
          <svg className="h-4 w-4 mr-1.5 text-purple-500 dark:text-purple-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 2H20V22H4V2Z" fill="currentColor" fillOpacity="0.2" />
            <path d="M15 12.5C15.2761 12.5 15.5 12.7239 15.5 13V15.5C15.5 16.0523 15.0523 16.5 14.5 16.5V18C15.6046 18 16.5 17.1046 16.5 16V13C16.5 12.1716 15.8284 11.5 15 11.5C14.1716 11.5 13.5 12.1716 13.5 13V15.5C13.5 16.6046 14.3954 17.5 15.5 17.5V16C15.5 15.4477 15.0523 15 14.5 15V13C14.5 12.7239 14.7239 12.5 15 12.5Z" fill="currentColor" />
            <path d="M7.5 11.5C6.67157 11.5 6 12.1716 6 13V16C6 17.1046 6.89543 18 8 18V16.5C7.40228 16.5 7 16 7 16V13.5V13C7 12.7239 7.22386 12.5 7.5 12.5H8.5C8.77614 12.5 9 12.7239 9 13V13.5H10V13C10 12.1716 9.32843 11.5 8.5 11.5H7.5Z" fill="currentColor" />
          </svg>
        );
      case 'md':
        return (
          <svg className="h-4 w-4 mr-1.5 text-gray-500 dark:text-gray-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 2H20V22H4V2Z" fill="currentColor" fillOpacity="0.2" />
            <path d="M7 18.5V7.5H9L11 10.5L13 7.5H15V18.5H13V11.5L11 14.5L9 11.5V18.5H7Z" fill="currentColor" />
          </svg>
        );
      case 'env':
      case 'example':
        return (
          <svg className="h-4 w-4 mr-1.5 text-gray-500 dark:text-gray-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 2H20V22H4V2Z" fill="currentColor" fillOpacity="0.2" />
            <path d="M6 6H16V8H6V6Z" fill="currentColor" />
            <path d="M6 9H17V11H6V9Z" fill="currentColor" />
            <path d="M6 12H18V14H6V12Z" fill="currentColor" />
          </svg>
        );
      case 'cfg':
      case 'config':
        return (
          <svg className="h-4 w-4 mr-1.5 text-gray-500 dark:text-gray-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 2H20V22H4V2Z" fill="currentColor" fillOpacity="0.2" />
            <path d="M12 15.5C13.933 15.5 15.5 13.933 15.5 12C15.5 10.067 13.933 8.5 12 8.5C10.067 8.5 8.5 10.067 8.5 12C8.5 13.933 10.067 15.5 12 15.5Z" fill="currentColor" />
          </svg>
        );
      default:
        return (
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            className="h-4 w-4 mr-1.5 text-gray-500 flex-shrink-0"
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" 
            />
          </svg>
        );
    }
  };
  
  // Add utility functions
  const getLanguageFromFileName = (fileName: string): string => {
    if (fileName.endsWith('.ts')) return 'typescript';
    if (fileName.endsWith('.js')) return 'javascript';
    if (fileName.endsWith('.py')) return 'python';
    if (fileName.endsWith('.json')) return 'json';
    if (fileName.endsWith('.java')) return 'java';
    if (fileName.endsWith('.md')) return 'markdown';
    if (fileName.endsWith('.html')) return 'html';
    if (fileName.endsWith('.css')) return 'css';
    if (fileName.endsWith('.yml') || fileName.endsWith('.yaml')) return 'yaml';
    return 'text';
  };

  const handleCopyContent = (content: string) => {
    navigator.clipboard.writeText(content).then(() => {
      // You might want to show a toast notification here
      console.log('Content copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy content:', err);
    });
  };

  const handleDownloadFile = (fileName: string, content: string) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };
  
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
        {state.scripts && Object.keys(state.scripts).length > 0 
          ? "Generated Test Scripts" 
          : "Generate Scripts For Target Frameworks"}
      </h2>
      
      {(generating || jobStatus.data?.status === 'queued' || jobStatus.data?.status === 'processing') && renderProgress()}
      {renderError()}
      
      {(!generating && jobStatus.data?.status !== 'queued' && jobStatus.data?.status !== 'processing') && renderOutput()}
      
      <div className="flex justify-between">
        <button
          onClick={() => {
            // Clear script-related state before navigating back
            setScripts({});
            setScriptJobId(null);
            setSelectedFile(null);
            processedJobRef.current = null;
            
            // If we came from a saved blueprint, go back to input
            if (state.blueprintIsValid && !state.blueprintJobId) {
              setCurrentStep('input');
            } else {
              onBack();
            }
          }}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
        >
          <span className="flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            {state.blueprintIsValid && !state.blueprintJobId ? 'Back to Specification Input' : 'Back to Blueprint'}
          </span>
        </button>
        
        {state.scripts && Object.keys(state.scripts).length > 0 && (
          <div className="flex space-x-3">
            <button
              onClick={() => {
                // Reset all application state before starting a new project
                setScripts({});
                setScriptJobId(null);
                setSelectedFile(null);
                processedJobRef.current = null;
                setBlueprint(null);
                setBlueprintIsValid(false);
                setSpec(null);
                setSpecFormat(null);
                
                // Navigate to input step
                setCurrentStep('input');
              }}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
            >
              Start New Project
            </button>
            <button 
              onClick={() => {
                // TODO: Implement sharing or exporting of the entire project
                alert('This feature is coming soon!');
              }}
              className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md transition-colors"
            >
              <span className="flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                </svg>
                Share Project
              </span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScriptOutput; 