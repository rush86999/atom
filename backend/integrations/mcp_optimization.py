import json
from typing import List, Dict, Any, Optional

class MCPContextOptimizer:
    """
    Optimizes Model Context Protocol (MCP) tool definitions for Small Language Models (SLMs).
    Implements schema minification (TS/Python signatures) and grammar generation (GBNF).
    """

    @staticmethod
    def _extract_properties(tool: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper to normalize parameter extraction.
        Supports both standard JSON Schema (parameters.properties) and
        simplified Atom-style (parameters being a direct dict of name->type).
        """
        params = tool.get("parameters", {})
        if "properties" in params and isinstance(params["properties"], dict):
            # Standard JSON Schema
            return params["properties"]
        else:
            # Simplified format: {"arg1": "type1", "arg2": "type2"}
            # We normalize this to {"arg1": {"type": "type1"}, ...}
            return {k: {"type": v} if isinstance(v, str) else v for k, v in params.items()}

    @staticmethod
    def _extract_required(tool: Dict[str, Any]) -> List[str]:
        """
        Helper to extract required fields.
        """
        params = tool.get("parameters", {})
        if "required" in params and isinstance(params["required"], list):
            return params["required"]

        # In simplified format, assume all are required unless marked optional?
        # Or just return empty list if not specified.
        # For this codebase's simplified format, explicit 'required' list is missing in the dicts I saw.
        # But we can assume if it's in the dict, it's an argument.
        # Let's treat all as optional by default unless we know better, or required.
        # Reviewing mcp_service.py: parameters are just "query": "string".
        # Let's assume all are optional to be safe, or just rely on 'required' if present.
        return []

    @staticmethod
    def to_typescript_interfaces(tools: List[Dict[str, Any]]) -> str:
        """
        Converts a list of MCP tool definitions (JSON Schema) into TypeScript interfaces.
        Reduces token usage by removing JSON syntax noise.
        """
        output = []
        for tool in tools:
            name = tool.get("name")
            description = tool.get("description", "")

            properties = MCPContextOptimizer._extract_properties(tool)
            required = MCPContextOptimizer._extract_required(tool)

            # Docstring
            ts_interface = f"// {description}\n"
            ts_interface += f"type {name} = (_: {{\n"

            for prop_name, prop_def in properties.items():
                # prop_def might be just a dict with 'type' now
                raw_type = prop_def.get("type", "any")
                prop_type = MCPContextOptimizer._map_json_type_to_ts(raw_type)

                is_required = prop_name in required
                # If simplified format, we don't know required, so maybe treat as optional (?)
                # or just optional to match '?'
                optional_marker = "?" if not is_required else ""

                # Handle enum constraints
                if "enum" in prop_def:
                    enum_values = prop_def["enum"]
                    prop_type = " | ".join([f'"{v}"' for v in enum_values])

                ts_interface += f"  {prop_name}{optional_marker}: {prop_type},\n"

            ts_interface += "}) => any;"
            output.append(ts_interface)

        return "\n\n".join(output)

    @staticmethod
    def to_python_signatures(tools: List[Dict[str, Any]]) -> str:
        """
        Converts tool definitions to Python function signatures.
        Ideal for code-trained models like Mistral, NexusRaven, CodeLlama.
        """
        output = []
        for tool in tools:
            name = tool.get("name")
            description = tool.get("description", "")

            properties = MCPContextOptimizer._extract_properties(tool)
            required = MCPContextOptimizer._extract_required(tool)

            args_list = []
            docstring_args = []

            for prop_name, prop_def in properties.items():
                raw_type = prop_def.get("type", "Any")
                prop_type = MCPContextOptimizer._map_json_type_to_python(raw_type)
                default_val = "" if prop_name in required else " = None"

                args_list.append(f"{prop_name}: {prop_type}{default_val}")

                desc = prop_def.get('description', '') if isinstance(prop_def, dict) else ''
                docstring_args.append(f"    {prop_name} ({prop_type}): {desc}")

            args_str = ", ".join(args_list)

            sig = f"def {name}({args_str}):\n"
            sig += f'    """\n    {description}\n\n'
            if docstring_args:
                sig += "    Args:\n" + "\n".join(docstring_args) + "\n"
            sig += '    """\n    pass'
            output.append(sig)

        return "\n\n".join(output)

    @staticmethod
    def generate_gbnf_grammar(tools: List[Dict[str, Any]]) -> str:
        """
        Generates a GBNF (Grammar-Based Normalization Form) string for Llama.cpp.
        This forces the model to output valid JSON for the available tools.
        """
        # Basic GBNF structure

        tool_names = []

        # We need to construct the root rule dynamically
        root_rules = []

        gbnf_rules = ""

        for tool in tools:
            name = tool.get("name")
            properties = MCPContextOptimizer._extract_properties(tool)
            required = MCPContextOptimizer._extract_required(tool)

            tool_names.append(f'"\\"{name}\\""')
            root_rules.append(f"{name}_call")

            # Define the specific call structure for this tool
            args_rule = MCPContextOptimizer._build_object_gbnf(properties, required)
            gbnf_rules += f'{name}_call ::= "{{" space "\\"tool\\"" space ":" space "\\"_{name}\\"" space "," space "\\"args\\"" space ":" space {name}_args "}}" space\n'
            gbnf_rules += f'{name}_args ::= {args_rule}\n'

        gbnf = "root ::= " + " | ".join(root_rules) + "\n"
        gbnf += "space ::= [ \\t\\n]*\n"
        gbnf += gbnf_rules

        # Add primitive rules
        gbnf += """
string ::= "\\"" ([^"\\\\] | "\\\\" (["\\\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\\""
number ::= ("-"? ([0-9]+) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?)
boolean ::= "true" | "false"
null ::= "null"
array ::= "[" space (value ("," space value)*)? "]"
value ::= string | number | boolean | null | object | array
object ::= "{" space (member ("," space member)*)? "}"
member ::= string space ":" space value
"""
        return gbnf

    @staticmethod
    def _build_object_gbnf(properties: Dict[str, Any], required: List[str]) -> str:
        """
        Constructs a GBNF rule for a JSON object with specific properties.
        This is a simplified builder.
        """
        if not properties:
            return '"{" space "}"'

        elements = []
        for prop_name, prop_def in properties.items():
            prop_rule = MCPContextOptimizer._get_gbnf_type_rule(prop_def)
            elements.append(f'"\\"{prop_name}\\"" space ":" space {prop_rule}')

        # Combine elements with commas
        # For PoC, we are strict about order/presence to guarantee simple grammar
        content = ' space "," space '.join(elements)
        return f'"{{ " space {content} space "}}"'

    @staticmethod
    def _get_gbnf_type_rule(prop_def: Dict[str, Any]) -> str:
        t = prop_def.get("type", "string")
        # Handle string like "list[str]" or "string (optional)"
        if "list" in t or "array" in t:
            return "array"
        if "dict" in t:
            return "object"
        if "number" in t or "int" in t:
            return "number"
        if "bool" in t:
            return "boolean"

        # Default to string
        if "enum" in prop_def:
            opts = [f'"\\"{v}\\""' for v in prop_def["enum"]]
            return "(" + " | ".join(opts) + ")"
        return "string"

    @staticmethod
    def _map_json_type_to_ts(json_type: str) -> str:
        # Handle complex strings like "list[str]" or "string (optional)"
        json_type = json_type.lower()

        if "list" in json_type or "array" in json_type:
            if "str" in json_type: return "string[]"
            return "any[]"
        if "dict" in json_type:
            return "Record<string, any>"
        if "number" in json_type or "int" in json_type:
            return "number"
        if "bool" in json_type:
            return "boolean"

        mapping = {
            "string": "string",
            "integer": "number",
            "number": "number",
            "boolean": "boolean",
            "null": "null"
        }
        # Clean up "string (optional)" -> "string"
        if "(" in json_type:
            base = json_type.split("(")[0].strip()
            return mapping.get(base, "any")

        return mapping.get(json_type, "any")

    @staticmethod
    def _map_json_type_to_python(json_type: str) -> str:
        json_type = json_type.lower()

        if "list" in json_type or "array" in json_type:
            return "List[Any]"
        if "dict" in json_type:
            return "Dict[str, Any]"
        if "number" in json_type or "int" in json_type:
            return "Union[int, float]"
        if "bool" in json_type:
            return "bool"

        mapping = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "null": "None"
        }
        if "(" in json_type:
            base = json_type.split("(")[0].strip()
            return mapping.get(base, "Any")

        return mapping.get(json_type, "Any")
