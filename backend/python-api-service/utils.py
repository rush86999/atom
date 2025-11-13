"""
Utility functions for ATOM API service
"""

import uuid
import re
from datetime import datetime
from typing import Dict, Any, Optional

def generate_uuid() -> str:
    """Generate a unique identifier"""
    return str(uuid.uuid4())

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_user_data(data: Dict[str, Any], partial: bool = False) -> Optional[str]:
    """Validate user data"""
    if not partial:
        required_fields = ['email', 'password', 'name']
        for field in required_fields:
            if field not in data:
                return f'{field} is required'

    if 'email' in data and not validate_email(data['email']):
        return 'Invalid email format'

    if 'password' in data and len(data['password']) < 8:
        return 'Password must be at least 8 characters long'

    if 'name' in data and len(data['name'].strip()) < 2:
        return 'Name must be at least 2 characters long'

    return None

def validate_task_data(data: Dict[str, Any], partial: bool = False) -> Optional[str]:
    """Validate task data"""
    if not partial:
        if 'title' not in data:
            return 'Title is required'

    if 'title' in data and len(data['title'].strip()) < 1:
        return 'Title cannot be empty'

    if 'status' in data and data['status'] not in ['pending', 'in_progress', 'completed']:
        return 'Invalid status. Must be pending, in_progress, or completed'

    if 'priority' in data and data['priority'] not in ['low', 'medium', 'high', 'critical']:
        return 'Invalid priority. Must be low, medium, high, or critical'

    if 'due_date' in data:
        try:
            datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return 'Invalid due_date format. Use ISO format.'

    return None

def validate_calendar_event_data(data: Dict[str, Any], partial: bool = False) -> Optional[str]:
    """Validate calendar event data"""
    if not partial:
        required_fields = ['title', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return f'{field} is required'

    if 'title' in data and len(data['title'].strip()) < 1:
        return 'Title cannot be empty'

    if 'color' in data and not re.match(r'^#[0-9A-Fa-f]{6}$', data['color']):
        return 'Invalid color format. Use hex color (e.g., #FF0000)'

    for time_field in ['start_time', 'end_time']:
        if time_field in data:
            try:
                datetime.fromisoformat(data[time_field].replace('Z', '+00:00'))
            except ValueError:
                return f'Invalid {time_field} format. Use ISO format.'

    if 'start_time' in data and 'end_time' in data:
        start = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
        if end <= start:
            return 'End time must be after start time'

    return None

def validate_workflow_data(data: Dict[str, Any], partial: bool = False) -> Optional[str]:
    """Validate workflow data"""
    if not partial:
        required_fields = ['name', 'triggers', 'actions']
        for field in required_fields:
            if field not in data:
                return f'{field} is required'

    if 'name' in data and len(data['name'].strip()) < 1:
        return 'Name cannot be empty'

    if 'triggers' in data and not isinstance(data['triggers'], list):
        return 'Triggers must be a list'

    if 'actions' in data and not isinstance(data['actions'], list):
        return 'Actions must be a list'

    return None

def validate_transaction_data(data: Dict[str, Any], partial: bool = False) -> Optional[str]:
    """Validate transaction data"""
    if not partial:
        required_fields = ['date', 'description', 'amount', 'category', 'type']
        for field in required_fields:
            if field not in data:
                return f'{field} is required'

    if 'amount' in data and (not isinstance(data['amount'], (int, float)) or data['amount'] < 0):
        return 'Amount must be a positive number'

    if 'type' in data and data['type'] not in ['debit', 'credit']:
        return 'Type must be debit or credit'

    if 'date' in data:
        try:
            datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
        except ValueError:
            return 'Invalid date format. Use ISO format.'

    return None

def sanitize_string(text: str, max_length: int = 1000) -> str:
    """Sanitize and truncate string input"""
    if not text:
        return ''
    # Remove potentially harmful characters
    sanitized = re.sub(r'[<>]', '', text)
    return sanitized[:max_length]

def format_datetime(dt: datetime) -> str:
    """Format datetime to ISO string"""
    return dt.isoformat() + 'Z'

def parse_datetime(date_str: str) -> datetime:
    """Parse ISO datetime string"""
    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))

def calculate_age(birth_date: datetime) -> int:
    """Calculate age from birth date"""
    today = datetime.utcnow()
    age = today.year - birth_date.year
    if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
        age -= 1
    return age

def generate_api_key() -> str:
    """Generate a secure API key"""
    return str(uuid.uuid4()) + str(uuid.uuid4()).replace('-', '')

def hash_string(text: str) -> str:
    """Generate a simple hash for non-sensitive data"""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()

def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text with suffix"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))*)?$'
    return re.match(pattern, url) is not None

def extract_domain_from_email(email: str) -> str:
    """Extract domain from email address"""
    try:
        return email.split('@')[1].lower()
    except IndexError:
        return ''

def generate_slug(text: str) -> str:
    """Generate URL-friendly slug from text"""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug.strip('-')

def format_currency(amount: float, currency: str = 'USD') -> str:
    """Format amount as currency"""
    return f"{currency} {amount:,.2f}"

def calculate_percentage(part: float, total: float) -> float:
    """Calculate percentage safely"""
    if total == 0:
        return 0.0
    return (part / total) * 100

def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    try:
        return filename.split('.')[-1].lower()
    except IndexError:
        return ''

def is_image_file(filename: str) -> bool:
    """Check if file is an image"""
    image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'}
    return get_file_extension(filename) in image_extensions

def generate_random_string(length: int = 8) -> str:
    """Generate a random string"""
    import random
    import string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries"""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result

def flatten_dict(d: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
    """Flatten nested dictionary"""
    items = []
    for k, v in d.items():
        new_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)

def get_nested_value(d: Dict[str, Any], keys: list, default=None) -> Any:
    """Get nested value from dictionary"""
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return default
    return d

def set_nested_value(d: Dict[str, Any], keys: list, value: Any) -> None:
    """Set nested value in dictionary"""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value

def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> list:
    """Basic JSON schema validation (simplified)"""
    errors = []

    def validate_object(obj, schema_obj, path=''):
        if not isinstance(schema_obj, dict):
            return

        for key, rules in schema_obj.items():
            current_path = f"{path}.{key}" if path else key

            if rules.get('required', False) and key not in obj:
                errors.append(f"Missing required field: {current_path}")
                continue

            if key in obj:
                value = obj[key]
                expected_type = rules.get('type')

                if expected_type and not isinstance(value, eval(expected_type)):
                    errors.append(f"Invalid type for {current_path}: expected {expected_type}")

                if 'min_length' in rules and len(str(value)) < rules['min_length']:
                    errors.append(f"Value too short for {current_path}: minimum {rules['min_length']}")

                if 'max_length' in rules and len(str(value)) > rules['max_length']:
                    errors.append(f"Value too long for {current_path}: maximum {rules['max_length']}")

                if 'enum' in rules and value not in rules['enum']:
                    errors.append(f"Invalid value for {current_path}: must be one of {rules['enum']}")

    validate_object(data, schema)
    return errors
