import React, { useContext } from 'react';
import { useAppContext } from '../context/AppContext';
import { AppStep } from '../types/app';

export const useNavigation = () => {
  const { state, setCurrentStep } = useAppContext();
  
  const canGoBack = () => {
    switch (state.currentStep) {
      case 'input':
        return false; // Already at the beginning
      case 'mode':
        return true; // Can go back to input
      case 'blueprint':
        return true; // Can go back to mode
      case 'scripts':
        // In autonomous mode with direct path, can only go back to input
        if (state.isAutonomousMode && !state.blueprintJobId) {
          return true;
        }
        // Regular flow
        return true; // Can go back to blueprint
      default:
        return false;
    }
  };
  
  const canGoForward = () => {
    switch (state.currentStep) {
      case 'input':
        return state.specValidation.isValid || state.blueprint; // Can go forward if spec is valid or blueprint exists
      case 'mode':
        return true; // Can always proceed from mode selection
      case 'blueprint':
        return state.blueprintIsValid; // Can go forward if blueprint is valid
      case 'scripts':
        return false; // Already at the end
      default:
        return false;
    }
  };
  
  const goBack = () => {
    switch (state.currentStep) {
      case 'mode':
        setCurrentStep('input');
        break;
      case 'blueprint':
        setCurrentStep('mode');
        break;
      case 'scripts':
        // In autonomous mode with direct path, go back to input
        if (state.isAutonomousMode && !state.blueprintJobId) {
          setCurrentStep('input');
        } else {
          // Regular flow
          setCurrentStep('blueprint');
        }
        break;
      default:
        break;
    }
  };
  
  const goForward = () => {
    switch (state.currentStep) {
      case 'input':
        setCurrentStep('mode');
        break;
      case 'mode':
        // When in autonomous mode, skip blueprint step
        if (state.isAutonomousMode) {
          setCurrentStep('scripts');
        } else {
          setCurrentStep('blueprint');
        }
        break;
      case 'blueprint':
        setCurrentStep('scripts');
        break;
      default:
        break;
    }
  };
  
  return {
    canGoBack,
    canGoForward,
    goBack,
    goForward
  };
}; 