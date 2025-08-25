import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

// Custom metrics
const errorRate = new Rate('errors');
const responseTimeTrend = new Trend('response_time');
const authSuccessRate = new Rate('auth_success');
const uploadSuccessRate = new Rate('upload_success');
const querySuccessRate = new Rate('query_success');
const concurrentUsers = new Counter('concurrent_users');

// Test configuration
export const options = {
  stages: [
    // Warm up
    { duration: '2m', target: 10 },
    
    // Load test
    { duration: '5m', target: 50 },
    
    // Spike test
    { duration: '2m', target: 100 },
    { duration: '3m', target: 100 },
    
    // Scale down
    { duration: '2m', target: 50 },
    { duration: '2m', target: 0 },
  ],
  
  thresholds: {
    // Performance requirements
    http_req_duration: ['p(95)<2000'], // 95% of requests under 2s
    http_req_duration: ['p(99)<5000'], // 99% of requests under 5s
    
    // Error rate requirements
    errors: ['rate<0.05'], // Error rate under 5%
    
    // Specific endpoint requirements
    'http_req_duration{endpoint:auth}': ['p(95)<500'],
    'http_req_duration{endpoint:upload}': ['p(95)<10000'],
    'http_req_duration{endpoint:query}': ['p(95)<3000'],
    
    // Success rate requirements
    auth_success: ['rate>0.95'],
    upload_success: ['rate>0.90'],
    query_success: ['rate>0.95'],
  },
  
  // Resource limits
  noConnectionReuse: false,
  userAgent: 'K6-LoadTest/1.0',
};

// Shared test data
const testQueries = new SharedArray('queries', function () {
  return [
    'What is machine learning?',
    'Explain artificial intelligence concepts',
    'How does natural language processing work?',
    'What are the applications of computer vision?',
    'Describe deep learning algorithms',
    'What is the difference between supervised and unsupervised learning?',
    'How do neural networks function?',
    'What are the ethical considerations in AI?',
    'Explain reinforcement learning principles',
    'What is the future of artificial intelligence?'
  ];
});

const testDocuments = new SharedArray('documents', function () {
  return [
    {
      name: 'machine_learning_basics.txt',
      content: 'Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data. It includes supervised learning, unsupervised learning, and reinforcement learning approaches.'
    },
    {
      name: 'ai_overview.txt',
      content: 'Artificial Intelligence encompasses machine learning, natural language processing, computer vision, and robotics. It aims to create systems that can perform tasks requiring human intelligence.'
    },
    {
      name: 'nlp_guide.txt',
      content: 'Natural Language Processing enables computers to understand, interpret, and generate human language. Applications include chatbots, translation systems, and sentiment analysis.'
    },
    {
      name: 'computer_vision.txt',
      content: 'Computer vision allows machines to interpret and understand visual information. It powers applications like image recognition, autonomous vehicles, and medical imaging analysis.'
    },
    {
      name: 'deep_learning.txt',
      content: 'Deep learning uses neural networks with multiple layers to learn complex patterns in data. It has revolutionized fields like image recognition, speech processing, and game playing.'
    }
  ];
});

// Test configuration from environment
const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const API_PREFIX = '/api/v1';

// Authentication helper
function authenticate() {
  const credentials = {
    email: `loadtest-${__VU}-${Math.random().toString(36).substring(7)}@test.com`,
    password: 'LoadTest123!',
  };

  // Register user
  group('User Registration', function () {
    const registerPayload = JSON.stringify({
      email: credentials.email,
      password: credentials.password,
      role: 'user',
    });

    const registerRes = http.post(
      `${BASE_URL}${API_PREFIX}/auth/register`,
      registerPayload,
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { endpoint: 'auth' },
      }
    );

    const registerSuccess = check(registerRes, {
      'registration successful': (r) => r.status === 201,
      'registration response time OK': (r) => r.timings.duration < 2000,
    });

    authSuccessRate.add(registerSuccess);
    errorRate.add(!registerSuccess);
  });

  // Login user
  let authToken = null;
  group('User Login', function () {
    const loginPayload = JSON.stringify({
      email: credentials.email,
      password: credentials.password,
    });

    const loginRes = http.post(
      `${BASE_URL}${API_PREFIX}/auth/login`,
      loginPayload,
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { endpoint: 'auth' },
      }
    );

    const loginSuccess = check(loginRes, {
      'login successful': (r) => r.status === 200,
      'login response time OK': (r) => r.timings.duration < 1000,
      'token received': (r) => r.json('data.access_token') !== undefined,
    });

    if (loginSuccess && loginRes.status === 200) {
      authToken = loginRes.json('data.access_token');
    }

    authSuccessRate.add(loginSuccess);
    errorRate.add(!loginSuccess);
    responseTimeTrend.add(loginRes.timings.duration);
  });

  return authToken;
}

