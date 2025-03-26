import React from 'react';
import { useAppContext } from '../context/AppContext';
import { AppStep } from '../types/app';
import SpecInput from './SpecInput';
import ModeSelection from './ModeSelection';
import BlueprintView from './BlueprintView';
import ScriptOutput from './ScriptOutput';

interface Props {
  children: React.ReactNode;
}

const Layout: React.FC<Props> = ({ children }) => {
  const { state, setCurrentStep } = useAppContext();
  
  const steps = [
    { id: 'input' as AppStep, label: 'Input Spec' },
    { id: 'mode' as AppStep, label: 'Generate Blueprint' },
    { id: 'blueprint' as AppStep, label: 'Review Blueprint' },
    { id: 'scripts' as AppStep, label: 'Generate Scripts' }
  ];
  
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
    <div className="min-h-screen flex flex-col bg-gray-900">
      {/* Header - FIXED WIDTH */}
      <header className="bg-gray-800 text-white shadow-md">
        <div className="max-w-5xl mx-auto px-4 py-3 w-full flex justify-center items-center">
          <h1 className="text-xl font-bold">API Automation Assistant</h1>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="flex-grow flex">
        {/* Stepper */}
        <div className="w-64 bg-gray-800 py-8 px-6 hidden md:block">
          <nav>
            <ul className="relative space-y-6">
              {/* Continuous vertical line for all steps */}
              <div className="stepper-line top-4 bottom-4"></div>
              
              {steps.map((step, index) => (
                <li key={step.id} className="relative z-10">
                  {/* Active step line segments - show when step is active or passed */}
                  {index > 0 && steps.indexOf(steps.find(s => s.id === state.currentStep)!) >= index && (
                    <div className="stepper-line-active top-0 -mt-6 h-6"></div>
                  )}
                  
                  {/* Step button */}
                  <button
                    onClick={() => setCurrentStep(step.id)}
                    disabled={steps.indexOf(steps.find(s => s.id === state.currentStep)!) < index}
                    className={`flex items-center w-full px-3 py-2 rounded-md transition-colors ${
                      state.currentStep === step.id
                        ? 'bg-blue-900/40 text-blue-400'
                        : steps.indexOf(steps.find(s => s.id === state.currentStep)!) >= index
                          ? 'text-gray-300 hover:bg-gray-700'
                          : 'text-gray-500 cursor-not-allowed'
                    }`}
                  >
                    {/* Step number */}
                    <span className={`relative z-20 flex items-center justify-center h-8 w-8 rounded-full mr-3 text-sm ${
                      state.currentStep === step.id
                        ? 'bg-blue-500 text-white'
                        : steps.indexOf(steps.find(s => s.id === state.currentStep)!) > index
                          ? 'bg-green-500 text-white'
                          : 'bg-gray-700 text-gray-400'
                    }`}>
                      {index + 1}
                    </span>
                    <span className="font-medium">{step.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        
        {/* Content - FIXED WIDTH */}
        <div className="flex-grow py-6 px-4 overflow-y-auto flex justify-center">
          <div className="max-w-5xl w-full">
            {renderStep()}
            {children}
          </div>
        </div>
      </main>
      
      {/* Footer - FIXED WIDTH */}
      <footer className="bg-gray-800 border-t border-gray-700 py-4">
        <div className="max-w-5xl mx-auto px-4 w-full text-center text-gray-400 text-sm">
          API Automation Assistant &copy; 2023
        </div>
      </footer>
    </div>
  );
};

export default Layout; 