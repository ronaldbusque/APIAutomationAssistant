import React, { useState } from 'react';
import { AppProvider } from './context/AppContext';
import { 
  useGenerateBlueprint, 
  useGenerateScripts, 
  useGenerateAutonomous 
} from './hooks/useApi';
import { useAppContext } from './context/AppContext';
import { useNavigation } from './hooks/useNavigation';
import { AppStep } from './types/app';

// Components
import Layout from './components/Layout';
import SpecInput from './components/SpecInput';
import ModeSelection from './components/ModeSelection';
import BlueprintView from './components/BlueprintView';
import ScriptOutput from './components/ScriptOutput';

const App: React.FC = () => {
  const { state, setCurrentStep, setIsAutonomousMode } = useAppContext();
  const { canGoBack, canGoForward, goBack, goForward } = useNavigation();
  
  // Include generation mutation for autonomous mode
  const generateAutonomousMutation = useGenerateAutonomous();
  
  // Helper function to determine content based on current step
  const renderContent = () => {
    switch (state.currentStep) {
      case 'input':
        return <SpecInput onNext={goForward} />;
      case 'mode':
        return <ModeSelection onBack={goBack} onNext={goForward} />;
      case 'blueprint':
        return <BlueprintView onBack={goBack} onNext={goForward} />;
      case 'scripts':
        return <ScriptOutput onBack={goBack} />;
      default:
        return <div>Unknown step</div>;
    }
  };
  
  // Handles navigation out of autonomous mode when turning it off
  const handleAutonomousModeChange = (enabled: boolean) => {
    setIsAutonomousMode(enabled);
    
    // Adjust current step if needed when changing modes
    if (!enabled && state.currentStep === 'scripts' && !state.blueprintJobId) {
      // If turning off autonomous mode while on scripts page, go back to blueprint
      setCurrentStep('blueprint');
    }
  };
  
  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-grow container mx-auto px-4 py-8">
        {/* Progress nav */}
        <div className="mb-8">
          <div className="mx-auto">
            <div className="flex justify-between items-center mb-8">
              <h1 className="text-2xl font-semibold">API Test Generator</h1>
              <div className="flex space-x-2">
                {canGoBack() && (
                  <button
                    onClick={goBack}
                    className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    Back
                  </button>
                )}
              </div>
            </div>
            
            <div className="flex justify-between relative mb-8">
              <div className="absolute top-1/2 left-0 w-full h-0.5 bg-gray-200 dark:bg-gray-700 -translate-y-1/2 z-0"></div>
              {['input', 'mode', 'blueprint', 'scripts'].map((step, index) => (
                <div 
                  key={step} 
                  className={`relative z-10 flex flex-col items-center ${
                    state.currentStep === step 
                      ? 'text-primary-600 dark:text-primary-400' 
                      : 'text-gray-500 dark:text-gray-400'
                  }`}
                >
                  <button
                    onClick={() => {
                      // Only allow going to steps we've already been to
                      const targetStep = step as AppStep;
                      if ((targetStep === 'blueprint' && state.blueprintJobId) || 
                          (targetStep === 'scripts' && state.scriptJobId)) {
                        setCurrentStep(targetStep);
                      } else if (targetStep === 'input' || targetStep === 'mode') {
                        setCurrentStep(targetStep);
                      }
                    }}
                    className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      state.currentStep === step 
                        ? 'bg-primary-100 border-2 border-primary-500 dark:bg-primary-900/30 dark:border-primary-400' 
                        : 'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600'
                    }`}
                    disabled={
                      (step === 'blueprint' && !state.blueprintJobId && state.currentStep !== 'mode') || 
                      (step === 'scripts' && !state.scriptJobId && state.currentStep !== 'blueprint')
                    }
                  >
                    <span className="text-sm font-medium">{index + 1}</span>
                  </button>
                  <span className="mt-2 text-sm font-medium">
                    {step === 'input' && 'Specification'}
                    {step === 'mode' && 'Mode'}
                    {step === 'blueprint' && (state.isAutonomousMode ? 'Autonomous' : 'Blueprint')}
                    {step === 'scripts' && 'Scripts'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Content */}
        <div className="mx-auto">
          {renderContent()}
        </div>
      </main>
    </div>
  );
};

const AppWithProvider: React.FC = () => {
  return (
    <AppProvider>
      <App />
    </AppProvider>
  );
};

export default AppWithProvider; 