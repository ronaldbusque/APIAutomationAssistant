import React, { useEffect, useRef, useState } from 'react';
import * as monaco from 'monaco-editor';
import { editor } from 'monaco-editor';

// Define editor options
const editorOptions: editor.IStandaloneEditorConstructionOptions = {
  language: 'json',
  automaticLayout: true,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  lineNumbers: 'on',
  scrollbar: {
    vertical: 'auto',
    horizontal: 'auto',
  },
  wordWrap: 'on',
  fontFamily: '"JetBrains Mono", monospace',
  fontSize: 14,
  tabSize: 2,
};

interface JsonEditorProps {
  value: string;
  onChange?: (value: string) => void;
  height?: string;
  readOnly?: boolean;
}

const JsonEditor: React.FC<JsonEditorProps> = ({
  value,
  onChange,
  height = '500px',
  readOnly = false,
}) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const [editor, setEditor] = useState<editor.IStandaloneCodeEditor | null>(null);
  const [monacoLoaded, setMonacoLoaded] = useState(false);

  // Initialize editor
  useEffect(() => {
    if (!editorRef.current || editor) return;

    const newEditor = monaco.editor.create(editorRef.current, {
      ...editorOptions,
      value,
      readOnly,
      theme: document.documentElement.classList.contains('dark') ? 'vs-dark' : 'vs',
    });

    // Register onChange handler
    if (onChange) {
      newEditor.onDidChangeModelContent(() => {
        const editorValue = newEditor.getValue();
        onChange(editorValue);
      });
    }

    setEditor(newEditor);
    setMonacoLoaded(true);

    // Cleanup
    return () => {
      newEditor.dispose();
    };
  }, [editorRef, onChange, readOnly]);

  // Update editor value when prop changes
  useEffect(() => {
    if (editor && value !== editor.getValue()) {
      editor.setValue(value);
    }
  }, [value, editor]);

  // Update the theme when system theme changes
  useEffect(() => {
    if (!editor) return;

    const handleThemeChange = (e: MediaQueryListEvent) => {
      monaco.editor.setTheme(e.matches ? 'vs-dark' : 'vs');
    };

    const darkModeMedia = window.matchMedia('(prefers-color-scheme: dark)');
    darkModeMedia.addEventListener('change', handleThemeChange);

    return () => {
      darkModeMedia.removeEventListener('change', handleThemeChange);
    };
  }, [editor]);

  // Format JSON function
  const formatJson = () => {
    if (!editor) return;
    
    try {
      const currentValue = editor.getValue();
      const parsedJson = JSON.parse(currentValue);
      const formattedJson = JSON.stringify(parsedJson, null, 2);
      editor.setValue(formattedJson);
    } catch (error) {
      console.error('Failed to format JSON', error);
    }
  };

  // Validate JSON function
  const validateJson = (): boolean => {
    if (!editor) return false;
    
    try {
      JSON.parse(editor.getValue());
      return true;
    } catch (error) {
      return false;
    }
  };

  return (
    <div className="flex flex-col w-full h-full">
      <div className="h-10 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-3">
        <span className="text-sm font-medium text-gray-500 dark:text-gray-400">JSON Editor</span>
        {!readOnly && (
          <button
            className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300"
            onClick={formatJson}
            title="Format JSON"
          >
            Format
          </button>
        )}
      </div>
      <div 
        ref={editorRef} 
        className="w-full flex-1" 
        style={{ height, minHeight: '200px' }}
      />
      {!monacoLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-white dark:bg-gray-900 bg-opacity-50 dark:bg-opacity-50">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
        </div>
      )}
    </div>
  );
};

// Standalone validate JSON function
export function validateJson(json: string): boolean {
  try {
    JSON.parse(json);
    return true;
  } catch (error) {
    return false;
  }
}

export default JsonEditor; 