// Document upload helper
function uploadDocument(authToken) {
  if (!authToken) return null;

  const document = testDocuments[Math.floor(Math.random() * testDocuments.length)];
  
  return group('Document Upload', function () {
    // Create multipart form data
    const formData = {
      file: http.file(Buffer.from(document.content), document.name, 'text/plain'),
    };

    const uploadRes = http.post(
      `${BASE_URL}${API_PREFIX}/documents/upload`,
      formData,
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        tags: { endpoint: 'upload' },
        timeout: '30s', // Longer timeout for uploads
      }
    );

    const uploadSuccess = check(uploadRes, {
      'upload successful': (r) => r.status === 201,
      'upload response time OK': (r) => r.timings.duration < 15000,
      'document ID received': (r) => r.json('data.documentId') !== undefined,
      'job ID received': (r) => r.json('data.jobId') !== undefined,
    });

    uploadSuccessRate.add(uploadSuccess);
    errorRate.add(!uploadSuccess);
    responseTimeTrend.add(uploadRes.timings.duration);

    if (uploadSuccess && uploadRes.status === 201) {
      return {
        documentId: uploadRes.json('data.documentId'),
        jobId: uploadRes.json('data.jobId'),
      };
    }

    return null;
  });
}

// Query execution helper
function executeQuery(authToken) {
  if (!authToken) return;

  const query = testQueries[Math.floor(Math.random() * testQueries.length)];
  const modes = ['local', 'global', 'hybrid', 'mix'];
  const mode = modes[Math.floor(Math.random() * modes.length)];

  group('Query Execution', function () {
    const queryPayload = JSON.stringify({
      query: query,
      mode: mode,
      queryType: 'text',
    });

    const queryRes = http.post(
      `${BASE_URL}${API_PREFIX}/query`,
      queryPayload,
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        tags: { endpoint: 'query' },
        timeout: '10s',
      }
    );

    const querySuccess = check(queryRes, {
      'query successful': (r) => r.status === 200,
      'query response time OK': (r) => r.timings.duration < 5000,
      'result received': (r) => r.json('data.result') !== undefined,
      'sources received': (r) => r.json('data.sources') !== undefined,
    });

    querySuccessRate.add(querySuccess);
    errorRate.add(!querySuccess);
    responseTimeTrend.add(queryRes.timings.duration);
  });
}

// Health check helper
function healthCheck() {
  group('Health Check', function () {
    const healthRes = http.get(`${BASE_URL}${API_PREFIX}/health`, {
      tags: { endpoint: 'health' },
    });

    check(healthRes, {
      'health check successful': (r) => r.status === 200,
      'health check fast': (r) => r.timings.duration < 500,
    });
  });
}

// Document listing helper
function listDocuments(authToken) {
  if (!authToken) return;

  group('List Documents', function () {
    const listRes = http.get(`${BASE_URL}${API_PREFIX}/documents`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
      tags: { endpoint: 'documents' },
    });

    const listSuccess = check(listRes, {
      'list successful': (r) => r.status === 200,
      'list response time OK': (r) => r.timings.duration < 2000,
      'documents array received': (r) => Array.isArray(r.json('data.documents')),
    });

    errorRate.add(!listSuccess);
    responseTimeTrend.add(listRes.timings.duration);
  });
}

// Query history helper
function getQueryHistory(authToken) {
  if (!authToken) return;

  group('Query History', function () {
    const historyRes = http.get(`${BASE_URL}${API_PREFIX}/queries/history?limit=10`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
      tags: { endpoint: 'history' },
    });

    const historySuccess = check(historyRes, {
      'history successful': (r) => r.status === 200,
      'history response time OK': (r) => r.timings.duration < 1000,
      'queries array received': (r) => Array.isArray(r.json('data.queries')),
    });

    errorRate.add(!historySuccess);
    responseTimeTrend.add(historyRes.timings.duration);
  });
}

// Main test scenario
export default function () {
  concurrentUsers.add(1);

  // Phase 1: Authentication
  const authToken = authenticate();
  if (!authToken) {
    console.error(`VU ${__VU}: Authentication failed, skipping remaining tests`);
    return;
  }

  sleep(1); // Brief pause between operations

  // Phase 2: Upload documents (70% of users)
  let uploadedDoc = null;
  if (Math.random() < 0.7) {
    uploadedDoc = uploadDocument(authToken);
    sleep(2); // Wait for processing to start
  }

  // Phase 3: Execute queries (all users)
  executeQuery(authToken);
  sleep(1);

  // Phase 4: List documents (50% of users)
  if (Math.random() < 0.5) {
    listDocuments(authToken);
    sleep(1);
  }

  // Phase 5: Check query history (30% of users)
  if (Math.random() < 0.3) {
    getQueryHistory(authToken);
    sleep(1);
  }

  // Phase 6: Health check (10% of users)
  if (Math.random() < 0.1) {
    healthCheck();
  }

  // Random sleep to simulate user think time
  sleep(Math.random() * 3 + 1); // 1-4 seconds
}

