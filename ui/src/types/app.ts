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
  isAutonomousMode: boolean;
  
  // Jobs and progress
  blueprintJobId: string | null;
  blueprintProgress: {
    stage: string;
    percent: number;
    message: string;
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
  business_rules?: string;
  test_data?: string;
  test_flow?: string;
}

export interface GenerateScriptsRequest {
  blueprint: any;
  targets: string[];
}

export interface GenerateAutonomousRequest {
  spec: string;
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
  };
  result?: any;
  error?: string;
} 