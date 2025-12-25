export const AUTO_GENERATED_PIECES: any[] = [
    {
        "id": "@activepieces/piece-activecampaign",
        "name": "ActiveCampaign",
        "description": "Email marketing, marketing automation, and CRM tools you need to create incredible customer experiences.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/activecampaign.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-activepieces",
        "name": "Activepieces Platform",
        "description": "Open source no-code business automation",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/activepieces.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-actualbudget",
        "name": "Actual Budget",
        "description": "Personal finance app",
        "category": "finance",
        "icon": "https://cdn.activepieces.com/pieces/actualbudget.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-acuity-scheduling",
        "name": "Acuity Scheduling",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/acuity-scheduling.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-acumbamail",
        "name": "Acumbamail",
        "description": "Easily send email and SMS campaigns and boost your business",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/acumbamail.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-afforai",
        "name": "Afforai",
        "description": "Helps you search, summarize, and translate knowledge from hundreds of documents to help you produce trustworthy research.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/afforai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-agentx",
        "name": "AgentX",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/agentx.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-ai",
        "name": "AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/text-ai.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-aianswer",
        "name": "AI Answer",
        "description": "",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/aianswer.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-aidbase",
        "name": "Aidbase",
        "description": "",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/aidbase.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-aircall",
        "name": "Aircall",
        "description": "",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/aircall.png",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-air-ops",
        "name": "AirOps",
        "description": "Build and deploy AI-powered workflows and agents.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/air-ops.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-airparser",
        "name": "Airparser",
        "description": "Extract structured data from emails, PDFs, or documents with Airparser.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/airparser.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-airtable",
        "name": "Airtable",
        "description": "Low\u2012code platform to build apps.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/airtable.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [
            {
                "name": "new_record",
                "displayName": "New Record",
                "description": "Triggers when a new record is added to the selected table.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "viewId": {
                        "displayName": "View",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "updated_record",
                "displayName": "New or Updated Record",
                "description": "Triggers when a record is created or updated in selected table.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sortFields": {
                        "displayName": "Trigger field",
                        "description": "**Last Modified Time** field will be used to watch new or updated records.Please create **Last Modified Time** field in your schema,if you don't have any timestamp field.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "viewId": {
                        "displayName": "View",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "airtable_create_record",
                "displayName": "Create Airtable Record",
                "description": "Adds a record into an airtable",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "fields": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_find_record",
                "displayName": "Find Airtable Record",
                "description": "Find a record in airtable",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "searchField": {
                        "displayName": "Search Field",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "searchValue": {
                        "displayName": "Search Value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "limitToView": {
                        "displayName": "View",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_update_record",
                "displayName": "Update Airtable Record",
                "description": "Update a record in airtable",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "recordId": {
                        "displayName": "Record ID",
                        "description": "The ID of the record.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "fields": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_delete_record",
                "displayName": "Delete Airtable Record",
                "description": "Deletes a record in airtable",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "recordId": {
                        "displayName": "Record ID",
                        "description": "The ID of the record.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_upload_file_to_column",
                "displayName": "Upload File to Column",
                "description": "Uploads a file to attachment type column.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "attachment_column": {
                        "displayName": "Attachment Column",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "recordId": {
                        "displayName": "Record ID",
                        "description": "The ID of the record to which you want to upload the file.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "file": {
                        "displayName": "File",
                        "description": "The file to be uploaded, which can be provided either as a public file URL or in Base64 encoded format.",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "file_content_type": {
                        "displayName": "File Content Type",
                        "description": "Specifies the MIME type of the file being uploaded (e.g., 'image/png', 'application/pdf').",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "filename": {
                        "displayName": "File Name",
                        "description": "The name of the file as it should appear after upload.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_add_comment_to_record",
                "displayName": "Add Comment to Record",
                "description": "Adds a comment to an existing record.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "recordId": {
                        "displayName": "Record ID",
                        "description": "The ID of the record.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Comment Text",
                        "description": "The content of the comment. To mention a user, use the format `@[userId]` or `@[userEmail]`.",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "parentCommentId": {
                        "displayName": "Parent Comment ID",
                        "description": "Optional. The ID of a parent comment to create a threaded reply.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_create_base",
                "displayName": "Create Base",
                "description": "Create a new base with a specified table structure.",
                "props": {
                    "workspaceId": {
                        "displayName": "Workspace",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Base Name",
                        "description": "The name for the new base.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "tables": {
                        "displayName": "Tables",
                        "description": "Define the tables for the new base. Use the default value as a template. The first field for each table will be its primary field.",
                        "type": "JSON",
                        "required": true,
                        "defaultValue": [
                            {
                                "name": "My First Table",
                                "fields": [
                                    {
                                        "name": "Name",
                                        "type": "singleLineText"
                                    },
                                    {
                                        "name": "Status",
                                        "type": "singleSelect",
                                        "options": {
                                            "choices": [
                                                {
                                                    "name": "Todo"
                                                },
                                                {
                                                    "name": "In Progress"
                                                },
                                                {
                                                    "name": "Done"
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            {
                "name": "airtable_create_table",
                "displayName": "Create Table",
                "description": "Create a new table in an existing base.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Table Name",
                        "description": "The name for the new table.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "An optional description for the new table.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "fields": {
                        "displayName": "Fields",
                        "description": "A JSON array of fields for the new table. The first field in the array will become the primary field.",
                        "type": "JSON",
                        "required": true,
                        "defaultValue": [
                            {
                                "name": "Name",
                                "type": "singleLineText",
                                "description": "This will be the primary field"
                            },
                            {
                                "name": "Notes",
                                "type": "multilineText"
                            }
                        ]
                    }
                }
            },
            {
                "name": "airtable_find_base",
                "displayName": "Find Base",
                "description": "Find a base by its name or a keyword.",
                "props": {
                    "baseName": {
                        "displayName": "Base Name or Keyword",
                        "description": "The name or keyword to search for within your base names.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_find_table_by_id",
                "displayName": "Find Table by ID",
                "description": "Get a table's details and schema using its ID.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_get_record_by_id",
                "displayName": "Get Record by ID",
                "description": "Retrieve a single record from a table by its unique ID.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableId": {
                        "displayName": "Table",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "recordId": {
                        "displayName": "Record",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_find_table",
                "displayName": "Find Table",
                "description": "Find a table in a given base by its name.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tableName": {
                        "displayName": "Table Name",
                        "description": "The exact name of the table you want to find.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "airtable_get_base_schema",
                "displayName": "Get Base Schema",
                "description": "Retrieve the schema for a specific base, including all its tables and fields.",
                "props": {
                    "base": {
                        "displayName": "Base",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-airtop",
        "name": "Airtop",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/airtop.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-apitable",
        "name": "AITable",
        "description": "Interactive spreadsheets with collaboration",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/apitable.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-alt-text-ai",
        "name": "AltText.ai",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/alt-text-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-alttextify",
        "name": "AltTextify",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/alttextify.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-amazon-s3",
        "name": "Amazon S3",
        "description": "Scalable storage in the cloud",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/amazon-s3.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-amazon-sns",
        "name": "Amazon SNS",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/amazon-sns.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-amazon-sqs",
        "name": "Amazon SQS",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/aws-sqs.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-aminos",
        "name": "Aminos",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/aminos.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-claude",
        "name": "Anthropic Claude",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/claude.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-anyhook-graphql",
        "name": "AnyHook GraphQL",
        "description": "AnyHook GraphQL enables real-time communication through AnyHook proxy server by allowing you to subscribe and listen to GraphQL subscription events",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/anyhook-graphql.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-anyhook-websocket",
        "name": "AnyHook Websocket",
        "description": "AnyHook Websocket enables real-time communication through AnyHook proxy server by allowing you to subscribe and listen to websocket events",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/anyhook-websocket.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-apify",
        "name": "Apify",
        "description": "Your full\u2011stack platform for web scraping",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/apify.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-apitemplate-io",
        "name": "APITemplate.io",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/apitemplate-io.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-apollo",
        "name": "Apollo",
        "description": "AI sales platform for prospecting, lead gen, and deal automation. Close more deals, faster, with smart data.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/apollo.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-appfollow",
        "name": "AppFollow",
        "description": "Appfollow helps to manage and improve app reviews and ratings.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/appfollow.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-approval",
        "name": "Approval (Legacy)",
        "description": "Build approval process in your workflows",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/approval.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-asana",
        "name": "Asana",
        "description": "Work management platform designed to help teams organize, track, and manage their work.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/asana.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": [
            {
                "name": "create_task",
                "displayName": "Create Task",
                "description": "Create a new task",
                "props": {
                    "workspace": {
                        "displayName": "Workspace",
                        "description": "Asana workspace to create the task in",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "project": {
                        "displayName": "Project",
                        "description": "Asana Project to create the task in",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Task Name",
                        "description": "The name of the task to create",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "notes": {
                        "displayName": "Task Description",
                        "description": "Free-form textual information associated with the task (i.e. its description).",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "due_on": {
                        "displayName": "Due Date",
                        "description": "The date on which this task is due in any format.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "Tags to add to the task",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "assignee": {
                        "displayName": "Assignee",
                        "description": "Assignee for the task",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-ashby",
        "name": "Ashby",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/ashby.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-ask-handle",
        "name": "AskHandle",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/ask-handle.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-assembled",
        "name": "Assembled",
        "description": "Workforce management platform for scheduling and forecasting",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/assembled.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-assemblyai",
        "name": "AssemblyAI",
        "description": "Transcribe and extract data from audio using AssemblyAI's Speech AI.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/assemblyai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-attio",
        "name": "Attio",
        "description": "Modern, collaborative CRM platform built to be fully customizable and real-time.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/attio.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-autocalls",
        "name": "Autocalls",
        "description": "Automate phone calls using our AI calling platform.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/autocalls.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-avoma",
        "name": "Avoma",
        "description": "Avoma is an AI Meeting Assistant that automatically records, transcribes, and summarizes your meetings.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/avoma.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-azure-blob-storage",
        "name": "Azure Blob Storage",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/azure-blob-storage.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-azure-communication-services",
        "name": "Azure Communication Services",
        "description": "Communication services from Microsoft Azure",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/azure-communication-services.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-azure-openai",
        "name": "Azure OpenAI",
        "description": "Powerful AI tools from Microsoft",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/azure-openai.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-backblaze",
        "name": "Backblaze",
        "description": "Scalable storage in the cloud",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/backblaze.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bamboohr",
        "name": "BambooHR",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/bamboohr.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bannerbear",
        "name": "Bannerbear",
        "description": "Automate image generation",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/bannerbear.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-base44",
        "name": "Base44",
        "description": "Build and manage custom apps with databases and entities",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/base44.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-baserow",
        "name": "Baserow",
        "description": "Open-source online database tool, alternative to Airtable",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/baserow.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-beamer",
        "name": "Beamer",
        "description": "Engage users with targeted announcements",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/beamer.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-beehiiv",
        "name": "Beehiiv",
        "description": "",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/beehiiv.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bettermode",
        "name": "Bettermode",
        "description": "Feature-rich engagement platform. Browse beautifully designed templates, each flexible for precise customization to your needs.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/bettermode.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bexio",
        "name": "Bexio",
        "description": "Swiss business software for accounting, invoicing, and project management",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/bexio.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bigcommerce",
        "name": "Bigcommerce",
        "description": "BigCommerce is a leading e-commerce platform that enables businesses to create and manage online stores.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/bigcommerce.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bigin-by-zoho",
        "name": "Bigin by Zoho CRM",
        "description": "Bigin by Zoho CRM is a lightweight CRM designed for small businesses to manage contacts, companies, deals (pipeline records), tasks, calls, and events.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/bigin-by-zoho.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bika",
        "name": "Bika.ai",
        "description": "Interactive spreadsheets with collaboration",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/bika.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-binance",
        "name": "Binance",
        "description": "Fetch the price of a crypto pair from Binance",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/binance.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-messagebird",
        "name": "Bird",
        "description": "Unified CRM for Marketing, Service & Payments",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/messagebird.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bitly",
        "name": "Bitly",
        "description": "URL shortening and link management platform with analytics.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/bitly.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-blackbaud",
        "name": "Blackbaud",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/blackbaud.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-blockscout",
        "name": "Blockscout",
        "description": "Blockscout is a tool for inspecting and analyzing EVM chains.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/blockscout.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bloomerang",
        "name": "Bloomerang",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/bloomerang.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bluesky",
        "name": "Bluesky",
        "description": "",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/bluesky.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bolna",
        "name": "Bolna AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/bolna.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bonjoro",
        "name": "Bonjoro",
        "description": "Send personal video messages to delight customers",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/bonjoro.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bookedin",
        "name": "Bookedin",
        "description": "AI agents for lead conversion and appointment booking.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/bookedin.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-box",
        "name": "Box",
        "description": "Secure content management and collaboration",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/box.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sendinblue",
        "name": "Brevo",
        "description": "Formerly Sendinblue, is a SaaS solution for relationship marketing",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/brevo.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-brilliant-directories",
        "name": "Brilliant Directories",
        "description": "All-in-one membership software",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/brilliant-directories.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-browse-ai",
        "name": "Browse AI",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/browse-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-browserless",
        "name": "Browserless",
        "description": "Browserless is a headless browser automation tool that allows you to scrape websites, take screenshots, and more.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/browserless.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bubble",
        "name": "Bubble",
        "description": "No-code platform for web and mobile apps",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/bubble.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bumpups",
        "name": "Bumpups",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/bumpups.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-bursty-ai",
        "name": "BurstyAI",
        "description": "Automate content creation, SEO optimization, email outreach, and influencer partnerships with BurstyAI's no-code AI workflows.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/bursty-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cal-com",
        "name": "Cal.com",
        "description": "Open-source alternative to Calendly",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/cal.com.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-calendly",
        "name": "Calendly",
        "description": "Simple, modern scheduling",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/calendly.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [
            {
                "name": "invitee_created",
                "displayName": "Event Scheduled",
                "description": "Triggers when a new Calendly event is scheduled",
                "props": {
                    "scope": {
                        "displayName": "Scope",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "value": "user",
                                    "label": "User"
                                },
                                {
                                    "value": "organization",
                                    "label": "Organization"
                                }
                            ],
                            "disabled": false
                        }
                    }
                }
            },
            {
                "name": "invitee_canceled",
                "displayName": "Event Canceled",
                "description": "Triggers when a new Calendly event is canceled",
                "props": {
                    "scope": {
                        "displayName": "Scope",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "value": "user",
                                    "label": "User"
                                },
                                {
                                    "value": "organization",
                                    "label": "Organization"
                                }
                            ],
                            "disabled": false
                        }
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-rounded-studio",
        "name": "Call-rounded",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/call-rounded.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-camb-ai",
        "name": "Camb.AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/camb-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-campaign-monitor",
        "name": "Campaign Monitor",
        "description": "Email marketing platform for delivering exceptional email campaigns.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/campaign-monitor.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-capsule-crm",
        "name": "Capsule CRM",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/capsule-crm.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-captain-data",
        "name": "Captain-data",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/captain-data.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cartloom",
        "name": "Cartloom",
        "description": "Sell products beautifully",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/cartloom.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/cashfree-payments",
        "name": "Cashfree Payments",
        "description": "Cashfree Payments integration for processing payments, refunds, and managing payment links and cashgrams.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/cashfree-payments.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cashfree-payments",
        "name": "Cashfree Payments",
        "description": "Cashfree Payments integration for processing payments, refunds, and managing payment links and cashgrams.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/cashfree-payments.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-certopus",
        "name": "Certopus",
        "description": "Your certificates, made simple",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/certopus.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chainalysis-api",
        "name": "Chainalysis Screening API",
        "description": "Chainalysis Screening API allows you to check if a blockchain address is sanctioned.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/chainalysis-api.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chaindesk",
        "name": "Chaindesk",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/chaindesk.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chargekeep",
        "name": "ChargeKeep",
        "description": "Easy-to-use recurring and one-time payments software for Stripe & PayPal",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/chargekeep.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chat-aid",
        "name": "Chat Aid",
        "description": "AI-powered assistant for your knowledge base.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/chat-aid.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chat-data",
        "name": "Chat Data",
        "description": "Build AI-chatbots with support for live chat escalation, knowledge bases, or custom backend endpoints.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/chat-data.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chatbase",
        "name": "Chatbase",
        "description": "Build and manage AI chatbots with custom sources.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/chatbase.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chatfly",
        "name": "Chatfly",
        "description": "ChatFly allows you to build AI chatbots trained on your data.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/chatfly.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chatling",
        "name": "Chatling",
        "description": "Build AI chatbots trained on your data.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/chatling.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chatnode",
        "name": "ChatNode",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/chatnode.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-chatsistant",
        "name": "Chatsistant",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/chatsistant.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-checkout",
        "name": "Checkout.com",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/checkout.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-circle",
        "name": "Circle",
        "description": "Circle.so is a platform for creating and managing communities.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/circle.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-clarifai",
        "name": "Clarifai",
        "description": "AI-powered visual recognition",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/clarifai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-clearout",
        "name": "Clearout",
        "description": "Bulk email validation and verification",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/clearout.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-clearoutphone",
        "name": "ClearoutPhone",
        "description": "ClearoutPhone is a phone number validation and verification service that helps businesses ensure the accuracy and validity of their phone number data.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/clearoutphone.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-clickfunnels",
        "name": "ClickFunnels",
        "description": "",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/clickfunnels.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-clicksend",
        "name": "ClickSend SMS",
        "description": "Cloud-based messaging platform for sending SMS, MMS, voice, email, and more.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/clicksend.png",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-clickup",
        "name": "ClickUp",
        "description": "All-in-one productivity platform",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/clickup.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-clockify",
        "name": "Clockify",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/clockify.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-clockodo",
        "name": "Clockodo",
        "description": "Time tracking made easy",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/clockodo.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-close",
        "name": "Close",
        "description": "Sales automation and CRM integration for Close",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/close.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cloudconvert",
        "name": "CloudConvert",
        "description": "File conversion and processing platform supporting 200+ formats",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/cloudconvert.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cloudinary",
        "name": "Cloudinary",
        "description": "Cloudinary is a cloud-based image and video management platform that allows you to upload, store, manage, and deliver your media assets. It provides a range of features for image and video optimization, transformation, and delivery.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/cloudinary.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cloutly",
        "name": "Cloutly",
        "description": "Review Management Tool",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/cloutly.svg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-coda",
        "name": "Coda",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/coda.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cody",
        "name": "Cody",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/cody.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cognito-forms",
        "name": "Cognito Forms",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/cognito-forms.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cometapi",
        "name": "CometAPI",
        "description": "Access multiple AI models through CometAPI - unified interface for GPT, Claude, Gemini, and more.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/cometapi.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-comfyicu",
        "name": "Comfy.ICU",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/comfyicu.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-confluence",
        "name": "Confluence",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/confluence.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-connections",
        "name": "Connections",
        "description": "Read connections dynamically",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/connections.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-constant-contact",
        "name": "Constant Contact",
        "description": "Email marketing for small businesses",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/constant-contact.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-contentful",
        "name": "Contentful",
        "description": "Content infrastructure for digital teams",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/contentful.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-contextual-ai",
        "name": "Contextual AI",
        "description": "Integrate with Contextual AI to automate document processing and AI workflows",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/contextual-ai.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-contiguity",
        "name": "Contiguity",
        "description": "Communications for what you're building",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/contiguity.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-convertkit",
        "name": "ConvertKit",
        "description": "Email marketing for creators",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/convertkit.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-copper",
        "name": "Copper",
        "description": "",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/copper.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-copy-ai",
        "name": "Copy.ai",
        "description": "AI-powered content generation and copywriting platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/copy-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-couchbase",
        "name": "Couchbase",
        "description": "NoSQL document database for modern applications",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/couchbase.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-crisp",
        "name": "Crisp",
        "description": "",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/crisp.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-crypto",
        "name": "Crypto",
        "description": "Generate random passwords and hash existing text",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/crypto.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-csv",
        "name": "CSV",
        "description": "Manipulate CSV text",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/csv.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cursor",
        "name": "Cursor",
        "description": "AI-powered code editor with cloud agents that can work on your repositories. Launch agents, monitor their status, and automate code-related tasks.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/cursor.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-customer-io",
        "name": "customer.io",
        "description": "Create personalized journeys across all channels with our customer engagement platform.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/customerio.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-customgpt",
        "name": "CustomGPT",
        "description": "CustomGPT allows you to create and deploy custom AI chatbots tailored to your specific needs.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/customgpt.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-cyberark",
        "name": "CyberArk",
        "description": "Manage users, groups, and access controls in CyberArk Privileged Access Management",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/cyberark.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-dappier",
        "name": "Dappier",
        "description": "Enable fast, free real-time web search and access premium data from trusted media brands\u2014news, financial markets, sports, entertainment, weather, and more. Build powerful AI agents with Dappier",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/dappier.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-dashworks",
        "name": "Dashworks",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/dashworks.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-data-mapper",
        "name": "Data Mapper",
        "description": "tools to manipulate data structure",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/data-mapper.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-data-summarizer",
        "name": "Data Summarizer",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/data-summarizer.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-datadog",
        "name": "Datadog",
        "description": "Cloud monitoring and analytics platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/datadog.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-datafuel",
        "name": "DataFuel",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/datafuel.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-date-helper",
        "name": "Date Helper",
        "description": "Manipulate, format, and extract time units for all your date and time needs.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/calendar_piece.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-datocms",
        "name": "Dato CMS",
        "description": "Dato is a modern headless CMS",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/datocms.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-deepgram",
        "name": "Deepgram",
        "description": "Deepgram is an AI-powered speech recognition platform that provides real-time transcription, text-to-speech, and audio analysis capabilities.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/deepgram.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-deepl",
        "name": "DeepL",
        "description": "AI-powered language translation",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/deepl.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-deepseek",
        "name": "DeepSeek",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/deepseek.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-delay",
        "name": "Delay",
        "description": "Use it to delay the execution of the next action",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/delay.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-denser-ai",
        "name": "Denser.ai",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/denser-ai.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-devin",
        "name": "Devin AI",
        "description": "AI-powered engineering assistant for automating development tasks, code generation, and technical conversations.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/devin.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-digital-pilot",
        "name": "DigitalPilot",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/digital-pilot.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-dimo",
        "name": "DIMO",
        "description": "DIMO is an open protocol using blockchain to establish universal digital vehicle identity, permissions, data transmission, vehicle control, and payments. Developers use DIMO to build apps based on connected vehicles around the world while the vehicle owners benefit from monetizing their vehicle data.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/dimo.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-discord",
        "name": "Discord",
        "description": "Instant messaging and VoIP social platform",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/discord.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [
            {
                "name": "new_message",
                "displayName": "New message",
                "description": "Triggers when a message is sent in a channel",
                "props": {
                    "limit": {
                        "displayName": "Limit",
                        "description": "The number of messages to fetch",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 50
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "List of channels",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_member",
                "displayName": "New Member",
                "description": "Triggers when a new member joins a guild",
                "props": {
                    "limit": {
                        "displayName": "Limit",
                        "description": "The number of members to fetch (max 1000)",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 50
                    },
                    "guildId": {
                        "displayName": "Guild ID",
                        "description": "The ID of the Discord guild (server)",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "sendMessageWithBot",
                "displayName": "Send Message with Bot",
                "description": "Send messages via bot to any channel or thread you want, with an optional file attachment.",
                "props": {
                    "channel_id": {
                        "displayName": "Channel",
                        "description": "List of channels",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "message": {
                        "displayName": "Message",
                        "description": "Message content to send.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "files": {
                        "displayName": "Attachments",
                        "description": "",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": []
                    }
                }
            },
            {
                "name": "send_message_webhook",
                "displayName": "Send Message Webhook",
                "description": "Send a discord message via webhook",
                "props": {
                    "webhook_url": {
                        "displayName": "Webhook URL",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "username": {
                        "displayName": "Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "content": {
                        "displayName": "Message",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "avatar_url": {
                        "displayName": "Avatar URL",
                        "description": "The avatar url for webhook",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "embeds": {
                        "displayName": "embeds",
                        "description": "Embeds to send along with the message",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": []
                    },
                    "tts": {
                        "displayName": "Text to speech",
                        "description": "Robot reads the message",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "request_approval_message",
                "displayName": "Request Approval in a Channel",
                "description": "send a message to a channel asking for approval and wait for a response",
                "props": {
                    "content": {
                        "displayName": "Message",
                        "description": "The message you want to send",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "List of channels",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add_role_to_member",
                "displayName": "Add role to member",
                "description": "Add Guild Member Role",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "user_id": {
                        "displayName": "User ID",
                        "description": "The user id of the member",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "role_id": {
                        "displayName": "Roles",
                        "description": "List of roles",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "remove_role_from_member",
                "displayName": "Remove role from member",
                "description": "Remove Guild Member Role",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "user_id": {
                        "displayName": "User ID",
                        "description": "The user id of the member",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "role_id": {
                        "displayName": "Roles",
                        "description": "List of roles",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "remove_member_from_guild",
                "displayName": "Remove member from guild",
                "description": "Remove Guild Member",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "user_id": {
                        "displayName": "User ID",
                        "description": "The user id of the member",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "list_guild_members",
                "displayName": "List guild members",
                "description": "List Guild Members",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "shortText": {
                        "displayName": "Search",
                        "description": "Search for a member",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "rename_channel",
                "displayName": "Rename channel",
                "description": "rename a channel",
                "props": {
                    "channel_id": {
                        "displayName": "Channel",
                        "description": "List of channels",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Name",
                        "description": "The new name of the channel",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_channel",
                "displayName": "Create channel",
                "description": "create a channel",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Name",
                        "description": "The name of the new channel",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete_channel",
                "displayName": "Delete channel",
                "description": "delete a channel",
                "props": {
                    "channel_id": {
                        "displayName": "Channel",
                        "description": "List of channels",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_channel",
                "displayName": "Find channel",
                "description": "find a channel by name",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Name",
                        "description": "The name of the channel",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "remove_ban_from_user",
                "displayName": "Remove ban from user",
                "description": "Removes the guild ban from a user",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "user_id": {
                        "displayName": "User ID",
                        "description": "The ID of the user",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "unban_reason": {
                        "displayName": "Unban Reason",
                        "description": "The reason for unbanning the user",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "createGuildRole",
                "displayName": "Create guild role",
                "description": "Creates a new role on the specified guild",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "role_name": {
                        "displayName": "Role Name",
                        "description": "The name of the role",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "role_color": {
                        "displayName": "Role Color",
                        "description": "The RGB color of the role (may be better to set manually on the server)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "display_separated": {
                        "displayName": "Display Separated",
                        "description": "Whether the role should be displayed separately in the sidebar",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "role_mentionable": {
                        "displayName": "Mentionable",
                        "description": "Whether the role can be mentioned by other users",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "creation_reason": {
                        "displayName": "Creation Reason",
                        "description": "The reason for creating the role",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "deleteGuildRole",
                "displayName": "Delete guild role",
                "description": "Deletes the specified role from the specified guild",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "role_id": {
                        "displayName": "Roles",
                        "description": "List of roles",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "deletion_reason": {
                        "displayName": "Deletion reason",
                        "description": "The reason for deleting the role",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "ban_guild_member",
                "displayName": "Ban guild member",
                "description": "Bans a guild member",
                "props": {
                    "guild_id": {
                        "displayName": "Guilds",
                        "description": "List of guilds",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "user_id": {
                        "displayName": "User ID",
                        "description": "The user id of the member",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "ban_reason": {
                        "displayName": "Ban Reason",
                        "description": "The reason for banning the member",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-discourse",
        "name": "Discourse",
        "description": "Modern open source forum software",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/discourse.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-dittofeed",
        "name": "Dittofeed",
        "description": "Customer data platform for user analytics and tracking",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/dittofeed.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-docsbot",
        "name": "DocsBot",
        "description": "DocsBot AI allows you to build AI-powered chatbots that pull answers from your existing documentation and content. This integration enables workflows to ask DocsBot questions and update its training sources dynamically.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/docsbot.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-doctly",
        "name": "Doctly AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/doctly.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-documentpro",
        "name": "DocumentPro",
        "description": "DocumentPro is an AI-powered document processing platform that automates data extraction from various document types using advanced machine learning algorithms.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/documentpro.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-documerge",
        "name": "DocuMerge",
        "description": "Merge and generate documents with dynamic data",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/documerge.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-docusign",
        "name": "Docusign",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/docusign.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-drip",
        "name": "Drip",
        "description": "E-commerce CRM for B2B marketers",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/drip.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-dropbox",
        "name": "Dropbox",
        "description": "Cloud storage and file synchronization",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/dropbox.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-drupal",
        "name": "Drupal",
        "description": "",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/drupal.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-dumpling-ai",
        "name": "Dumpling AI",
        "description": "Transform unstructured website content into clean, AI-ready data",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/dumpling-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-dust",
        "name": "Dust",
        "description": "Secure messaging and collaboration",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/dust.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-easy-peasy-ai",
        "name": "Easy-Peasy.AI",
        "description": "Create professional-quality music in any genre with just a text prompt. From hip-hop to classical, our AI generates custom tracks for your projects in seconds.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/easy-peasy-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-echowin",
        "name": "Echowin",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/echowin.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-eden-ai",
        "name": "Eden AI",
        "description": "Eden AI is a platform that provides a range of AI services, including text generation, summarization, translation, and more.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/eden-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-elevenlabs",
        "name": "ElevenLabs",
        "description": "AI Voice Generator & Text to Speech",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/elevenlabs.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-emailoctopus",
        "name": "EmailOctopus",
        "description": "Email marketing platform for list management, campaign sending, tagging & unsubscribes. Automate contact management and campaign engagement tracking.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/emailoctopus.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-esignatures",
        "name": "eSignatures",
        "description": "",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/esignatures.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-eth-name-service",
        "name": "Ethereum Name Service (ENS)",
        "description": "Ethereum Name Service (ENS) is a decentralized naming system on the Ethereum blockchain.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/eth-name-service.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-exa",
        "name": "Exa",
        "description": "AI-powered search and content extraction from the web.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/exa.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-extracta-ai",
        "name": "Extracta.ai",
        "description": "An AI document extraction & content analysis platform that transforms unstructured files (PDFs, images, URLs, etc.) into structured data.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/extracta-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-facebook-leads",
        "name": "Facebook Leads",
        "description": "Capture leads from Facebook",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/facebook.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-facebook-pages",
        "name": "Facebook Pages",
        "description": "Manage your Facebook pages to grow your business",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/facebook.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-famulor",
        "name": "Famulor AI - Voice Agent",
        "description": "AI-powered calling and SMS platform. Automate outbound campaigns, manage leads, and get real-time call analytics.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/famulor.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-fathom",
        "name": "Fathom",
        "description": "Fathom is an AI meeting assistant that automatically records, transcribes, highlights, and generates AI summaries and action items from your meetings. Integrate with workflows to react to meeting events and retrieve meeting data.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/fathom.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-feathery",
        "name": "Feathery",
        "description": "Build powerful forms, workflows, and document automation.",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/feathery.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-fellow",
        "name": "Fellow.ai",
        "description": "AI Meeting Assistant and Notetaker",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/fellow.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-figma",
        "name": "Figma",
        "description": "Collaborative interface design tool",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/figma.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "new_comment",
                "displayName": "New Comment (Figma Professional plan only)",
                "description": "Triggers when a new comment is posted",
                "props": {
                    "team_id": {
                        "displayName": "Team ID",
                        "description": "Naviate to team page, copy the Id from the URL after the word team/",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "get_file",
                "displayName": "Get File",
                "description": "Get file",
                "props": {
                    "file_key": {
                        "displayName": "File Key",
                        "description": "The Figma file key (copy from Figma file URL)",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_comments",
                "displayName": "Get File Comments",
                "description": "Get file comments",
                "props": {
                    "file_key": {
                        "displayName": "File Key",
                        "description": "The Figma file key (copy from Figma file URL)",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "post_comment",
                "displayName": "Post File Comment",
                "description": "Post file comment",
                "props": {
                    "file_key": {
                        "displayName": "File Key",
                        "description": "The Figma file key (copy from Figma file URL)",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "message": {
                        "displayName": "Comment",
                        "description": "Your comment",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-file-helper",
        "name": "Files Helper",
        "description": "Read file content and return it in different formats.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/file-piece.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-fillout-forms",
        "name": "Fillout Forms",
        "description": "Create interactive forms and automate workflows with Fillout",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/fillout-forms.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-fireberry",
        "name": "Fireberry",
        "description": "",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/fireberry.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-firecrawl",
        "name": "Firecrawl",
        "description": "Extract structured data from websites using AI with natural language prompts",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/firecrawl.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-fireflies-ai",
        "name": "Fireflies.ai",
        "description": "Meeting assistant that automatically records, transcribes, and analyzes conversations",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/fireflies-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-fliqr-ai",
        "name": "Fliqr AI",
        "description": "Omnichannel AI chatbot enhancing customer interactions across WhatsApp, Facebook, Instagram, Telegram, and 6 other platforms.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/fliqr-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-flow-helper",
        "name": "Flow Helper",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/flow-helper.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-flowise",
        "name": "Flowise",
        "description": "No-Code AI workflow builder",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/flowise.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-flowlu",
        "name": "Flowlu",
        "description": "Business management software",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/flowlu.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-flow-parser",
        "name": "FlowParser",
        "description": "Upload, process, and manage documents programmatically with FlowParser's REST API.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/flow-parser.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-folk",
        "name": "Folk",
        "description": "Folk is a CRM for building relationships at scale. Manage your contacts, companies, and relationships in one place.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/folk.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-foreplay-co",
        "name": "Foreplay",
        "description": "Competitive advertising data and creative insights platform. Search, filter, and analyze ads and brands with live and historical ad creatives, metadata, and competitive intelligence.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/foreplay-co.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-formbricks",
        "name": "Formbricks",
        "description": "Open source Survey Platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/formbricks.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-formsite",
        "name": "Formsite",
        "description": "Formsite is an online form builder that allows you to create forms and surveys easily.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/formsite.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-formspark",
        "name": "Formspark",
        "description": "",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/formspark.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-formstack",
        "name": "Formstack",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/formstack.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-fountain",
        "name": "Fountain",
        "description": "Automate your complete HR hiring and onboarding workflow. Manage applicants, job openings, interview scheduling, and track progress through hiring stages with real-time webhooks.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/fountain.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-fragment",
        "name": "Fragment",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/fragment.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-frame",
        "name": "Frame",
        "description": "Collaborative workspace platform",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/frameio.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-free-agent",
        "name": "FreeAgent",
        "description": "Accounting and invoicing software for small businesses",
        "category": "finance",
        "icon": "https://cdn.activepieces.com/pieces/free-agent.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-freshdesk",
        "name": "Freshdesk",
        "description": "Customer support software",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/freshdesk.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-freshsales",
        "name": "Freshsales",
        "description": "Sales CRM software",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/freshsales.png",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-front",
        "name": "Front",
        "description": "",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/front.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sftp",
        "name": "FTP/SFTP",
        "description": "Connect to FTP, FTPS or SFTP servers",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/sftp.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gameball",
        "name": "Gameball",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/gameball.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gamma",
        "name": "Gamma",
        "description": "An AI-powered design partner that helps users generate presentations, documents, social media posts, cards, etc., via natural language.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/gamma.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gcloud-pubsub",
        "name": "GCloud Pub/Sub",
        "description": "Google Cloud's event streaming service",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/gcloud-pubsub.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-generatebanners",
        "name": "GenerateBanners",
        "description": "Image generation API for banners and social media posts",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/generatebanners.png",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-ghostcms",
        "name": "GhostCMS",
        "description": "Publishing platform for professional bloggers",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/ghostcms.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-giftbit",
        "name": "Giftbit",
        "description": "Send digital gift cards and rewards to recipients via email.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/giftbit.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gistly",
        "name": "Gistly",
        "description": "YouTube Transcripts",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/gistly.svg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-github",
        "name": "GitHub",
        "description": "Developer platform that allows developers to create, store, manage and share their code",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/github.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "trigger_pull_request",
                "displayName": "New Pull Request",
                "description": "Triggers when there is activity on a pull request.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "trigger_star",
                "displayName": "New Star",
                "description": "Trigger when there is activity relating to repository stars.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "trigger_issues",
                "displayName": "New Issue",
                "description": "Triggers when there is activity relating to an issue.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "trigger_push",
                "displayName": "Push",
                "description": "Triggers when there is a push to a repository branch. This includes when a commit is pushed, when a commit tag is pushed, when a branch is deleted, when a tag is deleted, or when a repository is created from a template.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "trigger_discussion",
                "displayName": "New Discussion",
                "description": "Triggers when there is activity relating to a discussion.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "trigger_discussion_comment",
                "displayName": "New Comment Posted",
                "description": "Triggers when there is a new comment posted on a discussion.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_branch",
                "displayName": "New Branch",
                "description": "Triggers when a new branch is created.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_collaborator",
                "displayName": "New Collaborator",
                "description": "Triggers when a new collaborator is added to a repository.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_label",
                "displayName": "New Label",
                "description": "Triggers when a new label is created in a repository.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_milestone",
                "displayName": "New Milestone",
                "description": "Triggers when a new milestone is created.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_release",
                "displayName": "New Release",
                "description": "Triggers when a new release is added.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "github_create_issue",
                "displayName": "Create Issue",
                "description": "Create Issue in GitHub Repository",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "The title of the issue",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "The description of the issue",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "labels": {
                        "displayName": "Labels",
                        "description": "Labels for the Issue",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "assignees": {
                        "displayName": "Assignees",
                        "description": "Assignees for the Issue",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "getIssueInformation",
                "displayName": "Get issue information",
                "description": "Grabs information from a specific issue",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "issue_number": {
                        "displayName": "Issue Number",
                        "description": "The number of the issue you want to get information from",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "createCommentOnAIssue",
                "displayName": "Create comment on a issue",
                "description": "Adds a comment to the specified issue (also works with pull requests)",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "issue_number": {
                        "displayName": "Issue number",
                        "description": "The number of the issue to comment on",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "comment": {
                        "displayName": "Comment",
                        "description": "The comment to add to the issue",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "lockIssue",
                "displayName": "Lock issue",
                "description": "Locks the specified issue",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "issue_number": {
                        "displayName": "Issue Number",
                        "description": "The number of the issue to be locked",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "lock_reason": {
                        "displayName": "Lock Reason",
                        "description": "The reason for locking the issue",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "unlockIssue",
                "displayName": "Unlock issue",
                "description": "Unlocks the specified issue",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "issue_number": {
                        "displayName": "Issue Number",
                        "description": "The number of the issue to be unlocked",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "rawGraphqlQuery",
                "displayName": "Raw GraphQL query",
                "description": "Perform a raw GraphQL query",
                "props": {
                    "query": {
                        "displayName": "Query",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "variables": {
                        "displayName": "Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "github_create_pull_request_review_comment",
                "displayName": "Create Pull Request Review Comment",
                "description": "Creates a review comment on a pull request in a GitHub repository",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "pull_number": {
                        "displayName": "Pull Request Number",
                        "description": "The number of the pull request",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "commit_id": {
                        "displayName": "Commit SHA",
                        "description": "The SHA of the commit to comment on",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "path": {
                        "displayName": "File Path",
                        "description": "The relative path to the file to comment on",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Comment Body",
                        "description": "The content of the review comment",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "position": {
                        "displayName": "Position",
                        "description": "The position in the diff where the comment should be placed",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "github_create_commit_comment",
                "displayName": "Create Commit Comment",
                "description": "Creates a comment on a commit in a GitHub repository",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sha": {
                        "displayName": "Commit SHA",
                        "description": "The SHA of the commit to comment on",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Comment Body",
                        "description": "The content of the comment",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "path": {
                        "displayName": "File Path",
                        "description": "The relative path to the file to comment on (optional)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "position": {
                        "displayName": "Position",
                        "description": "The line index in the diff to comment on (optional)",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "github_create_discussion_comment",
                "displayName": "Create Discussion Comment",
                "description": "Creates a comment on a discussion in a GitHub repository",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "discussion_number": {
                        "displayName": "Discussion Number",
                        "description": "The number of the discussion to comment on",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Comment Body",
                        "description": "The content of the comment (supports markdown)",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add_labels_to_issue",
                "displayName": "Add Labels to Issue",
                "description": "Adds labels to an existing issue.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "issue_number": {
                        "displayName": "Issue",
                        "description": "The issue to select.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "labels": {
                        "displayName": "Labels",
                        "description": "Labels for the Issue",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_branch",
                "displayName": "Create Branch",
                "description": "Creates a new branch on a repository.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "source_branch": {
                        "displayName": "Source Branch",
                        "description": "The source branch that will be used to create the new branch",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "new_branch_name": {
                        "displayName": "New Branch Name",
                        "description": "The name for the new branch (e.g., 'feature/new-design').",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete_branch",
                "displayName": "Delete Branch",
                "description": "Deletes a branch from a repository.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "branch": {
                        "displayName": "Branch",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_issue",
                "displayName": "Update Issue",
                "description": "Updates an existing issue.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "issue_number": {
                        "displayName": "Issue",
                        "description": "The issue to select.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "state": {
                        "displayName": "State",
                        "description": "The new state of the issue.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Open",
                                    "value": "open"
                                },
                                {
                                    "label": "Closed",
                                    "value": "closed"
                                }
                            ]
                        }
                    },
                    "state_reason": {
                        "displayName": "State Reason",
                        "description": "The reason for the state change. (Only used if State is changed).",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Completed",
                                    "value": "completed"
                                },
                                {
                                    "label": "Not Planned",
                                    "value": "not_planned"
                                },
                                {
                                    "label": "Reopened",
                                    "value": "reopened"
                                },
                                {
                                    "label": "Duplicate",
                                    "value": "duplicate"
                                }
                            ]
                        }
                    },
                    "milestone": {
                        "displayName": "Milestone",
                        "description": "The milestone to associate this issue with.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "labels": {
                        "displayName": "Labels",
                        "description": "Labels for the Issue",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "assignees": {
                        "displayName": "Assignees",
                        "description": "Assignees for the Issue",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_branch",
                "displayName": "Find Branch",
                "description": "Finds a branch by name and returns its details.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "branch": {
                        "displayName": "Branch Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_issue",
                "displayName": "Find Issue",
                "description": "Finds an issue based title.",
                "props": {
                    "repository": {
                        "displayName": "Repository",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "state": {
                        "displayName": "State",
                        "description": "Filter issues by their state.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Open",
                                    "value": "open"
                                },
                                {
                                    "label": "Closed",
                                    "value": "closed"
                                },
                                {
                                    "label": "All",
                                    "value": "all"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "find_user",
                "displayName": "Find User",
                "description": "Finds a user by their login name.",
                "props": {
                    "username": {
                        "displayName": "Username",
                        "description": "The GitHub username (login) to look up.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-gitlab",
        "name": "GitLab",
        "description": "Collaboration tool for developers",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/gitlab.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gladia",
        "name": "Gladia",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/gladia.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gmail",
        "name": "Gmail",
        "description": "Email service by Google",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/gmail.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "gmail_new_email_received",
                "displayName": "New Email",
                "description": "Triggers when new mail is found in your Gmail inbox",
                "props": {
                    "subject": {
                        "displayName": "Email subject",
                        "description": "The email subject",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": ""
                    },
                    "from": {
                        "displayName": "Email sender",
                        "description": "Optional filteration, leave empty to filter based on the email sender",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": ""
                    },
                    "to": {
                        "displayName": "Email recipient",
                        "description": "Optional filteration, leave empty to filter based on the email recipient",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": ""
                    },
                    "label": {
                        "displayName": "Label",
                        "description": "Optional filteration, leave unselected to filter based on the email label",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": ""
                    },
                    "category": {
                        "displayName": "Category",
                        "description": "Optional filteration, leave unselected to filter based on the email category",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Primary",
                                    "value": "primary"
                                },
                                {
                                    "label": "Social",
                                    "value": "social"
                                },
                                {
                                    "label": "Promotions",
                                    "value": "promotions"
                                },
                                {
                                    "label": "Updates",
                                    "value": "updates"
                                },
                                {
                                    "label": "Forums",
                                    "value": "forums"
                                },
                                {
                                    "label": "Reservations",
                                    "value": "reservations"
                                },
                                {
                                    "label": "Purchases",
                                    "value": "purchases"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "new_labeled_email",
                "displayName": "New Labeled Email",
                "description": "Triggers when a label is added to an email",
                "props": {
                    "label": {
                        "displayName": "Label",
                        "description": "Optional filteration, leave unselected to filter based on the email label",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": ""
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "send_email",
                "displayName": "Send Email",
                "description": "Send an email through a Gmail account",
                "props": {
                    "receiver": {
                        "displayName": "Receiver Email (To)",
                        "description": "",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    },
                    "cc": {
                        "displayName": "CC Email",
                        "description": "",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "bcc": {
                        "displayName": "BCC Email",
                        "description": "",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "subject": {
                        "displayName": "Subject",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body_type": {
                        "displayName": "Body Type",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "plain_text",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "plain text",
                                    "value": "plain_text"
                                },
                                {
                                    "label": "html",
                                    "value": "html"
                                }
                            ]
                        }
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "Body for the email you want to send",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "reply_to": {
                        "displayName": "Reply-To Email",
                        "description": "Email address to set as the \"Reply-To\" header",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "sender_name": {
                        "displayName": "Sender Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "from": {
                        "displayName": "Sender Email",
                        "description": "The address must be listed in your GMail account's settings",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "attachments": {
                        "displayName": "Attachments",
                        "description": "",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "in_reply_to": {
                        "displayName": "In reply to",
                        "description": "Reply to this Message-ID",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "draft": {
                        "displayName": "Create draft",
                        "description": "Create draft without sending the actual email",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-google-calendar",
        "name": "Google Calendar",
        "description": "Get organized and stay on schedule",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/google-calendar.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "new_or_updated_event",
                "displayName": "New or Updated Event",
                "description": "Triggers when an event is added or updated",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "expandRecurringEvent": {
                        "displayName": "Expand Recurring Event?",
                        "description": "If true, the trigger will activate for every occurrence of a recurring event.",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new_event",
                "displayName": "New Event",
                "description": "Fires when a new event is created in a calendar.",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "event_types": {
                        "displayName": "Event Types to Monitor",
                        "description": "Filter by specific event types (leave empty to monitor all event types)",
                        "type": "STATIC_MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Default Events",
                                    "value": "default"
                                },
                                {
                                    "label": "Birthday Events",
                                    "value": "birthday"
                                },
                                {
                                    "label": "Focus Time",
                                    "value": "focusTime"
                                },
                                {
                                    "label": "Out of Office",
                                    "value": "outOfOffice"
                                },
                                {
                                    "label": "Working Location",
                                    "value": "workingLocation"
                                },
                                {
                                    "label": "From Gmail",
                                    "value": "fromGmail"
                                }
                            ]
                        }
                    },
                    "search_filter": {
                        "displayName": "Search Filter",
                        "description": "Only trigger for events containing this text in title, description, or location (optional)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "exclude_all_day": {
                        "displayName": "Exclude All-Day Events",
                        "description": "Skip triggering for all-day events",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "event_ends",
                "displayName": "Event Ends",
                "description": "Fires when an event ends.",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "specific_event": {
                        "displayName": "Target Specific Event",
                        "description": "Enable to monitor a specific event instead of all events in the calendar.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "event_id": {
                        "displayName": "Event",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "event_starts_in",
                "displayName": "Event Start (Time Before)",
                "description": "Fires at a specified amount of time before an event starts (e.g., a reminder).",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "specific_event": {
                        "displayName": "Target Specific Event",
                        "description": "Enable to monitor a specific event instead of all events in the calendar.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "event_id": {
                        "displayName": "Event",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "time_value": {
                        "displayName": "Time Before",
                        "description": "The amount of time before the event starts.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 15
                    },
                    "time_unit": {
                        "displayName": "Time Unit",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "minutes",
                        "options": {
                            "options": [
                                {
                                    "label": "Minutes",
                                    "value": "minutes"
                                },
                                {
                                    "label": "Hours",
                                    "value": "hours"
                                },
                                {
                                    "label": "Days",
                                    "value": "days"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "new_event_matching_search",
                "displayName": "New Event Matching Search",
                "description": "Fires when a new event is created that matches a specified search term.",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "search_term": {
                        "displayName": "Search Term",
                        "description": "The keyword(s) to search for in new events (searches across title, description, location, and attendees by default).",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "event_types": {
                        "displayName": "Event Types",
                        "description": "Filter by specific event types (optional)",
                        "type": "STATIC_MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Default Events",
                                    "value": "default"
                                },
                                {
                                    "label": "Birthday Events",
                                    "value": "birthday"
                                },
                                {
                                    "label": "Focus Time",
                                    "value": "focusTime"
                                },
                                {
                                    "label": "Out of Office",
                                    "value": "outOfOffice"
                                },
                                {
                                    "label": "Working Location",
                                    "value": "workingLocation"
                                },
                                {
                                    "label": "From Gmail",
                                    "value": "fromGmail"
                                }
                            ]
                        }
                    },
                    "search_fields": {
                        "displayName": "Search In Fields",
                        "description": "Specify which fields to search in (leave empty to use Google's default search across all fields)",
                        "type": "STATIC_MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Event Title/Summary",
                                    "value": "summary"
                                },
                                {
                                    "label": "Event Description",
                                    "value": "description"
                                },
                                {
                                    "label": "Event Location",
                                    "value": "location"
                                },
                                {
                                    "label": "Attendee Names/Emails",
                                    "value": "attendees"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "event_cancelled",
                "displayName": "Event Cancelled",
                "description": "Fires when an event is canceled or deleted.",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "specific_event": {
                        "displayName": "Target Specific Event",
                        "description": "Enable to monitor a specific event instead of all events in the calendar.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "event_id": {
                        "displayName": "Event",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "cancellation_reason": {
                        "displayName": "Cancellation Reasons",
                        "description": "Filter by specific types of cancellations (optional)",
                        "type": "STATIC_MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Event Deleted",
                                    "value": "deleted"
                                },
                                {
                                    "label": "Attendee Declined",
                                    "value": "declined"
                                },
                                {
                                    "label": "Event Rescheduled",
                                    "value": "rescheduled"
                                },
                                {
                                    "label": "Other Cancellations",
                                    "value": "other"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "new_calendar",
                "displayName": "New Calendar",
                "description": "Fires when a new calendar is created or becomes accessible.",
                "props": {
                    "access_role_filter": {
                        "displayName": "Access Role Filter",
                        "description": "Only trigger for calendars with specific access roles (optional)",
                        "type": "STATIC_MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Owner",
                                    "value": "owner"
                                },
                                {
                                    "label": "Writer",
                                    "value": "writer"
                                },
                                {
                                    "label": "Reader",
                                    "value": "reader"
                                },
                                {
                                    "label": "Free/Busy Reader",
                                    "value": "freeBusyReader"
                                }
                            ]
                        }
                    },
                    "calendar_name_filter": {
                        "displayName": "Calendar Name Filter",
                        "description": "Only trigger for calendars containing this text in name or description (optional)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "exclude_shared": {
                        "displayName": "Exclude Shared Calendars",
                        "description": "Only trigger for calendars you own, not shared calendars",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "google-calendar-add-attendees",
                "displayName": "Add Attendees to Event",
                "description": "Add one or more person to existing event.",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "eventId": {
                        "displayName": "Event ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "attendees": {
                        "displayName": "Attendees",
                        "description": "Emails of the attendees (guests)",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_quick_event",
                "displayName": "Create Quick Event",
                "description": "Add Quick Calendar Event",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Summary",
                        "description": "The text describing the event to be created",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "send_updates": {
                        "displayName": "Send Updates",
                        "description": "Guests who should receive notifications about the creation of the new event.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "All",
                                    "value": "all"
                                },
                                {
                                    "label": "External Only",
                                    "value": "externalOnly"
                                },
                                {
                                    "label": "none",
                                    "value": "none"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "create_google_calendar_event",
                "displayName": "Create Event",
                "description": "Add Event",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title of the event",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "start_date_time": {
                        "displayName": "Start date time of the event",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": true,
                        "defaultValue": null
                    },
                    "end_date_time": {
                        "displayName": "End date time of the event",
                        "description": "By default it'll be 30 min post start time",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "location": {
                        "displayName": "Location",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "Description of the event. You can use HTML tags here.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "colorId": {
                        "displayName": "Color",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "attendees": {
                        "displayName": "Attendees",
                        "description": "Emails of the attendees (guests)",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "guests_can_modify": {
                        "displayName": "Guests can modify",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "guests_can_invite_others": {
                        "displayName": "Guests can invite others",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "guests_can_see_other_guests": {
                        "displayName": "Guests can see other guests",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "send_notifications": {
                        "displayName": "Send Notifications",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "all",
                        "options": {
                            "options": [
                                {
                                    "label": "Yes, to everyone",
                                    "value": "all"
                                },
                                {
                                    "label": "To non-Google Calendar guests only",
                                    "value": "externalOnly"
                                },
                                {
                                    "label": "To no one",
                                    "value": "none"
                                }
                            ]
                        }
                    },
                    "create_meet_link": {
                        "displayName": "Create Google Meet Link",
                        "description": "Automatically create a Google Meet video conference link for this event",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "google_calendar_get_events",
                "displayName": "Get all Events",
                "description": "Get Events",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "event_types": {
                        "displayName": "Event types",
                        "description": "Select event types",
                        "type": "STATIC_MULTI_SELECT_DROPDOWN",
                        "required": true,
                        "defaultValue": [
                            "default",
                            "focusTime",
                            "outOfOffice"
                        ],
                        "options": {
                            "options": [
                                {
                                    "label": "Default",
                                    "value": "default"
                                },
                                {
                                    "label": "Out Of Office",
                                    "value": "outOfOffice"
                                },
                                {
                                    "label": "Focus Time",
                                    "value": "focusTime"
                                },
                                {
                                    "label": "Working Location",
                                    "value": "workingLocation"
                                }
                            ]
                        }
                    },
                    "search": {
                        "displayName": "Search Term",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "start_date": {
                        "displayName": "Date from",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "end_date": {
                        "displayName": "Date to",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "singleEvents": {
                        "displayName": "Expand Recurring Event?",
                        "description": "Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves.",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "update_event",
                "displayName": "Update Event",
                "description": "Updates an event in Google Calendar.",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "eventId": {
                        "displayName": "Event ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title of the event",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "start_date_time": {
                        "displayName": "Start date time of the event",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "end_date_time": {
                        "displayName": "End date time of the event",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "location": {
                        "displayName": "Location",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "Description of the event. You can use HTML tags here.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "colorId": {
                        "displayName": "Color",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "attendees": {
                        "displayName": "Attendees",
                        "description": "Emails of the attendees (guests)",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "guests_can_modify": {
                        "displayName": "Guests can modify",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "guests_can_invite_others": {
                        "displayName": "Guests can invite others",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "guests_can_see_other_guests": {
                        "displayName": "Guests can see other guests",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "delete_event",
                "displayName": "Delete Event",
                "description": "Deletes an event from Google Calendar.",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "eventId": {
                        "displayName": "Event ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "google_calendar_find_busy_free_periods",
                "displayName": "Find Busy/Free Periods in Calendar",
                "description": "Finds free/busy calendar details from Google Calendar.",
                "props": {
                    "calendar_ids": {
                        "displayName": "Calendars",
                        "description": "Select the calendars to check for busy periods.",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "start_date": {
                        "displayName": "Start Time",
                        "description": "The start of the time range to check.",
                        "type": "DATE_TIME",
                        "required": true,
                        "defaultValue": null
                    },
                    "end_date": {
                        "displayName": "End Time",
                        "description": "The end of the time range to check.",
                        "type": "DATE_TIME",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "google_calendar_get_event_by_id",
                "displayName": "Get Event by ID",
                "description": "Fetch event details by its unique ID from Google Calendar.",
                "props": {
                    "calendar_id": {
                        "displayName": "Calendar",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "event_id": {
                        "displayName": "Event ID",
                        "description": "The unique ID of the event (e.g., \"abc123def456\"). You can find this in the event URL or from other calendar actions.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "max_attendees": {
                        "displayName": "Max Attendees",
                        "description": "Maximum number of attendees to include in the response. If there are more attendees, only the participant is returned.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "time_zone": {
                        "displayName": "Time Zone",
                        "description": "Time zone for the response (e.g., \"America/New_York\", \"Europe/London\"). Defaults to the calendar's time zone if not specified.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-googlechat",
        "name": "Google Chat",
        "description": "Google Chat is a messaging app that allows you to send and receive messages, create spaces, and more.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/googlechat.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-cloud-storage",
        "name": "Google Cloud Storage",
        "description": "Automate file storage operations with Google Cloud Storage. Upload, download, manage buckets, set permissions, and monitor changes with real-time triggers.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/google-cloud-storage.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-contacts",
        "name": "Google Contacts",
        "description": "Stay connected and organized",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/google-contacts.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-docs",
        "name": "Google Docs",
        "description": "Create and edit documents online",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/google-docs.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-drive",
        "name": "Google Drive",
        "description": "Cloud storage and file backup",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/google-drive.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "new_file",
                "displayName": "New File",
                "description": "Trigger when a new file is uploaded.",
                "props": {
                    "parentFolder": {
                        "displayName": "Parent Folder",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "include_file_content": {
                        "displayName": "Include File Content",
                        "description": "Include the file content in the output. This will increase the time taken to fetch the files and might cause issues with large files.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new_folder",
                "displayName": "New Folder",
                "description": "Trigger when a new folder is created or uploaded.",
                "props": {
                    "parentFolder": {
                        "displayName": "Parent Folder",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "create_new_gdrive_folder",
                "displayName": "Create new folder",
                "description": "Create a new empty folder in your Google Drive",
                "props": {
                    "folderName": {
                        "displayName": "Folder name",
                        "description": "The name of the new folder",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "parentFolder": {
                        "displayName": "Parent Folder",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "create_new_gdrive_file",
                "displayName": "Create new file",
                "description": "Create a new text file in your Google Drive from text",
                "props": {
                    "fileName": {
                        "displayName": "File name",
                        "description": "The name of the new text file",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Text",
                        "description": "The text content to add to file",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "fileType": {
                        "displayName": "Content type",
                        "description": "Select file type",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "plain/text",
                        "options": {
                            "options": [
                                {
                                    "label": "Text",
                                    "value": "plain/text"
                                },
                                {
                                    "label": "CSV",
                                    "value": "text/csv"
                                },
                                {
                                    "label": "XML",
                                    "value": "text/xml"
                                }
                            ]
                        }
                    },
                    "parentFolder": {
                        "displayName": "Parent Folder",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "upload_gdrive_file",
                "displayName": "Upload file",
                "description": "Upload a file in your Google Drive",
                "props": {
                    "fileName": {
                        "displayName": "File name",
                        "description": "The name of the file",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "file": {
                        "displayName": "File",
                        "description": "The file URL or base64 to upload",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "parentFolder": {
                        "displayName": "Parent Folder",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "read-file",
                "displayName": "Read File Content",
                "description": "Read a selected file from google drive file",
                "props": {
                    "fileId": {
                        "displayName": "File ID",
                        "description": "File ID coming from | New File -> id |",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "fileName": {
                        "displayName": "Destination File name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-file-or-folder-by-id",
                "displayName": "Get File Information",
                "description": "Get a file folder for files/sub-folders",
                "props": {
                    "id": {
                        "displayName": "File / Folder Id",
                        "description": "The Id of the file/folder to search for.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "list-files",
                "displayName": "List files",
                "description": "List files from a Google Drive folder",
                "props": {
                    "folderId": {
                        "displayName": "Folder ID",
                        "description": "Folder ID coming from | New Folder -> id | (or any other source)",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "includeTrashed": {
                        "displayName": "Include Trashed",
                        "description": "Include new files that have been trashed.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "depthLevel": {
                        "displayName": "Depth Level",
                        "description": "How many levels deep to search for files. 1 = current folder only, 2 = current + next level, etc.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 1
                    },
                    "downloadFiles": {
                        "displayName": "Download Files",
                        "description": "Download all file contents in a list",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "search-folder",
                "displayName": "Search",
                "description": "Search a Google Drive folder for files/sub-folders",
                "props": {
                    "queryTerm": {
                        "displayName": "Query Term",
                        "description": "The Query term or field of file/folder to search upon.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "name",
                        "options": {
                            "options": [
                                {
                                    "label": "File name",
                                    "value": "name"
                                },
                                {
                                    "label": "Full text search",
                                    "value": "fullText"
                                },
                                {
                                    "label": "Content type",
                                    "value": "mimeType"
                                }
                            ]
                        }
                    },
                    "operator": {
                        "displayName": "Operator",
                        "description": "The operator to create criteria.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "contains",
                        "options": {
                            "options": [
                                {
                                    "label": "Contains",
                                    "value": "contains"
                                },
                                {
                                    "label": "Equals",
                                    "value": "="
                                }
                            ]
                        }
                    },
                    "query": {
                        "displayName": "Value",
                        "description": "Value of the field of file/folder to search for.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "type": {
                        "displayName": "File Type",
                        "description": "(Optional) Choose between files and folders.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": "all",
                        "options": {
                            "options": [
                                {
                                    "label": "All",
                                    "value": "all"
                                },
                                {
                                    "label": "Files",
                                    "value": "file"
                                },
                                {
                                    "label": "Folders",
                                    "value": "folder"
                                }
                            ]
                        }
                    },
                    "parentFolder": {
                        "displayName": "Parent Folder",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "duplicate_file",
                "displayName": "Duplicate File",
                "description": "Duplicate a file from Google Drive. Returns the new file ID.",
                "props": {
                    "fileId": {
                        "displayName": "File ID",
                        "description": "The ID of the file to duplicate",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Name",
                        "description": "The name of the new file",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "folderId": {
                        "displayName": "Folder ID",
                        "description": "The ID of the folder where the file will be duplicated",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "mimeType": {
                        "displayName": "Duplicate as",
                        "description": "If left unselected the file will be duplicated as it is",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Google Sheets",
                                    "value": "application/vnd.google-apps.spreadsheet"
                                },
                                {
                                    "label": "Google Docs",
                                    "value": "application/vnd.google-apps.document"
                                }
                            ]
                        }
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "save_file_as_pdf",
                "displayName": "Save Document as PDF",
                "description": "Save a document as PDF in a Google Drive folder",
                "props": {
                    "documentId": {
                        "displayName": "Document ID",
                        "description": "The ID of the document to export",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "folderId": {
                        "displayName": "Folder ID",
                        "description": "The ID of the folder where the file will be exported",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Name",
                        "description": "The name of the new file (do not include the extension)",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "update_permissions",
                "displayName": "Update permissions",
                "description": "Update permissions for a file or folder",
                "props": {
                    "fileId": {
                        "displayName": "File or Folder ID",
                        "description": "The ID of the file or folder to update permissions for",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "user_email": {
                        "displayName": "User email",
                        "description": "The email address of the user to update permissions for",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "permission_name": {
                        "displayName": "Role",
                        "description": "The role to grant to user. See more at: https://developers.google.com/drive/api/guides/ref-roles",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Organizer",
                                    "value": "organizer"
                                },
                                {
                                    "label": "File Organizer",
                                    "value": "fileOrganizer"
                                },
                                {
                                    "label": "Writer",
                                    "value": "writer"
                                },
                                {
                                    "label": "Commenter",
                                    "value": "commenter"
                                },
                                {
                                    "label": "Reader",
                                    "value": "reader"
                                }
                            ]
                        }
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "send_invitation_email": {
                        "displayName": "Send invitation email",
                        "description": "Send an email to the user to notify them of the new permissions",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete_permissions",
                "displayName": "Delete permissions",
                "description": "Removes a role from an user for a file or folder",
                "props": {
                    "fileId": {
                        "displayName": "File or Folder ID",
                        "description": "The ID of the file or folder to update permissions for",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "user_email": {
                        "displayName": "User email",
                        "description": "The email address of the user to update permissions for",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "permission_name": {
                        "displayName": "Role",
                        "description": "The role to remove from user.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Organizer",
                                    "value": "organizer"
                                },
                                {
                                    "label": "File Organizer",
                                    "value": "fileOrganizer"
                                },
                                {
                                    "label": "Writer",
                                    "value": "writer"
                                },
                                {
                                    "label": "Commenter",
                                    "value": "commenter"
                                },
                                {
                                    "label": "Reader",
                                    "value": "reader"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "set_public_access",
                "displayName": "Set public access",
                "description": "Set public access for a file or folder",
                "props": {
                    "fileId": {
                        "displayName": "File or Folder ID",
                        "description": "The ID of the file or folder to update permissions for",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "google-drive-move-file",
                "displayName": "Move File",
                "description": "Moves a file from one folder to another.",
                "props": {
                    "fileId": {
                        "displayName": "File ID",
                        "description": "You can use **Search Folder/File** action to retrieve ID.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "folderId": {
                        "displayName": "Parent Folder",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete_gdrive_file",
                "displayName": "Delete file",
                "description": "Delete permanently a file from your Google Drive",
                "props": {
                    "fileId": {
                        "displayName": "File ID",
                        "description": "The ID of the file to delete",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "trash_gdrive_file",
                "displayName": "Trash file",
                "description": "Move a file to the trash in your Google Drive",
                "props": {
                    "fileId": {
                        "displayName": "File ID",
                        "description": "The ID of the file to trash",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "include_team_drives": {
                        "displayName": "Include Team Drives",
                        "description": "Determines if folders from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-google-forms",
        "name": "Google Forms",
        "description": "Receive form responses from Google Forms",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/google-forms.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-gemini",
        "name": "Google Gemini",
        "description": "Use the new Gemini models from Google",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/google-gemini.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-my-business",
        "name": "Google My Business",
        "description": "Manage your business on Google",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/google-business.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-search-console",
        "name": "Google Search Console",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/google-search-console.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-sheets",
        "name": "Google Sheets",
        "description": "Create, edit, and collaborate on spreadsheets online",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/google-sheets.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "google-sheets-new-or-updated-row",
                "displayName": "New or Updated Row",
                "description": "Triggers when a new row is added or modified in a spreadsheet.",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "Please note that there might be a delay of up to 3 minutes for the trigger to be fired, due to a delay from Google.",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "trigger_column": {
                        "displayName": "Trigger Column",
                        "description": "Trigger on changes to cells in this column only. \nSelect **Any Column** if you want the flow to trigger on changes to any cell within the row.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": "all_columns"
                    }
                }
            },
            {
                "name": "googlesheets_new_row_added",
                "displayName": "New Row Added",
                "description": "Triggers when a new row is added to bottom of a spreadsheet.",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "Please note that there might be a delay of up to 3 minutes for the trigger to be fired, due to a delay from Google.",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-spreadsheet",
                "displayName": "New Spreadsheet",
                "description": "Triggers when a new spreadsheet is created.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new-worksheet",
                "displayName": "New Worksheet",
                "description": "Triggers when a worksheet is created in a spreadsheet.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "insert_row",
                "displayName": "Insert Row",
                "description": "Append a row of values to an existing sheet",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "as_string": {
                        "displayName": "As String",
                        "description": "Inserted values that are dates and formulas will be entered strings and have no effect",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "first_row_headers": {
                        "displayName": "Does the first row contain headers?",
                        "description": "If the first row is headers",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    },
                    "values": {
                        "displayName": "Values",
                        "description": "The values to insert",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "google-sheets-insert-multiple-rows",
                "displayName": "Insert Multiple Rows",
                "description": "Add one or more new rows in a specific spreadsheet.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "input_type": {
                        "displayName": "Rows Input Format",
                        "description": "Select the format of the input values to be inserted into the sheet.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "column_names",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "value": "csv",
                                    "label": "CSV"
                                },
                                {
                                    "value": "json",
                                    "label": "JSON"
                                },
                                {
                                    "value": "column_names",
                                    "label": "Column Names"
                                }
                            ]
                        }
                    },
                    "values": {
                        "displayName": "Values",
                        "description": "The values to insert.",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "overwrite": {
                        "displayName": "Overwrite Existing Data?",
                        "description": "Enable this option to replace all existing data in the sheet with new data from your input. This will clear any extra rows beyond the updated range.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "check_for_duplicate": {
                        "displayName": "Avoid Duplicates?",
                        "description": "Enable this option to check for duplicate values before inserting data into the sheet. Only unique rows will be added based on the selected column.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "check_for_duplicate_column": {
                        "displayName": "Duplicate Value Column",
                        "description": "The column to check for duplicate values.",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "as_string": {
                        "displayName": "As String",
                        "description": "Inserted values that are dates and formulas will be entered as strings and have no effect",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "headerRow": {
                        "displayName": "Header Row",
                        "description": "Which row contains the headers?",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 1
                    }
                }
            },
            {
                "name": "delete_row",
                "displayName": "Delete Row",
                "description": "Delete a row on an existing sheet you have access to",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "rowId": {
                        "displayName": "Row Number",
                        "description": "The row number to remove",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_row",
                "displayName": "Update Row",
                "description": "Overwrite values in an existing row",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "row_id": {
                        "displayName": "Row Number",
                        "description": "The row number to update",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "first_row_headers": {
                        "displayName": "Does the first row contain headers?",
                        "description": "If the first row is headers",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    },
                    "values": {
                        "displayName": "Values",
                        "description": "The values to insert",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_rows",
                "displayName": "Find Rows",
                "description": "Find or get rows in a Google Sheet by column name and search value",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "columnName": {
                        "displayName": "The name of the column to search in",
                        "description": "Column Name",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "searchValue": {
                        "displayName": "Search Value",
                        "description": "The value to search for in the specified column. If left empty, all rows will be returned.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "matchCase": {
                        "displayName": "Exact match",
                        "description": "Whether to choose the rows with exact match or choose the rows that contain the search value",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    },
                    "startingRow": {
                        "displayName": "Starting Row",
                        "description": "The row number to start searching from",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "numberOfRows": {
                        "displayName": "Number of Rows",
                        "description": "The number of rows to return ( the default is 1 if not specified )",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 1
                    },
                    "headerRow": {
                        "displayName": "Header Row",
                        "description": "Which row contains the headers?",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 1
                    },
                    "useHeaderNames": {
                        "displayName": "Use header names for keys",
                        "description": "Map A/B/C\u2026 to the actual column headers (row specified above).",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "create-spreadsheet",
                "displayName": "Create Spreadsheet",
                "description": "Creates a blank spreadsheet.",
                "props": {
                    "title": {
                        "displayName": "Title",
                        "description": "The title of the new spreadsheet.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "folder": {
                        "displayName": "Parent Folder",
                        "description": "The folder to create the worksheet in.By default, the new worksheet is created in the root folder of drive.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-worksheet",
                "displayName": "Create Worksheet",
                "description": "Create a blank worksheet with a title.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "The title of the new worksheet.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "clear_sheet",
                "displayName": "Clear Sheet",
                "description": "Clears all rows on an existing sheet",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "is_first_row_headers": {
                        "displayName": "Is First row Headers?",
                        "description": "If the first row is headers",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": true
                    },
                    "headerRow": {
                        "displayName": "Header Row",
                        "description": "Which row contains the headers?",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 1
                    }
                }
            },
            {
                "name": "find_row_by_num",
                "displayName": "Get Row",
                "description": "Get a row in a Google Sheet by row number",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "rowNumber": {
                        "displayName": "Row Number",
                        "description": "The row number to get from the sheet",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "headerRow": {
                        "displayName": "Header Row",
                        "description": "Which row contains the headers?",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 1
                    }
                }
            },
            {
                "name": "get_next_rows",
                "displayName": "Get next row(s)",
                "description": "Get next group of rows from a Google Sheet",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "startRow": {
                        "displayName": "Start Row",
                        "description": "Which row to start from?",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 1
                    },
                    "headerRow": {
                        "displayName": "Header Row",
                        "description": "Which row contains the headers?",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 1
                    },
                    "useHeaderNames": {
                        "displayName": "Use header names for keys",
                        "description": "Map A/B/C\u2026 to the actual column headers (row specified above).",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "\n**Notes:**\n\n- Memory key is used to remember where last row was processed and will be used in the following runs.\n- Republishing the flow **keeps** the memory key value, If you want to start over **change** the memory key.\n",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "memKey": {
                        "displayName": "Memory Key",
                        "description": "The key used to store the current row number in memory",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": "row_number"
                    },
                    "groupSize": {
                        "displayName": "Group Size",
                        "description": "The number of rows to get",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 1
                    }
                }
            },
            {
                "name": "get-many-rows",
                "displayName": "Get Many Rows",
                "description": "Get all values from the selected sheet.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "first_row_headers": {
                        "displayName": "Does the first row contain headers?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "find_spreadsheets",
                "displayName": "Find Spreadsheet(s)",
                "description": "Find spreadsheet(s) by name.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheet_name": {
                        "displayName": "Spreadsheet Name",
                        "description": "The name of the spreadsheet(s) to find.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "exact_match": {
                        "displayName": "Exact Match",
                        "description": "If true, only return spreadsheets that exactly match the name. If false, return spreadsheets that contain the name.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "find-worksheet",
                "displayName": "Find Worksheet(s)",
                "description": "Finds a worksheet(s) by title.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "exact_match": {
                        "displayName": "Exact Match",
                        "description": "If true, only return worksheets that exactly match the name. If false, return worksheets that contain the name.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "copy-worksheet",
                "displayName": "Copy Worksheet",
                "description": "Creates a new worksheet by copying an existing one.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet Containing the Worksheet to Copy",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Worksheet to Copy",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "desinationSpeadsheetId": {
                        "displayName": "Spreadsheet to paste in",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-multiple-rows",
                "displayName": "Update Multiple Rows",
                "description": "Updates multiple rows in a specific spreadsheet.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "values": {
                        "displayName": "Values",
                        "description": "The values to update.",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "as_string": {
                        "displayName": "As String",
                        "description": "Inserted values that are dates and formulas will be entered as strings and have no effect",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "headerRow": {
                        "displayName": "Header Row",
                        "description": "Which row contains the headers?",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 1
                    }
                }
            },
            {
                "name": "create-column",
                "displayName": "Create Spreadsheet Column",
                "description": "Adds a new column to a spreadsheet.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "columnName": {
                        "displayName": "Column Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "columnIndex": {
                        "displayName": "Column Index",
                        "description": "The column index starts from 1.For example, if you want to add a column to the third column, enter 3.Ff the input is less than 1 the column will be added after the last current column.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "export_sheet",
                "displayName": "Export Sheet",
                "description": "Export a Google Sheets tab to CSV or TSV format.",
                "props": {
                    "includeTeamDrives": {
                        "displayName": "Include Team Drive Sheets ?",
                        "description": "Determines if sheets from Team Drives should be included in the results.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "spreadsheetId": {
                        "displayName": "Spreadsheet",
                        "description": "The ID of the spreadsheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "sheetId": {
                        "displayName": "Sheet",
                        "description": "The ID of the sheet to use.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "format": {
                        "displayName": "Export Format",
                        "description": "The format to export the sheet to.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "csv",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Comma Separated Values (.csv)",
                                    "value": "csv"
                                },
                                {
                                    "label": "Tab Separated Values (.tsv)",
                                    "value": "tsv"
                                }
                            ]
                        }
                    },
                    "returnAsText": {
                        "displayName": "Return as Text",
                        "description": "Return the exported data as text instead of a file.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-google-slides",
        "name": "Google Slides",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/google-slides.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-google-tasks",
        "name": "Google Tasks",
        "description": "Task list management application",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/google-tasks.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gotify",
        "name": "Gotify",
        "description": "Self-hosted push notification service",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/gotify.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gptzero-detect-ai",
        "name": "GPTZero",
        "description": "Detect AI-generated text with GPTZero API",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/gptzero-detect-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-graphql",
        "name": "GraphQL",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/graphql.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-gravityforms",
        "name": "Gravity Forms",
        "description": "Build and publish your WordPress forms",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/gravityforms.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-greenpt",
        "name": "GreenPT",
        "description": "GreenPT is a green AI and privacy friendly GPT-powered chat platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/greenpt.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-greip",
        "name": "Greip",
        "description": "Detect and prevent fraud in your website or app with Greip's Fraud Prevention API. Protect your business from financial losses and gain better insights into your users.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/greip.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-griptape",
        "name": "Griptape Cloud",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/griptape.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-grist",
        "name": "Grist",
        "description": "open source spreadsheet",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/grist.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-grok-xai",
        "name": "Grok by xAI",
        "description": "AI chatbot by xAI that answers questions, generates text, extracts data, and provides real-time insights.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/grok-xai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-groq",
        "name": "Groq",
        "description": "Use Groq's fast language models and audio processing capabilities.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/groq.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-guidelite",
        "name": "GuideLite",
        "description": "GuideLite is a platform that helps organizations build and utilize AI assistants",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/guidelite.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-hackernews",
        "name": "Hacker News",
        "description": "A social news website",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/hackernews.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-harvest",
        "name": "Harvest",
        "description": "Time Tracking Software with Invoicing",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/harvest.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-hastewire",
        "name": "Hastewire",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/hastewire.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-heartbeat",
        "name": "Heartbeat",
        "description": "Monitoring and alerting made easy",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/heartbeat.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-hedy",
        "name": "Hedy",
        "description": "AI-powered meeting intelligence \u2013 be the brightest person in the room.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/hedy.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-help-scout",
        "name": "Help Scout",
        "description": "",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/help-scout.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-heygen",
        "name": "HeyGen",
        "description": "Generate and manage AI avatar videos using HeyGen.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/heygen.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-housecall-pro",
        "name": "Housecall Pro",
        "description": "Manage your home service business with Housecall Pro CRM integration",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/housecall-pro.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-http",
        "name": "HTTP",
        "description": "Sends HTTP requests and return responses",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/http.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-http-oauth2",
        "name": "HTTP (OAuth2)",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/http.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-hubspot",
        "name": "HubSpot",
        "description": "Powerful CRM that offers tools for sales, customer service, and marketing automation.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/hubspot.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "new-or-updated-company",
                "displayName": "Company Recently Created or Updated",
                "description": "Triggers when a company recently created or updated.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    name, domain, industry, about_us, phone, address, address2, city, state, zip, country, website, type, description, founded_year, hs_createdate, hs_lastmodifieddate, hs_object_id, is_public, timezone, total_money_raised, total_revenue, owneremail, ownername, numberofemployees, annualrevenue, lifecyclestage, createdate, web_technologies\n                                    \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-or-updated-contact",
                "displayName": "Contact Recently Created or Updated",
                "description": "Triggers when a contact recently created or updated.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    firstname, lastname, email, company, website, mobilephone, phone, fax, address, city, state, zip, salutation, country, jobtitle, hs_createdate, hs_email_domain, hs_object_id, lastmodifieddate, hs_persona, hs_language, lifecyclestage, createdate, numemployees, annualrevenue, industry\t\t\t\n                                    \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-deal-property-change",
                "displayName": "New Deal Property Change",
                "description": "Triggers when a specified property is updated on a deal.",
                "props": {
                    "propertyName": {
                        "displayName": "Property Name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-email-subscriptions-timeline",
                "displayName": "New Email Subscriptions Timeline",
                "description": "Triggers when a new email timeline subscription added for the portal.",
                "props": {}
            },
            {
                "name": "new-or-updated-line-item",
                "displayName": "Line Item Recently Created or Updated",
                "description": "Triggers when a line item recently created or updated.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    name, description, price, quantity, amount, discount, tax, createdate, hs_object_id, hs_product_id, hs_images, hs_lastmodifieddate, hs_line_item_currency_code, hs_sku, hs_url, hs_cost_of_goods_sold, hs_discount_percentage, hs_term_in_months           \n                                    \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-company",
                "displayName": "New Company",
                "description": "Trigger when a new company is added.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                \n                  name, domain, industry, about_us, phone, address, address2, city, state, zip, country, website, type, description, founded_year, hs_createdate, hs_lastmodifieddate, hs_object_id, is_public, timezone, total_money_raised, total_revenue, owneremail, ownername, numberofemployees, annualrevenue, lifecyclestage, createdate, web_technologies\n                                \n                  **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-company-property-change",
                "displayName": "New Company Property Change",
                "description": "Triggers when a specified property is updated on a company.",
                "props": {
                    "propertyName": {
                        "displayName": "Property Name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-contact",
                "displayName": "New Contact",
                "description": "Trigger when new contact is available.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                        \n              firstname, lastname, email, company, website, mobilephone, phone, fax, address, city, state, zip, salutation, country, jobtitle, hs_createdate, hs_email_domain, hs_object_id, lastmodifieddate, hs_persona, hs_language, lifecyclestage, createdate, numemployees, annualrevenue, industry\t\t\t\n                                        \n              **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-contact-in-list",
                "displayName": "New Contact in List",
                "description": "Triggers when a new contact is added to the specified list.",
                "props": {
                    "listId": {
                        "displayName": "Contact List",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                         \n                         firstname, lastname, email, company, website, mobilephone, phone, fax, address, city, state, zip, salutation, country, jobtitle, hs_createdate, hs_email_domain, hs_object_id, lastmodifieddate, hs_persona, hs_language, lifecyclestage, createdate, numemployees, annualrevenue, industry\t\t\t\n                                                 \n                         **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-contact-property-change",
                "displayName": "New Contact Property Change",
                "description": "Triggers when a specified property is updated on a contact.",
                "props": {
                    "propertyName": {
                        "displayName": "Property Name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-blog-article",
                "displayName": "New COS Blog Article",
                "description": "Triggers when a new article is added to your COS blog.",
                "props": {
                    "articleState": {
                        "displayName": "Article State",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Published Only",
                                    "value": "PUBLISHED"
                                },
                                {
                                    "label": "Draft Only",
                                    "value": "DRAFT"
                                },
                                {
                                    "label": "Both",
                                    "value": "BOTH"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "new-custom-object",
                "displayName": "New Custom Object",
                "description": "Triggers when new custom object is available.",
                "props": {
                    "customObjectType": {
                        "displayName": "Type of Custom Object",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                    \n                    hs_object_id, hs_lastmodifieddate, hs_createdate   \n                        \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional Properties to Retrieve",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-custom-object-property-change",
                "displayName": "New Custom Object Property Change",
                "description": "Triggers when a specified property is updated on a custom object.",
                "props": {
                    "customObjectType": {
                        "displayName": "Type of Custom Object",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "propertyName": {
                        "displayName": "Property Name",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-deal",
                "displayName": "New Deal",
                "description": "Trigger when a new deal is added.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                        \n\t\t\t\t\tdealtype, dealname, amount, description, closedate, createdate, num_associated_contacts, hs_forecast_amount, hs_forecast_probability, hs_manual_forecast_category, hs_next_step, hs_object_id, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-email-event",
                "displayName": "New Email Event",
                "description": "Triggers when all,or specific new email event is available.",
                "props": {
                    "eventType": {
                        "displayName": "Event Type",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Sent",
                                    "value": "SENT"
                                },
                                {
                                    "label": "Dropped",
                                    "value": "DROPPED"
                                },
                                {
                                    "label": "Processed",
                                    "value": "PROCESSED"
                                },
                                {
                                    "label": "Delivered",
                                    "value": "DELIVERED"
                                },
                                {
                                    "label": "Deferred",
                                    "value": "DEFERRED"
                                },
                                {
                                    "label": "Bounce",
                                    "value": "BOUNCE"
                                },
                                {
                                    "label": "Open",
                                    "value": "OPEN"
                                },
                                {
                                    "label": "Click",
                                    "value": "CLICK"
                                },
                                {
                                    "label": "Status Change",
                                    "value": "STATUSCHANGE"
                                },
                                {
                                    "label": "Spam Report",
                                    "value": "SPAMREPORT"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "new-engagement",
                "displayName": "New Engagement",
                "description": "Triggers when a new engagement is created.",
                "props": {
                    "eventType": {
                        "displayName": "Type",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Note",
                                    "value": "NOTE"
                                },
                                {
                                    "label": "Task",
                                    "value": "TASK"
                                },
                                {
                                    "label": "Meeting",
                                    "value": "MEETING"
                                },
                                {
                                    "label": "Email",
                                    "value": "EMAIL"
                                },
                                {
                                    "label": "Call",
                                    "value": "CALL"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "new-form-submission",
                "displayName": "New Form Submission",
                "description": "Triggers when a form is submitted.",
                "props": {
                    "formId": {
                        "displayName": "Form",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "allowMultipleFiles": {
                        "displayName": "Allow Multiple Files",
                        "description": "Return all file fields as array",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new-line-item",
                "displayName": "New Line Item",
                "description": "Triggers when new line item is available.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                    \n                    name, description, price, quantity, amount, discount, tax, createdate, hs_object_id, hs_product_id, hs_images, hs_lastmodifieddate, hs_line_item_currency_code, hs_sku, hs_url, hs_cost_of_goods_sold, hs_discount_percentage, hs_term_in_months           \n                        \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-product",
                "displayName": "New Product",
                "description": "Triggers when new product is available.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                    \n                    createdate, description, name, price, tax, hs_lastmodifieddate\n                        \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-ticket",
                "displayName": "New Ticket",
                "description": "Trigger when new ticket is available.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                        \n              subject, content, source_type, createdate, hs_pipeline, hs_pipeline_stage, hs_resolution, hs_ticket_category, hs_ticket_id, hs_ticket_priority, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n\n              **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-ticket-property-change",
                "displayName": "New Ticket Property Change",
                "description": "Triggers when a specified property is updated on a ticket.",
                "props": {
                    "propertyName": {
                        "displayName": "Property Name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-or-updated-product",
                "displayName": "Product Recently Created or Updated",
                "description": "Triggers when a product recently created or updated.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    createdate, description, name, price, tax, hs_lastmodifieddate\n                                    \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new-task",
                "displayName": "New Task",
                "description": "Trigger when a new task is added.",
                "props": {
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                        \n\t\t\t\t\ths_task_subject, hs_task_type, hs_task_priority, hubspot_owner_id, hs_timestamp, hs_queue_membership_ids, hs_lastmodifieddate,hs_createdate\n\n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "deal-stage-updated",
                "displayName": "Updated Deal Stage",
                "description": "Triggers when a deal enters a specified stage.",
                "props": {
                    "pipelineId": {
                        "displayName": "Deal Pipeline",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "stageId": {
                        "displayName": "Deal Stage",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\tdealtype, dealname, amount, description, closedate, createdate, num_associated_contacts, hs_forecast_amount, hs_forecast_probability, hs_manual_forecast_category, hs_next_step, hs_object_id, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id, hs_v2_date_entered_current_stage\n\t\t\t\t\t\t\t\t\t\n\t\t\t\t\t\t\t**Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "add_contact_to_list",
                "displayName": "Add contact To List",
                "description": "Add contact to list",
                "props": {
                    "listId": {
                        "displayName": "List ID",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Contact Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add-contact-to-workflow",
                "displayName": "Add Contact to Workflow",
                "description": "Adds a contact to a specified workflow in your HubSpot account.",
                "props": {
                    "workflowId": {
                        "displayName": "Workflow",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Contact's Email",
                        "description": "The email of the contact to add to the workflow.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-associations",
                "displayName": "Create Associations",
                "description": "Creates associations between objects",
                "props": {
                    "fromObjectId": {
                        "displayName": "From Object ID",
                        "description": "The ID of the object being associated.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "fromObjectType": {
                        "displayName": "From Object Type",
                        "description": "The type of the object being associated.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "toObjectType": {
                        "displayName": "To Object Type",
                        "description": "Type of the objects the from object is being associated with.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "associationType": {
                        "displayName": "Type of the association",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "toObjectIds": {
                        "displayName": "To Object IDs",
                        "description": "The ID'sof the objects the from object is being associated with",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-company",
                "displayName": "Create Company",
                "description": "Creates a company in Hubspot.",
                "props": {
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                            \n                    name, domain, industry, about_us, phone, address, address2, city, state, zip, country, website, type, description, founded_year, hs_createdate, hs_lastmodifieddate, hs_object_id, is_public, timezone, total_money_raised, total_revenue, owneremail, ownername, numberofemployees, annualrevenue, lifecyclestage, createdate, web_technologies\n                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-contact",
                "displayName": "Create Contact",
                "description": "Creates a contact in Hubspot.",
                "props": {
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    firstname, lastname, email, company, website, mobilephone, phone, fax, address, city, state, zip, salutation, country, jobtitle, hs_createdate, hs_email_domain, hs_object_id, lastmodifieddate, hs_persona, hs_language, lifecyclestage, createdate, numemployees, annualrevenue, industry\t\t\t\n                                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-blog-post",
                "displayName": "Create COS Blog Post",
                "description": "Creates a blog post in you Hubspot COS blog.",
                "props": {
                    "contentGroupId": {
                        "displayName": "Blog URL",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "authorId": {
                        "displayName": "Blog Author",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Publish This Post?",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Leave As Draft",
                                    "value": "DRAFT"
                                },
                                {
                                    "label": "Publish Immediately",
                                    "value": "PUBLISHED"
                                }
                            ]
                        }
                    },
                    "slug": {
                        "displayName": "Slug",
                        "description": "The slug of the blog post. This is the URL of the post on your COS blog.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Blog Post Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Blog Post Content",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "meta": {
                        "displayName": "Meta Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "imageUrl": {
                        "displayName": "Featured Image URL",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-custome-object",
                "displayName": "Create Custom Object",
                "description": "Creates a custom object in Hubspot.",
                "props": {
                    "customObjectType": {
                        "displayName": "Type of Custom Object",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Custom Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                            \n                    hs_object_id, hs_lastmodifieddate, hs_createdate   \n\n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional Properties to Retrieve",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-deal",
                "displayName": "Create Deal",
                "description": "Creates a new deal in Hubspot.",
                "props": {
                    "dealname": {
                        "displayName": "Deal Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "pipelineId": {
                        "displayName": "Deal Pipeline",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "pipelineStageId": {
                        "displayName": "Deal Stage",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                        \n              dealtype, dealname, amount, description, closedate, createdate, num_associated_contacts, hs_forecast_amount, hs_forecast_probability, hs_manual_forecast_category, hs_next_step, hs_object_id, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n                                                \n              **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-line-item",
                "displayName": "Create Line Item",
                "description": "Creates a line item in Hubspot.",
                "props": {
                    "productId": {
                        "displayName": "Line Item Information: Product ID",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                            \n                    name, description, price, quantity, amount, discount, tax, createdate, hs_object_id, hs_product_id, hs_images, hs_lastmodifieddate, hs_line_item_currency_code, hs_sku, hs_url, hs_cost_of_goods_sold, hs_discount_percentage, hs_term_in_months           \n                \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-page",
                "displayName": "Create Page",
                "description": "Creates a new landing/site page.",
                "props": {
                    "pageType": {
                        "displayName": "Page Type",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "landing_page",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Landing Page",
                                    "value": "landing_page"
                                },
                                {
                                    "label": "Site Page",
                                    "value": "site_page"
                                }
                            ]
                        }
                    },
                    "pageTitle": {
                        "displayName": "Page Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "internalPageName": {
                        "displayName": "Internal Page Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "templatePath": {
                        "displayName": "Template Path",
                        "description": "The path should not include a slash (/) at the start.For example,\"@hubspot/elevate/templates/blank.hubl.html\".",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "slug": {
                        "displayName": "Slug",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "language": {
                        "displayName": "Language",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": "en-us"
                    },
                    "metaDescription": {
                        "displayName": "Meta Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "state": {
                        "displayName": "State",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": "DRAFT",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Draft",
                                    "value": "DRAFT"
                                },
                                {
                                    "label": "Publish",
                                    "value": "PUBLISHED_OR_SCHEDULED"
                                }
                            ]
                        }
                    },
                    "headHtml": {
                        "displayName": "Additional Head HTML",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "footerHtml": {
                        "displayName": "Additional Footer HTML",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-or-update-contact",
                "displayName": "Create or Update Contact",
                "description": "Creates a new contact or updates an existing contact based on email address.",
                "props": {
                    "email": {
                        "displayName": "Contact Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-product",
                "displayName": "Create Product",
                "description": "Creates a product in Hubspot.",
                "props": {
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    createdate, description, name, price, tax, hs_lastmodifieddate\n                                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-ticket",
                "displayName": "Create Ticket",
                "description": "Creates a ticket in HubSpot.",
                "props": {
                    "ticketName": {
                        "displayName": "Ticket Name",
                        "description": "The name of the ticket to create.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "pipelineId": {
                        "displayName": "Ticket Pipeline",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "pipelineStageId": {
                        "displayName": "Ticket Pipeline Stage",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n            \n            subject, content, source_type, createdate, hs_pipeline, hs_pipeline_stage, hs_resolution, hs_ticket_category, hs_ticket_id, hs_ticket_priority, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n            \n            **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-company",
                "displayName": "Get Company",
                "description": "Gets a company.",
                "props": {
                    "companyId": {
                        "displayName": "Company ID",
                        "description": "The ID of the company to get.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n\t\t\t\t\t\n\t\t\t\t\tname, domain, industry, about_us, phone, address, address2, city, state, zip, country, website, type, description, founded_year, hs_createdate, hs_lastmodifieddate, hs_object_id, is_public, timezone, total_money_raised, total_revenue, owneremail, ownername, numberofemployees, annualrevenue, lifecyclestage, createdate, web_technologies\n\t\t\t\t\t\n\t\t\t\t\t**Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-contact",
                "displayName": "Get Contact",
                "description": "Gets a contact.",
                "props": {
                    "contactId": {
                        "displayName": "Contact ID",
                        "description": "The ID of the contact to get.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n\t\t\t\t\t\t\t\n\t\t\t\t\tfirstname, lastname, email, company, website, mobilephone, phone, fax, address, city, state, zip, salutation, country, jobtitle, hs_createdate, hs_email_domain, hs_object_id, lastmodifieddate, hs_persona, hs_language, lifecyclestage, createdate, numemployees, annualrevenue, industry\t\t\t\n\t\t\t\t\t\t\t\t\t\n\t\t\t\t\t**Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-custom-object",
                "displayName": "Get Custom Object",
                "description": "Gets a custom object.",
                "props": {
                    "customObjectType": {
                        "displayName": "Type of Custom Object",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "customObjectId": {
                        "displayName": "Custom Object ID",
                        "description": "The ID of the custom object to get.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                  \n                    hs_object_id, hs_lastmodifieddate, hs_createdate   \n      \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional Properties to Retrieve",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-deal",
                "displayName": "Get Deal",
                "description": "Gets a deal.",
                "props": {
                    "dealId": {
                        "displayName": "Deal ID",
                        "description": "The ID of the deal to get.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n\t\t\t\t\t\t\t\t\t\n\t\t\t\t\tdealtype, dealname, amount, description, closedate, createdate, num_associated_contacts, hs_forecast_amount, hs_forecast_probability, hs_manual_forecast_category, hs_next_step, hs_object_id, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n\t\t\t\t\t\t\t\t\t\t\t\n\t\t\t\t\t**Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-line-item",
                "displayName": "Get Line Item",
                "description": "Gets a line item.",
                "props": {
                    "lineItemId": {
                        "displayName": "Line Item ID",
                        "description": "The ID of the line item to get.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                            \n                    name, description, price, quantity, amount, discount, tax, createdate, hs_object_id, hs_product_id, hs_images, hs_lastmodifieddate, hs_line_item_currency_code, hs_sku, hs_url, hs_cost_of_goods_sold, hs_discount_percentage, hs_term_in_months           \n\n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-product",
                "displayName": "Get Product",
                "description": "Gets a product.",
                "props": {
                    "productId": {
                        "displayName": "Product ID",
                        "description": "The ID of the product to get.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n\t\t\t\t\t\t\t\t\t\t\t\n                    createdate, description, name, price, tax, hs_lastmodifieddate\t\n\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\n\t\t\t\t\t**Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-page",
                "displayName": "Get Page",
                "description": "Gets landing/site page Details.",
                "props": {
                    "pageType": {
                        "displayName": "Page Type",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "landing_page",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Landing Page",
                                    "value": "landing_page"
                                },
                                {
                                    "label": "Site Page",
                                    "value": "site_page"
                                }
                            ]
                        }
                    },
                    "pageId": {
                        "displayName": "Page ID",
                        "description": "The ID of the page to get.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-ticket",
                "displayName": "Get Ticket",
                "description": "Gets a ticket.",
                "props": {
                    "ticketId": {
                        "displayName": "Ticket ID",
                        "description": "The ID of the ticket to get.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n\t\t\t\t\t\t\t\t\t\t\t\t\t\n\t\t\t\t\tsubject, content, source_type, createdate, hs_pipeline, hs_pipeline_stage, hs_resolution, hs_ticket_category, hs_ticket_id, hs_ticket_priority, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\n\t\t\t\t\t**Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete-page",
                "displayName": "Delete Page",
                "description": "Deletes an existing landing/site page.",
                "props": {
                    "pageType": {
                        "displayName": "Page Type",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "landing_page",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Landing Page",
                                    "value": "landing_page"
                                },
                                {
                                    "label": "Site Page",
                                    "value": "site_page"
                                }
                            ]
                        }
                    },
                    "pageId": {
                        "displayName": "Page ID",
                        "description": "The ID of the page to delete.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "remove-associations",
                "displayName": "Remove Associations",
                "description": "Removes associations between objects",
                "props": {
                    "fromObjectId": {
                        "displayName": "From Object ID",
                        "description": "The ID of the object you want to remove the association from.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "fromObjectType": {
                        "displayName": "From Object Type",
                        "description": "The type of the object you want to remove the association from.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "toObjectType": {
                        "displayName": "To Object Type",
                        "description": "Type of the currently associated objects that you're removing the association from.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "associationType": {
                        "displayName": "Type of the association",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "toObjectIds": {
                        "displayName": "To Object IDs",
                        "description": "The IDs of the currently associated objects that you're removing the association from.",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "remove-contact-from-list",
                "displayName": "Remove Contact from List",
                "description": "Remove a contact from a specific list.",
                "props": {
                    "listId": {
                        "displayName": "List ID",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Contact Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "remove-email-subscription",
                "displayName": "Remove Email Subscription",
                "description": "Removes email subscription.",
                "props": {
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-company",
                "displayName": "Update Company",
                "description": "Updates a company in Hubspot.",
                "props": {
                    "companyId": {
                        "displayName": "Company ID",
                        "description": "The ID of the company to update.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                            \n                    name, domain, industry, about_us, phone, address, address2, city, state, zip, country, website, type, description, founded_year, hs_createdate, hs_lastmodifieddate, hs_object_id, is_public, timezone, total_money_raised, total_revenue, owneremail, ownername, numberofemployees, annualrevenue, lifecyclestage, createdate, web_technologies\n                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-contact",
                "displayName": "Update Contact",
                "description": "Updates a contact in Hubspot.",
                "props": {
                    "contactId": {
                        "displayName": "Contact ID",
                        "description": "The ID of the contact to update.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    firstname, lastname, email, company, website, mobilephone, phone, fax, address, city, state, zip, salutation, country, jobtitle, hs_createdate, hs_email_domain, hs_object_id, lastmodifieddate, hs_persona, hs_language, lifecyclestage, createdate, numemployees, annualrevenue, industry\t\t\t\n                                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-custome-object",
                "displayName": "Update Custom Object",
                "description": "Updates a custom object in Hubspot.",
                "props": {
                    "customObjectType": {
                        "displayName": "Type of Custom Object",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "customObjectId": {
                        "displayName": "Custom Object ID",
                        "description": "The ID of the custom object to update.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Custom Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                            \n                    hs_object_id, hs_lastmodifieddate, hs_createdate   \n\n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional Properties to Retrieve",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-deal",
                "displayName": "Update Deal",
                "description": "Updates a deal in HubSpot.",
                "props": {
                    "dealId": {
                        "displayName": "Deal ID",
                        "description": "The ID of the deal to update.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "dealname": {
                        "displayName": "Deal Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "pipelineId": {
                        "displayName": "Deal Pipeline",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "pipelineStageId": {
                        "displayName": "Deal Stage",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n\t\t\t\t\t\t\t\t\t\t\t\t\n\t\t\t\t\t  dealtype, dealname, amount, description, closedate, createdate, num_associated_contacts, hs_forecast_amount, hs_forecast_probability, hs_manual_forecast_category, hs_next_step, hs_object_id, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n\t\t\t\t\t\t\t\t\t\t\t\t\t\t\n\t\t\t\t\t  **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-line-item",
                "displayName": "Update Line Item",
                "description": "Updates a line item in Hubspot.",
                "props": {
                    "lineItemId": {
                        "displayName": "Line Item ID",
                        "description": "The ID of the line item to update.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "productId": {
                        "displayName": "Line Item Information: Product ID",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                            \n                    name, description, price, quantity, amount, discount, tax, createdate, hs_object_id, hs_product_id, hs_images, hs_lastmodifieddate, hs_line_item_currency_code, hs_sku, hs_url, hs_cost_of_goods_sold, hs_discount_percentage, hs_term_in_months           \n                \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-product",
                "displayName": "Update Product",
                "description": "Updates a product in Hubspot.",
                "props": {
                    "productId": {
                        "displayName": "Product ID",
                        "description": "The ID of the product to update.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    createdate, description, name, price, tax, hs_lastmodifieddate\n                                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-ticket",
                "displayName": "Update Ticket",
                "description": "Updates a ticket in HubSpot.",
                "props": {
                    "ticketId": {
                        "displayName": "Ticket ID",
                        "description": "The ID of the ticket to update.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "ticketName": {
                        "displayName": "Ticket Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "pipelineId": {
                        "displayName": "Ticket Pipeline",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "pipelineStageId": {
                        "displayName": "Ticket Pipeline Stage",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "objectProperties": {
                        "displayName": "Object Properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n            \n            subject, content, source_type, createdate, hs_pipeline, hs_pipeline_stage, hs_resolution, hs_ticket_category, hs_ticket_id, hs_ticket_priority, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n            \n            **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "upload-file",
                "displayName": "Upload File",
                "description": "Uploads a file to HubSpot File Manager.",
                "props": {
                    "folderId": {
                        "displayName": "Folder",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "fileName": {
                        "displayName": "File Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "accessLevel": {
                        "displayName": "Access Level",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "value": "PUBLIC_INDEXABLE",
                                    "label": "PUBLIC_INDEXABLE"
                                },
                                {
                                    "value": "PUBLIC_NOT_INDEXABLE",
                                    "label": "PUBLIC_NOT_INDEXABLE"
                                },
                                {
                                    "label": "PRIVATE",
                                    "value": "PRIVATE"
                                }
                            ]
                        }
                    },
                    "file": {
                        "displayName": "File",
                        "description": "",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-associations",
                "displayName": "Find Associations",
                "description": "Finds associations between objects",
                "props": {
                    "fromObjectId": {
                        "displayName": "From Object ID",
                        "description": "The ID of the object you want to search the association.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "fromObjectType": {
                        "displayName": "From Object Type",
                        "description": "The type of the object you want to search the association.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "toObjectType": {
                        "displayName": "To Object Type",
                        "description": "Type of the object the from object is being associated with.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-company",
                "displayName": "Find Company",
                "description": "Finds a company by searching.",
                "props": {
                    "firstSearchPropertyName": {
                        "displayName": "First search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "firstSearchPropertyValue": {
                        "displayName": "First search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "secondSearchPropertyName": {
                        "displayName": "Second search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "secondSearchPropertyValue": {
                        "displayName": "Second search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                        \n                    name, domain, industry, about_us, phone, address, address2, city, state, zip, country, website, type, description, founded_year, hs_createdate, hs_lastmodifieddate, hs_object_id, is_public, timezone, total_money_raised, total_revenue, owneremail, ownername, numberofemployees, annualrevenue, lifecyclestage, createdate, web_technologies\n\n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-contact",
                "displayName": "Find Contact",
                "description": "Finds a contact by searching.",
                "props": {
                    "firstSearchPropertyName": {
                        "displayName": "First search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "firstSearchPropertyValue": {
                        "displayName": "First search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "secondSearchPropertyName": {
                        "displayName": "Second search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "secondSearchPropertyValue": {
                        "displayName": "Second search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    firstname, lastname, email, company, website, mobilephone, phone, fax, address, city, state, zip, salutation, country, jobtitle, hs_createdate, hs_email_domain, hs_object_id, lastmodifieddate, hs_persona, hs_language, lifecyclestage, createdate, numemployees, annualrevenue, industry\t\t\t\n                                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-custom-object",
                "displayName": "Find Custom Object",
                "description": "Finds a custom object by searching.",
                "props": {
                    "customObjectType": {
                        "displayName": "Type of Custom Object",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "firstSearchPropertyName": {
                        "displayName": "First search property name",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "firstSearchPropertyValue": {
                        "displayName": "First search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "secondSearchPropertyName": {
                        "displayName": "Second search property name",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "secondSearchPropertyValue": {
                        "displayName": "Second search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                    \n                    hs_object_id, hs_lastmodifieddate, hs_createdate   \n                                            \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional Properties to Retrieve",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-deal",
                "displayName": "Find Deal",
                "description": "Finds a deal by searching.",
                "props": {
                    "firstSearchPropertyName": {
                        "displayName": "First search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "firstSearchPropertyValue": {
                        "displayName": "First search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "secondSearchPropertyName": {
                        "displayName": "Second search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "secondSearchPropertyValue": {
                        "displayName": "Second search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                \n                      dealtype, dealname, amount, description, closedate, createdate, num_associated_contacts, hs_forecast_amount, hs_forecast_probability, hs_manual_forecast_category, hs_next_step, hs_object_id, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n                                                        \n                      **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-line-item",
                "displayName": "Find Line Item",
                "description": "Finds a line item by searching.",
                "props": {
                    "firstSearchPropertyName": {
                        "displayName": "First search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "firstSearchPropertyValue": {
                        "displayName": "First search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "secondSearchPropertyName": {
                        "displayName": "Second search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "secondSearchPropertyValue": {
                        "displayName": "Second search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                            \n                    name, description, price, quantity, amount, discount, tax, createdate, hs_object_id, hs_product_id, hs_images, hs_lastmodifieddate, hs_line_item_currency_code, hs_sku, hs_url, hs_cost_of_goods_sold, hs_discount_percentage, hs_term_in_months           \n        \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-product",
                "displayName": "Find Product",
                "description": "Finds a product by searching.",
                "props": {
                    "firstSearchPropertyName": {
                        "displayName": "First search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "firstSearchPropertyValue": {
                        "displayName": "First search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "secondSearchPropertyName": {
                        "displayName": "Second search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "secondSearchPropertyValue": {
                        "displayName": "Second search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                        \n                    createdate, description, name, price, tax, hs_lastmodifieddate       \n\n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-ticket",
                "displayName": "Find Ticket",
                "description": "Finds a ticket by searching.",
                "props": {
                    "firstSearchPropertyName": {
                        "displayName": "First search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "firstSearchPropertyValue": {
                        "displayName": "First search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "secondSearchPropertyName": {
                        "displayName": "Second search property name",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "secondSearchPropertyValue": {
                        "displayName": "Second search property value",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "### Properties to retrieve:\n                                                        \n                    subject, content, source_type, createdate, hs_pipeline, hs_pipeline_stage, hs_resolution, hs_ticket_category, hs_ticket_id, hs_ticket_priority, hs_lastmodifieddate, hubspot_owner_id, hubspot_team_id\n                                                                                \n                    **Specify here a list of additional properties to retrieve**",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "additionalPropertiesToRetrieve": {
                        "displayName": "Additional properties to retrieve",
                        "description": "",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-owner-by-email",
                "displayName": "Get Owner by Email",
                "description": "Gets an existing owner by email.",
                "props": {
                    "email": {
                        "displayName": "Owner Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-owner-by-id",
                "displayName": "Get Owner by ID",
                "description": "Gets an existing owner by ID.",
                "props": {
                    "ownerId": {
                        "displayName": "Owner ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-pipeline-stage-details",
                "displayName": "Get Pipeline Stage Details",
                "description": "Finds and retrieves CRM object pipeline stage details.",
                "props": {
                    "objectType": {
                        "displayName": "Object Type",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Tickets",
                                    "value": "ticket"
                                },
                                {
                                    "label": "Deal",
                                    "value": "deal"
                                }
                            ]
                        }
                    },
                    "pipelineId": {
                        "displayName": "Pipeline ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "stageId": {
                        "displayName": "Stage ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-hugging-face",
        "name": "Hugging Face",
        "description": "Run inference on 100,000+ open ML models for NLP, vision, and audio tasks",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/huggingface.svg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-forms",
        "name": "Human Input",
        "description": "Trigger a flow through human input.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/human-input.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-hume-ai",
        "name": "Hume AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/hume-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-hunter",
        "name": "Hunter",
        "description": "Find, verify and manage professional email addresses at scale. Automate email discovery, validation, lead tracking, and campaign outreach with Hunter.io.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/hunter.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-hystruct",
        "name": "Hystruct",
        "description": "AI-powered document structuring and data extraction",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/hystruct.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-ibm-cognose",
        "name": "IBM Cognos Analytics",
        "description": "Business intelligence and performance management suite for data analysis and reporting",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/ibm-cognose.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-image-helper",
        "name": "Image Helper",
        "description": "Tools for image manipulations",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/image-helper.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-image-router",
        "name": "ImageRouter",
        "description": "Generate images with any model available on ImageRouter.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/image-router.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-imap",
        "name": "IMAP",
        "description": "Receive new email trigger",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/imap.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-insightly",
        "name": "Insightly",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/insightly.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-insighto-ai",
        "name": "Insighto.ai",
        "description": "AI-powered platform for capturing forms, conversations, and data sources with automated processing and outbound communications",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/insighto-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-instabase",
        "name": "Instabase",
        "description": "Integrate with Instabase AI Hub to automate document processing and AI workflows",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/instabase.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-instagram-business",
        "name": "Instagram for Business",
        "description": "Grow your business on Instagram",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/instagram.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-instantly-ai",
        "name": "Instantly.ai",
        "description": "Powerful cold email outreach and lead engagement platform.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/instantly-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-instasent",
        "name": "Instasent",
        "description": "",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/instasent.jpg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-intercom",
        "name": "Intercom",
        "description": "Customer messaging platform for sales, marketing, and support",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/intercom.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-invoiceninja",
        "name": "Invoice Ninja",
        "description": "Free open-source invoicing tool",
        "category": "finance",
        "icon": "https://cdn.activepieces.com/pieces/invoiceninja.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-jina-ai",
        "name": "Jina AI",
        "description": "AI-powered web content extraction, search, and classification",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/jinaai.jpeg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-jira-cloud",
        "name": "Jira Cloud",
        "description": "Issue tracking and project management",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/jira.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-jogg-ai",
        "name": "JoggAI",
        "description": "AI-powered content creation platform for generating avatar photos, videos, and product content using advanced AI technology.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/jogg-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-jotform",
        "name": "Jotform",
        "description": "Create online forms and surveys",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/jotform.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-json",
        "name": "JSON",
        "description": "Convert JSON to text and vice versa",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/json.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-kallabot-ai",
        "name": "Kallabot",
        "description": "AI-powered voice agents and conversational interfaces.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/kallabot-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-katana",
        "name": "Katana",
        "description": "Katana is a cloud-based manufacturing ERP software for inventory, production, and order management.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/katana.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-kimai",
        "name": "Kimai",
        "description": "Open-source time tracking software",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/kimai.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-kissflow",
        "name": "Kissflow",
        "description": "Low-code no-code platform",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/kissflow.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-kizeo-forms",
        "name": "Kizeo Forms",
        "description": "Create custom mobile forms",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/kizeo-forms.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-knack",
        "name": "Knack",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/knack.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-kommo",
        "name": "Kommo",
        "description": "",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/kommo.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-krisp-call",
        "name": "KrispCall",
        "description": "KrispCall is a cloud telephony system for modern businesses, offering advanced features for high-growth startups and modern enterprises.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/krispcall.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-kudosity",
        "name": "Kudosity",
        "description": "Kudosity is a cloud-based SMS platform that enables businesses to send and receive text messages globally.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/kudosity.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-lead-connector",
        "name": "LeadConnector",
        "description": "Lead Connector - Go High Level",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/lead-connector.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-leexi",
        "name": "Leexi",
        "description": "AI Notetaker",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/leexi.png",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-lemlist",
        "name": "Lemlist",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/lemlist.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-lemon-squeezy",
        "name": "Lemon Squeezy",
        "description": "Lemon Squeezy is a payment gateway for e-commerce and subscription-based businesses.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/lemon-squeezy.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-letta",
        "name": "Letta",
        "description": "Letta is the platform for building stateful agents: open AI with advanced memory that can learn and self-improve over time.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/letta.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-lever",
        "name": "Lever",
        "description": "Lever is a modern, collaborative recruiting platform that powers a more human approach to hiring.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/lever.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-lightfunnels",
        "name": "Lightfunnels",
        "description": "",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/lightfunnels.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-line",
        "name": "Line Bot",
        "description": "Build chatbots for LINE",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/line.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-linear",
        "name": "Linear",
        "description": "Issue tracking for modern software teams",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/linear.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [
            {
                "name": "new_issue",
                "displayName": "New Issue",
                "description": "Triggers when Linear receives a new issue",
                "props": {
                    "team_id": {
                        "displayName": "Team",
                        "description": "The team for which the issue, project or comment will be created",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "updated_issue",
                "displayName": "Updated Issue",
                "description": "Triggers when an existing Linear issue is updated",
                "props": {
                    "team_id": {
                        "displayName": "Team",
                        "description": "The team for which the issue, project or comment will be created",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "removed_issue",
                "displayName": "Removed Issue",
                "description": "Triggers when an existing Linear issue is removed",
                "props": {
                    "team_id": {
                        "displayName": "Team",
                        "description": "The team for which the issue, project or comment will be created",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "linear_create_issue",
                "displayName": "Create Issue",
                "description": "Create a new issue in Linear workspace",
                "props": {
                    "team_id": {
                        "displayName": "Team",
                        "description": "The team for which the issue, project or comment will be created",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "state_id": {
                        "displayName": "Status",
                        "description": "Status of the Issue",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "labels": {
                        "displayName": "Labels",
                        "description": "Labels for the Issue",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "assignee_id": {
                        "displayName": "Assignee",
                        "description": "Assignee of the Issue / Comment",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "priority_id": {
                        "displayName": "Priority",
                        "description": "Priority of the Issue",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "template_id": {
                        "displayName": "Template",
                        "description": "ID of Template",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "linear_update_issue",
                "displayName": "Update Issue",
                "description": "Update a issue in Linear Workspace",
                "props": {
                    "team_id": {
                        "displayName": "Team",
                        "description": "The team for which the issue, project or comment will be created",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "issue_id": {
                        "displayName": "Issue",
                        "description": "ID of Linear Issue",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "state_id": {
                        "displayName": "Status",
                        "description": "Status of the Issue",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "labels": {
                        "displayName": "Labels",
                        "description": "Labels for the Issue",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "assignee_id": {
                        "displayName": "Assignee",
                        "description": "Assignee of the Issue / Comment",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "priority_id": {
                        "displayName": "Priority",
                        "description": "Priority of the Issue",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "linear_create_project",
                "displayName": "Create Project",
                "description": "Create a new project in Linear workspace",
                "props": {
                    "team_id": {
                        "displayName": "Team",
                        "description": "The team for which the issue, project or comment will be created",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Project Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "icon": {
                        "displayName": "Icon",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "color": {
                        "displayName": "Color",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "startDate": {
                        "displayName": "Start Date",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "targetDate": {
                        "displayName": "Target Date",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "linear_update_project",
                "displayName": "Update Project",
                "description": "Update a existing project in Linear workspace",
                "props": {
                    "team_id": {
                        "displayName": "Team",
                        "description": "The team for which the issue, project or comment will be created",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "project_id": {
                        "displayName": "Project",
                        "description": "ID of Linear Project",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Project Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "icon": {
                        "displayName": "Icon",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "color": {
                        "displayName": "Color",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "startDate": {
                        "displayName": "Start Date",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "targetDate": {
                        "displayName": "Target Date",
                        "description": "",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "linear_create_comment",
                "displayName": "Create Comment",
                "description": "Create a new comment on an issue in Linear workspace",
                "props": {
                    "team_id": {
                        "displayName": "Team",
                        "description": "The team for which the issue, project or comment will be created",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "user_id": {
                        "displayName": "Assignee",
                        "description": "Assignee of the Issue / Comment",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "issue_id": {
                        "displayName": "Issue",
                        "description": "ID of Linear Issue",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Comment Body",
                        "description": "The content of the comment",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "rawGraphqlQuery",
                "displayName": "Raw GraphQL query",
                "description": "Perform a raw GraphQL query",
                "props": {
                    "query": {
                        "displayName": "Query",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "variables": {
                        "displayName": "Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-linka",
        "name": "Linka",
        "description": "Linka white-label B2B marketplace platform powers communities and digital storefronts",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/linka.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-linkedin",
        "name": "LinkedIn",
        "description": "Connect and network with professionals",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/linkedin.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-linkup",
        "name": "Linkup",
        "description": "Linkup is a web search engine for AI apps. Connect your AI application to the internet and get grounding data to enrich your AI's output.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/linkup.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-llmrails",
        "name": "LLMRails",
        "description": "LLM Rails Platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/llmrails.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-localai",
        "name": "LocalAI",
        "description": "The free, Self-hosted, community-driven and local-first. Drop-in replacement for OpenAI running on consumer-grade hardware. No GPU required.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/localai.jpeg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-lofty",
        "name": "Lofty",
        "description": "Lofty is a product of the technology company Lofty Inc, which offers a complete tech solution for real estate agents.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/lofty.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-logrocket",
        "name": "LogRocket",
        "description": "Get AI-generated summaries of user sessions to understand customer behavior and troubleshoot issues faster.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/logrocket.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-lusha",
        "name": "Lusha",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/lusha.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-luxury-presence",
        "name": "Luxury Presence",
        "description": "Luxury Presence is a software company designed for real estate agents. Their all-in-one platform combines a CRM, website builder, marketing tools, and more to help agents grow their business and close more deals.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/luxury-presence.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-magical-api",
        "name": "Magical API",
        "description": "Automate resume parsing, review, scoring, and LinkedIn profile/company data retrieval with Magical API.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/magical-api.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-magicslides",
        "name": "MagicSlides",
        "description": "Create PowerPoint presentations from topics, summaries, or YouTube videos using AI.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/magicslides.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mailchain",
        "name": "Mailchain",
        "description": "Mailchain is a simple, secure, and decentralized communications protocol that enables blockchain-based email.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mailchain.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mailchimp",
        "name": "Mailchimp",
        "description": "All-in-One integrated marketing platform for managing audiences, sending campaigns, tracking engagement, and automating lifecycle communications.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/mailchimp.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "subscribe",
                "displayName": "Member Subscribed to Audience",
                "description": "Fires when a new subscriber joins your Mailchimp audience. This trigger captures new subscriptions, opt-ins, and audience growth events with comprehensive subscriber information.",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "unsubscribe",
                "displayName": "Member Unsubscribed from Audience",
                "description": "Fires when a subscriber unsubscribes from your Mailchimp audience. This trigger captures unsubscribe events, opt-outs, and audience churn with comprehensive subscriber information for retention analysis.",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_campaign",
                "displayName": "New Campaign",
                "description": "Fires when a new campaign is created or sent",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "link_clicked",
                "displayName": "Link Clicked",
                "description": "Fires when a recipient clicks a specified link in a campaign",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "email_opened",
                "displayName": "Email Opened",
                "description": "Fires when a recipient opens a an email in a specific campaign",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "subscriber_updated",
                "displayName": "Subscriber Updated",
                "description": "Fires when a subscriber profile is updated, including changes to merge fields, interests, or contact information. This trigger captures profile updates, new subscriptions, and subscriber modifications.",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_customer",
                "displayName": "New Customer",
                "description": "Fires when a new customer is added to a connected store",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_order",
                "displayName": "New Order",
                "description": "Fires when a new order is created in the connected store",
                "props": {
                    "store_id": {
                        "displayName": "Store",
                        "description": "Select the e-commerce store",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_segment_tag_subscriber",
                "displayName": "New Segment Tag Subscriber",
                "description": "Fires when a subscriber joins a specific segment or tag",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "segment_id": {
                        "displayName": "Segment ID (Optional)",
                        "description": "The specific segment ID to monitor. Leave empty to monitor all segments.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tag_name": {
                        "displayName": "Tag Name (Optional)",
                        "description": "The specific tag name to monitor. Leave empty to monitor all tags.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "add_member_to_list",
                "displayName": "Add or Update Subscriber",
                "description": "Add a new subscriber to an audience or update existing subscriber",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email_address": {
                        "displayName": "Email Address",
                        "description": "Email address for the subscriber",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "status_if_new": {
                        "displayName": "Status if New",
                        "description": "Status for new subscribers",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Subscribed",
                                    "value": "subscribed"
                                },
                                {
                                    "label": "Unsubscribed",
                                    "value": "unsubscribed"
                                },
                                {
                                    "label": "Cleaned",
                                    "value": "cleaned"
                                },
                                {
                                    "label": "Pending",
                                    "value": "pending"
                                },
                                {
                                    "label": "Transactional",
                                    "value": "transactional"
                                }
                            ]
                        }
                    },
                    "email_type": {
                        "displayName": "Email Type",
                        "description": "Type of email this member wants to receive",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "HTML",
                                    "value": "html"
                                },
                                {
                                    "label": "Text",
                                    "value": "text"
                                }
                            ]
                        }
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "Current status of subscriber (for updates)",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Subscribed",
                                    "value": "subscribed"
                                },
                                {
                                    "label": "Unsubscribed",
                                    "value": "unsubscribed"
                                },
                                {
                                    "label": "Cleaned",
                                    "value": "cleaned"
                                },
                                {
                                    "label": "Pending",
                                    "value": "pending"
                                },
                                {
                                    "label": "Transactional",
                                    "value": "transactional"
                                }
                            ]
                        }
                    },
                    "first_name": {
                        "displayName": "First Name",
                        "description": "First name of the subscriber",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "last_name": {
                        "displayName": "Last Name",
                        "description": "Last name of the subscriber",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "language": {
                        "displayName": "Language",
                        "description": "Subscriber language (e.g., \"en\", \"es\", \"fr\")",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "vip": {
                        "displayName": "VIP",
                        "description": "VIP status for subscriber",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "skip_merge_validation": {
                        "displayName": "Skip Merge Validation",
                        "description": "Accept member data without merge field values even if required",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "add_note_to_subscriber",
                "displayName": "Add Note to Subscriber",
                "description": "Add a note to a subscriber in your Mailchimp audience.",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email Address",
                        "description": "The email address of the subscriber to add a note to",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "note": {
                        "displayName": "Note Content",
                        "description": "The note content to add to the subscriber",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add_subscriber_to_tag",
                "displayName": "Add Subscriber to Tag",
                "description": "Add a subscriber to a specific tag in your Mailchimp audience.",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email Address",
                        "description": "The email address of the subscriber to add to the tag",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "tag_name": {
                        "displayName": "Tag Name",
                        "description": "The name of the tag to add the subscriber to",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "remove_subscriber_from_tag",
                "displayName": "Remove Subscriber from Tag",
                "description": "Remove a subscriber from a specific tag in your Mailchimp audience.",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email Address",
                        "description": "The email address of the subscriber to remove from the tag",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "tag_name": {
                        "displayName": "Tag Name",
                        "description": "The name of the tag to remove the subscriber from",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_member_in_list",
                "displayName": "Update Member in an Audience (List)",
                "description": "Update a member in an existing Mailchimp audience (list)",
                "props": {
                    "email": {
                        "displayName": "Email",
                        "description": "Email of the new contact",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Subscribed",
                                    "value": "subscribed"
                                },
                                {
                                    "label": "Unsubscribed",
                                    "value": "unsubscribed"
                                },
                                {
                                    "label": "Cleaned",
                                    "value": "cleaned"
                                },
                                {
                                    "label": "Pending",
                                    "value": "pending"
                                },
                                {
                                    "label": "Transactional",
                                    "value": "transactional"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "create_campaign",
                "displayName": "Create Campaign",
                "description": "Create a new Mailchimp campaign",
                "props": {
                    "campaign_type": {
                        "displayName": "Campaign Type",
                        "description": "The type of campaign to create",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Regular",
                                    "value": "regular"
                                },
                                {
                                    "label": "Plain Text",
                                    "value": "plaintext"
                                },
                                {
                                    "label": "A/B Test",
                                    "value": "ab"
                                },
                                {
                                    "label": "RSS",
                                    "value": "rss"
                                },
                                {
                                    "label": "Variate",
                                    "value": "variate"
                                }
                            ]
                        }
                    },
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "subject_line": {
                        "displayName": "Subject Line",
                        "description": "The subject line for the campaign",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Campaign Title",
                        "description": "The title of the campaign",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "from_name": {
                        "displayName": "From Name",
                        "description": "The name that will appear in the \"From\" field",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "from_email": {
                        "displayName": "From Email",
                        "description": "The email address that will appear in the \"From\" field",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "reply_to": {
                        "displayName": "Reply To Email",
                        "description": "The email address that will receive replies",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "to_name": {
                        "displayName": "To Name",
                        "description": "The name that will appear in the \"To\" field (e.g., *|FNAME|*)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "content_type": {
                        "displayName": "Content Type",
                        "description": "How the campaign content is put together",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Template",
                                    "value": "template"
                                },
                                {
                                    "label": "HTML",
                                    "value": "html"
                                },
                                {
                                    "label": "URL",
                                    "value": "url"
                                },
                                {
                                    "label": "Multichannel",
                                    "value": "multichannel"
                                }
                            ]
                        }
                    },
                    "content_url": {
                        "displayName": "Content URL",
                        "description": "The URL where the campaign content is hosted (required if content_type is \"url\")",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "template_id": {
                        "displayName": "Template ID",
                        "description": "The ID of the template to use (required if content_type is \"template\")",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "html_content": {
                        "displayName": "HTML Content",
                        "description": "The HTML content for the campaign (required if content_type is \"html\")",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_campaign_report",
                "displayName": "Get Campaign Report",
                "description": "Get comprehensive report details for a specific sent campaign including opens, clicks, bounces, and performance metrics",
                "props": {
                    "campaign_id": {
                        "displayName": "Campaign",
                        "description": "Select the campaign to get information for",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "fields": {
                        "displayName": "Include Fields",
                        "description": "Comma-separated list of fields to return (e.g., \"opens.unique_opens,clicks.click_rate\")",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "exclude_fields": {
                        "displayName": "Exclude Fields",
                        "description": "Comma-separated list of fields to exclude (e.g., \"timeseries,_links\")",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_audience",
                "displayName": "Create Audience",
                "description": "Create a new audience (list) in your Mailchimp account",
                "props": {
                    "name": {
                        "displayName": "List Name",
                        "description": "The name of the list",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "company": {
                        "displayName": "Company",
                        "description": "Company name for list contact information",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "address1": {
                        "displayName": "Address Line 1",
                        "description": "Street address for list contact information",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "address2": {
                        "displayName": "Address Line 2",
                        "description": "Additional address information (optional)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "city": {
                        "displayName": "City",
                        "description": "City for list contact information",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "state": {
                        "displayName": "State/Province",
                        "description": "State or province for list contact information",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "zip": {
                        "displayName": "ZIP/Postal Code",
                        "description": "ZIP or postal code for list contact information",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "country": {
                        "displayName": "Country",
                        "description": "Country for list contact information",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "phone": {
                        "displayName": "Phone",
                        "description": "Phone number for list contact information (optional)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "permission_reminder": {
                        "displayName": "Permission Reminder",
                        "description": "The permission reminder for the list",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": "You are receiving this email because you signed up for updates from us."
                    },
                    "from_name": {
                        "displayName": "Default From Name",
                        "description": "Default from name for campaigns",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "from_email": {
                        "displayName": "Default From Email",
                        "description": "Default from email address for campaigns",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "subject": {
                        "displayName": "Default Subject",
                        "description": "Default subject line for campaigns",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "language": {
                        "displayName": "Language",
                        "description": "Default language for campaigns (e.g., \"en\", \"es\", \"fr\")",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": "en"
                    },
                    "email_type_option": {
                        "displayName": "Email Type Option",
                        "description": "Whether the list supports multiple email formats (HTML/plain text)",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": true
                    },
                    "use_archive_bar": {
                        "displayName": "Use Archive Bar",
                        "description": "Whether campaigns use the Archive Bar in archives by default",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "notify_on_subscribe": {
                        "displayName": "Notify on Subscribe",
                        "description": "Email address to send subscribe notifications to (optional)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "notify_on_unsubscribe": {
                        "displayName": "Notify on Unsubscribe",
                        "description": "Email address to send unsubscribe notifications to (optional)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "double_optin": {
                        "displayName": "Double Opt-in",
                        "description": "Whether to require subscriber confirmation via email",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "marketing_permissions": {
                        "displayName": "Marketing Permissions",
                        "description": "Whether the list has marketing permissions (GDPR) enabled",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "archive_subscriber",
                "displayName": "Archive Subscriber",
                "description": "Archive an existing audience member",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "subscriber_hash": {
                        "displayName": "Subscriber Hash or Email",
                        "description": "MD5 hash of the lowercase email address, email address, or contact_id",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "unsubscribe_email",
                "displayName": "Unsubscribe Email",
                "description": "Unsubscribe an email address from an audience",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email_address": {
                        "displayName": "Email Address",
                        "description": "Email address to unsubscribe",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "skip_merge_validation": {
                        "displayName": "Skip Merge Validation",
                        "description": "Accept member data without merge field values even if required",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "skip_duplicate_check": {
                        "displayName": "Skip Duplicate Check",
                        "description": "Ignore duplicates in the request",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "update_existing": {
                        "displayName": "Update Existing",
                        "description": "Change existing members subscription status",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": true
                    }
                }
            },
            {
                "name": "find_campaign",
                "displayName": "Find Campaign",
                "description": "Search all campaigns for the specified query terms",
                "props": {
                    "query": {
                        "displayName": "Search Query",
                        "description": "Search terms to find campaigns",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "fields": {
                        "displayName": "Fields",
                        "description": "Comma-separated list of fields to return",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "exclude_fields": {
                        "displayName": "Exclude Fields",
                        "description": "Comma-separated list of fields to exclude",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_customer",
                "displayName": "Find Customer",
                "description": "Find a customer by email address in a store",
                "props": {
                    "store_id": {
                        "displayName": "Store",
                        "description": "Select the e-commerce store",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email_address": {
                        "displayName": "Email Address",
                        "description": "Email address to search for",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "fields": {
                        "displayName": "Include Fields",
                        "description": "Comma-separated list of fields to return",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "exclude_fields": {
                        "displayName": "Exclude Fields",
                        "description": "Comma-separated list of fields to exclude",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "count": {
                        "displayName": "Count",
                        "description": "Number of records to return (max 1000)",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 10
                    },
                    "offset": {
                        "displayName": "Offset",
                        "description": "Number of records to skip for pagination",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 0
                    }
                }
            },
            {
                "name": "find_tag",
                "displayName": "Find Tag",
                "description": "Search for tags on a list by name",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Tag Name",
                        "description": "Search query to filter tags (optional - if empty, returns all tags)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_subscriber",
                "displayName": "Find Subscriber",
                "description": "Search for subscribers across all lists or within a specific list. This action provides comprehensive subscriber information including merge fields, interests, and activity data.",
                "props": {
                    "list_id": {
                        "displayName": "Audience",
                        "description": "Audience you want to add the contact to",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email Address",
                        "description": "Email address of the subscriber to search for",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "include_fields": {
                        "displayName": "Include Fields",
                        "description": "Fields to include in the response (leave empty for all fields). Use dot notation for nested fields (e.g., \"merge_fields.FNAME\")",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "exclude_fields": {
                        "displayName": "Exclude Fields",
                        "description": "Fields to exclude from the response. Use dot notation for nested fields",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-mailercheck",
        "name": "Mailercheck",
        "description": "MailerCheck is an easy-to-use email and campaign analysis tool. Anyone using an email service provider can keep their email lists clean and their campaigns deliverable.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/mailercheck.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mailer-lite",
        "name": "MailerLite",
        "description": "Email marketing software",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/mailer-lite.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-maileroo",
        "name": "Maileroo",
        "description": "Email Delivery Service with Real-Time Analytics and Reporting",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/maileroo.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mailjet",
        "name": "Mailjet",
        "description": "Email delivery service for sending transactional and marketing emails",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/mailjet.svg",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-manus",
        "name": "Manus",
        "description": "AI-powered automation and task execution platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/manus.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-manychat",
        "name": "Manychat",
        "description": "Automations for Instagram, WhatsApp, TikTok, and Messenger marketing.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/manychat.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mastodon",
        "name": "Mastodon",
        "description": "Open-source decentralized social network",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/mastodon.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-math-helper",
        "name": "Math Helper",
        "description": "\nPerform mathematical operations.\n",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/math-helper.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-matomo",
        "name": "Matomo",
        "description": "Open source alternative to Google Analytics",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/matomo.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-matrix",
        "name": "Matrix",
        "description": "Open standard for interoperable, decentralized, real-time communication",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/matrix.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mattermost",
        "name": "Mattermost",
        "description": "Open-source, self-hosted Slack alternative",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/mattermost.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mautic",
        "name": "Mautic",
        "description": "Open-source marketing automation software",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/mautic.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mcp",
        "name": "MCP",
        "description": "Connect to your hosted MCP Server using any MCP client to communicate with tools",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mcp.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-medullar",
        "name": "Medullar",
        "description": "AI-powered discovery & insight platform that acts as your extended digital mind",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/medullar.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-meetgeek-ai",
        "name": "Meetgeek",
        "description": "AI-powered meeting assistant that automates note-taking, summarization, and insights generation for your meetings.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/meetgeek-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-meistertask",
        "name": "MeisterTask",
        "description": "Intuitive online task manager for teams, personal productivity, and everything in between.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/meistertask.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mem",
        "name": "Mem",
        "description": "Capture and organize your thoughts using Mem.ai",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/mem.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mempool-space",
        "name": "Mempool",
        "description": "The mempool.space website invented the concept of visualizing a Bitcoin node's mempool as projected blocks.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mempool-space.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-metabase",
        "name": "Metabase",
        "description": "The simplest way to ask questions and learn from data",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/metabase.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-metatext",
        "name": "Metatext",
        "description": "AI content moderation and safety guard API",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/metatext.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-365-people",
        "name": "Microsoft 365 People",
        "description": "Manage contacts in Microsoft 365 People",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-365-people.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-365-planner",
        "name": "Microsoft 365 Planner",
        "description": "Microsoft 365 Planner is part of the Microsoft 365 suite, offering lightweight task and bucket-based planning for teams. This integration supports creating plans, buckets, tasks, fetching them, deleting them, and custom API calls.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-365-planner.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-dynamics-365-business-central",
        "name": "Microsoft Dynamics 365 Business Central",
        "description": "All-in-one business management solution by Microsoft.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-dynamics-365-business-central.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-dynamics-crm",
        "name": "Microsoft Dynamics CRM",
        "description": "Customer relationship management software package developed by Microsoft.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-dynamics-crm.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-excel-365",
        "name": "Microsoft Excel 365",
        "description": "Spreadsheet software by Microsoft",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-excel-365.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-onedrive",
        "name": "Microsoft OneDrive",
        "description": "Cloud storage by Microsoft",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/oneDrive.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-onenote",
        "name": "Microsoft OneNote",
        "description": "Microsoft OneNote is a note-taking app that allows you to create, edit, and share notes with others.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-onenote.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-outlook",
        "name": "Microsoft Outlook",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-outlook.jpg",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-outlook-calendar",
        "name": "Microsoft Outlook Calendar",
        "description": "Calendar software by Microsoft",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-outlook.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-power-bi",
        "name": "Microsoft Power BI",
        "description": "Create and manage Power BI datasets and push data to them",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-power-bi.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-sharepoint",
        "name": "Microsoft SharePoint",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-sharepoint.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-teams",
        "name": "Microsoft Teams",
        "description": "",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-teams.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-microsoft-todo",
        "name": "Microsoft To Do",
        "description": "Cloud based task management application.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/microsoft-todo.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-millionverifier",
        "name": "MillionVerifier",
        "description": "MillionVerifier is an email verifier service and API",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/millionverifier.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mindee",
        "name": "Mindee",
        "description": "Document automation API",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/mindee.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mind-studio",
        "name": "MindStudio",
        "description": "Run MindStudio workflows and get AI results.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mind-studio.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-missive",
        "name": "Missive",
        "description": "",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/missive.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mistral-ai",
        "name": "Mistral AI",
        "description": "Mistral AI provides state-of-the-art open-weight and hosted language models for text generation, embeddings, and reasoning tasks.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mistral-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mixpanel",
        "name": "Mixpanel",
        "description": "Simple and powerful product analytics that helps everyone make better decisions",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mixpanel.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mollie",
        "name": "Mollie",
        "description": "Automate Mollie payments, orders, refunds, customers, and invoices. Triggers on payment events and statuses.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mollie.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-monday",
        "name": "monday.com",
        "description": "Work operating system for businesses",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/monday.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mongodb",
        "name": "MongoDB",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mongodb.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-motion",
        "name": "Motion",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/motion.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-motiontools",
        "name": "MotionTools",
        "description": "Digitize processes, boost efficiency and excite users with MotionTools, the operating system for fleet-based service providers.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/motiontools.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-moxie-crm",
        "name": "Moxie",
        "description": "CRM build for the freelancers.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/moxie-crm.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-murf-api",
        "name": "Murf AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/murf-api.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mycase-piece",
        "name": "MyCase",
        "description": "Automate legal case management workflows with MyCase. Create and manage cases, clients, companies, events, tasks, time entries, documents, and more. Get notified when cases, events, people, companies, or leads are added or updated.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mycase-piece.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-mysql",
        "name": "MySQL",
        "description": "The world's most popular open-source database",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/mysql.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-netlify",
        "name": "Netlify",
        "description": "Netlify is a platform for building and deploying websites and apps.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/netlify.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-netsuite",
        "name": "NetSuite",
        "description": "",
        "category": "finance",
        "icon": "https://cdn.activepieces.com/pieces/netsuite.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-neverbounce",
        "name": "NeverBounce",
        "description": "NeverBounce is an email verification service that improves deliverability and helps businesses adhere to strict deliverability guidelines.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/neverbounce.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-nifty",
        "name": "Nifty",
        "description": "Project management made simple",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/nifty.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-ninox",
        "name": "Ninox",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/ninox.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-nocodb",
        "name": "NocoDB",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/nocodb.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-notion",
        "name": "Notion",
        "description": "The all-in-one workspace",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/notion.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "new_database_item",
                "displayName": "New Database Item",
                "description": "Triggers when an item is added to a database.",
                "props": {
                    "database_id": {
                        "displayName": "Database",
                        "description": "Choose the Notion database you want to work with from your workspace",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "updated_database_item",
                "displayName": "Updated Database Item",
                "description": "Triggers when an item is updated in a database.",
                "props": {
                    "database_id": {
                        "displayName": "Database",
                        "description": "Choose the Notion database you want to work with from your workspace",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_comment",
                "displayName": "New Comment",
                "description": "Triggers whenever someone adds a new comment to a specific Notion page. Perfect for notifications, review workflows, or automated responses to team feedback.",
                "props": {
                    "page_id": {
                        "displayName": "Page",
                        "description": "Choose the Notion page you want to work with. This list shows your 100 most recently edited pages for easy selection.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "updated_page",
                "displayName": "Updated Page",
                "description": "Triggers whenever any page in your Notion workspace is modified or updated. Ideal for syncing content changes, backup processes, or notifying teams about documentation updates.",
                "props": {}
            }
        ],
        "actions": [
            {
                "name": "create_database_item",
                "displayName": "Create Database Item",
                "description": "Add a new item to a Notion database with custom field values and optional content. Ideal for creating tasks, records, or entries in structured databases.",
                "props": {
                    "database_id": {
                        "displayName": "Database",
                        "description": "Choose the Notion database you want to work with from your workspace",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "databaseFields": {
                        "displayName": "Fields",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "content": {
                        "displayName": "Content",
                        "description": "The content you want to append to your item.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_database_item",
                "displayName": "Update Database Item",
                "description": "Update specific fields in a Notion database item. Perfect for maintaining data, tracking changes, or syncing information across systems.",
                "props": {
                    "database_id": {
                        "displayName": "Database",
                        "description": "Choose the Notion database you want to work with from your workspace",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "database_item_id": {
                        "displayName": "Database Item",
                        "description": "Select the item you want to update",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "databaseFields": {
                        "displayName": "Fields",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "notion-find-database-item",
                "displayName": "Find Database Item",
                "description": "Searches for an item in database by field.",
                "props": {
                    "database_id": {
                        "displayName": "Database",
                        "description": "Choose the Notion database you want to work with from your workspace",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "filterDatabaseFields": {
                        "displayName": "Fields",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "createPage",
                "displayName": "Create Page",
                "description": "Create a new Notion page as a sub-page with custom title and content. Perfect for organizing documentation, notes, or creating structured page hierarchies.",
                "props": {
                    "pageId": {
                        "displayName": "Page",
                        "description": "Choose the Notion page you want to work with. This list shows your 100 most recently edited pages for easy selection.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "The title of the page.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "content": {
                        "displayName": "Content",
                        "description": "The content of the page.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "append_to_page",
                "displayName": "Append to Page",
                "description": "Appends content to the end of a page.",
                "props": {
                    "pageId": {
                        "displayName": "Page",
                        "description": "Choose the Notion page you want to work with. This list shows your 100 most recently edited pages for easy selection.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "content": {
                        "displayName": "Content",
                        "description": "The content you want to append. You can use markdown formatting.",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "getPageOrBlockChildren",
                "displayName": "Get block content",
                "description": "Retrieve the actual content of a page (represented by blocks).",
                "props": {
                    "parentId": {
                        "displayName": "Page or parent block ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "markdown": {
                        "displayName": "Markdown",
                        "description": "Convert Notion JSON blocks to Markdown",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    },
                    "dynamic": {
                        "displayName": "Dynamic properties",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "archive_database_item",
                "displayName": "Archive Database Item",
                "description": "Archive (soft-delete) a database item without permanently removing it. Archived items can be restored later if needed.",
                "props": {
                    "database_id": {
                        "displayName": "Database",
                        "description": "Choose the Notion database you want to work with from your workspace",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "database_item_id": {
                        "displayName": "Database Item",
                        "description": "Select the item you want to update",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "restore_database_item",
                "displayName": "Restore Database Item",
                "description": "Restore an archived database item back to active status. Perfect for recovering accidentally archived tasks, projects, or records.",
                "props": {
                    "database_id": {
                        "displayName": "Database",
                        "description": "Choose the Notion database you want to work with from your workspace",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "archived_item_id": {
                        "displayName": "Archived Item",
                        "description": "Choose which archived item to restore from the selected database",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add_comment",
                "displayName": "Add Comment",
                "description": "Add a comment to any Notion page to start discussions, provide feedback, or leave notes for team collaboration.",
                "props": {
                    "page_id": {
                        "displayName": "Page",
                        "description": "Choose the Notion page you want to work with. This list shows your 100 most recently edited pages for easy selection.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "comment_text": {
                        "displayName": "Comment Text",
                        "description": "Enter your comment text. Supports plain text and will be posted as a new comment thread on the selected page.",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "retrieve_database",
                "displayName": "Retrieve Database Structure",
                "description": "Get detailed information about a Notion database including all its properties, field types, and configuration. Perfect for building dynamic forms, validation rules, or understanding database schemas.",
                "props": {
                    "database_id": {
                        "displayName": "Database",
                        "description": "Choose the Notion database you want to work with from your workspace",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_page_comments",
                "displayName": "Get Page Comments",
                "description": "Retrieve all comments from a Notion page, organized by discussion threads. Perfect for tracking feedback, managing reviews, or monitoring page discussions.",
                "props": {
                    "page_id": {
                        "displayName": "Page",
                        "description": "Choose the Notion page you want to work with. This list shows your 100 most recently edited pages for easy selection.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_page",
                "displayName": "Find Page",
                "description": "Search for Notion pages by title with flexible matching options. Perfect for finding specific pages, building page references, or creating automated workflows based on page discovery.",
                "props": {
                    "title": {
                        "displayName": "Page Title",
                        "description": "Enter the page title or part of the title you want to search for",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "exact_match": {
                        "displayName": "Exact Match",
                        "description": "Enable this to find pages with exactly the same title. Disable for partial matching (finds pages containing your search term).",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "limit": {
                        "displayName": "Maximum Results",
                        "description": "How many pages to return at most (between 1 and 100)",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 10
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-ntfy",
        "name": "ntfy",
        "description": "Notification management made easy",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/ntfy.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-nuelink",
        "name": "Nuelink",
        "description": "",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/nuelink.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-octopush-sms",
        "name": "Octopush SMS",
        "description": "Send bulk messaging for your promotions, order tracking, appointment reminders, voice messages, one-time passwords (OTP), 2-way chat sms and much more!",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/octopush-sms.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-odoo",
        "name": "Odoo",
        "description": "Open source all-in-one management software",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/odoo.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-okta",
        "name": "Okta",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/okta.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-omni-co",
        "name": "Omni",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/omni-co.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-oncehub",
        "name": "Oncehub",
        "description": "Build meaningful on-brand scheduling experiences with OnceHubs online appointment booking software",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/oncehub.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-onfleet",
        "name": "Onfleet",
        "description": "Last mile delivery software",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/onfleet.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-openai",
        "name": "OpenAI",
        "description": "Use the many tools ChatGPT has to offer.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/openai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": [
            {
                "name": "ask_chatgpt",
                "displayName": "Ask ChatGPT",
                "description": "Ask ChatGPT anything you want!",
                "props": {
                    "model": {
                        "displayName": "Model",
                        "description": "The model which will generate the completion. Some models are suitable for natural language tasks, others specialize in code.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": "gpt-3.5-turbo"
                    },
                    "prompt": {
                        "displayName": "Question",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "temperature": {
                        "displayName": "Temperature",
                        "description": "Controls randomness: Lowering results in less random completions. As the temperature approaches zero, the model will become deterministic and repetitive.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 1
                    },
                    "maxTokens": {
                        "displayName": "Maximum Tokens",
                        "description": "The maximum number of tokens to generate. Requests can use up to 2,048 or 4,096 tokens shared between prompt and completion depending on the model. Don't set the value to maximum and leave some tokens for the input. (One token is roughly 4 characters for normal English text)",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 2048
                    },
                    "topP": {
                        "displayName": "Top P",
                        "description": "An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top 10% probability mass are considered.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 1
                    },
                    "frequencyPenalty": {
                        "displayName": "Frequency penalty",
                        "description": "Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 0
                    },
                    "presencePenalty": {
                        "displayName": "Presence penalty",
                        "description": "Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far, increasing the mode's likelihood to talk about new topics.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "memoryKey": {
                        "displayName": "Memory Key",
                        "description": "A memory key that will keep the chat history shared across runs and flows. Keep it empty to leave ChatGPT without memory of previous messages.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "roles": {
                        "displayName": "Roles",
                        "description": "Array of roles to specify more accurate response",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant."
                            }
                        ]
                    }
                }
            },
            {
                "name": "ask_assistant",
                "displayName": "Ask Assistant",
                "description": "Ask a GPT assistant anything you want!",
                "props": {
                    "assistant": {
                        "displayName": "Assistant",
                        "description": "The assistant which will generate the completion.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "prompt": {
                        "displayName": "Question",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "memoryKey": {
                        "displayName": "Memory Key",
                        "description": "A memory key that will keep the chat history shared across runs and flows. Keep it empty to leave your assistant without memory of previous messages.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "generate_image",
                "displayName": "Generate Image",
                "description": "Generate an image using text-to-image models",
                "props": {
                    "model": {
                        "displayName": "Model",
                        "description": "The model which will generate the image.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": "dall-e-3"
                    },
                    "prompt": {
                        "displayName": "Prompt",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "resolution": {
                        "displayName": "Resolution",
                        "description": "The resolution to generate the image in.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": "1024x1024"
                    },
                    "quality": {
                        "displayName": "Quality",
                        "description": "Standard is faster, HD has better details.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": "standard"
                    }
                }
            },
            {
                "name": "vision_prompt",
                "displayName": "Vision Prompt",
                "description": "Ask GPT a question about an image",
                "props": {
                    "image": {
                        "displayName": "Image",
                        "description": "The image URL or file you want GPT's vision to read.",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "prompt": {
                        "displayName": "Question",
                        "description": "What do you want ChatGPT to tell you about the image?",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "detail": {
                        "displayName": "Detail",
                        "description": "Control how the model processes the image and generates textual understanding.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": "auto"
                    },
                    "temperature": {
                        "displayName": "Temperature",
                        "description": "Controls randomness: Lowering results in less random completions. As the temperature approaches zero, the model will become deterministic and repetitive.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 0.9
                    },
                    "maxTokens": {
                        "displayName": "Maximum Tokens",
                        "description": "The maximum number of tokens to generate. Requests can use up to 2,048 or 4,096 tokens shared between prompt and completion, don't set the value to maximum and leave some tokens for the input. The exact limit varies by model. (One token is roughly 4 characters for normal English text)",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 2048
                    },
                    "topP": {
                        "displayName": "Top P",
                        "description": "An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top 10% probability mass are considered.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 1
                    },
                    "frequencyPenalty": {
                        "displayName": "Frequency penalty",
                        "description": "Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 0
                    },
                    "presencePenalty": {
                        "displayName": "Presence penalty",
                        "description": "Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far, increasing the mode's likelihood to talk about new topics.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 0.6
                    },
                    "roles": {
                        "displayName": "Roles",
                        "description": "Array of roles to specify more accurate response",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant."
                            }
                        ]
                    }
                }
            },
            {
                "name": "text_to_speech",
                "displayName": "Text-to-Speech",
                "description": "Generate an audio recording from text",
                "props": {
                    "text": {
                        "displayName": "Text",
                        "description": "The text you want to hear.",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "model": {
                        "displayName": "Model",
                        "description": "The model which will generate the audio.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "tts-1",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "tts-1",
                                    "value": "tts-1"
                                },
                                {
                                    "label": "tts-1-hd",
                                    "value": "tts-1-hd"
                                }
                            ]
                        }
                    },
                    "speed": {
                        "displayName": "Speed",
                        "description": "The speed of the audio. Minimum is 0.25 and maximum is 4.00.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 1
                    },
                    "voice": {
                        "displayName": "Voice",
                        "description": "The voice to generate the audio in.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "alloy",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "alloy",
                                    "value": "alloy"
                                },
                                {
                                    "label": "echo",
                                    "value": "echo"
                                },
                                {
                                    "label": "fable",
                                    "value": "fable"
                                },
                                {
                                    "label": "onyx",
                                    "value": "onyx"
                                },
                                {
                                    "label": "nova",
                                    "value": "nova"
                                },
                                {
                                    "label": "shimmer",
                                    "value": "shimmer"
                                }
                            ]
                        }
                    },
                    "format": {
                        "displayName": "Output Format",
                        "description": "The format you want the audio file in.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "mp3",
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "mp3",
                                    "value": "mp3"
                                },
                                {
                                    "label": "opus",
                                    "value": "opus"
                                },
                                {
                                    "label": "aac",
                                    "value": "aac"
                                },
                                {
                                    "label": "flac",
                                    "value": "flac"
                                }
                            ]
                        }
                    },
                    "fileName": {
                        "displayName": "File Name",
                        "description": "The name of the output audio file (without extension).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": "audio"
                    }
                }
            },
            {
                "name": "transcribe",
                "displayName": "Transcribe Audio",
                "description": "Transcribe audio to text using whisper-1 model",
                "props": {
                    "audio": {
                        "displayName": "Audio",
                        "description": "Audio file to transcribe",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "language": {
                        "displayName": "Language of the Audio",
                        "description": "Language of the audio file the default is en (English).",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": "en",
                        "options": {
                            "options": [
                                {
                                    "value": "es",
                                    "label": "Spanish"
                                },
                                {
                                    "value": "it",
                                    "label": "Italian"
                                },
                                {
                                    "value": "en",
                                    "label": "English"
                                },
                                {
                                    "value": "pt",
                                    "label": "Portuguese"
                                },
                                {
                                    "value": "de",
                                    "label": "German"
                                },
                                {
                                    "value": "ja",
                                    "label": "Japanese"
                                },
                                {
                                    "value": "pl",
                                    "label": "Polish"
                                },
                                {
                                    "value": "ar",
                                    "label": "Arabic"
                                },
                                {
                                    "value": "af",
                                    "label": "Afrikaans"
                                },
                                {
                                    "value": "az",
                                    "label": "Azerbaijani"
                                },
                                {
                                    "value": "bg",
                                    "label": "Bulgarian"
                                },
                                {
                                    "value": "bs",
                                    "label": "Bosnian"
                                },
                                {
                                    "value": "ca",
                                    "label": "Catalan"
                                },
                                {
                                    "value": "cs",
                                    "label": "Czech"
                                },
                                {
                                    "value": "da",
                                    "label": "Danish"
                                },
                                {
                                    "value": "el",
                                    "label": "Greek"
                                },
                                {
                                    "value": "et",
                                    "label": "Estonian"
                                },
                                {
                                    "value": "fa",
                                    "label": "Persian"
                                },
                                {
                                    "value": "fi",
                                    "label": "Finnish"
                                },
                                {
                                    "value": "tl",
                                    "label": "Tagalog"
                                },
                                {
                                    "value": "fr",
                                    "label": "French"
                                },
                                {
                                    "value": "gl",
                                    "label": "Galician"
                                },
                                {
                                    "value": "he",
                                    "label": "Hebrew"
                                },
                                {
                                    "value": "hi",
                                    "label": "Hindi"
                                },
                                {
                                    "value": "hr",
                                    "label": "Croatian"
                                },
                                {
                                    "value": "hu",
                                    "label": "Hungarian"
                                },
                                {
                                    "value": "hy",
                                    "label": "Armenian"
                                },
                                {
                                    "value": "id",
                                    "label": "Indonesian"
                                },
                                {
                                    "value": "is",
                                    "label": "Icelandic"
                                },
                                {
                                    "value": "kk",
                                    "label": "Kazakh"
                                },
                                {
                                    "value": "kn",
                                    "label": "Kannada"
                                },
                                {
                                    "value": "ko",
                                    "label": "Korean"
                                },
                                {
                                    "value": "lt",
                                    "label": "Lithuanian"
                                },
                                {
                                    "value": "lv",
                                    "label": "Latvian"
                                },
                                {
                                    "value": "ma",
                                    "label": "Maori"
                                },
                                {
                                    "value": "mk",
                                    "label": "Macedonian"
                                },
                                {
                                    "value": "mr",
                                    "label": "Marathi"
                                },
                                {
                                    "value": "ms",
                                    "label": "Malay"
                                },
                                {
                                    "value": "ne",
                                    "label": "Nepali"
                                },
                                {
                                    "value": "nl",
                                    "label": "Dutch"
                                },
                                {
                                    "value": "no",
                                    "label": "Norwegian"
                                },
                                {
                                    "value": "ro",
                                    "label": "Romanian"
                                },
                                {
                                    "value": "ru",
                                    "label": "Russian"
                                },
                                {
                                    "value": "sk",
                                    "label": "Slovak"
                                },
                                {
                                    "value": "sl",
                                    "label": "Slovenian"
                                },
                                {
                                    "value": "sr",
                                    "label": "Serbian"
                                },
                                {
                                    "value": "sv",
                                    "label": "Swedish"
                                },
                                {
                                    "value": "sw",
                                    "label": "Swahili"
                                },
                                {
                                    "value": "ta",
                                    "label": "Tamil"
                                },
                                {
                                    "value": "th",
                                    "label": "Thai"
                                },
                                {
                                    "value": "tr",
                                    "label": "Turkish"
                                },
                                {
                                    "value": "uk",
                                    "label": "Ukrainian"
                                },
                                {
                                    "value": "ur",
                                    "label": "Urdu"
                                },
                                {
                                    "value": "vi",
                                    "label": "Vietnamese"
                                },
                                {
                                    "value": "zh",
                                    "label": "Chinese (Simplified)"
                                },
                                {
                                    "value": "cy",
                                    "label": "Welsh"
                                },
                                {
                                    "value": "be",
                                    "label": "Belarusian"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "translate",
                "displayName": "Translate Audio",
                "description": "Translate audio to text using whisper-1 model",
                "props": {
                    "audio": {
                        "displayName": "Audio",
                        "description": "Audio file to translate",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "extract-structured-data",
                "displayName": "Extract Structured Data from Text",
                "description": "Returns structured data from provided unstructured text.",
                "props": {
                    "model": {
                        "displayName": "Model",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": "gpt-3.5-turbo"
                    },
                    "text": {
                        "displayName": "Unstructured Text",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "params": {
                        "displayName": "Data Definition",
                        "description": "",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-openmic-ai",
        "name": "OpenMic AI",
        "description": "An AI-powered platform that automates phone calls using advanced language models.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/openmic-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-open-phone",
        "name": "OpenPhone",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/open-phone.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-open-router",
        "name": "OpenRouter",
        "description": "Use any AI model to generate code, text, or images via OpenRouter.ai.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/open-router.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-opnform",
        "name": "Opnform",
        "description": "Create beautiful online forms and surveys with unlimited fields and submissions",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/opnform.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-opportify",
        "name": "Opportify",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/opportify.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-oracle-database",
        "name": "Oracle Database",
        "description": "Enterprise-grade relational database",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/oracle-database.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-orimon",
        "name": "Orimon",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/orimon.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pandadoc",
        "name": "PandaDoc",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/pandadoc.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-paperform",
        "name": "Paperform",
        "description": "",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/paperform.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-parser-expert",
        "name": "Parser Expert",
        "description": "Parse documents and extract data from PDFs, DOCX files, images, and webpages using Parser Expert's powerful API.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/parser-expert.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-parseur",
        "name": "Parseur",
        "description": "Parseur is a document/email parsing tool that extracts structured data from emails, attachments, PDFs, invoices, forms, etc. It supports dynamic templates and table fields, and delivers parsed output to integrations (e.g. via webhook or API). This integration enables reactive workflows based on new processed documents, failed processing, mailbox changes, and more.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/parseur.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pastebin",
        "name": "Pastebin",
        "description": "Simple and secure text sharing",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/pastebin.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pastefy",
        "name": "Pastefy",
        "description": "Sharing code snippets platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/pastefy.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pdf",
        "name": "PDF",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/pdf.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pdf-co",
        "name": "PDF.co",
        "description": "Automate PDF conversion, editing, extraction",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/pdf-co.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pdfmonkey",
        "name": "PDFMonkey",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/pdfmonkey.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-peekshot",
        "name": "PeekShot",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/peekshot.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-perplexity-ai",
        "name": "Perplexity AI",
        "description": "AI powered search engine",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/perplexity-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-personal-ai",
        "name": "Personal AI",
        "description": "Manage memory storage, messaging, and documents through AI integration.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/personal-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-phantombuster",
        "name": "PhantomBuster",
        "description": "Automate your web scraping and web automation tasks",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/phantombuster.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-photoroom",
        "name": "Photoroom",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/photoroom.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pinecone",
        "name": "Pinecone",
        "description": "Manage vector databases, store embeddings, and perform similarity searches",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/pinecone.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pinterest",
        "name": "Pinterest",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/pinterest.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pipedrive",
        "name": "Pipedrive",
        "description": "Sales CRM and pipeline management software",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/pipedrive.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-placid",
        "name": "Placid",
        "description": "Creative automation engine that generates dynamic images, PDFs, and videos from templates and data.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/placid.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-podio",
        "name": "Podio",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/podio.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pollybot-ai",
        "name": "PollyBot AI",
        "description": "Automate lead management with PollyBot AI chatbot integration.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/pollybot-ai.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-poper",
        "name": "Poper",
        "description": "AI Driven Pop-up Builder that can convert visitors into customers,increase subscriber count, and skyrocket sales.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/poper.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-postgres",
        "name": "Postgres",
        "description": "The world's most advanced open-source relational database",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/postgres.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-posthog",
        "name": "PostHog",
        "description": "Open-source product analytics",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/posthog.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-predict-leads",
        "name": "PredictLeads",
        "description": "Company Intelligence Data Source",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/predict-leads.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-presentation",
        "name": "Presenton",
        "description": "Generate AI-powered presentations using Presenton (https://presenton.ai). Supports templates, themes, images, synchronous and asynchronous generation, status polling, and export to PPTX/PDF.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/presenton.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-productboard",
        "name": "Productboard",
        "description": "Productboard is a product management tool that helps you manage your product roadmap and features.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/productboard.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-prompthub",
        "name": "PromptHub",
        "description": "Integrate with PromptHub projects, retrieve heads, and run prompts.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/prompthub.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-promptmate",
        "name": "PromptMate",
        "description": "AI-powered automation platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/promptmate.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pushbullet",
        "name": "Pushbullet",
        "description": "Cross-device notification service",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/pushbullet.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pushover",
        "name": "Pushover",
        "description": "Simple push notification service",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/pushover.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-pylon",
        "name": "Pylon",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/pylon.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-qdrant",
        "name": "Qdrant",
        "description": "Make any action on your qdrant vector database",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/qdrant.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-qrcode",
        "name": "QR Code",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/qrcode.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-queue",
        "name": "Queue",
        "description": "A piece that allows you to push items into a queue, providing a way to throttle requests or process data in a First-In-First-Out (FIFO) manner.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/queue.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-quickbase",
        "name": "Quickbase",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/quickbase.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-quickbooks",
        "name": "Quickbooks Online",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/quickbooks.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "new_invoice",
                "displayName": "New Invoice",
                "description": "Triggers when an invoice is created .",
                "props": {}
            },
            {
                "name": "new_expense",
                "displayName": "New Expense (Purchase)",
                "description": "Triggers when an Expense (Purchase) is created.",
                "props": {}
            },
            {
                "name": "new_customer",
                "displayName": "New Customer",
                "description": "Triggers when a new customer is created.",
                "props": {}
            },
            {
                "name": "new_deposit",
                "displayName": "New Deposit",
                "description": "Triggers when a Deposit is created.",
                "props": {}
            },
            {
                "name": "new_transfer",
                "displayName": "New Transfer",
                "description": "Triggers when a Transfer is created.",
                "props": {}
            }
        ],
        "actions": [
            {
                "name": "find_invoice",
                "displayName": "Find Invoice",
                "description": "Search for an invoice by its number in QuickBooks.",
                "props": {
                    "invoice_number": {
                        "displayName": "Invoice Number",
                        "description": "The document number (DocNumber) of the invoice to search for.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_customer",
                "displayName": "Find Customer",
                "description": "Search for a customer by display name in QuickBooks.",
                "props": {
                    "search_term": {
                        "displayName": "Customer Name",
                        "description": "The display name of the customer to search for.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_payment",
                "displayName": "Find Payment",
                "description": "Finds an existing payment in QuickBooks.",
                "props": {
                    "customerId": {
                        "displayName": "Customer ID",
                        "description": "The ID of the customer to find payments for.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_invoice",
                "displayName": "Create Invoice",
                "description": "Creates an invoice in QuickBooks.",
                "props": {
                    "customerRef": {
                        "displayName": "Customer",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "lineItems": {
                        "displayName": "Line Items",
                        "description": "Line items for the invoice",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    },
                    "emailStatus": {
                        "displayName": "Email Status",
                        "description": "Specify whether the invoice should be emailed after creation.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": "NotSet",
                        "options": {
                            "options": [
                                {
                                    "label": "Not Set (Default - No Email)",
                                    "value": "NotSet"
                                },
                                {
                                    "label": "Needs To Be Sent",
                                    "value": "NeedToSend"
                                }
                            ]
                        }
                    },
                    "billEmail": {
                        "displayName": "Billing Email Address",
                        "description": "Email address to send the invoice to. Required if Email Status is \"Needs To Be Sent\". Overrides customer default.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "dueDate": {
                        "displayName": "Due Date",
                        "description": "The date when the payment for the invoice is due. If not provided, default term from customer or company is used.",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "docNumber": {
                        "displayName": "Invoice Number",
                        "description": "Optional reference number for the invoice. If not provided, QuickBooks assigns the next sequential number.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "txnDate": {
                        "displayName": "Transaction Date",
                        "description": "The date entered on the transaction. Defaults to the current date if not specified.",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "privateNote": {
                        "displayName": "Private Note (Memo)",
                        "description": "Note to self. Does not appear on the invoice sent to the customer.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "customerMemo": {
                        "displayName": "Customer Memo (Statement Memo)",
                        "description": "Memo to be displayed on the invoice sent to the customer (appears on statement).",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_expense",
                "displayName": "Create Expense",
                "description": "Creates an expense transaction (purchase) in QuickBooks.",
                "props": {
                    "accountRef": {
                        "displayName": "Bank/Credit Card Account",
                        "description": "The account from which the expense was paid.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "paymentType": {
                        "displayName": "Payment Type",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "Cash",
                        "options": {
                            "options": [
                                {
                                    "label": "Cash",
                                    "value": "Cash"
                                },
                                {
                                    "label": "Check",
                                    "value": "Check"
                                },
                                {
                                    "label": "Credit Card",
                                    "value": "CreditCard"
                                }
                            ]
                        }
                    },
                    "entityRef": {
                        "displayName": "Payee (Vendor)",
                        "description": "Optional - The vendor the expense was paid to.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "txnDate": {
                        "displayName": "Payment Date",
                        "description": "The date the expense occurred.",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "lineItems": {
                        "displayName": "Line Items",
                        "description": "Details of the expense (e.g., categories or items purchased). At least one line is required.",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    },
                    "privateNote": {
                        "displayName": "Memo (Private Note)",
                        "description": "Internal note about the expense.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-quickzu",
        "name": "Quickzu",
        "description": "Streamline ordering from whatsapp",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/quickzu.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-qwilr",
        "name": "Qwilr",
        "description": "Create beautiful, interactive sales documents and proposals with Qwilr. Automate page creation, track views, and handle acceptance events.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/qwilr.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-rabbitmq",
        "name": "RabbitMQ",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/rabbitmq.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-raia-ai",
        "name": "raia",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/raia-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-rapidtext-ai",
        "name": "RapidText AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/rapidtext-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-razorpay",
        "name": "Razorpay",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/razorpay.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-retune",
        "name": "re:tune",
        "description": "Everything you need to transform your business with AI, from custom chatbots to autonomous agents.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/retune.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-reachinbox",
        "name": "Reachinbox",
        "description": "",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/reachinbox.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-recall-ai",
        "name": "Recall.ai",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/recall-ai.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-reddit",
        "name": "Reddit",
        "description": "Interact with Reddit - fetch and submit posts.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/reddit.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-reoon-verifier",
        "name": "Reoon Email Verifier",
        "description": "Email validation service that cleans invalid, temporary & unsafe email addresses.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/reoon-verifier.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-resend",
        "name": "Resend",
        "description": "Email for developers",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/resend.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-respaid",
        "name": "Respaid",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/respaid.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-respond-io",
        "name": "Respond.io",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/respond-io.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-retable",
        "name": "Retable",
        "description": "Turn your spreadsheets into smart database apps",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/retable.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-retell-ai",
        "name": "Retell AI",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/retell-ai.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-returning-ai",
        "name": "Returning AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/returning-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-robolly",
        "name": "Robolly",
        "description": "Robolly is the all\u2011in\u2011one service for personalized image, video & PDF generation with API",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/robolly.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-rss",
        "name": "RSS Feed",
        "description": "Stay updated with RSS feeds",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/rss.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-runware",
        "name": "Runware",
        "description": "Runware.AI is a high-performance, cost-effective AI media generation API specializing in images and videos. Through this integration, workflows can automatically generate visuals via text or image prompts and interact with Runware\u2019s full-featured API.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/runware.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-runway",
        "name": "Runway",
        "description": "AI-powered content generation platform for creating high-quality images and videos using text prompts",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/runway.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-saastic",
        "name": "Saastic",
        "description": "Revenue and churn analytics for Stripe",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/saastic.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-saleor",
        "name": "Saleor",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/saleor.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-salesforce",
        "name": "Salesforce",
        "description": "CRM software solutions and enterprise cloud computing",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/salesforce.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "new_case_attachment",
                "displayName": "New Case Attachment",
                "description": "Fires when a new Attachment or File is added to any Case record.",
                "props": {}
            },
            {
                "name": "new_contact",
                "displayName": "New Contact",
                "description": "Fires when a new Contact record is created in Salesforce.",
                "props": {}
            },
            {
                "name": "new_field_history_event",
                "displayName": "New Field History Event",
                "description": "Fires when a tracked field is updated on a specified object.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_lead",
                "displayName": "New Lead",
                "description": "Fires when a new Lead record is created in Salesforce.",
                "props": {}
            },
            {
                "name": "new_or_updated_record",
                "displayName": "New or Updated Record",
                "description": "Triggers when there is new or updated record",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "conditions": {
                        "displayName": "Conditions (Advanced)",
                        "description": "Enter a SOQL query where clause i. e. IsDeleted = TRUE",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_outbound_message",
                "displayName": "New Outbound Message",
                "description": "Fires when a new outbound message is received from Salesforce.",
                "props": {}
            },
            {
                "name": "new_record",
                "displayName": "New Record",
                "description": "Triggers when there is new record",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "conditions": {
                        "displayName": "Conditions (Advanced)",
                        "description": "Enter a SOQL query where clause i. e. IsDeleted = TRUE",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_updated_file",
                "displayName": "New or Updated File",
                "description": "Fires when a file (ContentDocument) is created or updated. Does not fire for classic Attachments or Notes.",
                "props": {}
            }
        ],
        "actions": [
            {
                "name": "add_contact_to_campaign",
                "displayName": "Add Contact to Campaign",
                "description": "Add a contact to a campaign.",
                "props": {
                    "campaign_id": {
                        "displayName": "Campaign",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "contact_id": {
                        "displayName": "Contact",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "The campaign member status (e.g., 'Sent', 'Responded').",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add_file_to_record",
                "displayName": "Add File to Record",
                "description": "Uploads a file and attaches it to an existing record.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "record_id": {
                        "displayName": "Record",
                        "description": "The record to select. The list shows the 20 most recently created records.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "file": {
                        "displayName": "File",
                        "description": "The file to upload.",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "file_name": {
                        "displayName": "File Name",
                        "description": "The name of the file, including its extension (e.g., \"report.pdf\").",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add_lead_to_campaign",
                "displayName": "Add Lead to Campaign",
                "description": "Adds an existing lead to an existing campaign.",
                "props": {
                    "campaign_id": {
                        "displayName": "Campaign",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "lead_id": {
                        "displayName": "Lead",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "The campaign member status (e.g., 'Sent', 'Responded').",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_attachment",
                "displayName": "Create Attachment (Legacy)",
                "description": "Creates a legacy Attachment record. Salesforce recommends using \"Add File to Record\" for modern apps.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "parent_id": {
                        "displayName": "Record",
                        "description": "The record to select. The list shows the 20 most recently created records.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "file": {
                        "displayName": "File",
                        "description": "The file to attach.",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "file_name": {
                        "displayName": "File Name",
                        "description": "The name of the file, including its extension (e.g., \"attachment.pdf\").",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_case",
                "displayName": "Create Case",
                "description": "Creates a Case, which represents a customer issue or problem.",
                "props": {
                    "Subject": {
                        "displayName": "Subject",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "Description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Status": {
                        "displayName": "Status",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "Priority": {
                        "displayName": "Priority",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "Origin": {
                        "displayName": "Origin",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "AccountId": {
                        "displayName": "Account",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "ContactId": {
                        "displayName": "Contact",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "other_fields": {
                        "displayName": "Other Fields",
                        "description": "Enter additional fields as a JSON object.",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_contact",
                "displayName": "Create Contact",
                "description": "Creates a new contact record.",
                "props": {
                    "LastName": {
                        "displayName": "Last Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "FirstName": {
                        "displayName": "First Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "AccountId": {
                        "displayName": "Account",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "Email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Phone": {
                        "displayName": "Phone",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "other_fields": {
                        "displayName": "Other Fields",
                        "description": "Enter additional fields as a JSON object.",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_lead",
                "displayName": "Create Lead",
                "description": "Creates a new lead.",
                "props": {
                    "LastName": {
                        "displayName": "Last Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "Company": {
                        "displayName": "Company",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "FirstName": {
                        "displayName": "First Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Phone": {
                        "displayName": "Phone",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "LeadSource": {
                        "displayName": "Lead Source",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "other_fields": {
                        "displayName": "Other Fields",
                        "description": "Enter additional fields as a JSON object (e.g., {\"Title\": \"Manager\", \"Website\": \"http://example.com\"}).",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_note",
                "displayName": "Create Note",
                "description": "Creates a note and attaches it to a record.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "parent_id": {
                        "displayName": "Record",
                        "description": "The record to select. The list shows the 20 most recently created records.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "Title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "Body": {
                        "displayName": "Body",
                        "description": "The content of the note.",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_opportunity",
                "displayName": "Create Opportunity",
                "description": "Creates a new opportunity.",
                "props": {
                    "Name": {
                        "displayName": "Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "CloseDate": {
                        "displayName": "Close Date",
                        "description": "The expected close date in YYYY-MM-DD format.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "StageName": {
                        "displayName": "Stage",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "AccountId": {
                        "displayName": "Account",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "Amount": {
                        "displayName": "Amount",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "other_fields": {
                        "displayName": "Other Fields",
                        "description": "Enter additional fields as a JSON object.",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_record",
                "displayName": "Create Record",
                "description": "Create a record of a given object.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "data": {
                        "displayName": "Record Data",
                        "description": "Enter the fields for the new record as a JSON object. For example: {\"Name\": \"My New Account\", \"Industry\": \"Technology\"}",
                        "type": "JSON",
                        "required": true,
                        "defaultValue": {}
                    }
                }
            },
            {
                "name": "create_task",
                "displayName": "Create Task",
                "description": "Creates a new task.",
                "props": {
                    "Subject": {
                        "displayName": "Subject",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "OwnerId": {
                        "displayName": "Owner",
                        "description": "The owner of the task.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "Status": {
                        "displayName": "Status",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "Priority": {
                        "displayName": "Priority",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "Description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "WhoId": {
                        "displayName": "Related To (Contact/Lead ID)",
                        "description": "The ID of a Contact or Lead to relate the task to.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "WhatId": {
                        "displayName": "Related To (Other Object ID)",
                        "description": "The ID of an Account, Opportunity, or other object to relate the task to.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete_opportunity",
                "displayName": "Delete Opportunity",
                "description": "Deletes an opportunity.",
                "props": {
                    "opportunity_id": {
                        "displayName": "Opportunity",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete_record",
                "displayName": "Delete Record",
                "description": "Deletes an existing record in an object.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "record_id": {
                        "displayName": "Record",
                        "description": "The record to select. The list shows the 20 most recently created records.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_child_records",
                "displayName": "Find Child Records",
                "description": "Finds child records related to a parent record.",
                "props": {
                    "parent_object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "parent_id": {
                        "displayName": "Parent Record",
                        "description": "The parent record to find child records for. The list shows the 20 most recently created records.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "child_relationship": {
                        "displayName": "Child Relationship",
                        "description": "The child relationship to retrieve records from.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_record",
                "displayName": "Find Record",
                "description": "Finds a record by a field value.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "field": {
                        "displayName": "Field",
                        "description": "Select the Field",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "search_value": {
                        "displayName": "Search Value",
                        "description": "The value to search for in the selected field.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_records_by_query",
                "displayName": "Find Records by Query (Advanced)",
                "description": "Finds records in an object using a SOQL WHERE clause.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "where_clause": {
                        "displayName": "WHERE Clause",
                        "description": "Enter the WHERE clause for your SOQL query. For example: `Name = 'Acme' AND Industry = 'Technology'`. Do not include the 'WHERE' keyword.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_record_attachments",
                "displayName": "Get Record Attachments",
                "description": "Get all attachments (both classic and modern Files) for a record.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "record_id": {
                        "displayName": "Record",
                        "description": "The record to select. The list shows the 20 most recently created records.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "run_query",
                "displayName": "Run Query (Advanced)",
                "description": "Run a salesforce query",
                "props": {
                    "query": {
                        "displayName": "Query",
                        "description": "Enter the query",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "run_report",
                "displayName": "Run Report",
                "description": "Execute a Salesforce analytics report.",
                "props": {
                    "report_id": {
                        "displayName": "Report",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "filters": {
                        "displayName": "Filters",
                        "description": "Apply dynamic filters to the report run.",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": [
                            {
                                "column": "ACCOUNT.NAME",
                                "operator": "equals",
                                "value": "Acme"
                            }
                        ]
                    }
                }
            },
            {
                "name": "send_email",
                "displayName": "Send Email",
                "description": "Sends an email to a Contact or Lead by creating an EmailMessage record.",
                "props": {
                    "recipientId": {
                        "displayName": "Recipient",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "subject": {
                        "displayName": "Subject",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "The content of the email. Can be plain text or HTML.",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "relatedToId": {
                        "displayName": "Related To ID (Optional)",
                        "description": "The ID of a record to relate the email to (e.g., an Account, Opportunity, or Case ID).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_contact",
                "displayName": "Update Contact",
                "description": "Update an existing contact.",
                "props": {
                    "contact_id": {
                        "displayName": "Contact",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "FirstName": {
                        "displayName": "First Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "LastName": {
                        "displayName": "Last Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "AccountId": {
                        "displayName": "Account",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "Email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Phone": {
                        "displayName": "Phone",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "other_fields": {
                        "displayName": "Other Fields (Advanced)",
                        "description": "Enter any additional fields to update as a JSON object.",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_lead",
                "displayName": "Update Lead",
                "description": "Update an existing lead.",
                "props": {
                    "lead_id": {
                        "displayName": "Lead",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "FirstName": {
                        "displayName": "First Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "LastName": {
                        "displayName": "Last Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Company": {
                        "displayName": "Company",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "Phone": {
                        "displayName": "Phone",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "LeadSource": {
                        "displayName": "Lead Source",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "other_fields": {
                        "displayName": "Other Fields (Advanced)",
                        "description": "Enter any additional fields to update as a JSON object.",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_record",
                "displayName": "Update Record",
                "description": "Updates an existing record.",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "record_id": {
                        "displayName": "Record",
                        "description": "The record to select. The list shows the 20 most recently created records.",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "data": {
                        "displayName": "Data to Update",
                        "description": "Enter the fields to update as a JSON object. For example: {\"BillingCity\": \"San Francisco\"}",
                        "type": "JSON",
                        "required": true,
                        "defaultValue": {}
                    }
                }
            },
            {
                "name": "upsert_by_external_id",
                "displayName": "Batch Upsert (Advanced)",
                "description": "Batch upsert a record by external id",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "external_field": {
                        "displayName": "External Field",
                        "description": "Select the External Field",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "records": {
                        "displayName": "Records",
                        "description": "Select the Records",
                        "type": "JSON",
                        "required": true,
                        "defaultValue": {
                            "records": []
                        }
                    }
                }
            },
            {
                "name": "upsert_by_external_id_bulk",
                "displayName": "Bulk Upsert (Advanced)",
                "description": "Bulk upsert a record by external id",
                "props": {
                    "object": {
                        "displayName": "Object",
                        "description": "Select the Object",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "external_field": {
                        "displayName": "External Field",
                        "description": "Select the External Field",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "records": {
                        "displayName": "Records",
                        "description": "Select the Records (CSV format)",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-salsa",
        "name": "Salsa",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/salsa.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-scenario",
        "name": "Scenario",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/scenario.png",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-schedule",
        "name": "Schedule",
        "description": "Trigger flow with fixed schedule",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/schedule.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-scrapegrapghai",
        "name": "ScrapeGraphAI",
        "description": "AI-powered web scraping and content extraction.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/scrapegraphai.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-scrapeless",
        "name": "Scrapeless",
        "description": "Scrapeless is an all-in-one and highly scalable web scraping toolkit for enterprises and developers.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/scrapeless.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-segment",
        "name": "Segment",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/segment.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sender",
        "name": "Sender",
        "description": "",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/sender.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sendfox",
        "name": "SendFox",
        "description": "Email marketing made simple",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/sendfox.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sendgrid",
        "name": "SendGrid",
        "description": "Email delivery service for sending transactional and marketing emails",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/sendgrid.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sendpulse",
        "name": "SendPulse",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/sendpulse.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sendy",
        "name": "Sendy",
        "description": "Self-hosted email marketing software",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/sendy.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-serp-api",
        "name": "SerpApi",
        "description": "Search Google, YouTube, News, and Trends with powerful filtering and analysis capabilities",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/serp-api.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-serpstat",
        "name": "Serpstat",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/serpstat.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-service-now",
        "name": "ServiceNow",
        "description": "Enterprise IT service management platform for incident, change, and service request management",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/service-now.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sessions-us",
        "name": "Sessions.us",
        "description": "Video conferencing platform for businesses and professionals",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/sessions-us.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-seven",
        "name": "seven",
        "description": "Business Messaging Gateway",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/seven.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-shippo",
        "name": "Shippo",
        "description": "Multi-carrier shipping platform for real-time rates, labels, and tracking",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/shippo.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-shopify",
        "name": "Shopify",
        "description": "Ecommerce platform for online stores",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/shopify.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [
            {
                "name": "new_abandoned_checkout",
                "displayName": "New Abandoned Checkout",
                "description": "Triggers when a checkout is abandoned.",
                "props": {}
            },
            {
                "name": "new_cancelled_order",
                "displayName": "New Cancelled Order",
                "description": "Triggered when order is cancelled",
                "props": {}
            },
            {
                "name": "new_customer",
                "displayName": "New Customer",
                "description": "Triggered when a new customer is created",
                "props": {}
            },
            {
                "name": "new_order",
                "displayName": "New Order",
                "description": "Triggered when a new order is created",
                "props": {}
            },
            {
                "name": "updated_product",
                "displayName": "Updated Product",
                "description": "Triggered when a product is updated.",
                "props": {}
            },
            {
                "name": "new_paid_order",
                "displayName": "New Paid Order",
                "description": "Triggered when a paid order is created",
                "props": {}
            }
        ],
        "actions": [
            {
                "name": "adjust_inventory_level",
                "displayName": "Adjust Inventory Level",
                "description": "Adjust inventory level of an item at a location.",
                "props": {
                    "id": {
                        "displayName": "Inventory Item",
                        "description": "The ID of the inventory item.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "locationId": {
                        "displayName": "Location",
                        "description": "The ID of the location.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "adjustment": {
                        "displayName": "Adjustment",
                        "description": "Positive values increase inventory, negative values decrease it.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "cancel_order",
                "displayName": "Cancel Order",
                "description": "Cancel an order.",
                "props": {
                    "orderId": {
                        "displayName": "Order",
                        "description": "The ID of the order.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "close_order",
                "displayName": "Close Order",
                "description": "Close an order.",
                "props": {
                    "orderId": {
                        "displayName": "Order",
                        "description": "The ID of the order.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_collect",
                "displayName": "Create Collect",
                "description": "Add a product to a collection.",
                "props": {
                    "id": {
                        "displayName": "Product",
                        "description": "The ID of the product.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "collectionId": {
                        "displayName": "Collection",
                        "description": "The ID of the collection.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_customer",
                "displayName": "Create Customer",
                "description": "Create a new customer.",
                "props": {
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "verifiedEmail": {
                        "displayName": "Verified Email",
                        "description": "Whether the customer has verified their email.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": true
                    },
                    "sendEmailInvite": {
                        "displayName": "Send Email Invite",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "firstName": {
                        "displayName": "First Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "lastName": {
                        "displayName": "Last Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "phoneNumber": {
                        "displayName": "Phone Number",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "A string of comma-separated tags for filtering and search",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "acceptsMarketing": {
                        "displayName": "Accepts Marketing ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_draft_order",
                "displayName": "Create Draft Order",
                "description": "Create a new draft order.",
                "props": {
                    "productId": {
                        "displayName": "Product",
                        "description": "The ID of the product to create the order with.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "variantId": {
                        "displayName": "Product Variant",
                        "description": "The ID of the variant to create the order with.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "quantity": {
                        "displayName": "Quantity",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 1
                    },
                    "price": {
                        "displayName": "Price",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "customerId": {
                        "displayName": "Customer",
                        "description": "The ID of the customer to use.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_fulfillment_event",
                "displayName": "Create Fulfillment Event",
                "description": "Create a new fulfillment event.",
                "props": {
                    "orderId": {
                        "displayName": "Order",
                        "description": "The ID of the order.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "fulfillmentId": {
                        "displayName": "Fulfillment",
                        "description": "The ID of the fulfillment.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "message": {
                        "displayName": "Message",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_order",
                "displayName": "Create Order",
                "description": "Create a new order.",
                "props": {
                    "productId": {
                        "displayName": "Product",
                        "description": "The ID of the product to create the order with.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "variantId": {
                        "displayName": "Product Variant",
                        "description": "The ID of the variant to create the order with.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "quantity": {
                        "displayName": "Quantity",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 1
                    },
                    "price": {
                        "displayName": "Price",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "customerId": {
                        "displayName": "Customer",
                        "description": "The ID of the customer to use.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "sendReceipt": {
                        "displayName": "Send Receipt",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "sendFulfillmentReceipt": {
                        "displayName": "Send Fulfillment Receipt",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "A string of comma-separated tags for filtering and search",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_product",
                "displayName": "Create Product",
                "description": "Create a new product.",
                "props": {
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "bodyHtml": {
                        "displayName": "Description",
                        "description": "Product description (supports HTML)",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "productType": {
                        "displayName": "Product Type",
                        "description": "A categorization for the product used for filtering and searching products",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "productImage": {
                        "displayName": "Product Image",
                        "description": "The public URL or the base64 image to use",
                        "type": "FILE",
                        "required": false,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "draft",
                        "options": {
                            "options": [
                                {
                                    "label": "Active",
                                    "value": "active"
                                },
                                {
                                    "label": "Draft",
                                    "value": "draft"
                                },
                                {
                                    "label": "Archived",
                                    "value": "archived"
                                }
                            ]
                        }
                    },
                    "vendor": {
                        "displayName": "Vendor",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "A string of comma-separated tags for filtering and search",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_transaction",
                "displayName": "Create Transaction",
                "description": "Create a new transaction.",
                "props": {
                    "orderId": {
                        "displayName": "Order",
                        "description": "The ID of the order to create a transaction for.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "kind": {
                        "displayName": "Type",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "currency": {
                        "displayName": "Currency",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "amount": {
                        "displayName": "Amount",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "authorization": {
                        "displayName": "Authorization Key",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "parentId": {
                        "displayName": "Parent ID",
                        "description": "The ID of an associated transaction.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "source": {
                        "displayName": "Source",
                        "description": "An optional origin of the transaction. Set to external to import a cash transaction for the associated order.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "test": {
                        "displayName": "Test",
                        "description": "Whether the transaction is a test transaction.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "get_asset",
                "displayName": "Get Asset",
                "description": "Get a theme's asset.",
                "props": {
                    "key": {
                        "displayName": "Asset Key",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "themeId": {
                        "displayName": "Theme",
                        "description": "The ID of the theme.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_customer",
                "displayName": "Get Customer",
                "description": "Get an existing customer's information.",
                "props": {
                    "customerId": {
                        "displayName": "Customer ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_customers",
                "displayName": "Get Customers",
                "description": "Get an existing customers.",
                "props": {}
            },
            {
                "name": "get_customer_orders",
                "displayName": "Get Customer Orders",
                "description": "Get an existing customer's orders.",
                "props": {
                    "customerId": {
                        "displayName": "Customer ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_fulfillment",
                "displayName": "Get Fulfillment",
                "description": "Get a fulfillment.",
                "props": {
                    "orderId": {
                        "displayName": "Order",
                        "description": "The ID of the order.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "fulfillmentId": {
                        "displayName": "Fulfillment",
                        "description": "The ID of the fulfillment.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_fulfillments",
                "displayName": "Get Fulfillments",
                "description": "Get an order's fulfillments.",
                "props": {
                    "orderId": {
                        "displayName": "Order",
                        "description": "The ID of the order.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_locations",
                "displayName": "Get Locations",
                "description": "Get locations.",
                "props": {}
            },
            {
                "name": "get_product",
                "displayName": "Get Product",
                "description": "Get existing product.",
                "props": {
                    "id": {
                        "displayName": "Product",
                        "description": "The ID of the product.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_product_variant",
                "displayName": "Get Product Variant",
                "description": "Get a product variant.",
                "props": {
                    "id": {
                        "displayName": "Product Variant",
                        "description": "The ID of the product variant.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_products",
                "displayName": "Get Products",
                "description": "Get existing products by title.",
                "props": {
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_transaction",
                "displayName": "Get Transaction",
                "description": "Get an existing transaction's information.",
                "props": {
                    "orderId": {
                        "displayName": "Order",
                        "description": "The ID of the order.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "transactionId": {
                        "displayName": "Transaction",
                        "description": "The ID of the transaction",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_transactions",
                "displayName": "Get Order Transactions",
                "description": "Get an order's transactions.",
                "props": {
                    "orderId": {
                        "displayName": "Order",
                        "description": "The ID of the order.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_customer",
                "displayName": "Update Customer",
                "description": "Update an existing customer.",
                "props": {
                    "customerId": {
                        "displayName": "Customer ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "verifiedEmail": {
                        "displayName": "Verified Email",
                        "description": "Whether the customer has verified their email.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": true
                    },
                    "sendEmailInvite": {
                        "displayName": "Send Email Invite",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "firstName": {
                        "displayName": "First Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "lastName": {
                        "displayName": "Last Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "phoneNumber": {
                        "displayName": "Phone Number",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "A string of comma-separated tags for filtering and search",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "acceptsMarketing": {
                        "displayName": "Accepts Marketing ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_order",
                "displayName": "Update Order",
                "description": "Update an existing order.",
                "props": {
                    "id": {
                        "displayName": "Order",
                        "description": "The ID of the order.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "phoneNumber": {
                        "displayName": "Phone Number",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "A string of comma-separated tags for filtering and search",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "note": {
                        "displayName": "Note",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_product",
                "displayName": "Update Product",
                "description": "Update an existing product.",
                "props": {
                    "id": {
                        "displayName": "Product",
                        "description": "The ID of the product.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "bodyHtml": {
                        "displayName": "Description",
                        "description": "Product description (supports HTML)",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "productType": {
                        "displayName": "Product Type",
                        "description": "A categorization for the product used for filtering and searching products",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "productImage": {
                        "displayName": "Product Image",
                        "description": "The public URL or the base64 image to use",
                        "type": "FILE",
                        "required": false,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "draft",
                        "options": {
                            "options": [
                                {
                                    "label": "Active",
                                    "value": "active"
                                },
                                {
                                    "label": "Draft",
                                    "value": "draft"
                                },
                                {
                                    "label": "Archived",
                                    "value": "archived"
                                }
                            ]
                        }
                    },
                    "vendor": {
                        "displayName": "Vendor",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "A string of comma-separated tags for filtering and search",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "upload_product_image",
                "displayName": "Upload Product Image",
                "description": "Upload a new product image.",
                "props": {
                    "id": {
                        "displayName": "Product",
                        "description": "The ID of the product.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "image": {
                        "displayName": "Image",
                        "description": "The public URL or the base64 image to use",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "position": {
                        "displayName": "Position",
                        "description": "1 makes it the main image.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-short-io",
        "name": "Short.io",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/short-io.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-signrequest",
        "name": "Signrequest",
        "description": "",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/signrequest.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-simplepdf",
        "name": "SimplePDF",
        "description": "PDF editing and generation tool",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/simplepdf.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-simpliroute",
        "name": "SimpliRoute",
        "description": "Connect with SimpliRoute, the last-mile delivery optimization platform. Manage clients, vehicles, visits, routes, and optimize your delivery operations.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/simpliroute.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-simplybookme",
        "name": "SimplyBook.me",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/simplybookme.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sitespeakai",
        "name": "SiteSpeakAI",
        "description": "Integrate with Sitespeakai to leverage AI-powered chatbots and enhance user interactions on your website.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/sitespeakai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-skyvern",
        "name": "Skyvern",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/skyvern.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-slack",
        "name": "Slack",
        "description": "Channel-based messaging platform",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/slack.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [
            {
                "name": "new-message",
                "displayName": "New Public Message Posted Anywhere",
                "description": "Triggers when a new message is posted to any channel.",
                "props": {
                    "ignoreBots": {
                        "displayName": "Ignore Bot Messages ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new-message-in-channel",
                "displayName": "New Message Posted to Channel",
                "description": "Triggers when a new message is posted to a specific #channel you choose.",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "ignoreBots": {
                        "displayName": "Ignore Bot Messages ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new-direct-message",
                "displayName": "New Direct Message",
                "description": "Triggers when a message was posted in a direct message channel.",
                "props": {
                    "ignoreBots": {
                        "displayName": "Ignore Bot Messages ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    },
                    "ignoreSelfMessages": {
                        "displayName": "Ignore Message from Yourself ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new_mention",
                "displayName": "New Mention in Channel",
                "description": "Triggers when a username is mentioned.",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly in an array like this: `{`{ ['your_channel_id_1', 'your_channel_id_2', ...] `}`}",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "user": {
                        "displayName": "User",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "channels": {
                        "displayName": "Channels",
                        "description": "If no channel is selected, the flow will be triggered for username mentions in all channels",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "ignoreBots": {
                        "displayName": "Ignore Bot Messages ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new-mention-in-direct-message",
                "displayName": "New Mention in Direct Message",
                "description": "Triggers when a username is mentioned in a direct message channel.",
                "props": {
                    "user": {
                        "displayName": "User",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "ignoreBots": {
                        "displayName": "Ignore Bot Messages ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    },
                    "ignoreSelfMessages": {
                        "displayName": "Ignore Message from Yourself ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new_reaction_added",
                "displayName": "New Reaction",
                "description": "Triggers when a new reaction is added to a message",
                "props": {
                    "emojis": {
                        "displayName": "Emojis (E.g fire, smile)",
                        "description": "Select emojis to trigger on",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "channel_created",
                "displayName": "Channel created",
                "description": "Triggers when a channel is created",
                "props": {}
            },
            {
                "name": "new_command",
                "displayName": "New Command in Channel",
                "description": "Triggers when a specific command is sent to the bot (e.g., @bot command arg1 arg2)",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly in an array like this: `{`{ ['your_channel_id_1', 'your_channel_id_2', ...] `}`}",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "user": {
                        "displayName": "User",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "commands": {
                        "displayName": "Commands",
                        "description": "List of valid commands that the bot should respond to (e.g., help, ocr, remind)",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": [
                            "help"
                        ]
                    },
                    "channels": {
                        "displayName": "Channels",
                        "description": "If no channel is selected, the flow will be triggered for commands in all channels",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "ignoreBots": {
                        "displayName": "Ignore Bot Messages ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": true
                    }
                }
            },
            {
                "name": "new-command-in-direct-message",
                "displayName": "New Command in Direct Message",
                "description": "Triggers when a specific command is sent to the bot (e.g., @bot command arg1 arg2) via Direct Message.",
                "props": {
                    "user": {
                        "displayName": "User",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "commands": {
                        "displayName": "Commands",
                        "description": "List of valid commands that the bot should respond to (e.g., help, ocr, remind)",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": [
                            "help"
                        ]
                    },
                    "ignoreBots": {
                        "displayName": "Ignore Bot Messages ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": true
                    },
                    "ignoreSelfMessages": {
                        "displayName": "Ignore Message from Yourself ?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "new-user",
                "displayName": "New User",
                "description": "Triggers when a new user is created / first joins your org.",
                "props": {}
            },
            {
                "name": "new-saved-message",
                "displayName": "New Saved Message",
                "description": "Triggers when you save a message.",
                "props": {}
            },
            {
                "name": "new-team-custom-emoji",
                "displayName": "New Team Custom Emoji",
                "description": "Triggers when a custom emoji has been added to a team.",
                "props": {}
            }
        ],
        "actions": [
            {
                "name": "slack-add-reaction-to-message",
                "displayName": "Add Reaction to Message",
                "description": "Add an emoji reaction to a message.",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "ts": {
                        "displayName": "Message Timestamp",
                        "description": "Please provide the timestamp of the message you wish to react, such as `1710304378.475129`. Alternatively, you can easily obtain the message link by clicking on the three dots next to the message and selecting the `Copy link` option.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "reaction": {
                        "displayName": "Reaction (emoji) name",
                        "description": "e.g.`thumbsup`",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "send_direct_message",
                "displayName": "Send Message To A User",
                "description": "Send message to a user",
                "props": {
                    "userId": {
                        "displayName": "User",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Message",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "username": {
                        "displayName": "Username",
                        "description": "The username of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "profilePicture": {
                        "displayName": "Profile Picture",
                        "description": "The profile picture of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "mentionOriginFlow": {
                        "displayName": "Mention flow of origin?",
                        "description": "If checked, adds a mention at the end of the Slack message to indicate which flow sent the notification, with a link to said flow.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "blocks": {
                        "displayName": "Block Kit blocks",
                        "description": "See https://api.slack.com/block-kit for specs",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": []
                    },
                    "unfurlLinks": {
                        "displayName": "Unfurl Links",
                        "description": "Enable link unfurling for this message",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": true
                    }
                }
            },
            {
                "name": "send_channel_message",
                "displayName": "Send Message To A Channel",
                "description": "Send message to a channel",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Message",
                        "description": "The text of your message. When using Block Kit blocks, this is used as a fallback for notifications.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "threadTs": {
                        "displayName": "Reply to Thread (Thread Message Link/Timestamp)",
                        "description": "Provide the ts (timestamp) or link value of the **parent** message to make this message a reply. Do not use the ts value of the reply itself; use its parent instead. For example `1710304378.475129`.Alternatively, you can easily obtain the message link by clicking on the three dots next to the parent message and selecting the `Copy link` option.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "username": {
                        "displayName": "Username",
                        "description": "The username of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "profilePicture": {
                        "displayName": "Profile Picture",
                        "description": "The profile picture of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "file": {
                        "displayName": "Attachment",
                        "description": "",
                        "type": "FILE",
                        "required": false,
                        "defaultValue": null
                    },
                    "replyBroadcast": {
                        "displayName": "Broadcast reply to channel",
                        "description": "When replying to a thread, also make the message visible to everyone in the channel (only applicable when Thread Timestamp is provided)",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "mentionOriginFlow": {
                        "displayName": "Mention flow of origin?",
                        "description": "If checked, adds a mention at the end of the Slack message to indicate which flow sent the notification, with a link to said flow.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "unfurlLinks": {
                        "displayName": "Unfurl Links",
                        "description": "Enable link unfurling for this message",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": true
                    },
                    "blocks": {
                        "displayName": "Block Kit blocks",
                        "description": "See https://api.slack.com/block-kit for specs",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": []
                    }
                }
            },
            {
                "name": "request_approval_direct_message",
                "displayName": "Request Approval from A User",
                "description": "Send approval message to a user and then wait until the message is approved or disapproved",
                "props": {
                    "userId": {
                        "displayName": "User",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Message",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "username": {
                        "displayName": "Username",
                        "description": "The username of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "profilePicture": {
                        "displayName": "Profile Picture",
                        "description": "The profile picture of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "request_approval_message",
                "displayName": "Request Approval in a Channel",
                "description": "Send approval message to a channel and then wait until the message is approved or disapproved",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Message",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "username": {
                        "displayName": "Username",
                        "description": "The username of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "profilePicture": {
                        "displayName": "Profile Picture",
                        "description": "The profile picture of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "request_action_direct_message",
                "displayName": "Request Action from A User",
                "description": "Send a message to a user and wait until the user selects an action",
                "props": {
                    "userId": {
                        "displayName": "User",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Message",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "actions": {
                        "displayName": "Action Buttons",
                        "description": "",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    },
                    "username": {
                        "displayName": "Username",
                        "description": "The username of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "profilePicture": {
                        "displayName": "Profile Picture",
                        "description": "The profile picture of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "request_action_message",
                "displayName": "Request Action in A Channel",
                "description": "Send a message in a channel and wait until an action is selected",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Message",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "actions": {
                        "displayName": "Action Buttons",
                        "description": "",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    },
                    "threadTs": {
                        "displayName": "Reply to Thread (Thread Message Link/Timestamp)",
                        "description": "Provide the ts (timestamp) or link value of the **parent** message to make this message a reply. Do not use the ts value of the reply itself; use its parent instead. For example `1710304378.475129`.Alternatively, you can easily obtain the message link by clicking on the three dots next to the parent message and selecting the `Copy link` option.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "username": {
                        "displayName": "Username",
                        "description": "The username of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "profilePicture": {
                        "displayName": "Profile Picture",
                        "description": "The profile picture of the bot",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "uploadFile",
                "displayName": "Upload file",
                "description": "Upload file without sharing it to a channel or user",
                "props": {
                    "file": {
                        "displayName": "Attachment",
                        "description": "",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "title": {
                        "displayName": "Title",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "filename": {
                        "displayName": "Filename",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-file",
                "displayName": "Get File",
                "description": "Return information about a given file ID.",
                "props": {
                    "fileId": {
                        "displayName": "File ID",
                        "description": "You can pass the file ID from the New Message Trigger payload.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "searchMessages",
                "displayName": "Search messages",
                "description": "Searches for messages matching a query",
                "props": {
                    "query": {
                        "displayName": "Search query",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "slack-find-user-by-email",
                "displayName": "Find User by Email",
                "description": "Finds a user by matching against their email address.",
                "props": {
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "slack-find-user-by-handle",
                "displayName": "Find User by Handle",
                "description": "Finds a user by matching against their Slack handle.",
                "props": {
                    "handle": {
                        "displayName": "Handle",
                        "description": "User handle (display name), without the leading @",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-user-by-id",
                "displayName": "Find User by ID",
                "description": "Finds a user by their ID.",
                "props": {
                    "id": {
                        "displayName": "ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "listUsers",
                "displayName": "List users",
                "description": "List all users of the workspace",
                "props": {
                    "includeBots": {
                        "displayName": "Include bots?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    },
                    "includeDisabled": {
                        "displayName": "Include disabled users?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "updateMessage",
                "displayName": "Update message",
                "description": "Update an existing message",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "ts": {
                        "displayName": "Message Timestamp",
                        "description": "Please provide the timestamp of the message you wish to update, such as `1710304378.475129`. Alternatively, you can easily obtain the message link by clicking on the three dots next to the message and selecting the `Copy link` option.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "text": {
                        "displayName": "Message",
                        "description": "The updated text of your message",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "blocks": {
                        "displayName": "Block Kit blocks",
                        "description": "See https://api.slack.com/block-kit for specs",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": []
                    }
                }
            },
            {
                "name": "slack-create-channel",
                "displayName": "Create Channel",
                "description": "Creates a new channel.",
                "props": {
                    "channelName": {
                        "displayName": "Channel Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "isPrivate": {
                        "displayName": "Is Private?",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "slack-update-profile",
                "displayName": "Update Profile",
                "description": "Update basic profile field such as name or title.",
                "props": {
                    "firstName": {
                        "displayName": "First Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "lastName": {
                        "displayName": "Last Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email",
                        "description": "Changing a user's email address will send an email to both the old and new addresses, and also post a slackbot message to the user informing them of the change.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "userId": {
                        "displayName": "User",
                        "description": "ID of user to change. This argument may only be specified by admins on paid teams.You can use **Find User by Email** action to retrieve ID.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "getChannelHistory",
                "displayName": "Get channel history",
                "description": "Retrieve all messages from a specific channel (\"conversation\") between specified timestamps",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "oldest": {
                        "displayName": "Oldest",
                        "description": "Only messages after this timestamp will be included in results",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "latest": {
                        "displayName": "Latest",
                        "description": "Only messages before this timestamp will be included in results. Default is the current time",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "inclusive": {
                        "displayName": "Inclusive",
                        "description": "Include messages with oldest or latest timestamps in results. Ignored unless either timestamp is specified",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    },
                    "includeAllMetadata": {
                        "displayName": "Include all metadata",
                        "description": "Return all metadata associated with each message",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "slack-set-user-status",
                "displayName": "Set User Status",
                "description": "Sets a user's custom status",
                "props": {
                    "text": {
                        "displayName": "Text",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "emoji": {
                        "displayName": "Emoji",
                        "description": "Emoji shortname (standard or custom), e.g. :tada: or :train:",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "expiration": {
                        "displayName": "Expires at",
                        "description": "Unix timestamp - if not set, the status will not expire",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "markdownToSlackFormat",
                "displayName": "Markdown to Slack format",
                "description": "Convert Markdown-formatted text to Slack's pseudo - markdown syntax",
                "props": {
                    "markdown": {
                        "displayName": "Markdown text",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "retrieveThreadMessages",
                "displayName": "Retrieve Thread Messages",
                "description": "Retrieves thread messages by channel and thread timestamp.",
                "props": {
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "threadTs": {
                        "displayName": "Thread ts",
                        "description": "Provide the ts (timestamp) value of the **parent** message to retrieve replies of this message. Do not use the ts value of the reply itself; use its parent instead. For example `1710304378.475129`.Alternatively, you can easily obtain the message link by clicking on the three dots next to the parent message and selecting the `Copy link` option.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "set-channel-topic",
                "displayName": "Set Channel Topic",
                "description": "Sets the topic on a selected channel.",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "topic": {
                        "displayName": "Topic",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get-message",
                "displayName": "Get Message by Timestamp",
                "description": "Retrieves a specific message from a channel history using the message's timestamp.",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "ts": {
                        "displayName": "Message Timestamp",
                        "description": "Please provide the timestamp of the message you wish to retrieve, such as `1710304378.475129`. Alternatively, you can easily obtain the message link by clicking on the three dots next to the message and selecting the `Copy link` option.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "invite-user-to-channel",
                "displayName": "Invite User to Channel",
                "description": "Invites an existing User to an existing channel.",
                "props": {
                    "info": {
                        "displayName": "Markdown",
                        "description": "\n\tPlease make sure add the bot to the channel by following these steps:\n\t  1. Type /invite in the channel's chat.\n\t  2. Click on Add apps to this channel.\n\t  3. Search for and add the bot.\n  \n**Note**: If you can't find the channel in the dropdown list (which fetches up to 2000 channels), please click on the **(F)** and type the channel ID directly.\n  ",
                        "type": "MARKDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "channel": {
                        "displayName": "Channel",
                        "description": "You can get the Channel ID by right-clicking on the channel and selecting 'View Channel Details.'",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "userId": {
                        "displayName": "User",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "useUserToken": {
                        "displayName": "Use user token",
                        "description": "Use user token instead of bot token",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": false
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-slidespeak",
        "name": "SlideSpeak",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/slidespeak.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-smaily",
        "name": "Smaily",
        "description": "",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/smaily.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-smartsheet",
        "name": "Smartsheet",
        "description": "Dynamic work execution platform for teams to plan, capture, manage, automate, and report on work at scale.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/smartsheet.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-smartsuite",
        "name": "SmartSuite",
        "description": "Collaborative work management platform combining databases with spreadsheets.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/smartsuite.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-smoove",
        "name": "Smoove",
        "description": "Smoove is a platform for creating and managing your email list and sending emails to your subscribers.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/smoove.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-smtp",
        "name": "SMTP",
        "description": "Send emails using Simple Mail Transfer Protocol",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/smtp.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-snowflake",
        "name": "Snowflake",
        "description": "Data warehouse built for the cloud",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/snowflake.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-soap",
        "name": "SOAP",
        "description": "Simple Object Access Protocol for communication between applications",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/soap.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-socialkit",
        "name": "Socialkit",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/socialkit.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-softr",
        "name": "Softr",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/softr.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-sperse",
        "name": "Sperse",
        "description": "Sperse CRM enables secure payment processing and affiliate marketing for online businesses",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/sperse.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-splitwise",
        "name": "Splitwise",
        "description": "Splitwise is a expense splitting app that helps you track and settle bills with friends, family, and roommates.",
        "category": "finance",
        "icon": "https://cdn.activepieces.com/pieces/splitwise.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-spotify",
        "name": "Spotify",
        "description": "Music for everyone",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/spotify.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-square",
        "name": "Square",
        "description": "Payment solutions for every business",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/square.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-stability-ai",
        "name": "Stability AI",
        "description": "Generative AI video model based on the image model Stable Diffusion.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/stability-ai.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-stable-diffusion-webui",
        "name": "Stable Dffusion web UI",
        "description": "A web interface for Stable Diffusion",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/stable-diffusion-webui.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-store",
        "name": "Storage",
        "description": "Store or retrieve data from key/value database",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/store.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-straico",
        "name": "Straico",
        "description": "All-in-one generative AI platform",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/straico.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-stripe",
        "name": "Stripe",
        "description": "Online payment processing for internet businesses",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/stripe.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [
            {
                "name": "new_payment",
                "displayName": "New Payment",
                "description": "Triggers when a new payment is made",
                "props": {}
            },
            {
                "name": "new_customer",
                "displayName": "New Customer",
                "description": "Triggers when a new customer is created",
                "props": {}
            },
            {
                "name": "payment_failed",
                "displayName": "Payment Failed",
                "description": "Triggers when a payment fails",
                "props": {}
            },
            {
                "name": "new_subscription",
                "displayName": "New Subscription",
                "description": "Triggers when a new subscription is made",
                "props": {}
            },
            {
                "name": "new_charge",
                "displayName": "New Charge",
                "description": "Fires when a charge is successfully completed.",
                "props": {}
            },
            {
                "name": "new_invoice",
                "displayName": "New Invoice",
                "description": "Fires when an invoice is created. Supports filters like status, customer, subscription.",
                "props": {
                    "status": {
                        "displayName": "Status",
                        "description": "Only trigger for invoices with this status.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Draft",
                                    "value": "draft"
                                },
                                {
                                    "label": "Open",
                                    "value": "open"
                                },
                                {
                                    "label": "Paid",
                                    "value": "paid"
                                },
                                {
                                    "label": "Uncollectible",
                                    "value": "uncollectible"
                                },
                                {
                                    "label": "Void",
                                    "value": "void"
                                }
                            ]
                        }
                    },
                    "customer": {
                        "displayName": "Customer ID",
                        "description": "Only trigger for invoices belonging to this customer ID (e.g., `cus_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "subscription": {
                        "displayName": "Subscription ID",
                        "description": "Only trigger for invoices belonging to this subscription ID (e.g., `sub_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "invoice_payment_failed",
                "displayName": "Invoice Payment Failed",
                "description": "Fires when a payment against an invoice fails.",
                "props": {
                    "customer": {
                        "displayName": "Customer ID",
                        "description": "Only trigger for invoices belonging to this customer ID (e.g., `cus_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "canceled_subscription",
                "displayName": "Canceled Subscription",
                "description": "Fires when a subscription is canceled.",
                "props": {
                    "customer": {
                        "displayName": "Customer ID",
                        "description": "Only trigger for subscriptions belonging to this customer ID (e.g., `cus_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_refund",
                "displayName": "New Refund",
                "description": "Fires when a charge is refunded (full or partial).",
                "props": {
                    "charge": {
                        "displayName": "Charge ID",
                        "description": "Only trigger for refunds related to this Charge ID (e.g., `ch_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "payment_intent": {
                        "displayName": "Payment Intent ID",
                        "description": "Only trigger for refunds related to this Payment Intent ID (e.g., `pi_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_dispute",
                "displayName": "New Dispute",
                "description": "Fires when a customer disputes a charge.",
                "props": {
                    "charge": {
                        "displayName": "Charge ID",
                        "description": "Only trigger for disputes related to this Charge ID (e.g., `ch_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "payment_intent": {
                        "displayName": "Payment Intent ID",
                        "description": "Only trigger for disputes related to this Payment Intent ID (e.g., `pi_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_payment_link",
                "displayName": "New Payment Link",
                "description": "Fires when a new Payment Link is created.",
                "props": {}
            },
            {
                "name": "updated_subscription",
                "displayName": "Updated Subscription",
                "description": "Fires when an existing subscription is changed.",
                "props": {
                    "status": {
                        "displayName": "New Status",
                        "description": "Only trigger when the subscription is updated to this status.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Incomplete",
                                    "value": "incomplete"
                                },
                                {
                                    "label": "Incomplete - Expired",
                                    "value": "incomplete_expired"
                                },
                                {
                                    "label": "Trialing",
                                    "value": "trialing"
                                },
                                {
                                    "label": "Active",
                                    "value": "active"
                                },
                                {
                                    "label": "Past Due",
                                    "value": "past_due"
                                },
                                {
                                    "label": "Canceled",
                                    "value": "canceled"
                                },
                                {
                                    "label": "Unpaid",
                                    "value": "unpaid"
                                },
                                {
                                    "label": "Paused",
                                    "value": "paused"
                                }
                            ]
                        }
                    },
                    "customer": {
                        "displayName": "Customer ID",
                        "description": "Only trigger for subscriptions belonging to this customer ID (e.g., `cus_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "checkout_session_completed",
                "displayName": "Checkout Session Completed",
                "description": "Fires when a Stripe Checkout Session is successfully completed.",
                "props": {
                    "customer": {
                        "displayName": "Customer ID",
                        "description": "Only trigger for checkout sessions created by this customer ID (e.g., `cus_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "create_customer",
                "displayName": "Create Customer",
                "description": "Create a customer in stripe",
                "props": {
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "phone": {
                        "displayName": "Phone",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "line1": {
                        "displayName": "Address Line 1",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "postal_code": {
                        "displayName": "Postal Code",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "city": {
                        "displayName": "City",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "state": {
                        "displayName": "State",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "country": {
                        "displayName": "Country",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_invoice",
                "displayName": "Create Invoice",
                "description": "Create an Invoice in stripe",
                "props": {
                    "customer_id": {
                        "displayName": "Customer ID",
                        "description": "Stripe Customer ID",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "currency": {
                        "displayName": "Currency",
                        "description": "Currency for the invoice (e.g., USD)",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "Description for the invoice",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "search_customer",
                "displayName": "Search Customer",
                "description": "Search for a customer in stripe by email",
                "props": {
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "search_subscriptions",
                "displayName": "Search Subscriptions",
                "description": "Search for subscriptions by price ID, status, customer ID and other filters, including customer details",
                "props": {
                    "price_ids": {
                        "displayName": "Price IDs",
                        "description": "Comma-separated list of price IDs to filter by (e.g., price_1ABC123, price_2DEF456)",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Subscription Status",
                        "description": "Filter by subscription status",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "All Statuses",
                                    "value": ""
                                },
                                {
                                    "label": "Active",
                                    "value": "active"
                                },
                                {
                                    "label": "Past Due",
                                    "value": "past_due"
                                },
                                {
                                    "label": "Unpaid",
                                    "value": "unpaid"
                                },
                                {
                                    "label": "Canceled",
                                    "value": "canceled"
                                },
                                {
                                    "label": "Incomplete",
                                    "value": "incomplete"
                                },
                                {
                                    "label": "Incomplete Expired",
                                    "value": "incomplete_expired"
                                },
                                {
                                    "label": "Trialing",
                                    "value": "trialing"
                                },
                                {
                                    "label": "Paused",
                                    "value": "paused"
                                }
                            ]
                        }
                    },
                    "customer_id": {
                        "displayName": "Customer ID",
                        "description": "Filter by specific customer ID (optional)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "created_after": {
                        "displayName": "Created After",
                        "description": "Filter subscriptions created after this date (YYYY-MM-DD format)",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "created_before": {
                        "displayName": "Created Before",
                        "description": "Filter subscriptions created before this date (YYYY-MM-DD format)",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "limit": {
                        "displayName": "Limit",
                        "description": "Maximum number of subscriptions to return (default: 100, set to 0 for all)",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": 100
                    },
                    "fetch_all": {
                        "displayName": "Fetch All Results",
                        "description": "Fetch all matching subscriptions (ignores limit, may take longer for large datasets)",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "include_customer_details": {
                        "displayName": "Include Customer Details",
                        "description": "Fetch detailed customer information for each subscription",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": true
                    }
                }
            },
            {
                "name": "retrieve_customer",
                "displayName": "Retrieve Customer",
                "description": "Retrieve a customer in stripe by id",
                "props": {
                    "id": {
                        "displayName": "ID",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_customer",
                "displayName": "Update Customer",
                "description": "Modify an existing customer\u2019s details.",
                "props": {
                    "customer": {
                        "displayName": "Customer",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "phone": {
                        "displayName": "Phone",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "line1": {
                        "displayName": "Address Line 1",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "postal_code": {
                        "displayName": "Postal Code",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "city": {
                        "displayName": "City",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "state": {
                        "displayName": "State",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "country": {
                        "displayName": "Country",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_payment_intent",
                "displayName": "Create Payment (Payment Intent)",
                "description": "Creates a new payment intent to start a payment flow.",
                "props": {
                    "amount": {
                        "displayName": "Amount",
                        "description": "The amount to charge, in a decimal format (e.g., 10.50 for $10.50).",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "currency": {
                        "displayName": "Currency",
                        "description": "The three-letter ISO code for the currency.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "US Dollar",
                                    "value": "usd"
                                },
                                {
                                    "label": "Euro",
                                    "value": "eur"
                                },
                                {
                                    "label": "Pound Sterling",
                                    "value": "gbp"
                                },
                                {
                                    "label": "Australian Dollar",
                                    "value": "aud"
                                },
                                {
                                    "label": "Canadian Dollar",
                                    "value": "cad"
                                },
                                {
                                    "label": "Swiss Franc",
                                    "value": "chf"
                                },
                                {
                                    "label": "Chinese Yuan",
                                    "value": "cny"
                                },
                                {
                                    "label": "Japanese Yen",
                                    "value": "jpy"
                                },
                                {
                                    "label": "Indian Rupee",
                                    "value": "inr"
                                },
                                {
                                    "label": "Singapore Dollar",
                                    "value": "sgd"
                                }
                            ]
                        }
                    },
                    "customer": {
                        "displayName": "Customer",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "payment_method": {
                        "displayName": "Payment Method ID",
                        "description": "The ID of the Payment Method to attach (e.g., `pm_...`). Required if you want to confirm the payment immediately.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "confirm": {
                        "displayName": "Confirm Payment Immediately",
                        "description": "If true, Stripe will attempt to charge the provided payment method. A `Payment Method ID` is required.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "return_url": {
                        "displayName": "Return URL",
                        "description": "The URL to redirect your customer back to after they authenticate their payment. Required when confirming the payment.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "receipt_email": {
                        "displayName": "Receipt Email",
                        "description": "The email address to send a receipt to. This will override the customer's email address.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_product",
                "displayName": "Create Product",
                "description": "Create a new product object in Stripe.",
                "props": {
                    "name": {
                        "displayName": "Product Name",
                        "description": "The product\u2019s name, meant to be displayable to the customer.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Description",
                        "description": "The product\u2019s description, meant to be displayable to the customer.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "active": {
                        "displayName": "Active",
                        "description": "Whether the product is currently available for purchase. Defaults to true.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "images": {
                        "displayName": "Image URLs",
                        "description": "A list of up to 8 URLs of images for this product.",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "url": {
                        "displayName": "Product URL",
                        "description": "A publicly-accessible online page for this product.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "metadata": {
                        "displayName": "Metadata",
                        "description": "A set of key-value pairs to store additional information about the product.",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_price",
                "displayName": "Create Price",
                "description": "Create a price (one-time or recurring), associated with a product.",
                "props": {
                    "product": {
                        "displayName": "Product",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "unit_amount": {
                        "displayName": "Unit Amount",
                        "description": "The price amount as a decimal, for example, 25.50 for $25.50.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    },
                    "currency": {
                        "displayName": "Currency",
                        "description": "The three-letter ISO code for the currency.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "US Dollar",
                                    "value": "usd"
                                },
                                {
                                    "label": "Euro",
                                    "value": "eur"
                                },
                                {
                                    "label": "Pound Sterling",
                                    "value": "gbp"
                                },
                                {
                                    "label": "Indian Rupee",
                                    "value": "inr"
                                },
                                {
                                    "label": "Australian Dollar",
                                    "value": "aud"
                                },
                                {
                                    "label": "Canadian Dollar",
                                    "value": "cad"
                                },
                                {
                                    "label": "Swiss Franc",
                                    "value": "chf"
                                },
                                {
                                    "label": "Chinese Yuan",
                                    "value": "cny"
                                },
                                {
                                    "label": "Japanese Yen",
                                    "value": "jpy"
                                },
                                {
                                    "label": "Singapore Dollar",
                                    "value": "sgd"
                                }
                            ]
                        }
                    },
                    "recurring_interval": {
                        "displayName": "Billing Interval",
                        "description": "Specify the billing frequency. Select 'One-Time' for a single, non-recurring payment.",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "one_time",
                        "options": {
                            "options": [
                                {
                                    "label": "One-Time",
                                    "value": "one_time"
                                },
                                {
                                    "label": "Daily",
                                    "value": "day"
                                },
                                {
                                    "label": "Weekly",
                                    "value": "week"
                                },
                                {
                                    "label": "Monthly",
                                    "value": "month"
                                },
                                {
                                    "label": "Yearly",
                                    "value": "year"
                                }
                            ]
                        }
                    },
                    "recurring_interval_count": {
                        "displayName": "Interval Count",
                        "description": "The number of intervals between subscription billings (e.g., for billing every 3 months, set Interval to Monthly and Interval Count to 3). Only used for recurring prices.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_subscription",
                "displayName": "Create Subscription",
                "description": "Start a subscription for a customer with specified items/prices.",
                "props": {
                    "customer": {
                        "displayName": "Customer",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "items": {
                        "displayName": "Subscription Items",
                        "description": "A list of prices to subscribe the customer to.",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    },
                    "collection_method": {
                        "displayName": "Collection Method",
                        "description": "How to collect payment. 'charge_automatically' will try to bill the default payment method. 'send_invoice' will email an invoice.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Charge Automatically",
                                    "value": "charge_automatically"
                                },
                                {
                                    "label": "Send Invoice",
                                    "value": "send_invoice"
                                }
                            ]
                        }
                    },
                    "days_until_due": {
                        "displayName": "Days Until Due",
                        "description": "Number of days before an invoice is due. Required if Collection Method is 'Send Invoice'.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "trial_period_days": {
                        "displayName": "Trial Period (Days)",
                        "description": "Integer representing the number of trial days the customer receives before the subscription bills for the first time.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "default_payment_method": {
                        "displayName": "Default Payment Method ID",
                        "description": "ID of the default payment method for the subscription (e.g., `pm_...`).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "metadata": {
                        "displayName": "Metadata",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "cancel_subscription",
                "displayName": "Cancel Subscription",
                "description": "Cancel an existing subscription, either immediately or at the end of the current billing period.",
                "props": {
                    "subscription": {
                        "displayName": "Subscription",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "cancel_at_period_end": {
                        "displayName": "Cancel at Period End",
                        "description": "If true, the subscription remains active until the end of the current billing period. If false, it cancels immediately.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    }
                }
            },
            {
                "name": "retrieve_invoice",
                "displayName": "Retrieve an Invoice",
                "description": "Retrieves the details of an existing invoice by its ID.",
                "props": {
                    "invoice_id": {
                        "displayName": "Invoice",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "retrieve_payout",
                "displayName": "Retrieve a Payout",
                "description": "Retrieves the details of an existing payout by its ID.",
                "props": {
                    "payout_id": {
                        "displayName": "Payout",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_refund",
                "displayName": "Create a Refund",
                "description": "Create a full or partial refund for a payment.",
                "props": {
                    "payment_intent": {
                        "displayName": "Payment Intent",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "amount": {
                        "displayName": "Amount",
                        "description": "The amount to refund (e.g., 12.99). If left blank, a full refund will be issued.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "reason": {
                        "displayName": "Reason",
                        "description": "An optional reason for the refund.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Duplicate",
                                    "value": "duplicate"
                                },
                                {
                                    "label": "Fraudulent",
                                    "value": "fraudulent"
                                },
                                {
                                    "label": "Requested by Customer",
                                    "value": "requested_by_customer"
                                }
                            ]
                        }
                    },
                    "metadata": {
                        "displayName": "Metadata",
                        "description": "A set of key-value pairs to store additional information about the refund.",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create_payment_link",
                "displayName": "Create Payment Link",
                "description": "Creates a shareable, Stripe-hosted payment link for one-time purchases or subscriptions.",
                "props": {
                    "line_items": {
                        "displayName": "Line Items",
                        "description": "The products and quantities to include in the payment link.",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    },
                    "after_completion_type": {
                        "displayName": "After Completion Behavior",
                        "description": "Controls the behavior after the purchase is complete. Defaults to showing Stripe's hosted confirmation page.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Show Confirmation Page",
                                    "value": "hosted_confirmation"
                                },
                                {
                                    "label": "Redirect to URL",
                                    "value": "redirect"
                                }
                            ]
                        }
                    },
                    "after_completion_redirect_url": {
                        "displayName": "Redirect URL",
                        "description": "The URL to redirect the customer to after a successful purchase. Only used if the behavior is set to \"Redirect to URL\".",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "allow_promotion_codes": {
                        "displayName": "Allow Promotion Codes",
                        "description": "Enables the user to enter a promotion code on the Payment Link page.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "billing_address_collection": {
                        "displayName": "Billing Address Collection",
                        "description": "Describes whether Checkout should collect the customer\u2019s billing address.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Auto",
                                    "value": "auto"
                                },
                                {
                                    "label": "Required",
                                    "value": "required"
                                }
                            ]
                        }
                    },
                    "metadata": {
                        "displayName": "Metadata",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "deactivate_payment_link",
                "displayName": "Deactivate Payment Link",
                "description": "Disable or deactivate a Payment Link so it can no longer be used.",
                "props": {
                    "payment_link_id": {
                        "displayName": "Payment Link",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "retrieve_payment_intent",
                "displayName": "Find Payment (by Payment Intent ID)",
                "description": "Retrieves the details of a payment by its unique Payment Intent ID.",
                "props": {
                    "payment_intent_id": {
                        "displayName": "Payment Intent",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find_invoice",
                "displayName": "Find Invoice",
                "description": "Finds an invoice by its unique ID.",
                "props": {
                    "invoice_id": {
                        "displayName": "Invoice",
                        "description": "",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-subflows",
        "name": "Sub Flows",
        "description": "Trigger and call another sub flow.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/flows.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-supabase",
        "name": "Supabase",
        "description": "The open-source Firebase alternative",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/supabase.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-supadata",
        "name": "Supadata",
        "description": "YouTube Transcripts",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/supadata.svg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-surrealdb",
        "name": "SurrealDB",
        "description": "Multi Model Database",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/surrealdb.jpg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-surveymonkey",
        "name": "SurveyMonkey",
        "description": "Receive survey responses from SurveyMonkey",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/surveymonkey.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-swarmnode",
        "name": "SwarmNode",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/swarmnode.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-synthesia",
        "name": "Synthesia",
        "description": "Create AI videos from text in minutes using Synthesia",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/synthesia.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-systeme-io",
        "name": "Systeme.io",
        "description": "Systeme.io is a CRM platform that allows you to manage your contacts, sales, and marketing campaigns.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/systeme-io.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tableau",
        "name": "Tableau",
        "description": "Business intelligence and analytics platform for data visualization",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/tableau.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tables",
        "name": "Tables",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/tables_piece.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tags",
        "name": "Tags",
        "description": "Add custom tags to your run for filtration",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/tags.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-talkable",
        "name": "Talkable",
        "description": "Referral marketing programs that drive revenue",
        "category": "marketing",
        "icon": "https://www.talkable.com/wp-content/uploads/2021/12/talkable-favicon.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tally",
        "name": "Tally",
        "description": "Receive form submissions from Tally forms",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/tally.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tarvent",
        "name": "Tarvent",
        "description": "Tarvent is an email marketing, automation, and email API platform that allows to you to send campaigns, manage contacts, automate your marketing, and more.",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/tarvent.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-taskade",
        "name": "Taskade",
        "description": "collaboration platform for remote teams to organize and manage projects",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/taskade.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tavily",
        "name": "Tavily",
        "description": "Search engine tailored for AI agents.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/tavily.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-teamleader",
        "name": "Teamleader",
        "description": "",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/teamleader.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-teamwork",
        "name": "Teamwork",
        "description": "Teamwork is a work and project management tool that helps teams improve collaboration, visibility, and accountability.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/teamwork.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-telegram-bot",
        "name": "Telegram Bot",
        "description": "Build chatbots for Telegram",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/telegram_bot.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-text-helper",
        "name": "Text Helper",
        "description": "Tools for text processing",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/text-helper.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-textcortex-ai",
        "name": "TextCortex AI",
        "description": "AI-powered writing assistant for content creation, code generation, translations, and more using multiple AI models.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/textcortex-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-thankster",
        "name": "Thankster",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/thankster.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-ticktick",
        "name": "TickTick",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/ticktick.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tidycal",
        "name": "TidyCal",
        "description": "Streamline your scheduling",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/tidycal.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-timelines-ai",
        "name": "TimelinesAI",
        "description": "",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/timelines-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tiny-talk-ai",
        "name": "Tiny Talk AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/tiny-talk-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-tl-dv",
        "name": "tl;dv",
        "description": "Record meetings, get transcripts, and access meeting notes automatically.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/tl-dv.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-todoist",
        "name": "Todoist",
        "description": "To-do list and task manager",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/todoist.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-todos",
        "name": "Todos",
        "description": "Create tasks for project members to take actions, useful for approvals, reviews, and manual actions performed by humans",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/manual-tasks.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-toggl-track",
        "name": "Toggl Track",
        "description": "Toggl Track is a time tracking application that allows users to track their daily activities across different platforms.",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/toggl-track.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-totalcms",
        "name": "Total CMS",
        "description": "Content management system for modern websites",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/totalcms.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-trello",
        "name": "Trello",
        "description": "Project management tool for teams",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/trello.png",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [
            {
                "name": "card_moved_to_list",
                "displayName": "Card Moved to list",
                "description": "Trigger when a card is moved to the list specified",
                "props": {
                    "board_id": {
                        "displayName": "Boards",
                        "description": "List of boards",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "list_id": {
                        "displayName": "Lists",
                        "description": "Get lists from a board",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_card",
                "displayName": "New Card",
                "description": "Trigger when a new card is created",
                "props": {
                    "board_id": {
                        "displayName": "Boards",
                        "description": "List of boards",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "list_id_opt": {
                        "displayName": "Lists",
                        "description": "Get lists from a board",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "deadline",
                "displayName": "Card Deadline",
                "description": "Triggers at a specified time before a card deadline.",
                "props": {
                    "board_id": {
                        "displayName": "Boards",
                        "description": "List of boards",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "list_id_opt": {
                        "displayName": "Lists",
                        "description": "Get lists from a board",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "time_unit": {
                        "displayName": "Time unit",
                        "description": "Select unit for time before due",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": "hours",
                        "options": {
                            "options": [
                                {
                                    "label": "Minutes",
                                    "value": "minutes"
                                },
                                {
                                    "label": "Hours",
                                    "value": "hours"
                                }
                            ]
                        }
                    },
                    "time_before_due": {
                        "displayName": "Time before due",
                        "description": "How long before the due date the trigger should run (use with time unit)",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": 24
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "create_card",
                "displayName": "Create Card",
                "description": "Create a new card in Trello",
                "props": {
                    "board_id": {
                        "displayName": "Boards",
                        "description": "List of boards",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "list_id": {
                        "displayName": "Lists",
                        "description": "Get lists from a board",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Task Name",
                        "description": "The name of the card to create",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Task Description",
                        "description": "The description of the card to create",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "position": {
                        "displayName": "Position",
                        "description": "Place the card on top or bottom of the list",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Top",
                                    "value": "top"
                                },
                                {
                                    "label": "Bottom",
                                    "value": "bottom"
                                }
                            ]
                        }
                    },
                    "labels": {
                        "displayName": "Labels",
                        "description": "Assign labels to the card",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_card",
                "displayName": "Get Card",
                "description": "Gets a card by ID.",
                "props": {
                    "cardId": {
                        "displayName": "Card ID",
                        "description": "The card ID",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update_card",
                "displayName": "Update Card",
                "description": "Updates an existing card.",
                "props": {
                    "card_id": {
                        "displayName": "Card ID",
                        "description": "The ID of the card to update",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Card Name",
                        "description": "The new name of the card",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "description": {
                        "displayName": "Card Description",
                        "description": "The new description of the card",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "board_id": {
                        "displayName": "Boards",
                        "description": "List of boards",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "list_id": {
                        "displayName": "Lists",
                        "description": "Get lists from a board",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "position": {
                        "displayName": "Position",
                        "description": "Move the card to a new position",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "Top",
                                    "value": "top"
                                },
                                {
                                    "label": "Bottom",
                                    "value": "bottom"
                                }
                            ]
                        }
                    },
                    "labels": {
                        "displayName": "Labels",
                        "description": "Assign labels to the card",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "closed": {
                        "displayName": "Archived",
                        "description": "Archive or unarchive the card",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "due": {
                        "displayName": "Due Date",
                        "description": "Set a due date for the card",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete_card",
                "displayName": "Delete Card",
                "description": "Deletes an existing card.",
                "props": {
                    "card_id": {
                        "displayName": "Card ID",
                        "description": "The ID of the card to delete.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_card_attachments",
                "displayName": "Get All Card Attachments",
                "description": "Gets all attachments on a card.",
                "props": {
                    "card_id": {
                        "displayName": "Card ID",
                        "description": "The ID of the card to get attachments from",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add_card_attachment",
                "displayName": "Add Card Attachment",
                "description": "Adds an attachment to a card.",
                "props": {
                    "card_id": {
                        "displayName": "Card ID",
                        "description": "The ID of the card to add attachment to",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "attachment": {
                        "displayName": "Attachment File",
                        "description": "",
                        "type": "FILE",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Attachment Name",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "mime_type": {
                        "displayName": "MIME Type",
                        "description": "",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "set_cover": {
                        "displayName": "Set as Cover",
                        "description": "Set this attachment as the card cover",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "get_card_attachment",
                "displayName": "Get Card Attachment",
                "description": "Gets a specific attachment on a card.",
                "props": {
                    "card_id": {
                        "displayName": "Card ID",
                        "description": "The ID of the card",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "attachment_id": {
                        "displayName": "Attachment ID",
                        "description": "The ID of the attachment to retrieve",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete_card_attachment",
                "displayName": "Delete Card Attachment",
                "description": "Deletes an attachment from a card.",
                "props": {
                    "card_id": {
                        "displayName": "Card ID",
                        "description": "The ID of the card",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "attachment_id": {
                        "displayName": "Attachment ID",
                        "description": "The ID of the attachment to delete",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-truelayer",
        "name": "TrueLayer",
        "description": "Connect with TrueLayer to leverage secure open banking services. This integration allows seamless interaction with TrueLayer's API to manage various financial processes.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/truelayer.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-twilio",
        "name": "Twilio",
        "description": "Cloud communications platform for building SMS, Voice & Messaging applications",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/twilio.png",
        "color": "#6366F1",
        "authType": "basic",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-twin-labs",
        "name": "Twin Web Agent",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/twin-labs.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-twitter",
        "name": "Twitter",
        "description": "Social media platform with over 500 million user",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/twitter.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-typeform",
        "name": "Typeform",
        "description": "Create beautiful online forms and surveys",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/typeform.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-upgradechat",
        "name": "Upgrade.chat",
        "description": "Supercharge your Discord or Telegram communities with subscription payments and membership tools.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/upgradechat.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-uscreen",
        "name": "Uscreen",
        "description": "All-in-one video monetization platform for creating, hosting, and selling online courses, memberships, and video content.",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/uscreen.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-vadoo-ai",
        "name": "Vadoo AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/vadoo-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-vbout",
        "name": "VBOUT",
        "description": "Marketing automation platform for agencies",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/vbout.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-vero",
        "name": "Vero",
        "description": "Vero is an event-based messaging platform. Increase conversions and customer satisfaction by sending more targeted emails.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/vero.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-video-ai",
        "name": "Video AI",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/video-ai-piece.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-videoask",
        "name": "VideoAsk",
        "description": "",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/videoask.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-vidlab7",
        "name": "VidLab7",
        "description": "AI Avatars that pitch, show demos, qualify buyers, follow up, secure meetings and close deals \u2013 on autopilot.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/vidlab7.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-village",
        "name": "Village",
        "description": "The Social Capital API",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/village.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-vimeo",
        "name": "Vimeo",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/vimeo.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-vlm-run",
        "name": "VLM Run",
        "description": "VLM Run is a visual AI platform that extracts data from images, videos, audio, and documents. It helps automate analysis workflows, such as object detection, transcription, image/audio analysis, and document parsing.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/vlm-run.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-voipstudio",
        "name": "VoIPstudio",
        "description": "VoIPstudio is a complete business phone system and scalable call center",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/voipstudio.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-vtex",
        "name": "VTEX",
        "description": "Unified commerce platform",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/vtex.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-vtiger",
        "name": "Vtiger",
        "description": "CRM software for sales, marketing, and support teams",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/vtiger.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-wealthbox",
        "name": "Wealthbox",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/wealthbox.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-webflow",
        "name": "Webflow",
        "description": "Design, build, and launch responsive websites visually",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/webflow.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-webhook",
        "name": "Webhook",
        "description": "Receive HTTP requests and trigger flows using unique URLs.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/webhook.svg",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-webling",
        "name": "Webling",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/webling.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-webscraping-ai",
        "name": "WebScraping AI",
        "description": "WebScraping AI is a powerful tool that allows you to scrape websites and extract data.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/webscraping-ai.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-wedof",
        "name": "Wedof",
        "description": "Automatisez la gestion de vos dossiers de formations (CPF, EDOF, Kairos, AIF, OPCO et autres)",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/wedof.svg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-what-converts",
        "name": "WhatConverts",
        "description": "",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/what-converts.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-whatsable",
        "name": "Whatsable",
        "description": "Manage your WhatsApp business account",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/whatsable.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-whatsapp",
        "name": "WhatsApp Business",
        "description": "Manage your WhatsApp business account",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/whatsapp.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-wonderchat",
        "name": "Wonderchat",
        "description": "Wonderchat is a no-code chatbot platform that lets you deploy AI-powered chatbots for websites quickly.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/wonderchat.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-woocommerce",
        "name": "WooCommerce",
        "description": "E-commerce platform built on WordPress",
        "category": "ecommerce",
        "icon": "https://cdn.activepieces.com/pieces/woocommerce.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-wootric",
        "name": "Wootric",
        "description": "Measure and boost customer happiness",
        "category": "other",
        "icon": "https://assets-production.wootric.com/assets/wootric-is-now-inmoment-250x108-85cb4900c62ff4d33200abafee7d63372d410abc5bf0cab90e80a07d4f4e5a31.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-wordpress",
        "name": "WordPress",
        "description": "Open-source website creation software",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/wordpress.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-workable",
        "name": "Workable",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/workable.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-wrike",
        "name": "Wrike",
        "description": "",
        "category": "productivity",
        "icon": "https://cdn.activepieces.com/pieces/wrike.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-writesonic-bulk",
        "name": "Writesonic",
        "description": "Writesonic AI-powered writing assistant",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/writesonic-bulk.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-wufoo",
        "name": "Wufoo",
        "description": "",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/wufoo.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-xero",
        "name": "Xero",
        "description": "Beautiful accounting software",
        "category": "finance",
        "icon": "https://cdn.activepieces.com/pieces/xero.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-xml",
        "name": "XML",
        "description": "Extensible Markup Language for storing and transporting data",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/xml.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-youcanbookme",
        "name": "YouCanBookMe",
        "description": "YouCanBookMe is an online scheduling tool that helps you manage appointments and bookings efficiently.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/youcanbookme.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-youform",
        "name": "Youform",
        "description": "",
        "category": "forms",
        "icon": "https://cdn.activepieces.com/pieces/youform.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-youtube",
        "name": "YouTube",
        "description": "Enjoy the videos and music you love, upload original content, and share it all with friends, family, and the world on YouTube",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/youtube.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zagomail",
        "name": "Zagomail",
        "description": "All-in-one email marketing and automation platform",
        "category": "marketing",
        "icon": "https://cdn.activepieces.com/pieces/zagomail.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zendesk",
        "name": "Zendesk",
        "description": "Customer service software and support ticket system",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/zendesk.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [
            {
                "name": "new_ticket_in_view",
                "displayName": "New ticket in view",
                "description": "Triggers when a new ticket is created in a view",
                "props": {
                    "view_id": {
                        "displayName": "View",
                        "description": "The view to monitor for new tickets",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_ticket",
                "displayName": "New Ticket",
                "description": "Fires when a new ticket is created (optionally filtered by organization). Requires a Zendesk Trigger with Notify active webhook.",
                "props": {
                    "organization_id": {
                        "displayName": "Organization (Optional)",
                        "description": "Filter tickets by organization. Leave empty to trigger for all organizations.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "updated_ticket",
                "displayName": "Updated Ticket",
                "description": "Fires when an existing ticket is updated. Requires a Zendesk Trigger with Notify active webhook.",
                "props": {
                    "organization_id": {
                        "displayName": "Organization (Optional)",
                        "description": "Filter tickets by organization. Leave empty to trigger for all organizations.",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "tag_added_to_ticket",
                "displayName": "Tag Added to Ticket",
                "description": "Fires when a ticket update includes the specified tag. Requires a Zendesk Trigger with Notify active webhook.",
                "props": {
                    "specific_tag": {
                        "displayName": "Specific Tag (Optional)",
                        "description": "Only trigger when this specific tag is added. Leave empty to trigger for any tag addition.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_organization",
                "displayName": "New Organization",
                "description": "Fires when a new organization record is created. Uses Zendesk event webhook (no Trigger needed).",
                "props": {}
            },
            {
                "name": "new_user",
                "displayName": "New User",
                "description": "Fires when a new user is created. Uses Zendesk event webhook (no Trigger needed).",
                "props": {
                    "user_role": {
                        "displayName": "User Role (Optional)",
                        "description": "Filter users by role. Leave empty to trigger for all user types.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select a user role (optional)",
                            "options": [
                                {
                                    "label": "All Roles",
                                    "value": "all"
                                },
                                {
                                    "label": "End User",
                                    "value": "end-user"
                                },
                                {
                                    "label": "Agent",
                                    "value": "agent"
                                },
                                {
                                    "label": "Admin",
                                    "value": "admin"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "new_suspended_ticket",
                "displayName": "New Suspended Ticket",
                "description": "Fires when a ticket is suspended. Requires a Zendesk Trigger with Notify active webhook. Suspended tickets auto-delete after 14 days.",
                "props": {
                    "organization_filter": {
                        "displayName": "Organization ID Filter (Optional)",
                        "description": "Only trigger for tickets from this organization ID. Leave empty for all organizations.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "new_action_on_ticket",
                "displayName": "New Action on Ticket",
                "description": "Fires when the specified ticket updates. Requires a Zendesk Trigger with Notify active webhook.",
                "props": {
                    "ticket_id": {
                        "displayName": "Ticket ID",
                        "description": "The specific ticket ID to monitor for actions/events.",
                        "type": "NUMBER",
                        "required": true,
                        "defaultValue": null
                    }
                }
            }
        ],
        "actions": [
            {
                "name": "create-ticket",
                "displayName": "Create Ticket",
                "description": "Create a new ticket in Zendesk.",
                "props": {
                    "subject": {
                        "displayName": "Subject",
                        "description": "The subject of the ticket (optional - will use first comment text if not provided)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "comment_body": {
                        "displayName": "Comment Body",
                        "description": "The comment body (text). Use this for plain text comments.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "comment_html_body": {
                        "displayName": "Comment HTML Body",
                        "description": "The comment body (HTML). Use this for HTML formatted comments. If provided, this takes precedence over Comment Body.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "requester_email": {
                        "displayName": "Requester Email",
                        "description": "Email address of the ticket requester. If not provided, the authenticated user will be the requester.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "requester_name": {
                        "displayName": "Requester Name",
                        "description": "Name of the ticket requester (used when creating a new user).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "assignee_email": {
                        "displayName": "Assignee Email",
                        "description": "Email address of the agent to assign the ticket to.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "priority": {
                        "displayName": "Priority",
                        "description": "The priority of the ticket.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select priority (optional)",
                            "options": [
                                {
                                    "label": "Low",
                                    "value": "low"
                                },
                                {
                                    "label": "Normal",
                                    "value": "normal"
                                },
                                {
                                    "label": "High",
                                    "value": "high"
                                },
                                {
                                    "label": "Urgent",
                                    "value": "urgent"
                                }
                            ]
                        }
                    },
                    "type": {
                        "displayName": "Type",
                        "description": "The type of ticket.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select type (optional)",
                            "options": [
                                {
                                    "label": "Problem",
                                    "value": "problem"
                                },
                                {
                                    "label": "Incident",
                                    "value": "incident"
                                },
                                {
                                    "label": "Question",
                                    "value": "question"
                                },
                                {
                                    "label": "Task",
                                    "value": "task"
                                }
                            ]
                        }
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "The status of the ticket.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select status (optional)",
                            "options": [
                                {
                                    "label": "New",
                                    "value": "new"
                                },
                                {
                                    "label": "Open",
                                    "value": "open"
                                },
                                {
                                    "label": "Pending",
                                    "value": "pending"
                                },
                                {
                                    "label": "Hold",
                                    "value": "hold"
                                },
                                {
                                    "label": "Solved",
                                    "value": "solved"
                                },
                                {
                                    "label": "Closed",
                                    "value": "closed"
                                }
                            ]
                        }
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "Array of tags to apply to the ticket.",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "organization_id": {
                        "displayName": "Organization",
                        "description": "Select the organization to work with",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "group_id": {
                        "displayName": "Group",
                        "description": "Select the group to assign",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "external_id": {
                        "displayName": "External ID",
                        "description": "An external ID for the ticket (useful for integrations).",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "collaborator_emails": {
                        "displayName": "Collaborator Emails",
                        "description": "Array of email addresses to add as collaborators.",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "follower_emails": {
                        "displayName": "Follower Emails",
                        "description": "Array of email addresses to add as followers.",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "due_at": {
                        "displayName": "Due Date",
                        "description": "The date and time when the ticket is due.",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "custom_fields": {
                        "displayName": "Custom Fields",
                        "description": "Custom ticket field values",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "comment_public": {
                        "displayName": "Public Comment",
                        "description": "Whether the comment is public (visible to the requester). Defaults to true.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "brand_id": {
                        "displayName": "Brand",
                        "description": "Select the brand to work with",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "forum_topic_id": {
                        "displayName": "Forum Topic ID",
                        "description": "The ID of the forum topic associated with the ticket.",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "problem_id": {
                        "displayName": "Problem Ticket",
                        "description": "Select the problem ticket this ticket is an incident of",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-ticket",
                "displayName": "Update Ticket",
                "description": "Modify ticket fields or status via API call.",
                "props": {
                    "ticket_id": {
                        "displayName": "Ticket",
                        "description": "Select the ticket to work with",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "subject": {
                        "displayName": "Subject",
                        "description": "Update the subject of the ticket",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "comment_body": {
                        "displayName": "Comment Body",
                        "description": "Add a comment to the ticket (plain text)",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "comment_html_body": {
                        "displayName": "Comment HTML Body",
                        "description": "Add a comment to the ticket (HTML). If provided, this takes precedence over Comment Body.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "comment_public": {
                        "displayName": "Public Comment",
                        "description": "Whether the comment is public (visible to the requester). Defaults to true.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "assignee_email": {
                        "displayName": "Assignee Email",
                        "description": "Email address of the agent to assign the ticket to",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "priority": {
                        "displayName": "Priority",
                        "description": "Update the priority of the ticket",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select priority (optional)",
                            "options": [
                                {
                                    "label": "Low",
                                    "value": "low"
                                },
                                {
                                    "label": "Normal",
                                    "value": "normal"
                                },
                                {
                                    "label": "High",
                                    "value": "high"
                                },
                                {
                                    "label": "Urgent",
                                    "value": "urgent"
                                }
                            ]
                        }
                    },
                    "type": {
                        "displayName": "Type",
                        "description": "Update the type of ticket",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select type (optional)",
                            "options": [
                                {
                                    "label": "Problem",
                                    "value": "problem"
                                },
                                {
                                    "label": "Incident",
                                    "value": "incident"
                                },
                                {
                                    "label": "Question",
                                    "value": "question"
                                },
                                {
                                    "label": "Task",
                                    "value": "task"
                                }
                            ]
                        }
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "Update the status of the ticket",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select status (optional)",
                            "options": [
                                {
                                    "label": "New",
                                    "value": "new"
                                },
                                {
                                    "label": "Open",
                                    "value": "open"
                                },
                                {
                                    "label": "Pending",
                                    "value": "pending"
                                },
                                {
                                    "label": "Hold",
                                    "value": "hold"
                                },
                                {
                                    "label": "Solved",
                                    "value": "solved"
                                },
                                {
                                    "label": "Closed",
                                    "value": "closed"
                                }
                            ]
                        }
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "Replace all tags with this array. Use \"Add Tag to Ticket\" action to add tags without replacing existing ones.",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "organization_id": {
                        "displayName": "Organization",
                        "description": "Select the organization to work with",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "group_id": {
                        "displayName": "Group",
                        "description": "Select the group to assign",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "external_id": {
                        "displayName": "External ID",
                        "description": "Update the external ID for the ticket",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "due_at": {
                        "displayName": "Due Date",
                        "description": "Update the date and time when the ticket is due",
                        "type": "DATE_TIME",
                        "required": false,
                        "defaultValue": null
                    },
                    "custom_fields": {
                        "displayName": "Custom Fields",
                        "description": "Update custom ticket field values",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "custom_status_id": {
                        "displayName": "Custom Status ID",
                        "description": "Set a custom status ID for the ticket",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "forum_topic_id": {
                        "displayName": "Forum Topic ID",
                        "description": "Update the forum topic associated with the ticket",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "collaborator_emails": {
                        "displayName": "Collaborator Emails",
                        "description": "Replace collaborators with this array of email addresses",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "follower_emails": {
                        "displayName": "Follower Emails",
                        "description": "Replace followers with this array of email addresses",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "requester_email": {
                        "displayName": "Requester Email",
                        "description": "Update the requester of the ticket",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "safe_update": {
                        "displayName": "Safe Update",
                        "description": "Prevent update collisions by checking timestamp",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "updated_stamp": {
                        "displayName": "Updated Timestamp",
                        "description": "Ticket timestamp from updated_at field for collision prevention",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "brand_id": {
                        "displayName": "Brand",
                        "description": "Select the brand to work with",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "problem_id": {
                        "displayName": "Problem Ticket",
                        "description": "Select the problem ticket this ticket is an incident of",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add-tag-to-ticket",
                "displayName": "Add Tag to Ticket",
                "description": "Apply one or more tags to a ticket.",
                "props": {
                    "ticket_id": {
                        "displayName": "Ticket",
                        "description": "Select the ticket to work with",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "Tags to add to the ticket (adds to existing tags)",
                        "type": "ARRAY",
                        "required": true,
                        "defaultValue": null
                    },
                    "safe_update": {
                        "displayName": "Safe Update",
                        "description": "Prevent tag loss from concurrent updates",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "updated_stamp": {
                        "displayName": "Updated Timestamp",
                        "description": "Ticket timestamp from updated_at field for collision prevention",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "add-comment-to-ticket",
                "displayName": "Add Comment to Ticket",
                "description": "Append a public/private comment to a ticket.",
                "props": {
                    "ticket_id": {
                        "displayName": "Ticket",
                        "description": "Select the ticket to work with",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "comment_body": {
                        "displayName": "Comment Body",
                        "description": "The comment text content",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "comment_html_body": {
                        "displayName": "Comment HTML Body",
                        "description": "HTML formatted comment (takes precedence over text)",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "public": {
                        "displayName": "Public Comment",
                        "description": "Make comment visible to requester (default: true)",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "author_email": {
                        "displayName": "Author Email",
                        "description": "Email of comment author (defaults to authenticated user)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "uploads": {
                        "displayName": "Attachment Tokens",
                        "description": "Upload tokens for file attachments",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "via_followup_source_id": {
                        "displayName": "Via Followup Source ID",
                        "description": "Original ticket ID if this is from a follow-up",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-organization",
                "displayName": "Create Organization",
                "description": "Create a new organization record.",
                "props": {
                    "name": {
                        "displayName": "Organization Name",
                        "description": "Unique name for the organization",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "details": {
                        "displayName": "Details",
                        "description": "Additional details about the organization",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "notes": {
                        "displayName": "Notes",
                        "description": "Internal notes about the organization",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "external_id": {
                        "displayName": "External ID",
                        "description": "External ID for integration purposes",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "group_id": {
                        "displayName": "Group",
                        "description": "Select the group to assign",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "domain_names": {
                        "displayName": "Domain Names",
                        "description": "Domain names associated with the organization",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "Tags to apply to the organization",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "organization_fields": {
                        "displayName": "Organization Fields",
                        "description": "Custom organization field values",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "shared_tickets": {
                        "displayName": "Shared Tickets",
                        "description": "Allow users to see each other's tickets",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "shared_comments": {
                        "displayName": "Shared Comments",
                        "description": "Allow users to see each other's comments",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "update-organization",
                "displayName": "Update Organization",
                "description": "Update existing organization fields.",
                "props": {
                    "organization_id": {
                        "displayName": "Organization",
                        "description": "Select the organization to work with",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Organization Name",
                        "description": "New name for the organization (must be unique)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "details": {
                        "displayName": "Details",
                        "description": "Additional details about the organization",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "notes": {
                        "displayName": "Notes",
                        "description": "Internal notes about the organization",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "external_id": {
                        "displayName": "External ID",
                        "description": "External ID for integration purposes",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "group_id": {
                        "displayName": "Group",
                        "description": "Select the group to assign",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "domain_names": {
                        "displayName": "Domain Names",
                        "description": "Domain names for the organization (replaces all existing)",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "Tags for the organization (replaces all existing)",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "organization_fields": {
                        "displayName": "Organization Fields",
                        "description": "Custom organization field values",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "shared_tickets": {
                        "displayName": "Shared Tickets",
                        "description": "Allow users to see each other's tickets",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "shared_comments": {
                        "displayName": "Shared Comments",
                        "description": "Allow users to see each other's comments",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "create-user",
                "displayName": "Create User",
                "description": "Add a new user to the Zendesk instance.",
                "props": {
                    "name": {
                        "displayName": "Name",
                        "description": "The name of the user",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email",
                        "description": "The primary email address of the user",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "role": {
                        "displayName": "Role",
                        "description": "The role of the user. Defaults to \"end-user\" if not specified.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select role (optional)",
                            "options": [
                                {
                                    "label": "End User",
                                    "value": "end-user"
                                },
                                {
                                    "label": "Agent",
                                    "value": "agent"
                                },
                                {
                                    "label": "Admin",
                                    "value": "admin"
                                }
                            ]
                        }
                    },
                    "custom_role_id": {
                        "displayName": "Custom Role",
                        "description": "Select the custom role for the agent",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "organization_id": {
                        "displayName": "Organization",
                        "description": "Select the organization to work with",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "organization_name": {
                        "displayName": "Organization Name",
                        "description": "Create and associate user with a new organization by name (alternative to Organization ID)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "phone": {
                        "displayName": "Phone",
                        "description": "The phone number of the user",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "alias": {
                        "displayName": "Alias",
                        "description": "An alias displayed to end users",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "details": {
                        "displayName": "Details",
                        "description": "Additional details about the user",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "notes": {
                        "displayName": "Notes",
                        "description": "Internal notes about the user",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "external_id": {
                        "displayName": "External ID",
                        "description": "A unique external ID for the user (useful for integrations)",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "time_zone": {
                        "displayName": "Time Zone",
                        "description": "The time zone of the user (e.g., \"America/New_York\")",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "locale": {
                        "displayName": "Locale",
                        "description": "The locale of the user (e.g., \"en-US\")",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "verified": {
                        "displayName": "Verified",
                        "description": "Whether the user is verified",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "active": {
                        "displayName": "Active",
                        "description": "Whether the user is active. Defaults to true.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "shared": {
                        "displayName": "Shared",
                        "description": "Whether the user is shared from a different Zendesk Support instance",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "shared_agent": {
                        "displayName": "Shared Agent",
                        "description": "Whether the user is a shared agent from a different Zendesk Support instance",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "moderator": {
                        "displayName": "Moderator",
                        "description": "Whether the user has forum moderation capabilities",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "suspended": {
                        "displayName": "Suspended",
                        "description": "Whether the user is suspended",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "restricted_agent": {
                        "displayName": "Restricted Agent",
                        "description": "Whether the agent has restrictions on what tickets they can access",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "only_private_comments": {
                        "displayName": "Only Private Comments",
                        "description": "Whether the user can only create private comments",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "report_csv": {
                        "displayName": "Report CSV",
                        "description": "Whether the user can access CSV reports",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "skip_verify_email": {
                        "displayName": "Skip Verify Email",
                        "description": "Skip sending a verification email to the user",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "ticket_restriction": {
                        "displayName": "Ticket Restriction",
                        "description": "The ticket restriction for the user",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "placeholder": "Select restriction (optional)",
                            "options": [
                                {
                                    "label": "Organization",
                                    "value": "organization"
                                },
                                {
                                    "label": "Groups",
                                    "value": "groups"
                                },
                                {
                                    "label": "Assigned",
                                    "value": "assigned"
                                },
                                {
                                    "label": "Requested",
                                    "value": "requested"
                                }
                            ]
                        }
                    },
                    "signature": {
                        "displayName": "Signature",
                        "description": "The user's signature for email responses",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "default_group_id": {
                        "displayName": "Group",
                        "description": "Select the group to assign",
                        "type": "DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "agent_brand_ids": {
                        "displayName": "Agent Brand Access",
                        "description": "Select the brands that the agent can access (for agents only)",
                        "type": "MULTI_SELECT_DROPDOWN",
                        "required": false,
                        "defaultValue": null
                    },
                    "tags": {
                        "displayName": "Tags",
                        "description": "Array of tags to apply to the user",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "user_fields": {
                        "displayName": "User Fields",
                        "description": "Custom user field values",
                        "type": "DYNAMIC",
                        "required": false,
                        "defaultValue": null
                    },
                    "identities": {
                        "displayName": "Identities",
                        "description": "Array of identity objects with type and value. Example: [{\"type\": \"email\", \"value\": \"test@user.com\"}, {\"type\": \"twitter\", \"value\": \"username\"}]",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "delete-user",
                "displayName": "Delete User",
                "description": "Remove a user and associated records from the account.",
                "props": {
                    "user_id": {
                        "displayName": "User",
                        "description": "Select the user to work with",
                        "type": "DROPDOWN",
                        "required": true,
                        "defaultValue": null
                    },
                    "confirmation": {
                        "displayName": "Confirm Deletion",
                        "description": "I understand that deleted users are not recoverable and this action cannot be undone.",
                        "type": "CHECKBOX",
                        "required": true,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "find-organization",
                "displayName": "Find Organization(s)",
                "description": "Search organizations by name, domain, external ID, or other criteria.",
                "props": {
                    "search_type": {
                        "displayName": "Search Type",
                        "description": "Choose how to search for organizations",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Search by Name",
                                    "value": "name"
                                },
                                {
                                    "label": "Search by Domain",
                                    "value": "domain"
                                },
                                {
                                    "label": "Search by External ID",
                                    "value": "external_id"
                                },
                                {
                                    "label": "Search by Tag",
                                    "value": "tag"
                                },
                                {
                                    "label": "Search by Details",
                                    "value": "details"
                                },
                                {
                                    "label": "Custom Query",
                                    "value": "custom"
                                }
                            ]
                        }
                    },
                    "name": {
                        "displayName": "Organization Name",
                        "description": "The name of the organization to search for",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "domain": {
                        "displayName": "Domain",
                        "description": "Search organizations by domain name",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "external_id": {
                        "displayName": "External ID",
                        "description": "Search organizations by external ID",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tag": {
                        "displayName": "Tag",
                        "description": "Search organizations containing this tag",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "details": {
                        "displayName": "Details",
                        "description": "Search in organization details/notes",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "custom_query": {
                        "displayName": "Custom Query",
                        "description": "Custom search query using Zendesk search syntax (e.g., \"type:organization domain:example.com\")",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "sort_by": {
                        "displayName": "Sort By",
                        "description": "How to sort the results",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Relevance (Default)",
                                    "value": "relevance"
                                },
                                {
                                    "label": "Created Date",
                                    "value": "created_at"
                                },
                                {
                                    "label": "Updated Date",
                                    "value": "updated_at"
                                }
                            ]
                        }
                    },
                    "sort_order": {
                        "displayName": "Sort Order",
                        "description": "Sort order for results",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Descending (Default)",
                                    "value": "desc"
                                },
                                {
                                    "label": "Ascending",
                                    "value": "asc"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "find-tickets",
                "displayName": "Find Ticket(s)",
                "description": "Search tickets by ID, field, or content.",
                "props": {
                    "search_type": {
                        "displayName": "Search Type",
                        "description": "Choose how to search for tickets",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Search by Ticket ID",
                                    "value": "id"
                                },
                                {
                                    "label": "Search by Status",
                                    "value": "status"
                                },
                                {
                                    "label": "Search by Priority",
                                    "value": "priority"
                                },
                                {
                                    "label": "Search by Type",
                                    "value": "type"
                                },
                                {
                                    "label": "Search by Tag",
                                    "value": "tag"
                                },
                                {
                                    "label": "Search by Requester Email",
                                    "value": "requester"
                                },
                                {
                                    "label": "Search by Assignee Email",
                                    "value": "assignee"
                                },
                                {
                                    "label": "Search by Subject/Content",
                                    "value": "content"
                                },
                                {
                                    "label": "Custom Query",
                                    "value": "custom"
                                }
                            ]
                        }
                    },
                    "timeFilter": {
                        "displayName": "Date Time Filter",
                        "description": "",
                        "type": "ARRAY",
                        "required": false,
                        "defaultValue": null
                    },
                    "ticket_id": {
                        "displayName": "Ticket ID",
                        "description": "The ID of the ticket to find",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "status": {
                        "displayName": "Status",
                        "description": "Search tickets by status",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "New",
                                    "value": "new"
                                },
                                {
                                    "label": "Open",
                                    "value": "open"
                                },
                                {
                                    "label": "Pending",
                                    "value": "pending"
                                },
                                {
                                    "label": "Hold",
                                    "value": "hold"
                                },
                                {
                                    "label": "Solved",
                                    "value": "solved"
                                },
                                {
                                    "label": "Closed",
                                    "value": "closed"
                                }
                            ]
                        }
                    },
                    "priority": {
                        "displayName": "Priority",
                        "description": "Search tickets by priority",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Low",
                                    "value": "low"
                                },
                                {
                                    "label": "Normal",
                                    "value": "normal"
                                },
                                {
                                    "label": "High",
                                    "value": "high"
                                },
                                {
                                    "label": "Urgent",
                                    "value": "urgent"
                                }
                            ]
                        }
                    },
                    "ticket_type": {
                        "displayName": "Type",
                        "description": "Search tickets by type",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Problem",
                                    "value": "problem"
                                },
                                {
                                    "label": "Incident",
                                    "value": "incident"
                                },
                                {
                                    "label": "Question",
                                    "value": "question"
                                },
                                {
                                    "label": "Task",
                                    "value": "task"
                                }
                            ]
                        }
                    },
                    "tag": {
                        "displayName": "Tag",
                        "description": "Search tickets containing this tag",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "requester_email": {
                        "displayName": "Requester Email",
                        "description": "Search tickets by requester email address",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "assignee_email": {
                        "displayName": "Assignee Email",
                        "description": "Search tickets by assignee email address",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "content": {
                        "displayName": "Content",
                        "description": "Search in ticket subject and content",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "custom_query": {
                        "displayName": "Custom Query",
                        "description": "Custom search query using Zendesk search syntax (e.g., \"type:ticket status:open priority:high\")",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "sort_by": {
                        "displayName": "Sort By",
                        "description": "How to sort the results",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Relevance (Default)",
                                    "value": "relevance"
                                },
                                {
                                    "label": "Created Date",
                                    "value": "created_at"
                                },
                                {
                                    "label": "Updated Date",
                                    "value": "updated_at"
                                },
                                {
                                    "label": "Priority",
                                    "value": "priority"
                                },
                                {
                                    "label": "Status",
                                    "value": "status"
                                },
                                {
                                    "label": "Ticket Type",
                                    "value": "ticket_type"
                                }
                            ]
                        }
                    },
                    "sort_order": {
                        "displayName": "Sort Order",
                        "description": "Sort order for results",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Descending (Default)",
                                    "value": "desc"
                                },
                                {
                                    "label": "Ascending",
                                    "value": "asc"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "find-user",
                "displayName": "Find User(s)",
                "description": "Search users by email, name, role, or other criteria.",
                "props": {
                    "search_type": {
                        "displayName": "Search Type",
                        "description": "Choose how to search for users",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Search by Email",
                                    "value": "email"
                                },
                                {
                                    "label": "Search by Name",
                                    "value": "name"
                                },
                                {
                                    "label": "Search by Role",
                                    "value": "role"
                                },
                                {
                                    "label": "Search by Organization",
                                    "value": "organization"
                                },
                                {
                                    "label": "Search by Tag",
                                    "value": "tag"
                                },
                                {
                                    "label": "Search by External ID",
                                    "value": "external_id"
                                },
                                {
                                    "label": "Custom Query",
                                    "value": "custom"
                                }
                            ]
                        }
                    },
                    "email": {
                        "displayName": "Email Address",
                        "description": "The email address of the user to search for",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "name": {
                        "displayName": "Name",
                        "description": "The name of the user to search for",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "role": {
                        "displayName": "Role",
                        "description": "Search users by role",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "End User",
                                    "value": "end-user"
                                },
                                {
                                    "label": "Agent",
                                    "value": "agent"
                                },
                                {
                                    "label": "Admin",
                                    "value": "admin"
                                }
                            ]
                        }
                    },
                    "organization": {
                        "displayName": "Organization",
                        "description": "Search users by organization name",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "tag": {
                        "displayName": "Tag",
                        "description": "Search users containing this tag",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "external_id": {
                        "displayName": "External ID",
                        "description": "Search users by external ID",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "custom_query": {
                        "displayName": "Custom Query",
                        "description": "Custom search query using Zendesk search syntax (e.g., \"type:user role:agent\")",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "sort_by": {
                        "displayName": "Sort By",
                        "description": "How to sort the results",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Relevance (Default)",
                                    "value": "relevance"
                                },
                                {
                                    "label": "Created Date",
                                    "value": "created_at"
                                },
                                {
                                    "label": "Updated Date",
                                    "value": "updated_at"
                                }
                            ]
                        }
                    },
                    "sort_order": {
                        "displayName": "Sort Order",
                        "description": "Sort order for results",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Descending (Default)",
                                    "value": "desc"
                                },
                                {
                                    "label": "Ascending",
                                    "value": "asc"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-zendesk-sell",
        "name": "Zendesk-sell",
        "description": "Sales CRM for pipeline management, lead tracking, and contact organization.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/zendesk-sell.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zerobounce",
        "name": "ZeroBounce",
        "description": "ZeroBounce is an email validation service that helps you reduce bounces, improve email deliverability and increase email marketing ROI.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/zerobounce.png",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoho-bookings",
        "name": "Zoho Bookings",
        "description": "Zoho Bookings is an appointment scheduling software for managing bookings, services, and customer appointments.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/zoho-bookings.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoho-books",
        "name": "Zoho Books",
        "description": "Comprehensive online accounting software for small businesses.",
        "category": "finance",
        "icon": "https://cdn.activepieces.com/pieces/zoho-books.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoho-campaigns",
        "name": "Zoho Campaigns",
        "description": "Zoho Campaigns is an email marketing platform for managing mailing lists, sending campaigns, tracking engagement, and automating subscriber workflows.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/zoho-campaigns.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoho-crm",
        "name": "Zoho CRM",
        "description": "Customer relationship management software",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/zoho-crm.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoho-desk",
        "name": "Zoho Desk",
        "description": "Helpdesk management software",
        "category": "support",
        "icon": "https://cdn.activepieces.com/pieces/zoho-desk.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoho-invoice",
        "name": "Zoho Invoice",
        "description": "Online invoicing software for businesses",
        "category": "finance",
        "icon": "https://cdn.activepieces.com/pieces/zoho-invoice.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoho-mail",
        "name": "Zoho Mail",
        "description": "Zoho Mail is a powerful email service that allows you to manage your email, contacts, and calendars efficiently.",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/zoho-mail.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoo",
        "name": "Zoo",
        "description": "Generate and iterate on 3D models from text descriptions using ML endpoints.",
        "category": "other",
        "icon": "https://cdn.activepieces.com/pieces/zoo.jpg",
        "color": "#6366F1",
        "authType": "api_key",
        "triggers": [],
        "actions": []
    },
    {
        "id": "@activepieces/piece-zoom",
        "name": "Zoom",
        "description": "Video conferencing, web conferencing, webinars, screen sharing",
        "category": "communication",
        "icon": "https://cdn.activepieces.com/pieces/zoom.png",
        "color": "#6366F1",
        "authType": "oauth2",
        "triggers": [],
        "actions": [
            {
                "name": "zoom_create_meeting",
                "displayName": "Create Zoom Meeting",
                "description": "Create a new Zoom Meeting",
                "props": {
                    "topic": {
                        "displayName": "Meeting's topic",
                        "description": "The meeting's topic",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "start_time": {
                        "displayName": "Start Time",
                        "description": "Meeting start date-time",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "duration": {
                        "displayName": "Duration (in Minutes)",
                        "description": "Duration of the meeting",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    },
                    "auto_recording": {
                        "displayName": "Auto Recording",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Local",
                                    "value": "local"
                                },
                                {
                                    "label": "Cloud",
                                    "value": "cloud"
                                },
                                {
                                    "label": "None",
                                    "value": "none"
                                }
                            ]
                        }
                    },
                    "audio": {
                        "displayName": "Audio",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Both telephony and VoIP",
                                    "value": "both"
                                },
                                {
                                    "label": "Telephony only",
                                    "value": "telephony"
                                },
                                {
                                    "label": "VoIP only",
                                    "value": "voip"
                                },
                                {
                                    "label": "Third party audio conference",
                                    "value": "thirdParty"
                                }
                            ]
                        }
                    },
                    "agenda": {
                        "displayName": "Agenda",
                        "description": "The meeting's agenda",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "password": {
                        "displayName": "Password",
                        "description": "The password required to join the meeting. By default, a password can only have a maximum length of 10 characters and only contain alphanumeric characters and the @, -, _, and * characters.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "pre_schedule": {
                        "displayName": "Pre Schedule",
                        "description": "Whether the prescheduled meeting was created via the GSuite app.",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "schedule_for": {
                        "displayName": "Schedule for",
                        "description": "The email address or user ID of the user to schedule a meeting for.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "join_url": {
                        "displayName": "Join URL",
                        "description": "URL for participants to join the meeting.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    }
                }
            },
            {
                "name": "zoom_create_meeting_registrant",
                "displayName": "Create Zoom Meeting Registrant",
                "description": "Create and submit a user's registration to a meeting.",
                "props": {
                    "meeting_id": {
                        "displayName": "Meeting ID",
                        "description": "The meeting ID.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "first_name": {
                        "displayName": "First name",
                        "description": "The registrant's first name.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "last_name": {
                        "displayName": "Last name",
                        "description": "The registrant's last name.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "email": {
                        "displayName": "Email",
                        "description": "The registrant's email address.",
                        "type": "SHORT_TEXT",
                        "required": true,
                        "defaultValue": null
                    },
                    "address": {
                        "displayName": "Address",
                        "description": "The registrant's address",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "city": {
                        "displayName": "City",
                        "description": "The registrant's city",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "state": {
                        "displayName": "State",
                        "description": "The registrant's state or province.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "zip": {
                        "displayName": "Zip",
                        "description": "The registrant's zip or postal code.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "country": {
                        "displayName": "Country",
                        "description": "The registrant's two-letter country code.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "phone": {
                        "displayName": "Phone",
                        "description": "The registrant's phone number.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "comments": {
                        "displayName": "Comments",
                        "description": "The registrant's questions and comments.",
                        "type": "LONG_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "custom_questions": {
                        "displayName": "Custom questions",
                        "description": "",
                        "type": "OBJECT",
                        "required": false,
                        "defaultValue": null
                    },
                    "industry": {
                        "displayName": "Industry",
                        "description": "The registrant's industry.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "job_title": {
                        "displayName": "Job title",
                        "description": "The registrant's job title.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "no_of_employees": {
                        "displayName": "No of employees",
                        "description": "The registrant's number of employees.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "1-20",
                                    "value": "1-20"
                                },
                                {
                                    "label": "21-50",
                                    "value": "21-50"
                                },
                                {
                                    "label": "51-100",
                                    "value": "51-100"
                                },
                                {
                                    "label": "101-500",
                                    "value": "101-500"
                                },
                                {
                                    "label": "500-1,000",
                                    "value": "500-1,000"
                                },
                                {
                                    "label": "1,001-5,000",
                                    "value": "1,001-5,000"
                                },
                                {
                                    "label": "5,001-10,000",
                                    "value": "5,001-10,000"
                                },
                                {
                                    "label": "More than 10,000",
                                    "value": "More than 10,000"
                                }
                            ]
                        }
                    },
                    "org": {
                        "displayName": "Organization",
                        "description": "The registrant's organization.",
                        "type": "SHORT_TEXT",
                        "required": false,
                        "defaultValue": null
                    },
                    "purchasing_time_frame": {
                        "displayName": "Purchasing time frame",
                        "description": "The registrant's purchasing time frame.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Within a month",
                                    "value": "Within a month"
                                },
                                {
                                    "label": "1-3 months",
                                    "value": "1-3 months"
                                },
                                {
                                    "label": "4-6 months",
                                    "value": "4-6 months"
                                },
                                {
                                    "label": "More than 6 months",
                                    "value": "More than 6 months"
                                },
                                {
                                    "label": "No timeframe",
                                    "value": "No timeframe"
                                }
                            ]
                        }
                    },
                    "role_in_purchase_process": {
                        "displayName": "Role in purchase process",
                        "description": "The registrant's role in the purchase process.",
                        "type": "STATIC_DROPDOWN",
                        "required": false,
                        "defaultValue": null,
                        "options": {
                            "disabled": false,
                            "options": [
                                {
                                    "label": "Decision Maker",
                                    "value": "Decision Maker"
                                },
                                {
                                    "label": "Evaluator/Recommender",
                                    "value": "Evaluator/Recommender"
                                },
                                {
                                    "label": "Influencer",
                                    "value": "Influencer"
                                },
                                {
                                    "label": "Not involved",
                                    "value": "Not involved"
                                }
                            ]
                        }
                    }
                }
            },
            {
                "name": "custom_api_call",
                "displayName": "Custom API Call",
                "description": "Make a custom API call to a specific endpoint",
                "props": {
                    "url": {
                        "displayName": "",
                        "description": "",
                        "type": "DYNAMIC",
                        "required": true,
                        "defaultValue": null
                    },
                    "method": {
                        "displayName": "Method",
                        "description": "",
                        "type": "STATIC_DROPDOWN",
                        "required": true,
                        "defaultValue": null,
                        "options": {
                            "options": [
                                {
                                    "label": "GET",
                                    "value": "GET"
                                },
                                {
                                    "label": "POST",
                                    "value": "POST"
                                },
                                {
                                    "label": "PATCH",
                                    "value": "PATCH"
                                },
                                {
                                    "label": "PUT",
                                    "value": "PUT"
                                },
                                {
                                    "label": "DELETE",
                                    "value": "DELETE"
                                },
                                {
                                    "label": "HEAD",
                                    "value": "HEAD"
                                }
                            ]
                        }
                    },
                    "headers": {
                        "displayName": "Headers",
                        "description": "Authorization headers are injected automatically from your connection.",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "queryParams": {
                        "displayName": "Query Parameters",
                        "description": "",
                        "type": "OBJECT",
                        "required": true,
                        "defaultValue": null
                    },
                    "body": {
                        "displayName": "Body",
                        "description": "",
                        "type": "JSON",
                        "required": false,
                        "defaultValue": null
                    },
                    "response_is_binary": {
                        "displayName": "Response is Binary ?",
                        "description": "Enable for files like PDFs, images, etc..",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": false
                    },
                    "failsafe": {
                        "displayName": "No Error on Failure",
                        "description": "",
                        "type": "CHECKBOX",
                        "required": false,
                        "defaultValue": null
                    },
                    "timeout": {
                        "displayName": "Timeout (in seconds)",
                        "description": "",
                        "type": "NUMBER",
                        "required": false,
                        "defaultValue": null
                    }
                }
            }
        ]
    },
    {
        "id": "@activepieces/piece-zuora",
        "name": "Zuora",
        "description": "Cloud-based subscription management platform that enables businesses to launch and monetize subscription services.",
        "category": "crm",
        "icon": "https://cdn.activepieces.com/pieces/zuora.png",
        "color": "#6366F1",
        "authType": "none",
        "triggers": [],
        "actions": []
    }
];
