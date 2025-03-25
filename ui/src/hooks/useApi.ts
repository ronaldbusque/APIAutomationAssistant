import { useMutation, useQuery } from '@tanstack/react-query';
import { GenerateBlueprintRequest, GenerateScriptsRequest, JobStatusResponse } from '../types/app';

// API base URL - point directly to backend server
const API_BASE_URL = 'http://localhost:8000';

// Generate blueprint
export const useGenerateBlueprint = () => {
  return useMutation({
    mutationFn: async (request: GenerateBlueprintRequest) => {
      const response = await fetch(`${API_BASE_URL}/generate-blueprint`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to generate blueprint: ${response.status}`);
      }
      
      return response.json();
    },
  });
};

// Generate scripts
export const useGenerateScripts = () => {
  return useMutation({
    mutationFn: async (request: GenerateScriptsRequest) => {
      const response = await fetch(`${API_BASE_URL}/generate-scripts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to generate scripts: ${response.status}`);
      }
      
      return response.json();
    },
  });
};

// Get job status
export const useJobStatus = (jobId: string | null) => {
  return useQuery({
    queryKey: ['jobStatus', jobId],
    queryFn: async () => {
      if (!jobId) return null;
      
      const response = await fetch(`${API_BASE_URL}/status/${jobId}`);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to fetch job status: ${response.status}`);
      }
      
      return response.json() as Promise<JobStatusResponse>;
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      
      // Don't poll if no data yet
      if (!data) return 1000;
      
      // Explicitly check the status property to handle all terminal states
      if (data.status === 'completed' || data.status === 'failed') {
        console.log(`Job ${jobId} reached terminal state: ${data.status}. Stopping polling.`);
        return false; // Stop polling
      }
      
      // Continue polling for in-progress jobs
      return 1000; // Poll every second
    },
    // Add a staletime to prevent unnecessary refetches
    staleTime: 30000, // 30 seconds
    gcTime: 60000, // 1 minute (was previously called cacheTime)
    // Retry failed requests a limited number of times
    retry: 3,
    retryDelay: 1000,
  });
};

// Connect to WebSocket for real-time updates
export const useWebSocket = (jobId: string | null, onMessage: (data: any) => void) => {
  const connect = () => {
    if (!jobId) return null;
    
    const ws = new WebSocket(`ws://localhost:8000/ws/${jobId}`);
    
    ws.onopen = () => {
      console.log('WebSocket connection established');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (err) {
        console.error('Failed to parse WebSocket message', err);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error', error);
    };
    
    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };
    
    return ws;
  };
  
  return { connect };
}; 