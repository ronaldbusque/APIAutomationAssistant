// Fixtures and helper functions

import { test as base } from '@playwright/test';

// Example: A fixture to set up a test user in the system before tests run
export const test = base.extend({
  // Define shared fixtures here if needed
  // e.g., userData: async ({}, use) => {
  //   const data = { id: 1, name: 'John Doe', email: 'john@example.com', age: 30 };
  //   await use(data);
  // }
});

// Helper function for common assertions or setup logic can go here