// Scenario variations for different test types
export function handleSummary(data) {
  return {
    'performance-test-results.html': htmlReport(data),
    'performance-test-results.json': JSON.stringify(data),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

// Custom HTML report generator
function htmlReport(data) {
  return `
<!DOCTYPE html>
<html>
<head>
    <title>RAG-Anything API Load Test Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f4f4f4; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .metric { display: inline-block; margin: 10px; padding: 10px; background: #f9f9f9; border-radius: 3px; }
        .error { color: red; }
        .success { color: green; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>RAG-Anything API Load Test Results</h1>
        <p><strong>Test Duration:</strong> ${data.state.testRunDurationMs / 1000}s</p>
        <p><strong>VUs:</strong> ${data.metrics.vus_max.values.max}</p>
        <p><strong>Iterations:</strong> ${data.metrics.iterations.values.count}</p>
    </div>
    
    <div class="section">
        <h2>Key Metrics</h2>
        <div class="metric">
            <strong>Response Time (p95):</strong> ${data.metrics.http_req_duration.values.p95.toFixed(2)}ms
        </div>
        <div class="metric">
            <strong>Error Rate:</strong> <span class="${data.metrics.errors.values.rate > 0.05 ? 'error' : 'success'}">${(data.metrics.errors.values.rate * 100).toFixed(2)}%</span>
        </div>
        <div class="metric">
            <strong>Requests/sec:</strong> ${data.metrics.http_reqs.values.rate.toFixed(2)}
        </div>
    </div>

    <div class="section">
        <h2>Endpoint Performance</h2>
        <table>
            <tr>
                <th>Endpoint</th>
                <th>Avg Response Time</th>
                <th>p95 Response Time</th>
                <th>Success Rate</th>
            </tr>
            ${Object.entries(data.metrics)
              .filter(([key]) => key.includes('endpoint:'))
              .map(([key, metric]) => `
                <tr>
                    <td>${key.split('endpoint:')[1]}</td>
                    <td>${metric.values.avg?.toFixed(2) || 'N/A'}ms</td>
                    <td>${metric.values.p95?.toFixed(2) || 'N/A'}ms</td>
                    <td>${((1 - (metric.values.rate || 0)) * 100).toFixed(2)}%</td>
                </tr>
              `).join('')}
        </table>
    </div>

    <div class="section">
        <h2>Thresholds</h2>
        ${Object.entries(data.thresholds || {})
          .map(([name, result]) => `
            <div class="metric ${result.ok ? 'success' : 'error'}">
                <strong>${name}:</strong> ${result.ok ? 'PASSED' : 'FAILED'}
            </div>
          `).join('')}
    </div>
</body>
</html>
  `;
}

// Text summary for stdout
function textSummary(data, options = {}) {
  const { indent = '', enableColors = false } = options;
  
  let summary = `
${indent}RAG-Anything API Load Test Summary
${indent}=====================================
${indent}Duration: ${(data.state.testRunDurationMs / 1000).toFixed(2)}s
${indent}VUs: ${data.metrics.vus_max.values.max}
${indent}Iterations: ${data.metrics.iterations.values.count}

${indent}Response Times:
${indent}  Average: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms
${indent}  p95: ${data.metrics.http_req_duration.values.p95.toFixed(2)}ms
${indent}  p99: ${data.metrics.http_req_duration.values.p99.toFixed(2)}ms

${indent}Success Rates:
${indent}  Overall: ${((1 - data.metrics.errors.values.rate) * 100).toFixed(2)}%
${indent}  Auth: ${(data.metrics.auth_success?.values.rate * 100 || 0).toFixed(2)}%
${indent}  Upload: ${(data.metrics.upload_success?.values.rate * 100 || 0).toFixed(2)}%
${indent}  Query: ${(data.metrics.query_success?.values.rate * 100 || 0).toFixed(2)}%

${indent}Throughput:
${indent}  Requests/sec: ${data.metrics.http_reqs.values.rate.toFixed(2)}
${indent}  Data Transferred: ${(data.metrics.data_received.values.count / 1024 / 1024).toFixed(2)}MB
  `;

  return summary;
}

// Export scenarios for different test types
export const scenarios = {
  // Standard load test
  load_test: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '2m', target: 10 },
      { duration: '5m', target: 50 },
      { duration: '2m', target: 0 },
    ],
    gracefulRampDown: '30s',
  },

  // Spike test
  spike_test: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '1m', target: 10 },
      { duration: '30s', target: 100 },
      { duration: '2m', target: 100 },
      { duration: '30s', target: 10 },
      { duration: '1m', target: 0 },
    ],
    gracefulRampDown: '30s',
  },

  // Stress test
  stress_test: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '2m', target: 20 },
      { duration: '5m', target: 100 },
      { duration: '5m', target: 200 },
      { duration: '2m', target: 0 },
    ],
    gracefulRampDown: '1m',
  },

  // Soak test
  soak_test: {
    executor: 'constant-vus',
    vus: 50,
    duration: '30m',
    gracefulRampDown: '2m',
  },
};