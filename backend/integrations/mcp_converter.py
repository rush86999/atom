from typing import Any

class MCPToolConverter:
    @staticmethod
    def convert_to_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Converts a list of MCP tools to OpenAI's function calling format.
        """
        openai_tools = []
        for tool in tools:
            # Basic JSON Schema construction from simplified parameter mapping
            properties = {}
            required = []
            
            for param_name, param_desc in tool.get("parameters", {}).items():
                # Heuristic: Parse description to infer type if possible, else default to string
                param_type = "string"
                if "integer" in param_desc.lower() or "number" in param_desc.lower():
                    param_type = "number"
                elif "array" in param_desc.lower() or "list" in param_desc.lower():
                    param_type = "array"
                elif "object" in param_desc.lower() or "dict" in param_desc.lower():
                    param_type = "object"
                elif "boolean" in param_desc.lower():
                    param_type = "boolean"
                
                properties[param_name] = {
                    "type": param_type,
                    "description": str(param_desc)
                }
                
                # Assume all parameters are optional unless marked required (or just leave required empty for leniency)
                # But typically for function calling we might want to specify strictness.
                # For now, let's leave required empty to avoid validation errors on missing args.

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "additionalProperties": False  # Best practice for OpenAI
                    }
                }
            })
        return openai_tools
