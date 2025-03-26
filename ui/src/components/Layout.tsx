import React from 'react';
import { useAppContext } from '../context/AppContext';
import { AppStep } from '../types/app';
import SpecInput from './SpecInput';
import ModeSelection from './ModeSelection';
import BlueprintView from './BlueprintView';
import ScriptOutput from './ScriptOutput';
import { 
  CheckIcon, 
  DocumentTextIcon, 
  Cog8ToothIcon, 
  EyeIcon, 
  CodeBracketSquareIcon 
} from '@heroicons/react/24/outline';

interface Props {
  children: React.ReactNode;
}

const Layout: React.FC<Props> = ({ children }) => {
  const { state, setCurrentStep } = useAppContext();
  
  const steps = [
    { id: 'input' as AppStep, label: 'Input Spec', icon: DocumentTextIcon },
    { id: 'mode' as AppStep, label: 'Configure', icon: Cog8ToothIcon },
    { id: 'blueprint' as AppStep, label: 'Review Blueprint', icon: EyeIcon },
    { id: 'scripts' as AppStep, label: 'Generate Scripts', icon: CodeBracketSquareIcon }
  ];
  
  const currentStepIndex = steps.findIndex(s => s.id === state.currentStep);

  // Function to determine step status
  const getStepStatus = (index: number): 'complete' | 'current' | 'upcoming' => {
    if (index < currentStepIndex) return 'complete';
    if (index === currentStepIndex) return 'current';
    return 'upcoming';
  };

  // Function to determine if a step is clickable
  const isStepClickable = (index: number): boolean => {
     // Allow clicking previous steps
     return index < currentStepIndex;
  };
  
  const renderStep = () => {
    switch (state.currentStep) {
      case 'input':
        return <SpecInput onNext={() => {
          // If we have a valid blueprint, skip directly to scripts
          if (state.blueprintIsValid && state.blueprint) {
            setCurrentStep('scripts');
          } else {
            setCurrentStep('mode');
          }
        }} />;
      case 'mode':
        // Skip mode selection if we already have a valid blueprint
        if (state.blueprintIsValid && state.blueprint) {
          setCurrentStep('scripts');
          return null;
        }
        return (
          <ModeSelection
            onBack={() => setCurrentStep('input')}
            onNext={() => setCurrentStep('blueprint')}
          />
        );
      case 'blueprint':
        // Only skip blueprint review if we're using a saved blueprint (no job ID)
        // Do NOT skip if we just generated a blueprint (has job ID)
        if (state.blueprintIsValid && state.blueprint && !state.blueprintJobId) {
          setCurrentStep('scripts');
          return null;
        }
        return (
          <BlueprintView
            onBack={() => setCurrentStep('mode')}
            onNext={() => setCurrentStep('scripts')}
          />
        );
      case 'scripts':
        return (
          <ScriptOutput
            onBack={() => setCurrentStep('blueprint')}
          />
        );
      default:
        return null;
    }
  };
  
  return (
    <div className="min-h-screen flex flex-col bg-gray-100 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">API Automation Assistant</h1>
        </div>
      </header>
      
      <div className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col md:flex-row gap-8">
        {/* Stepper Sidebar */}
        <nav className="w-full md:w-64 flex-shrink-0" aria-label="Progress">
          <ol role="list" className="space-y-4 md:space-y-6">
            {steps.map((step, index) => {
              const status = getStepStatus(index);
              const clickable = isStepClickable(index);
              const StepIcon = step.icon;
              return (
                <li key={step.id} className="relative md:flex md:items-center">
                  {/* Connector Line (Mobile) */}
                  {index !== steps.length - 1 ? (
                     <div className="absolute left-4 top-4 -ml-px mt-0.5 h-full w-0.5 bg-gray-300 dark:bg-gray-600 md:hidden" aria-hidden="true" />
                  ) : null}

                  <button
                    onClick={() => clickable && setCurrentStep(step.id)}
                    disabled={!clickable && status !== 'current'}
                    className={`group w-full flex items-center ${clickable ? 'cursor-pointer' : status === 'current' ? 'cursor-default' : 'cursor-not-allowed'}`}
                    aria-current={status === 'current' ? 'step' : undefined}
                  >
                    <span className="flex h-9 items-center" aria-hidden="true">
                      <span className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full ${
                        status === 'complete' ? 'bg-primary-600 group-hover:bg-primary-800' :
                        status === 'current' ? 'border-2 border-primary-500 bg-white dark:bg-gray-900' :
                        'border-2 border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 group-hover:border-gray-400 dark:group-hover:border-gray-500'
                      }`}>
                        {status === 'complete' ? (
                          <CheckIcon className="h-5 w-5 text-white" aria-hidden="true" />
                        ) : status === 'current' ? (
                          <StepIcon className="h-4 w-4 text-primary-500" />
                        ) : (
                          <StepIcon className="h-4 w-4 text-gray-400 dark:text-gray-500" />
                        )}
                      </span>
                    </span>
                    <span className="ml-4 flex min-w-0 flex-col">
                      <span className={`text-sm font-medium ${
                        status === 'current' ? 'text-primary-600 dark:text-primary-400' :
                        status === 'complete' ? 'text-gray-900 dark:text-white' :
                        'text-gray-500 dark:text-gray-400'
                      }`}>
                        {step.label}
                      </span>
                    </span>
                  </button>

                   {/* Connector Line (Desktop) */}
                  {index !== steps.length - 1 ? (
                    <div className="hidden md:block absolute left-4 top-4 -ml-px mt-0.5 h-full w-0.5 bg-gray-300 dark:bg-gray-600" aria-hidden="true" />
                  ) : null}
                </li>
              );
            })}
          </ol>
        </nav>

        {/* Main Content Area */}
        <div className="flex-grow min-w-0">
          {/* Render the active step's component */}
          {renderStep()}
          {/* Render children passed to Layout (like the debug button) */}
          {children}
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-gray-500 dark:text-gray-400 text-sm">
          API Automation Assistant &copy; {new Date().getFullYear()}
        </div>
      </footer>
    </div>
  );
};

export default Layout; 