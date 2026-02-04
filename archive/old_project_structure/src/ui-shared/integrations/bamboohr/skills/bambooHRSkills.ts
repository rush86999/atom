/**
 * ATOM BambooHR Skills
 * Comprehensive HR management capabilities with natural language processing
 */

export const bambooHRSkills = [
  {
    id: 'bamboohr_connect',
    name: 'Connect BambooHR',
    description: 'Connect and authenticate with BambooHR',
    category: 'integration',
    examples: [
      'Connect to BambooHR',
      'Authenticate with BambooHR',
      'Setup BambooHR integration'
    ],
    endpoint: '/api/auth/bamboohr/authorize',
    method: 'GET'
  },
  {
    id: 'bamboohr_employee_list',
    name: 'List Employees',
    description: 'Get comprehensive list of employees with details',
    category: 'employee_management',
    examples: [
      'Show me all employees',
      'List employees in the engineering department',
      'Get employee directory'
    ],
    endpoint: '/api/bamboohr/employees',
    method: 'GET',
    parameters: [
      { name: 'department', type: 'string', description: 'Filter by department' },
      { name: 'limit', type: 'number', description: 'Number of results to return' }
    ]
  },
  {
    id: 'bamboohr_employee_create',
    name: 'Create Employee',
    description: 'Add a new employee to the system',
    category: 'employee_management',
    examples: [
      'Add new employee John Doe',
      'Create employee for marketing team',
      'Hire new software engineer'
    ],
    endpoint: '/api/bamboohr/employees',
    method: 'POST',
    parameters: [
      { name: 'firstName', type: 'string', required: true },
      { name: 'lastName', type: 'string', required: true },
      { name: 'workEmail', type: 'string', required: true },
      { name: 'jobTitle', type: 'string' },
      { name: 'department', type: 'string' },
      { name: 'location', type: 'string' }
    ]
  },
  {
    id: 'bamboohr_employee_update',
    name: 'Update Employee',
    description: 'Update employee information and details',
    category: 'employee_management',
    examples: [
      'Update Jane Smiths job title',
      'Change employee department',
      'Update employee contact information'
    ],
    endpoint: '/api/bamboohr/employees/{employee_id}',
    method: 'PUT',
    parameters: [
      { name: 'employee_id', type: 'string', required: true },
      { name: 'firstName', type: 'string' },
      { name: 'lastName', type: 'string' },
      { name: 'jobTitle', type: 'string' },
      { name: 'department', type: 'string' },
      { name: 'location', type: 'string' }
    ]
  },
  {
    id: 'bamboohr_employee_search',
    name: 'Search Employees',
    description: 'Search for employees by name, email, or other criteria',
    category: 'employee_management',
    examples: [
      'Find employee John',
      'Search for someone in marketing',
      'Look up email address'
    ],
    endpoint: '/api/bamboohr/employees/search',
    method: 'GET',
    parameters: [
      { name: 'q', type: 'string', required: true, description: 'Search query' },
      { name: 'limit', type: 'number', description: 'Number of results' }
    ]
  },
  {
    id: 'bamboohr_timeoff_list',
    name: 'List Time Off Requests',
    description: 'Get all time off requests and their status',
    category: 'time_management',
    examples: [
      'Show all time off requests',
      'List pending vacation requests',
      'Get approved time off'
    ],
    endpoint: '/api/bamboohr/time-off',
    method: 'GET',
    parameters: [
      { name: 'employee_id', type: 'string', description: 'Filter by employee' },
      { name: 'status', type: 'string', description: 'Filter by status' }
    ]
  },
  {
    id: 'bamboohr_timeoff_create',
    name: 'Request Time Off',
    description: 'Create a new time off request',
    category: 'time_management',
    examples: [
      'Request vacation next week',
      'Apply for sick leave',
      'Schedule time off for conference'
    ],
    endpoint: '/api/bamboohr/time-off',
    method: 'POST',
    parameters: [
      { name: 'employeeId', type: 'string', required: true },
      { name: 'start', type: 'string', required: true },
      { name: 'end', type: 'string', required: true },
      { name: 'type', type: 'string', required: true },
      { name: 'notes', type: 'string' }
    ]
  },
  {
    id: 'bamboohr_timeoff_approve',
    name: 'Approve Time Off',
    description: 'Approve a pending time off request',
    category: 'time_management',
    examples: [
      'Approve Johns vacation request',
      'Accept time off for team meeting',
      'Confirm sick leave approval'
    ],
    endpoint: '/api/bamboohr/time-off/{request_id}/approve',
    method: 'POST',
    parameters: [
      { name: 'request_id', type: 'string', required: true }
    ]
  },
  {
    id: 'bamboohr_whos_out',
    name: 'Who\'s Out',
    description: 'See who is out of office for specific dates',
    category: 'time_management',
    examples: [
      'Who is out this week',
      'Check who\'s on vacation tomorrow',
      'Show absences for next month'
    ],
    endpoint: '/api/bamboohr/whos-out',
    method: 'GET',
    parameters: [
      { name: 'start_date', type: 'string', description: 'Start date (YYYY-MM-DD)' },
      { name: 'end_date', type: 'string', description: 'End date (YYYY-MM-DD)' }
    ]
  },
  {
    id: 'bamboohr_company_info',
    name: 'Company Information',
    description: 'Get company details and settings',
    category: 'company_management',
    examples: [
      'Show company information',
      'Get organization details',
      'Display company profile'
    ],
    endpoint: '/api/bamboohr/company',
    method: 'GET'
  },
  {
    id: 'bamboohr_reports',
    name: 'HR Reports',
    description: 'Generate and view HR analytics reports',
    category: 'analytics',
    examples: [
      'Generate employee report',
      'Show HR analytics',
      'Get department statistics'
    ],
    endpoint: '/api/bamboohr/reports',
    method: 'GET',
    parameters: [
      { name: 'report_type', type: 'string', description: 'Type of report' }
    ]
  },
  {
    id: 'bamboohr_dashboard',
    name: 'HR Dashboard',
    description: 'Get comprehensive HR dashboard data',
    category: 'analytics',
    examples: [
      'Show HR dashboard',
      'Get employee metrics',
      'Display company statistics'
    ],
    endpoint: '/api/bamboohr/dashboard',
    method: 'GET'
  }
];

