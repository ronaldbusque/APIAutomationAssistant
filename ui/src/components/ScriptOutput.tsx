import React, { useState, useEffect, useRef } from 'react';
import { useAppContext } from '../context/AppContext';
import { useGenerateScripts, useJobStatus, useWebSocket } from '../hooks/useApi';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';

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
  
  // After the useState declarations at the top of the component, add a new state for tracking expanded directories
  const [expandedDirs, setExpandedDirs] = useState<Record<string, boolean>>({});
  
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
  
  // Add this function to handle autonomous mode progress stages
  const mapAutonomousStage = (stage: string): string => {
    switch (stage) {
      case 'spec_analysis':
        return 'Analyzing OpenAPI Specification';
      case 'blueprint_authoring':
        return 'Creating Blueprint';
      case 'blueprint_reviewing':
        return 'Reviewing Blueprint';
      case 'blueprint_generation_complete':
        return 'Blueprint Completed';
      case 'script_coding':
        return 'Generating Scripts';
      case 'script_reviewing':
        return 'Reviewing Scripts';
      case 'script_generation_complete':
        return 'Scripts Completed';
      case 'completed':
        return 'Generation Complete';
      default:
        return stage.charAt(0).toUpperCase() + stage.slice(1).replace(/_/g, ' ');
    }
  };

  // Regular stage name helper function
  const getStageName = (stage: string): string => {
    switch (stage) {
      case 'planning': 
        return 'Planning Test Structure';
      case 'coding': 
        return 'Generating Test Scripts';
      case 'initializing': 
        return 'Initializing';
      case 'waiting_for_review': 
        return 'Waiting for Review';
      case 'completed': 
        return 'Completed';
      case 'failed': 
        return 'Failed';
      default: 
        return stage.charAt(0).toUpperCase() + stage.slice(1);
    }
  };

  // Handle script generation
  const handleGenerateScripts = async () => {
    // Skip script generation in autonomous mode - it's already being handled
    if (state.isAutonomousMode) {
      console.log("Script generation is handled automatically in autonomous mode");
      return;
    }

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
    if (!jobStatus.data || !jobStatus.data.progress) return null;
    
    const progress = jobStatus.data.progress;
    
    // Check for autonomous mode stages
    const isAutonomousStage = [
      'spec_analysis',
      'blueprint_authoring',
      'blueprint_reviewing',
      'blueprint_generation_complete',
      'script_coding',
      'script_reviewing', 
      'script_generation_complete'
    ].includes(progress.stage);
    
    // Get appropriate stage name
    const stageName = isAutonomousStage ? 
      mapAutonomousStage(progress.stage) : 
      getStageName(progress.stage);
    
    return (
      <div className="mb-8">
        <div className="flex justify-between mb-1">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{stageName}</span>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{`${Math.round(progress.percent)}%`}</span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
          <div 
            className="bg-primary-600 h-2.5 rounded-full transition-all duration-300 ease-in-out" 
            style={{ width: `${progress.percent}%` }}
          ></div>
        </div>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{progress.message}</p>
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
              onClick={() => setShowDebugInfo(!showDebugInfo)}
              className="text-xs px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full flex items-center transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {showDebugInfo ? 'Hide Debug Info' : 'Show Debug Info'}
            </button>
            
            {showDebugInfo && (
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
    const jobData = jobStatus.data;
    
    if (jobData?.status === 'processing' || jobData?.status === 'queued') {
      return (
        <div className="animate-fade-in p-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-300 dark:border-gray-600">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
            {state.isAutonomousMode ? 'Autonomous Generation in Progress' : 'Script Generation in Progress'}
          </h3>
          {renderProgress()}
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            {state.isAutonomousMode ? 
              'AI agents are iteratively generating and refining your test artifacts.' : 
              'Please wait while we generate your test scripts. This may take a few minutes depending on the complexity of your API.'}
          </p>
        </div>
      );
    }
    
    if (jobData?.status === 'completed' && jobData.result) {
      // For autonomous mode, copy the blueprint from the result to state if it exists
      if (state.isAutonomousMode && jobData.result.blueprint && !state.blueprint) {
        setBlueprint(jobData.result.blueprint);
        setBlueprintIsValid(true);
      }
      
      // Continue with existing code to display scripts/files
      // ... (rest of existing renderOutput function)
    }
    
    // ... (rest of existing renderOutput function)
  };
  
  const renderFileContent = () => {
    if (!selectedTarget || !selectedFile || !state.scripts[selectedTarget]?.[selectedFile]) {
      return (
        <div className="h-[calc(100vh-320px)] flex items-center justify-center border border-gray-200 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-900">
          <div className="text-center p-8">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div className="text-gray-500 dark:text-gray-400 mb-2 font-medium">
              {selectedTarget ? 'Select a file to view' : 'Select a target first'}
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-500">
              {selectedTarget 
                ? 'Choose a file from the left panel to view its content'
                : 'Choose a target framework from the dropdown menu above'
              }
            </p>
          </div>
        </div>
      );
    }

    // Get the language for syntax highlighting based on file extension
    const getLanguage = () => {
      if (selectedFile?.endsWith('.ts')) return 'typescript';
      if (selectedFile?.endsWith('.js')) return 'javascript';
      if (selectedFile?.endsWith('.py')) return 'python';
      if (selectedFile?.endsWith('.json')) return 'json';
      if (selectedFile?.endsWith('.java')) return 'java';
      if (selectedFile?.endsWith('.md')) return 'markdown';
      if (selectedFile?.endsWith('.html')) return 'html';
      if (selectedFile?.endsWith('.css')) return 'css';
      if (selectedFile?.endsWith('.yml') || selectedFile?.endsWith('.yaml')) return 'yaml';
      return 'text';
    };

    const content = state.scripts[selectedTarget][selectedFile];
    const language = getLanguage();
    const isDarkMode = document.documentElement.classList.contains('dark');

    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h3 className="font-medium text-gray-800 dark:text-gray-200 flex items-center">
            <span className="mr-2">{selectedFile}</span>
            {selectedFile.endsWith('.ts') && (
              <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded-full">TypeScript</span>
            )}
            {selectedFile.endsWith('.js') && (
              <span className="text-xs px-2 py-0.5 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 rounded-full">JavaScript</span>
            )}
            {selectedFile.endsWith('.py') && (
              <span className="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 rounded-full">Python</span>
            )}
            {selectedFile.endsWith('.json') && (
              <span className="text-xs px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 rounded-full">JSON</span>
            )}
          </h3>
          
          <div className="flex space-x-2">
            <button
              onClick={handleCopy}
              className="px-3 py-1 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md border border-gray-300 dark:border-gray-600 text-sm flex items-center transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-2M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Copy
            </button>
            <button
              onClick={handleDownload}
              className="px-3 py-1 text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded-md border border-primary-300 dark:border-primary-700 text-sm flex items-center transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download
            </button>
          </div>
        </div>
        
        <div className="w-full h-[calc(100vh-320px)] border border-gray-200 dark:border-gray-700 rounded-md overflow-hidden syntax-highlighter-container">
          <SyntaxHighlighter
            language={language}
            style={isDarkMode ? oneDark : oneLight}
            customStyle={{
              margin: 0,
              padding: '1rem',
              height: '100%',
              width: '100%',
              fontSize: '0.875rem',
              lineHeight: '1.5',
              borderRadius: 0,
              backgroundColor: isDarkMode ? '#171717' : '#f9fafb',
              overflowX: 'auto',
              whiteSpace: 'pre'
            }}
            wrapLongLines={false}
            showLineNumbers={true}
            className="overflow-scrollbar"
            lineNumberStyle={{ 
              minWidth: '2.5em', 
              paddingRight: '1em', 
              color: isDarkMode ? '#6b7280' : '#9ca3af',
              borderRight: isDarkMode ? '1px solid #374151' : '1px solid #e5e7eb',
              marginRight: '1em'
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
  
  return (
    <div className="space-y-10">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          {state.isAutonomousMode ? 'Autonomous Generation Output' : 'Script Generation'}
        </h2>
        <button
          onClick={onBack}
          className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
        >
          Back
        </button>
      </div>
      
      {/* Only show the generation button and target selection when NOT in autonomous mode 
          or when autonomous process is complete */}
      {(!state.isAutonomousMode || 
        (jobStatus.data?.status === 'completed' && jobStatus.data?.result)) && (
        <>
          {/* Target Selection */}
          <div className="border-b dark:border-gray-700 pb-4">
            <h3 className="font-medium text-gray-900 dark:text-white mb-3">Target Frameworks</h3>
            <div className="flex flex-wrap gap-2">
              {state.targets.map((target) => (
                <button
                  key={target}
                  onClick={() => handleTargetChange(target)}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                    selectedTarget === target
                      ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-800 dark:text-primary-300 border border-primary-300 dark:border-primary-700'
                      : 'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                  }`}
                >
                  {target.charAt(0).toUpperCase() + target.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
      
      {/* Only show the Generate Scripts button when NOT in autonomous mode */}
      {!state.isAutonomousMode && !state.scriptJobId && state.blueprint && (
        <div className="flex justify-center">
          <button
            onClick={handleGenerateScripts}
            disabled={generating || !state.blueprint}
            className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {generating ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Generating...
              </>
            ) : (
              'Generate Scripts'
            )}
          </button>
        </div>
      )}
      
      {/* Output Display */}
      {renderOutput()}
      
      {/* Error Display */}
      {renderError()}
    </div>
  );
};

export default ScriptOutput; 