import React, { useState, useEffect, useRef } from 'react';
import { useAppContext } from '../context/AppContext';
import { useGenerateScripts, useJobStatus, useWebSocket } from '../hooks/useApi';

interface Props {
  onBack: () => void;
}

const ScriptOutput: React.FC<Props> = ({ onBack }) => {
  const { 
    state, 
    setScriptJobId, 
    setScripts, 
    setTargets, 
    setBlueprint, 
    setBlueprintIsValid,
    setCurrentStep 
  } = useAppContext();
  
  const [selectedTarget, setSelectedTarget] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [blueprintInput, setBlueprintInput] = useState<string>('');
  const [showBlueprintInput, setShowBlueprintInput] = useState<boolean>(false);
  const [showDebugInfo, setShowDebugInfo] = useState<boolean>(false);
  
  const generateScriptsMutation = useGenerateScripts();
  const jobStatus = useJobStatus(state.scriptJobId);
  
  const processedJobRef = useRef<string | null>(null);
  const wsRef = useRef<any>(null);
  
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
  
  // Set initial selected target
  useEffect(() => {
    if (state.targets.length > 0 && !selectedTarget) {
      setSelectedTarget(state.targets[0]);
    }
  }, [state.targets, selectedTarget]);
  
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
        
        // Get available targets from the response
        const availableTargets = Object.keys(scriptsData);
        console.log('Available targets in response:', availableTargets);
        
        // Always select a target that exists in the response
        if (availableTargets.length > 0) {
          // First check if currently selected target exists in the response
          const targetExists = selectedTarget && availableTargets.includes(selectedTarget);
          
          if (!targetExists) {
            // If not, select the first available target
            const newTarget = availableTargets[0];
            console.log(`Selected target "${selectedTarget}" not found in response. Setting target to ${newTarget}`);
            setSelectedTarget(newTarget);
            
            // Set the first file as selected if available for this target
            if (scriptsData[newTarget]) {
              const fileNames = Object.keys(scriptsData[newTarget]);
              if (fileNames.length > 0) {
                console.log(`Setting selected file to ${fileNames[0]}`);
                setSelectedFile(fileNames[0]);
              }
            }
          } else {
            // Target exists, but we might need to update the selected file
            console.log(`Selected target "${selectedTarget}" exists in response`);
            
            // Check if current file still exists, otherwise select first available file
            if (selectedFile && !scriptsData[selectedTarget][selectedFile]) {
              const fileNames = Object.keys(scriptsData[selectedTarget]);
              if (fileNames.length > 0) {
                console.log(`Selected file "${selectedFile}" not found. Setting to ${fileNames[0]}`);
                setSelectedFile(fileNames[0]);
              }
            }
          }
        }
      } else {
        console.error('No valid scripts data found in response');
        setError('No valid scripts data found in the server response');
      }
      
      setGenerating(false);
    } else if (jobStatus.data.status === 'failed') {
      console.error('Script generation failed:', jobStatus.data.error);
      setError(jobStatus.data.error || 'Script generation failed.');
      setGenerating(false);
    }
  }, [jobStatus.data, jobStatus.isLoading, setScripts, selectedTarget, setSelectedTarget, selectedFile]);
  
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
  
  // Handle script generation
  const handleGenerateScripts = async () => {
    setGenerating(true);
    setError(null);
    
    try {
      const request = {
        blueprint: state.blueprint,
        targets: state.targets,
      };
      
      const result = await generateScriptsMutation.mutateAsync(request);
      setScriptJobId(result.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate scripts');
      setGenerating(false);
    }
  };
  
  // Handle target change
  const handleTargetChange = (target: string) => {
    setSelectedTarget(target);
    setSelectedFile(null);
  };
  
  // Handle file selection
  const handleFileSelect = async (file: string) => {
    setSelectedFile(file);
    
    // If we have a file list without content, try to fetch the content
    if (selectedTarget && 
        state.scripts[selectedTarget] && 
        state.scripts[selectedTarget][file] && 
        (state.scripts[selectedTarget][file].startsWith('// Content for') || 
         state.scripts[selectedTarget][file].length < 100)
       ) {
      await fetchFileContent(selectedTarget, file);
    }
  };
  
  // Fetch file content if needed
  const fetchFileContent = async (target: string, filename: string) => {
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
    if (selectedTarget && selectedFile && state.scripts[selectedTarget]?.[selectedFile]) {
      navigator.clipboard.writeText(state.scripts[selectedTarget][selectedFile]);
    }
  };
  
  // Handle download
  const handleDownload = () => {
    if (selectedTarget && selectedFile && state.scripts[selectedTarget]?.[selectedFile]) {
      const content = state.scripts[selectedTarget][selectedFile];
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
    if (!selectedTarget || !state.scripts[selectedTarget]) return;
    
    try {
      // Dynamically import JSZip (with type assertion to avoid TypeScript errors)
      const JSZipModule = await import('jszip');
      const JSZip = JSZipModule.default;
      const zip = new JSZip();
      
      // Add all files to the ZIP
      const files = state.scripts[selectedTarget];
      for (const [filename, content] of Object.entries(files)) {
        // Create directory structure in the ZIP
        zip.file(filename, content);
      }
      
      // Generate ZIP and trigger download
      const zipBlob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(zipBlob);
      
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedTarget}_scripts.zip`;
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
      return <div className="text-center p-8">Loading job status...</div>;
    }
    
    const progress = jobStatus.data?.progress || state.scriptProgress;
    const status = jobStatus.data?.status || 'processing';
    const message = progress?.message || 'Processing...';
    const stage = progress?.stage || 'initializing';
    
    // Get more descriptive stage name
    const getStageName = (stage: string) => {
      switch (stage) {
        case 'planning': return 'Planning Test Structure';
        case 'coding': return 'Generating Test Scripts';
        case 'initializing': return 'Initializing';
        case 'waiting_for_review': return 'Waiting for Review';
        case 'completed': return 'Completed';
        case 'failed': return 'Failed';
        default: return stage.charAt(0).toUpperCase() + stage.slice(1);
      }
    };
    
    return (
      <div className="mb-6 border border-gray-300 dark:border-gray-600 rounded-md p-6 bg-gray-50 dark:bg-gray-800/50">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium">Generation Progress</h3>
          <div className="flex space-x-2">
            <div className="text-xs px-2 py-1 bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 rounded-full capitalize">
              {status}
            </div>
            <button 
              onClick={() => jobStatus.refetch()}
              className="text-xs px-2 py-1 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-full flex items-center"
              title="Manually refresh status"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>
        </div>
        
        <div className="mb-4">
          <div className="flex items-center mb-3">
            <div className="font-medium text-sm">
              {getStageName(stage)}
            </div>
          </div>
          
          {/* Visual animated indicator instead of percentage */}
          <div className="flex items-center">
            <div className="relative w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              {status === 'processing' || status === 'queued' ? (
                <div className="absolute h-full bg-blue-500 animate-progress-pulse"></div>
              ) : status === 'completed' ? (
                <div className="absolute h-full w-full bg-green-500"></div>
              ) : status === 'failed' ? (
                <div className="absolute h-full w-full bg-red-500"></div>
              ) : (
                <div className="absolute h-full w-1/4 bg-blue-500"></div>
              )}
            </div>
          </div>
          
          <div className="mt-3 text-sm text-gray-700 dark:text-gray-300 border-l-2 border-blue-500 pl-3">
            {message}
          </div>
        </div>
        
        {/* Show job details for debugging */}
        <div className="mt-4 flex justify-end">
          <button
            onClick={() => setShowDebugInfo(!showDebugInfo)}
            className="text-xs px-2 py-1 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-full flex items-center"
          >
            {showDebugInfo ? 'Hide Details' : 'Show Details'}
          </button>
        </div>
        
        {showDebugInfo && jobStatus.data && (
          <div className="mt-2 p-3 bg-gray-100 dark:bg-gray-800 rounded-md text-xs font-mono overflow-auto max-h-48">
            <div>
              <strong>Job ID:</strong> {jobStatus.data.job_id}
            </div>
            <div>
              <strong>Status:</strong> {jobStatus.data.status}
            </div>
            <div>
              <strong>Stage:</strong> {progress?.stage || 'N/A'}
            </div>
            <div>
              <strong>Trace ID:</strong> {jobStatus.data.result?.trace_id || 'N/A'}
            </div>
            <div>
              <strong>Last Updated:</strong> {new Date().toLocaleTimeString()}
            </div>
            <div>
              <strong>Message:</strong> {message}
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
      <div className="p-4 mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md text-red-700 dark:text-red-300">
        <div className="flex items-center">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{error}</span>
        </div>
        
        {/* Debug button to show job result data */}
        {jobStatus.data && (
          <div className="mt-2">
            <button
              onClick={() => setShowDebugInfo(!showDebugInfo)}
              className="text-xs px-2 py-1 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-full flex items-center"
            >
              {showDebugInfo ? 'Hide Debug Info' : 'Show Debug Info'}
            </button>
            
            {showDebugInfo && (
              <div className="mt-2 overflow-auto max-h-64 p-2 bg-gray-100 dark:bg-gray-800 rounded-md text-xs font-mono">
                <pre>
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
    console.log('Render output - selectedTarget:', selectedTarget);
    
    if (selectedTarget) {
      console.log('Render output - files for selected target:', 
        state.scripts[selectedTarget] ? Object.keys(state.scripts[selectedTarget]) : 'No files');
    }
    
    // Check if scripts are empty or undefined
    const hasScripts = state.scripts && Object.keys(state.scripts).length > 0;
    console.log('Render output - has scripts:', hasScripts);
    
    // Check if there's a mismatch between selected target and available targets
    if (hasScripts && selectedTarget && !state.scripts[selectedTarget]) {
      // There's a target mismatch, let's fix it
      const availableTargets = Object.keys(state.scripts);
      if (availableTargets.length > 0) {
        console.log(`Target mismatch detected. Selected: ${selectedTarget}, Available: ${availableTargets.join(', ')}`);
        console.log(`Auto-selecting first available target: ${availableTargets[0]}`);
        
        // Using setTimeout to avoid state updates during render
        setTimeout(() => {
          setSelectedTarget(availableTargets[0]);
        }, 0);
      }
    }
    
    if (!hasScripts) {
      return (
        <div className="p-8">
          {!showBlueprintInput && (
            <div className="mb-6 border border-gray-300 dark:border-gray-600 rounded-md p-6 bg-gray-50 dark:bg-gray-800/50">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium">Use Saved Blueprint</h3>
                <div className="flex space-x-2">
                  <label className="px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-md flex items-center text-sm cursor-pointer">
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
                    className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md flex items-center text-sm"
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
            <div className="mb-6 border border-gray-300 dark:border-gray-600 rounded-md p-6 bg-gray-50 dark:bg-gray-800/50">
              <h3 className="text-lg font-medium mb-2">Paste Your Blueprint</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Paste a valid JSON test blueprint to generate scripts:
              </p>
              <textarea
                value={blueprintInput}
                onChange={(e) => setBlueprintInput(e.target.value)}
                className="w-full h-64 p-3 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 rounded-md font-mono text-sm"
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
              ></textarea>
              <div className="flex mt-4 space-x-2 justify-end">
                <button
                  onClick={() => setShowBlueprintInput(false)}
                  className="px-3 py-1 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
                >
                  Cancel
                </button>
                <button
                  onClick={handleBlueprintSubmit}
                  className="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded-md"
                >
                  Use Blueprint
                </button>
              </div>
            </div>
          )}

          {/* Show blueprint status - whether loaded or not */}
          {!showBlueprintInput && (
            <div className="mb-6 border border-gray-300 dark:border-gray-600 rounded-md p-6 bg-gray-50 dark:bg-gray-800/50">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-lg font-medium">Blueprint Status</h3>
                {state.blueprint ? (
                  <div className="flex space-x-2 items-center">
                    <div className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded-full">Ready for Script Generation</div>
                    <button 
                      onClick={() => {
                        setBlueprint(null);
                        setBlueprintIsValid(false);
                      }}
                      className="text-xs px-2 py-1 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-full flex items-center"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Clear
                    </button>
                  </div>
                ) : (
                  <div className="text-xs px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full">No Blueprint Loaded</div>
                )}
              </div>
              {state.blueprint ? (
                <>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Blueprint for <strong>{state.blueprint.apiName || 'Unknown API'}</strong> has been loaded successfully.
                  </p>
                  <div className="mt-2 text-xs text-gray-500">
                    <span className="font-medium">Contains:</span> {state.blueprint.groups?.length || 0} test groups with {' '}
                    {state.blueprint.groups?.reduce((total: number, group: any) => total + (group.tests?.length || 0), 0) || 0} tests
                  </div>
                </>
              ) : (
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Please upload or paste a blueprint, or navigate back to generate one from your API specification.
                </p>
              )}
            </div>
          )}

          <div className="mb-6 border border-gray-300 dark:border-gray-600 rounded-md p-6 bg-gray-50 dark:bg-gray-800/50">
            <h3 className="text-lg font-medium mb-4">Target Frameworks</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Select the frameworks you want to generate test scripts for:
            </p>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {['postman', 'playwright', 'python', 'typescript', 'java'].map((target) => (
                <label 
                  key={target}
                  className={`flex items-center p-3 rounded-md border ${
                    state.targets.includes(target)
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                      : 'border-gray-300 dark:border-gray-600'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={state.targets.includes(target)}
                    onChange={() => {
                      const newTargets = [...state.targets];
                      const index = newTargets.indexOf(target);
                      
                      if (index === -1) {
                        newTargets.push(target);
                      } else {
                        newTargets.splice(index, 1);
                      }
                      
                      setTargets(newTargets);
                    }}
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                  />
                  <span className="ml-2 capitalize">{target}</span>
                </label>
              ))}
            </div>
          </div>
          
          <div className="text-center">
            <button 
              onClick={handleGenerateScripts}
              disabled={generating || state.targets.length === 0 || !state.blueprint}
              className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center mx-auto shadow-md"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span className="font-medium text-lg">{generating ? 'Generating Scripts...' : 'Generate Scripts'}</span>
            </button>
            {state.targets.length === 0 && (
              <p className="mt-2 text-sm text-orange-500">Please select at least one target framework</p>
            )}
            {!state.blueprint && (
              <p className="mt-2 text-sm text-orange-500">Please upload/paste a blueprint or navigate back to create one</p>
            )}
          </div>
        </div>
      );
    }
    
    return (
      <div className="flex flex-col md:flex-row gap-4">
        {/* Target and file selector */}
        <div className="w-full md:w-64 space-y-4">
          <div>
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Target</h3>
            <select
              value={selectedTarget || ''}
              onChange={(e) => handleTargetChange(e.target.value)}
              className="w-full p-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 rounded-md"
            >
              {Object.keys(state.scripts).map((target) => (
                <option key={target} value={target}>
                  {target}
                </option>
              ))}
            </select>
          </div>
          
          {selectedTarget && (
            <div>
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Files</h3>
                <button
                  onClick={handleDownloadAllFiles}
                  className="text-xs px-2 py-1 text-primary-700 dark:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded-md border border-primary-300 dark:border-primary-700 flex items-center"
                >
                  <svg 
                    xmlns="http://www.w3.org/2000/svg" 
                    className="h-3 w-3 mr-1"
                    fill="none" 
                    viewBox="0 0 24 24" 
                    stroke="currentColor"
                  >
                    <path 
                      strokeLinecap="round" 
                      strokeLinejoin="round" 
                      strokeWidth={2} 
                      d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" 
                    />
                  </svg>
                  Download All as ZIP
                </button>
              </div>
              <div className="border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden max-h-96 overflow-y-auto">
                {(() => {
                  // Group files by directory
                  const filesByDir: Record<string, string[]> = {};
                  const rootFiles: string[] = [];
                  
                  // Organize files into directories
                  Object.keys(state.scripts[selectedTarget] || {}).forEach(file => {
                    if (file.includes('/')) {
                      // Split path and extract directory
                      const parts = file.split('/');
                      const dirPath = parts.slice(0, -1).join('/');
                      
                      if (!filesByDir[dirPath]) {
                        filesByDir[dirPath] = [];
                      }
                      filesByDir[dirPath].push(file);
                    } else {
                      rootFiles.push(file);
                    }
                  });
                  
                  // Render directory structure
                  const renderDir = (dirPath: string, level: number) => {
                    const dirName = dirPath.split('/').pop();
                    const indent = level * 12;
                    
                    return (
                      <div key={dirPath}>
                        <div 
                          className="block w-full text-left px-3 py-2 text-sm border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 font-medium"
                          style={{ paddingLeft: `${indent + 12}px` }}
                        >
                          <span className="flex items-center">
                            <svg 
                              xmlns="http://www.w3.org/2000/svg" 
                              className="h-4 w-4 mr-1 text-gray-500"
                              fill="none" 
                              viewBox="0 0 24 24" 
                              stroke="currentColor"
                            >
                              <path 
                                strokeLinecap="round" 
                                strokeLinejoin="round" 
                                strokeWidth={2} 
                                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" 
                              />
                            </svg>
                            {dirName}
                          </span>
                        </div>
                        
                        {filesByDir[dirPath].map(file => {
                          const fileName = file.split('/').pop();
                          return (
                            <button
                              key={file}
                              onClick={() => handleFileSelect(file)}
                              className={`block w-full text-left px-3 py-2 text-sm border-b border-gray-200 dark:border-gray-700 last:border-b-0 ${
                                selectedFile === file
                                  ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                                  : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                              }`}
                              style={{ paddingLeft: `${indent + 24}px` }}
                            >
                              <span className="flex items-center">
                                <svg 
                                  xmlns="http://www.w3.org/2000/svg" 
                                  className="h-4 w-4 mr-1 text-gray-500"
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
                                {fileName}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    );
                  };
                  
                  // Get all unique top-level directories
                  const topDirs = Object.keys(filesByDir).filter(dir => !dir.includes('/'));
                  
                  // Process subdirectories
                  const processedDirs = new Set<string>();
                  const allDirs = Object.keys(filesByDir).sort();
                  
                  // Build full directory structure
                  return (
                    <>
                      {/* Root files first */}
                      {rootFiles.map(file => (
                        <button
                          key={file}
                          onClick={() => handleFileSelect(file)}
                          className={`block w-full text-left px-3 py-2 text-sm border-b border-gray-200 dark:border-gray-700 last:border-b-0 ${
                            selectedFile === file
                              ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                              : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                          }`}
                          style={{ paddingLeft: '12px' }}
                        >
                          <span className="flex items-center">
                            <svg 
                              xmlns="http://www.w3.org/2000/svg" 
                              className="h-4 w-4 mr-1 text-gray-500"
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
                            {file}
                          </span>
                        </button>
                      ))}
                      
                      {/* Process all directories by level */}
                      {allDirs.map(dir => {
                        // Skip if already processed
                        if (processedDirs.has(dir)) return null;
                        processedDirs.add(dir);
                        
                        // Calculate directory level
                        const level = dir.split('/').length;
                        
                        return renderDir(dir, level - 1);
                      })}
                    </>
                  );
                })()}
              </div>
            </div>
          )}
        </div>
        
        {/* Script content */}
        <div className="flex-grow">
          {selectedTarget && selectedFile ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="font-medium">{selectedFile}</h3>
                <div className="flex space-x-2">
                  <button
                    onClick={handleCopy}
                    className="px-3 py-1 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md border border-gray-300 dark:border-gray-600 text-sm"
                  >
                    Copy
                  </button>
                  <button
                    onClick={handleDownload}
                    className="px-3 py-1 text-primary-700 dark:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded-md border border-primary-300 dark:border-primary-700 text-sm"
                  >
                    Download
                  </button>
                </div>
              </div>
              
              <pre className="w-full h-96 p-4 bg-gray-100 dark:bg-gray-800 rounded-md overflow-auto font-mono text-sm border border-gray-300 dark:border-gray-600">
                {state.scripts[selectedTarget][selectedFile]}
              </pre>
            </div>
          ) : (
            <div className="h-96 flex items-center justify-center border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-800">
              <div className="text-gray-500 dark:text-gray-400">
                {selectedTarget ? 'Select a file to view' : 'Select a target first'}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };
  
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">
        {state.scripts && Object.keys(state.scripts).length > 0 
          ? "Generated Scripts" 
          : "Generate Scripts For Target Frameworks"}
      </h2>
      
      {/* Debug Tools for Development (hidden in production) */}
      {process.env.NODE_ENV === 'development' && (
        <div className="mb-4 p-3 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-800/50">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Development Debug Tools</h3>
            <button
              onClick={() => setShowDebugInfo(!showDebugInfo)}
              className="text-xs px-2 py-1 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-full"
            >
              {showDebugInfo ? 'Hide Debug' : 'Show Debug'}
            </button>
          </div>
          
          {showDebugInfo && (
            <div className="mt-2">
              <h4 className="text-xs font-medium mb-1">Scripts Data Structure:</h4>
              <pre className="text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded-md overflow-auto max-h-48">
                {JSON.stringify(state.scripts, null, 2)}
              </pre>
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => {
                    // Force refresh the scripts from the backend
                    if (state.scriptJobId) {
                      fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/status/${state.scriptJobId}`)
                        .then(res => res.json())
                        .then(data => {
                          if (data.result?.scripts) {
                            console.log('Refreshed scripts data:', data.result.scripts);
                            setScripts(data.result.scripts);
                          } else {
                            console.error('No scripts in refresh response');
                          }
                        })
                        .catch(err => console.error('Error refreshing scripts:', err));
                    }
                  }}
                  className="text-xs px-2 py-1 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded"
                >
                  Refresh Scripts
                </button>
                <button
                  onClick={() => {
                    // Reset selected target to force re-selection
                    setSelectedTarget(null);
                    setSelectedFile(null);
                  }}
                  className="text-xs px-2 py-1 bg-orange-100 text-orange-700 hover:bg-orange-200 rounded"
                >
                  Reset Selection
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      
      {(generating || jobStatus.data?.status === 'queued' || jobStatus.data?.status === 'processing') && renderProgress()}
      {renderError()}
      
      {(!generating && jobStatus.data?.status !== 'queued' && jobStatus.data?.status !== 'processing') && renderOutput()}
      
      <div className="flex justify-between">
        <button
          onClick={() => {
            // If we came from a saved blueprint, go back to input
            if (state.blueprintIsValid && !state.blueprintJobId) {
              setCurrentStep('input');
            } else {
              onBack();
            }
          }}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
        >
          {state.blueprintIsValid && !state.blueprintJobId ? 'Back to Input' : 'Back to Blueprint'}
        </button>
      </div>
    </div>
  );
};

export default ScriptOutput; 