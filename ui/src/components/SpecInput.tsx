import React, { useState } from 'react';
import { useAppContext } from '../context/AppContext';

interface Props {
  onNext: () => void;
}

type InputMethod = 'url' | 'paste' | 'file' | 'blueprint';

const SpecInput: React.FC<Props> = ({ onNext }) => {
  const {
    state,
    setSpec,
    setSpecFormat,
    setCurrentStep,
    setBlueprint,
    setBlueprintIsValid,
    setOpenApiSpec
  } = useAppContext();
  
  const [activeTab, setActiveTab] = useState<InputMethod>('url');
  const [specUrl, setSpecUrl] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showContent, setShowContent] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number | null>(null);
  const [blueprintInput, setBlueprintInput] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [pasteInput, setPasteInput] = useState('');
  const [fileInput, setFileInput] = useState<File | null>(null);

  const handleUrlSubmit = async () => {
    setError(null);
    setLoading(true);
    
    if (!urlInput.trim()) {
      setError('Please enter a valid URL');
      setLoading(false);
      return;
    }
    
    try {
      // Fetch the spec from the URL
      const response = await fetch(urlInput);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch spec: ${response.status} ${response.statusText}`);
      }
      
      const text = await response.text();
      
      // Determine format based on content or URL extension
      let format: 'yaml' | 'json' = 'json';
      
      if (urlInput.endsWith('.yaml') || urlInput.endsWith('.yml')) {
        format = 'yaml';
      } else {
        // Try to parse as JSON to validate format
        try {
          JSON.parse(text);
          format = 'json';
        } catch {
          format = 'yaml';
        }
      }
      
      // Set the spec in state
      setSpec(text);
      setSpecFormat(format);
      setOpenApiSpec(text);
      
      // Reset blueprint state for new specifications
      setBlueprint(null);
      setBlueprintIsValid(false);
      
      // Move to next step
      onNext();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch spec');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    
    // Check if a file was selected
    if (!event.target.files || event.target.files.length === 0) {
      return;
    }
    
    const file = event.target.files[0];
    
    // Check file size (max 1MB)
    if (file.size > 1024 * 1024) {
      setError('File size exceeds the maximum limit of 1MB');
      return;
    }
    
    setFileInput(file);
    setUploadedFileName(file.name);
    setFileSize(file.size);
    
    // Determine format based on file extension
    const format: 'yaml' | 'json' = 
      file.name.endsWith('.json') ? 'json' : 'yaml';
    
    // Read file contents
    const reader = new FileReader();
    
    reader.onload = (e) => {
      if (e.target && typeof e.target.result === 'string') {
        const content = e.target.result;
        setSpec(content);
        setSpecFormat(format);
        setOpenApiSpec(content);
      }
    };
    
    reader.onerror = () => {
      setError('Failed to read file');
    };
    
    reader.readAsText(file);
  };

  const handlePasteSubmit = () => {
    setError(null);
    
    if (!pasteInput.trim()) {
      setError('Please enter an OpenAPI specification');
      return;
    }
    
    // Determine format based on content
    let format: 'yaml' | 'json' = 'json';
    
    // Try to parse as JSON to validate format
    try {
      JSON.parse(pasteInput);
      format = 'json';
    } catch {
      format = 'yaml';
    }
    
    // Set the spec in state
    setSpec(pasteInput);
    setSpecFormat(format);
    setOpenApiSpec(pasteInput);
    
    // Reset blueprint state for new specifications
    setBlueprint(null);
    setBlueprintIsValid(false);
    
    // Move to next step
    onNext();
  };

  // Handle blueprint submission
  const handleBlueprintSubmit = () => {
    setError(null);
    
    if (!blueprintInput.trim()) {
      setError('Please enter a valid blueprint');
      return;
    }
    
    try {
      // Parse the JSON blueprint
      const parsedBlueprint = JSON.parse(blueprintInput);
      
      // Set the blueprint in state
      setBlueprint(parsedBlueprint);
      setBlueprintIsValid(true);
      
      // Skip to scripts step
      setCurrentStep('scripts');
    } catch (err) {
      setError('Invalid JSON format. Please ensure your blueprint is a valid JSON object.');
    }
  };
  
  // Handle blueprint file upload
  const handleBlueprintFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) {
      return;
    }
    
    const file = e.target.files[0];
    
    // Check file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      setError('File size exceeds the limit of 2MB');
      return;
    }
    
    // Check file extension
    if (!file.name.endsWith('.json')) {
      setError('Please upload a JSON file');
      return;
    }
    
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const content = event.target?.result as string;
        setBlueprintInput(content);
        // Optionally, immediately process the blueprint
        try {
          const blueprintJson = JSON.parse(content);
          handleSubmitBlueprint(blueprintJson);
        } catch (error) {
          setError('Invalid JSON format in the uploaded file');
        }
      } catch (error) {
        setError('Error reading the file');
      }
    };
    
    reader.onerror = () => {
      setError('Error reading the file');
    };
    
    reader.readAsText(file);
  };

  const handleSubmitBlueprint = (blueprintJson?: any) => {
    try {
      // If blueprint is passed directly, use it, otherwise parse from input
      const blueprint = blueprintJson || JSON.parse(blueprintInput);
      
      // Update the app context with the blueprint
      setBlueprint(blueprint);
      setBlueprintIsValid(true);
      
      // Skip directly to the scripts step, bypassing mode selection and blueprint generation
      setCurrentStep('scripts');
      
      // Call the onNext prop to advance in the workflow
      onNext();
    } catch (error) {
      setError('Invalid JSON format. Please check your blueprint.');
    }
  };

  const renderFileUpload = () => {
    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        
        // Create a synthetic event object
        const syntheticEvent = {
          target: {
            files: e.dataTransfer.files
          }
        } as React.ChangeEvent<HTMLInputElement>;
        
        handleFileUpload(syntheticEvent);
      }
    };
    
    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
    };
    
    return (
      <div className="mt-2">
        <div
          className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 flex flex-col items-center justify-center cursor-pointer hover:border-primary-500 dark:hover:border-primary-400 transition-colors bg-white dark:bg-gray-800"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onClick={() => document.getElementById('file-upload')?.click()}
        >
          <svg className="w-16 h-16 text-gray-400 dark:text-gray-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          
          {uploadedFileName ? (
            <div className="text-center">
              <p className="text-lg font-medium text-gray-700 dark:text-gray-300">
                {uploadedFileName}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {(fileSize ? (fileSize / 1024).toFixed(2) : '')} KB
              </p>
              <button
                type="button"
                className="mt-4 px-3 py-1 text-sm text-red-600 dark:text-red-400 hover:text-red-500 dark:hover:text-red-300 border border-red-200 dark:border-red-800 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20"
                onClick={(e) => {
                  e.stopPropagation();
                  setFileInput(null);
                  setUploadedFileName(null);
                  setFileSize(null);
                }}
              >
                Remove file
              </button>
            </div>
          ) : (
            <div className="text-center">
              <p className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">
                Drag and drop your file here
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                or click to select a file
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-500 mt-4">
                Supports YAML or JSON files (max 1MB)
              </p>
            </div>
          )}
          
          <input
            id="file-upload"
            type="file"
            accept=".yaml,.yml,.json"
            className="hidden"
            onChange={handleFileUpload}
          />
        </div>
        
        {fileInput && (
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              className="px-5 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md transition-colors font-medium"
              onClick={() => {
                // Reset blueprint state for new specifications
                setBlueprint(null);
                setBlueprintIsValid(false);
                onNext();
              }}
            >
              Continue with Selected File
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">Input API Specification</h2>
      
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="flex border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
          <button
            className={`px-5 py-3 font-medium text-sm focus:outline-none transition-colors ${
              activeTab === 'url' 
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500 dark:border-primary-400 bg-white dark:bg-gray-800' 
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            onClick={() => setActiveTab('url')}
          >
            URL
          </button>
          <button
            className={`px-5 py-3 font-medium text-sm focus:outline-none transition-colors ${
              activeTab === 'paste' 
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500 dark:border-primary-400 bg-white dark:bg-gray-800' 
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            onClick={() => setActiveTab('paste')}
          >
            Paste
          </button>
          <button
            className={`px-5 py-3 font-medium text-sm focus:outline-none transition-colors ${
              activeTab === 'file' 
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500 dark:border-primary-400 bg-white dark:bg-gray-800' 
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            onClick={() => setActiveTab('file')}
          >
            Upload
          </button>
          <button
            className={`px-5 py-3 font-medium text-sm focus:outline-none transition-colors ${
              activeTab === 'blueprint' 
                ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-500 dark:border-primary-400 bg-white dark:bg-gray-800' 
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            onClick={() => setActiveTab('blueprint')}
          >
            Use Blueprint
          </button>
        </div>
        
        {/* Error message */}
        {error && (
          <div className="m-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md text-red-700 dark:text-red-300">
            <div className="flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{error}</span>
            </div>
          </div>
        )}
        
        <div className="p-6">
          {/* Tab content */}
          {activeTab === 'paste' && (
            <div>
              <p className="mb-2 text-sm text-gray-600 dark:text-gray-400">
                Paste your OpenAPI specification in JSON or YAML format
              </p>
              <textarea
                value={pasteInput}
                onChange={(e) => setPasteInput(e.target.value)}
                placeholder={'# Example OpenAPI Spec\nopenapi: 3.0.0\ninfo:\n  title: Example API\n  version: 1.0.0\npaths:\n  /users:\n    get:\n      summary: Get users\n      responses:\n        \'200\':\n          description: Success'}
                className="w-full h-80 p-4 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-md font-mono text-sm resize-y text-gray-800 dark:text-gray-300"
                spellCheck="false"
              />
              <div className="mt-6 flex justify-end">
                <button
                  disabled={!pasteInput.trim() || loading}
                  onClick={handlePasteSubmit}
                  className="px-6 py-2.5 bg-primary-600 hover:bg-primary-700 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  {loading ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Processing...
                    </span>
                  ) : (
                    'Continue'
                  )}
                </button>
              </div>
            </div>
          )}
          
          {activeTab === 'file' && renderFileUpload()}
          
          {activeTab === 'url' && (
            <div>
              <p className="mb-2 text-sm text-gray-600 dark:text-gray-400">
                Enter the URL of your OpenAPI specification
              </p>
              <div className="flex">
                <input
                  type="url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="https://example.com/openapi.yaml"
                  className="flex-1 p-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-l-md text-gray-800 dark:text-gray-300 focus:ring-primary-500 focus:border-primary-500"
                />
                <button
                  disabled={!urlInput.trim() || loading}
                  onClick={handleUrlSubmit}
                  className="px-5 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-r-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  {loading ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Fetching...
                    </span>
                  ) : (
                    'Fetch'
                  )}
                </button>
              </div>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Supports both YAML and JSON formats. The URL must be publicly accessible.
              </p>
            </div>
          )}
          
          {activeTab === 'blueprint' && (
            <div className="text-center py-6">
              <div className="mb-6 border border-gray-200 dark:border-gray-600 rounded-md p-6 bg-gray-50 dark:bg-gray-800/50">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto mb-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">Use Saved Blueprint</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                  If you have a previously saved test blueprint, you can skip directly to the script generation page where you can upload or paste your blueprint.
                </p>
                <button
                  onClick={() => setCurrentStep('scripts')}
                  className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-md shadow-sm flex items-center mx-auto"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                  <span className="font-medium">Continue to Script Generation</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SpecInput; 