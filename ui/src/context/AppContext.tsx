import React, { createContext, useContext, ReactNode, useState } from 'react';
import { AppState, AppStep } from '../types/app';

// Initial state
const initialState: AppState = {
  currentStep: 'input',
  spec: null,
  specFormat: null,
  specValidation: {
    isValid: false,
    warnings: [],
    errors: [],
  },
  mode: 'basic',
  businessRules: '',
  testData: '',
  testFlow: '',
  target: 'postman',
  maxIterations: 3,
  blueprintJobId: null,
  blueprintProgress: {
    stage: '',
    percent: 0,
    message: '',
  },
  blueprint: null,
  blueprintValidation: {
    isValid: false,
    warnings: [],
    errors: [],
  },
  scriptJobId: null,
  scriptProgress: {
    stage: '',
    percent: 0,
    message: '',
    files: {},
  },
  scripts: {},
  openApiSpec: '',
  blueprintIsValid: false,
};

// Context type
interface AppContextType {
  state: AppState;
  setCurrentStep: (step: AppStep) => void;
  setSpec: (spec: string | null) => void;
  setSpecFormat: (format: 'yaml' | 'json' | null) => void;
  setMode: (mode: 'basic' | 'advanced') => void;
  setBusinessRules: (rules: string) => void;
  setTestData: (data: string) => void;
  setTestFlow: (flow: string) => void;
  setTarget: (target: string | null) => void;
  setMaxIterations: (iterations: number) => void;
  setBlueprintJobId: (id: string | null) => void;
  setBlueprintProgress: (progress: AppState['blueprintProgress']) => void;
  setBlueprint: (blueprint: any) => void;
  setBlueprintValidation: (validation: AppState['blueprintValidation']) => void;
  setScriptJobId: (id: string | null) => void;
  setScriptProgress: (progress: AppState['scriptProgress']) => void;
  setScripts: (scripts: Record<string, Record<string, string>>) => void;
  setOpenApiSpec: (spec: string) => void;
  setBlueprintIsValid: (isValid: boolean) => void;
}

// Create context
const AppContext = createContext<AppContextType | null>(null);

// Provider component
interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [state, setState] = useState<AppState>(initialState);

  const setCurrentStep = (step: AppStep) => {
    setState(prev => ({ ...prev, currentStep: step }));
  };

  const setSpec = (spec: string | null) => {
    setState(prev => ({ ...prev, spec }));
  };

  const setSpecFormat = (format: 'yaml' | 'json' | null) => {
    setState(prev => ({ ...prev, specFormat: format }));
  };

  const setMode = (mode: 'basic' | 'advanced') => {
    setState(prev => ({ ...prev, mode }));
  };

  const setBusinessRules = (rules: string) => {
    setState(prev => ({ ...prev, businessRules: rules }));
  };

  const setTestData = (data: string) => {
    setState(prev => ({ ...prev, testData: data }));
  };

  const setTestFlow = (flow: string) => {
    setState(prev => ({ ...prev, testFlow: flow }));
  };

  const setTarget = (target: string | null) => {
    setState(prev => ({ ...prev, target }));
  };

  const setMaxIterations = (iterations: number) => {
    setState(prev => ({ ...prev, maxIterations: iterations }));
  };

  const setBlueprintJobId = (id: string | null) => {
    setState(prev => ({ ...prev, blueprintJobId: id }));
  };

  const setBlueprintProgress = (progress: AppState['blueprintProgress']) => {
    setState(prev => ({ ...prev, blueprintProgress: progress }));
  };

  const setBlueprint = (blueprint: any) => {
    setState(prev => ({ ...prev, blueprint }));
  };

  const setBlueprintValidation = (validation: AppState['blueprintValidation']) => {
    setState(prev => ({ ...prev, blueprintValidation: validation }));
  };

  const setScriptJobId = (id: string | null) => {
    setState(prev => ({ ...prev, scriptJobId: id }));
  };

  const setScriptProgress = (progress: AppState['scriptProgress']) => {
    setState(prev => ({ ...prev, scriptProgress: progress }));
  };

  const setScripts = (scripts: Record<string, Record<string, string>>) => {
    setState(prev => ({ ...prev, scripts }));
  };

  const setOpenApiSpec = (spec: string) => {
    setState(prev => ({ ...prev, openApiSpec: spec }));
  };

  const setBlueprintIsValid = (isValid: boolean) => {
    setState(prev => ({ ...prev, blueprintIsValid: isValid }));
  };

  const value = {
    state,
    setCurrentStep,
    setSpec,
    setSpecFormat,
    setMode,
    setBusinessRules,
    setTestData,
    setTestFlow,
    setTarget,
    setMaxIterations,
    setBlueprintJobId,
    setBlueprintProgress,
    setBlueprint,
    setBlueprintValidation,
    setScriptJobId,
    setScriptProgress,
    setScripts,
    setOpenApiSpec,
    setBlueprintIsValid,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

// Hook for using the context
export const useAppContext = (): AppContextType => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
}; 