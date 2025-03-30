export type AppStep = 'input' | 'mode' | 'blueprint' | 'scripts';

export interface AppState {
  // Current step in the workflow
  currentStep: AppStep;
  
  // Input spec data
  spec: string | null;
  specFormat: 'yaml' | 'json' | null;
  specValidation: {
    isValid: boolean;
    warnings: string[];
    errors: string[];
  };
  
  // Mode selection
  mode: string | null;
  businessRules: string;
  testData: string;
  testFlow: string;
  targets: string[];
  maxIterations: number;
  
  // Jobs and progress
  blueprintJobId: string | null;
  blueprintProgress: {
    stage: string;
    percent: number;
    message: string;
    autonomous_stage?: string;
    agent?: string;
  };
  
  // Blueprint data
  blueprint: any;
  blueprintValidation: {
    isValid: boolean;
    warnings: string[];
    errors: string[];
  };
  
  // Script generation
  scriptJobId: string | null;
  scriptProgress: {
    stage: string;
    percent: number;
    message: string;
    autonomous_stage?: string;
    target?: string;
    agent?: string;
    files: {
      [target: string]: {
        name: string;
        status: 'pending' | 'generating' | 'completed';
      }[];
    };
  };
  
  // Generated scripts
  scripts: Record<string, Record<string, string>>;
  
  // Add any other state properties here
  openApiSpec: string;
  blueprintIsValid: boolean;
}

export interface GenerateBlueprintRequest {
  spec: string;
  mode: 'basic' | 'advanced';
  max_iterations?: number;
}

export interface GenerateScriptsRequest {
  blueprint: any;
  targets: string[];
  max_iterations?: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress?: {
    stage: string;
    percent: number;
    message: string;
    autonomous_stage?: string;
    target?: string;
    agent?: string;
  };
  result?: any;
  error?: string;
} 