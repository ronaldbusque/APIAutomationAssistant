import { test, expect } from '@playwright/test';

const BASE_URL = 'https://api.example.com/v1';

// Group: User Collection Tests
test.describe('User Collection Tests', () => {
  test('GET All Users - Valid Request', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/users`);
    expect(response.status()).toBe(200);
    // Optionally, validate response body schema here
  });

  test('GET All Users - Invalid Query Parameter', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/users`, {
      params: { status: 'invalid' }
    });
    expect(response.status()).toBe(400);
  });
});

// Group: User Management Tests
test.describe('User Management Tests', () => {
  test('POST Create User - Valid Request', async ({ request }) => {
    const response = await request.post(`${BASE_URL}/users`, {
      data: { id: 1, name: 'John Doe', email: 'john@example.com', age: 30 }
    });
    expect(response.status()).toBe(201);
  });

  test('POST Create User - Missing Required Fields', async ({ request }) => {
    const response = await request.post(`${BASE_URL}/users`, {
      data: { id: 2, name: 'Jane Doe' } // Missing email
    });
    expect(response.status()).toBe(400);
  });
});

// Group: Single User Tests
test.describe('Single User Tests', () => {
  test('GET User By ID - Valid Request', async ({ request }) => {
    // Use a valid userId
    const userId = 1;
    const response = await request.get(`${BASE_URL}/users/${userId}`);
    expect(response.status()).toBe(200);
  });

  test('GET User By ID - Non-existent User', async ({ request }) => {
    const userId = 999; // Non-existent userId
    const response = await request.get(`${BASE_URL}/users/${userId}`);
    expect(response.status()).toBe(404);
  });
});
