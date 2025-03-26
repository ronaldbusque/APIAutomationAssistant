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
      
      // Check job status to determine polling frequency
      if (data.status === 'processing' || data.status === 'queued') {
        console.log(`Job ${jobId} is ${data.status}. Polling more frequently.`);
        return 500; // Poll every 500ms for more responsive UI updates during processing
      }
      
      // Explicitly check the status property to handle all terminal states
      if (data.status === 'completed' || data.status === 'failed') {
        console.log(`Job ${jobId} reached terminal state: ${data.status}. Stopping polling.`);
        return false; // Stop polling
      }
      
      // Continue polling for in-progress jobs
      return 1000; // Poll every second for other states
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
    
    console.log(`Connecting to WebSocket for job ${jobId}...`);
    
    // Prepare WebSocket URL - updating to match the server's expected path
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
    // Fix the WebSocket URL to exactly match the server endpoint path '/ws/job/{job_id}'
    const wsURL = `${wsProtocol}//${wsHost}/ws/job/${jobId}`;
    
    console.log(`WebSocket URL: ${wsURL}`);
    
    // Create WebSocket connection
    const ws = new WebSocket(wsURL);
    
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    let reconnectTimeout: number | null = null;
    
    // Connection opened
    ws.onopen = () => {
      console.log(`WebSocket connection established for job ${jobId}`);
      reconnectAttempts = 0; // Reset reconnect attempts on successful connection
    };
    
    // Message received
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log(`WebSocket message received for job ${jobId}:`, data);
        onMessage(data);
      } catch (err) {
        console.error('Failed to parse WebSocket message', err);
      }
    };
    
    // Connection error
    ws.onerror = (error) => {
      console.error(`WebSocket error for job ${jobId}:`, error);
    };
    
    // Connection closed
    ws.onclose = (event) => {
      console.log(`WebSocket connection closed for job ${jobId}. Code: ${event.code}, Reason: ${event.reason}`);
      
      // Attempt to reconnect if the job might still be processing
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        const reconnectDelay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000); // Exponential backoff
        
        console.log(`Attempting to reconnect WebSocket in ${reconnectDelay}ms (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
        
        if (reconnectTimeout) {
          window.clearTimeout(reconnectTimeout);
        }
        
        reconnectTimeout = window.setTimeout(() => {
          console.log(`Reconnecting WebSocket for job ${jobId}...`);
          connect(); // Recursive call to reconnect
        }, reconnectDelay);
      }
    };
    
    // Return WebSocket instance and cleanup function
    return {
      socket: ws,
      disconnect: () => {
        console.log(`Manually disconnecting WebSocket for job ${jobId}`);
        if (reconnectTimeout) {
          window.clearTimeout(reconnectTimeout);
          reconnectTimeout = null;
        }
        ws.close();
      }
    };
  };
  
  return { connect };
}; 