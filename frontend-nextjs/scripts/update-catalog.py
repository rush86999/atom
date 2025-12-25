import requests
import json
import os

# API Endpoint for Activepieces pieces
PIECES_API = "https://cloud.activepieces.com/api/v1/pieces"

# Mapping Activepieces categories to Atom categories
CATEGORY_MAP = {
    'MARKETING': 'marketing',
    'SALES_AND_CRM': 'crm',
    'PRODUCTIVITY': 'productivity',
    'COMMUNICATION': 'communication',
    'DEV_TOOLS': 'developer',
    'STORAGE': 'storage',
    'DATABASE': 'database',
    'COMMERCE': 'ecommerce',
    'CUSTOMER_SUPPORT': 'support',
    'FORMS_AND_SURVEYS': 'forms',
    'ACCOUNTING': 'finance',
    'SECURITY': 'security',
    'IOT': 'iot',
    'MEDIA': 'media',
    'EDUCATION': 'education',
}

def fetch_pieces():
    print(f"Fetching pieces from {PIECES_API}...")
    try:
        response = requests.get(PIECES_API)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching pieces: {e}")
        return []

# List of pieces to fetch detailed metadata for (to avoid 559+ API calls)
DETAILED_PIECES = [
    '@activepieces/piece-slack',
    '@activepieces/piece-gmail',
    '@activepieces/piece-salesforce',
    '@activepieces/piece-hubspot',
    '@activepieces/piece-google-drive',
    '@activepieces/piece-google-sheets',
    '@activepieces/piece-google-calendar',
    '@activepieces/piece-openai',
    '@activepieces/piece-github',
    '@activepieces/piece-discord',
    '@activepieces/piece-stripe',
    '@activepieces/piece-jira',
    '@activepieces/piece-notion',
    '@activepieces/piece-asana',
    '@activepieces/piece-trello',
    '@activepieces/piece-airtable',
    '@activepieces/piece-zendesk',
    '@activepieces/piece-zoom',
    '@activepieces/piece-calendly',
    '@activepieces/piece-mailchimp',
    '@activepieces/piece-shopify',
    '@activepieces/piece-quickbooks',
    '@activepieces/piece-linear',
    '@activepieces/piece-figma',
]

def fetch_piece_details(piece_name):
    print(f"  Fetching details for {piece_name}...")
    try:
        url = f"{PIECES_API}/{piece_name}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching details for {piece_name}: {e}")
        return None

def simplify_props(props):
    simplified = {}
    if not props:
        return simplified
    
    for key, prop in props.items():
        simplified[key] = {
            'displayName': prop.get('displayName', key),
            'description': prop.get('description', ''),
            'type': prop.get('type', 'SHORT_TEXT'),
            'required': prop.get('required', False),
            'defaultValue': prop.get('defaultValue')
        }
        # Handle options for dropdowns
        if 'options' in prop:
            simplified[key]['options'] = prop['options']
            
    return simplified

def extract_actions_triggers(piece_details):
    actions = []
    triggers = []
    
    if not piece_details:
        return actions, triggers
        
    # Extract actions
    ap_actions = piece_details.get('actions', {})
    for act_name, act in ap_actions.items():
        actions.append({
            'name': act_name,
            'displayName': act.get('displayName', act_name),
            'description': act.get('description', ''),
            'props': simplify_props(act.get('props', {}))
        })
        
    # Extract triggers
    ap_triggers = piece_details.get('triggers', {})
    for trig_name, trig in ap_triggers.items():
        triggers.append({
            'name': trig_name,
            'displayName': trig.get('displayName', trig_name),
            'description': trig.get('description', ''),
            'props': simplify_props(trig.get('props', {}))
        })
        
    return actions, triggers

def map_piece_to_integration(piece, detailed=False):
    # Determine category
    ap_categories = piece.get('categories') or []
    atom_category = 'other'
    for cap in ap_categories:
        if cap in CATEGORY_MAP:
            atom_category = CATEGORY_MAP[cap]
            break
    
    # Determine auth type
    auth = piece.get('auth')
    auth_type = 'none'
    if auth:
        if isinstance(auth, list):
            auth_item = auth[0] if auth else {}
        else:
            auth_item = auth
            
        auth_type_str = str(auth_item.get('type', '')).upper() if isinstance(auth_item, dict) else ''
        if 'OAUTH2' in auth_type_str:
            auth_type = 'oauth2'
        elif 'SECRET' in auth_type_str or 'API_KEY' in auth_type_str:
            auth_type = 'api_key'
        elif 'BASIC' in auth_type_str:
            auth_type = 'basic'

    actions = []
    triggers = []
    
    if detailed:
        actions, triggers = extract_actions_triggers(piece)

    return {
        'id': piece.get('name'),
        'name': piece.get('displayName'),
        'description': piece.get('description', ''),
        'category': atom_category,
        'icon': piece.get('logoUrl'),
        'color': '#6366F1',
        'authType': auth_type,
        'triggers': triggers,
        'actions': actions
    }

def main():
    pieces = fetch_pieces()
    if not pieces:
        return

    integrations = []
    for piece in pieces:
        name = piece.get('name')
        if name in DETAILED_PIECES:
            detailed_piece = fetch_piece_details(name)
            if detailed_piece:
                integrations.append(map_piece_to_integration(detailed_piece, detailed=True))
            else:
                integrations.append(map_piece_to_integration(piece))
        else:
            integrations.append(map_piece_to_integration(piece))

    print(f"Processed {len(integrations)} pieces.")
    
    # Generate the TypeScript code
    ts_code = "export const AUTO_GENERATED_PIECES: any[] = " # Use any[] since structure is complex
    ts_code += json.dumps(integrations, indent=4)
    ts_code += ";\n"
    
    # Save to lib directory directly for seeding
    output_path = os.path.join(os.path.dirname(__file__), "../lib/auto-generated-pieces.ts")
    with open(output_path, "w") as f:
        f.write(ts_code)
    
    print(f"Saved {len(integrations)} integrations to {output_path}")

if __name__ == "__main__":
    main()
