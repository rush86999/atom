DO $$
DECLARE
    component_id uuid;
BEGIN
    -- MCP Tool Execution Node
    component_id := 'f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Execute MCP Tool', 'action', 'mcp', 'Executes a tool from a connected MCP server.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "server_id": {
                "type": "string",
                "title": "MCP Server ID",
                "description": "ID of the connected MCP server"
            },
            "tool_name": {
                "type": "string",
                "title": "Tool Name",
                "description": "Name of the tool to execute"
            },
            "arguments": {
                "type": "object",
                "title": "Tool Arguments",
                "description": "JSON object containing tool arguments"
            }
        },
        "required": ["server_id", "tool_name"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "result": { "type": "object", "title": "Tool Result" },
            "server_id": { "type": "string", "title": "Server ID Used" },
            "tool_name": { "type": "string", "title": "Tool Executed" },
            "execution_time": { "type": "string", "title": "Execution Time" }
        }
    }');

    -- Main Agent with MCP Node
    component_id := 'a2b3c4d5-e6f7-4a8b-9c0d-1e2f3a4b5c6d';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'Main Agent with MCP', 'action', 'main_agent', 'Executes main agent with access to MCP server tools.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "agent_action": {
                "type": "string",
                "title": "Agent Action",
                "description": "Action for the main agent to perform"
            },
            "input_data": {
                "type": "object",
                "title": "Input Data",
                "description": "Data to pass to the agent"
            },
            "mcp_servers": {
                "type": "array",
                "title": "MCP Servers",
                "description": "List of MCP server IDs to make available to the agent",
                "items": { "type": "string" }
            },
            "agent_prompt": {
                "type": "string",
                "title": "Agent Prompt",
                "description": "Custom prompt for the agent"
            }
        },
        "required": ["agent_action"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "agent_response": { "type": "string", "title": "Agent Response" },
            "mcp_tools_used": { "type": "array", "title": "MCP Tools Used", "items": { "type": "string" } },
            "execution_details": { "type": "object", "title": "Execution Details" },
            "mcp_servers_used": { "type": "array", "title": "MCP Servers Used", "items": { "type": "string" } }
        }
    }');

    -- MCP File System Operations Node
    component_id := 'b3c4d5e6-f7a8-4b9c-0d1e-2f3a4b5c6d7e';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'MCP File Operations', 'action', 'mcp', 'Perform file system operations using MCP filesystem server.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "title": "Operation",
                "enum": ["read_file", "write_file", "list_directory", "create_directory", "delete_file"],
                "description": "File system operation to perform"
            },
            "path": {
                "type": "string",
                "title": "File Path",
                "description": "Path to the file or directory"
            },
            "content": {
                "type": "string",
                "title": "File Content",
                "description": "Content for write operations"
            }
        },
        "required": ["operation", "path"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "content": { "type": "string", "title": "File Content" },
            "files": { "type": "array", "title": "Directory Files", "items": { "type": "object" } },
            "success": { "type": "boolean", "title": "Operation Success" },
            "message": { "type": "string", "title": "Status Message" }
        }
    }');

    -- MCP Database Operations Node
    component_id := 'c4d5e6f7-a8b9-4c0d-1e2f-3a4b5c6d7e8f';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'MCP Database Query', 'action', 'mcp', 'Execute database queries using MCP database server.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "title": "Query Type",
                "enum": ["select", "insert", "update", "delete"],
                "description": "Type of database query"
            },
            "table": {
                "type": "string",
                "title": "Table Name",
                "description": "Database table name"
            },
            "query": {
                "type": "string",
                "title": "SQL Query",
                "description": "Complete SQL query to execute"
            },
            "data": {
                "type": "object",
                "title": "Data",
                "description": "Data for insert/update operations"
            }
        },
        "required": ["query_type"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "results": { "type": "array", "title": "Query Results", "items": { "type": "object" } },
            "rows_affected": { "type": "number", "title": "Rows Affected" },
            "success": { "type": "boolean", "title": "Query Success" },
            "error": { "type": "string", "title": "Error Message" }
        }
    }');

    -- MCP Web Search Node
    component_id := 'd5e6f7a8-b9c0-4d1e-2f3a-4b5c6d7e8f90';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'MCP Web Search', 'action', 'mcp', 'Perform web searches using MCP search server.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "title": "Search Query",
                "description": "Search query string"
            },
            "max_results": {
                "type": "number",
                "title": "Max Results",
                "description": "Maximum number of results to return",
                "default": 10
            },
            "search_type": {
                "type": "string",
                "title": "Search Type",
                "enum": ["web", "news", "images"],
                "default": "web"
            }
        },
        "required": ["query"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "title": "Search Results",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": { "type": "string" },
                        "url": { "type": "string" },
                        "snippet": { "type": "string" }
                    }
                }
            },
            "total_results": { "type": "number", "title": "Total Results" },
            "search_time": { "type": "number", "title": "Search Time (seconds)" }
        }
    }');

    -- MCP Git Operations Node
    component_id := 'e6f7a8b9-c0d1-4e2f-3a4b-5c6d7e8f9012';
    INSERT INTO public.workflow_components (id, name, type, service, description)
    VALUES (component_id, 'MCP Git Operations', 'action', 'mcp', 'Perform Git operations using MCP Git server.');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'input', '{
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "title": "Git Operation",
                "enum": ["status", "add", "commit", "push", "pull", "branch", "merge"],
                "description": "Git operation to perform"
            },
            "repository_path": {
                "type": "string",
                "title": "Repository Path",
                "description": "Path to the Git repository"
            },
            "files": {
                "type": "array",
                "title": "Files",
                "description": "Files to add (for add operation)",
                "items": { "type": "string" }
            },
            "commit_message": {
                "type": "string",
                "title": "Commit Message",
                "description": "Message for commit operation"
            },
            "branch_name": {
                "type": "string",
                "title": "Branch Name",
                "description": "Name for branch operation"
            }
        },
        "required": ["operation", "repository_path"]
    }');

    INSERT INTO public.workflow_component_schemas (component_id, type, schema)
    VALUES (component_id, 'output', '{
        "type": "object",
        "properties": {
            "status": { "type": "object", "title": "Git Status" },
            "commit_hash": { "type": "string", "title": "Commit Hash" },
            "branch": { "type": "string", "title": "Current Branch" },
            "success": { "type": "boolean", "title": "Operation Success" },
            "output": { "type": "string", "title": "Command Output" }
        }
    }');

    RAISE NOTICE 'MCP workflow components populated successfully';
END $$;