// Natural language processing patterns
export const bambooHRNLPPatterns = {
  employeeActions: [
    /(?:add|create|hire) (?:new )?employee/i,
    /(?:update|edit|modify) employee/i,
    /(?:delete|remove|terminate) employee/i,
    /(?:find|search|lookup) employee/i,
    /(?:list|show|display) (?:all )?employees/i
  ],
  timeOffActions: [
    /(?:request|apply for|schedule) (?:vacation|time off|sick leave)/i,
    /(?:approve|accept|confirm) (?:time off|vacation|leave)/i,
    /(?:deny|reject) (?:time off|vacation|leave)/i,
    /(?:show|list|display) (?:all )?(?:time off|vacation) requests/i,
    /who'?s (?:out|away|on vacation|off)/i
  ],
  companyActions: [
    /(?:show|display|get) company/i,
    /(?:update|edit|modify) company/i,
    /(?:company|organization) (?:information|details|profile)/i
  ],
  reportActions: [
    /(?:generate|create|run) (?:report|analytics)/i,
    /(?:show|display|get) (?:HR|employee|department) (?:statistics|metrics|report)/i,
    /(?:dashboard|overview|summary)/i
  ]
};

// Intent classification
export const classifyBambooHRIntent = (input: string) => {
  const text = input.toLowerCase().trim();
  
  // Employee management
  for (const pattern of bambooHRNLPPatterns.employeeActions) {
    if (pattern.test(text)) {
      if (text.includes('add') || text.includes('create') || text.includes('hire')) {
        return { intent: 'create_employee', confidence: 0.9 };
      } else if (text.includes('update') || text.includes('edit') || text.includes('modify')) {
        return { intent: 'update_employee', confidence: 0.9 };
      } else if (text.includes('delete') || text.includes('remove') || text.includes('terminate')) {
        return { intent: 'delete_employee', confidence: 0.9 };
      } else if (text.includes('find') || text.includes('search') || text.includes('lookup')) {
        return { intent: 'search_employee', confidence: 0.9 };
      } else if (text.includes('list') || text.includes('show') || text.includes('display')) {
        return { intent: 'list_employees', confidence: 0.9 };
      }
    }
  }
  
  // Time off management
  for (const pattern of bambooHRNLPPatterns.timeOffActions) {
    if (pattern.test(text)) {
      if (text.includes('request') || text.includes('apply') || text.includes('schedule')) {
        return { intent: 'request_time_off', confidence: 0.9 };
      } else if (text.includes('approve') || text.includes('accept') || text.includes('confirm')) {
        return { intent: 'approve_time_off', confidence: 0.9 };
      } else if (text.includes('deny') || text.includes('reject')) {
        return { intent: 'deny_time_off', confidence: 0.9 };
      } else if (text.includes('list') || text.includes('show') || text.includes('display')) {
        return { intent: 'list_time_off', confidence: 0.9 };
      } else if (text.includes("who's") || text.includes('who is')) {
        return { intent: 'whos_out', confidence: 0.9 };
      }
    }
  }
  
  // Company management
  for (const pattern of bambooHRNLPPatterns.companyActions) {
    if (pattern.test(text)) {
      return { intent: 'company_info', confidence: 0.9 };
    }
  }
  
  // Reports and analytics
  for (const pattern of bambooHRNLPPatterns.reportActions) {
    if (pattern.test(text)) {
      return { intent: 'reports', confidence: 0.9 };
    }
  }
  
  return { intent: 'unknown', confidence: 0.1 };
};

// Entity extraction
export const extractBambooHREntities = (input: string) => {
  const text = input.toLowerCase();
  const entities = {};
  
  // Extract names (simple pattern matching)
  const namePattern = /(?:employee|add|create|update|edit|find|search)\s+(?:named\s+)?([a-z]+\s+[a-z]+)/i;
  const nameMatch = text.match(namePattern);
  if (nameMatch) {
    entities.name = nameMatch[1];
  }
  
  // Extract departments
  const departments = ['engineering', 'sales', 'marketing', 'hr', 'finance', 'operations', 'it'];
  for (const dept of departments) {
    if (text.includes(dept)) {
      entities.department = dept;
      break;
    }
  }
  
  // Extract time off types
  const timeOffTypes = ['vacation', 'sick', 'personal', 'holiday', 'maternity', 'paternity'];
  for (const type of timeOffTypes) {
    if (text.includes(type)) {
      entities.timeOffType = type;
      break;
    }
  }
  
  // Extract email addresses
  const emailPattern = /([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})/i;
  const emailMatch = text.match(emailPattern);
  if (emailMatch) {
    entities.email = emailMatch[1];
  }
  
  // Extract dates (simple pattern)
  const datePattern = /(\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2}\/\d{4})/g;
  const dateMatches = text.match(datePattern);
  if (dateMatches) {
    entities.dates = dateMatches;
  }
  
  return entities;
};