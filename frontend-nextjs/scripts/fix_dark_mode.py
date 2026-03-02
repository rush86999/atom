import os
import re

SEARCH_DIRS = ['c:/Users/Mannan Bajaj/atom/frontend-nextjs/components', 'c:/Users/Mannan Bajaj/atom/frontend-nextjs/pages']

CLASS_MAP = {
    'bg-white': 'dark:bg-gray-900',
    'text-gray-900': 'dark:text-gray-100',
    'text-gray-800': 'dark:text-gray-200',
    'text-gray-700': 'dark:text-gray-300',
    'text-gray-600': 'dark:text-gray-400',
    'text-gray-500': 'dark:text-gray-400',
    'text-black': 'dark:text-white',
    
    'bg-gray-50': 'dark:bg-gray-800',
    'bg-gray-100': 'dark:bg-gray-800',
    'bg-gray-200': 'dark:bg-gray-800',
    
    'border-gray-100': 'dark:border-gray-800',
    'border-gray-200': 'dark:border-gray-700',
    'border-gray-300': 'dark:border-gray-600',
    
    'bg-slate-50': 'dark:bg-slate-900',
    'bg-slate-100': 'dark:bg-slate-800',
    'bg-slate-200': 'dark:bg-slate-800',
    
    'text-slate-900': 'dark:text-slate-100',
    'text-slate-800': 'dark:text-slate-200',
    'text-slate-700': 'dark:text-slate-300',
    'text-slate-600': 'dark:text-slate-400',
    'text-slate-500': 'dark:text-slate-400',
    
    'border-slate-100': 'dark:border-slate-800',
    'border-slate-200': 'dark:border-slate-700',
}

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        return

    original_content = content
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        new_line = line
        for light_class, dark_class in CLASS_MAP.items():
            if re.search(r'\b' + light_class + r'\b', new_line):
                prefix = 'dark:bg-' if 'bg-' in dark_class else ('dark:text-' if 'text-' in dark_class else 'dark:border-')
                
                # Check if the line already contains a dark variant for this specific property
                if not re.search(r'\b' + prefix, new_line):
                    new_line = re.sub(r'\b' + light_class + r'\b', f"{light_class} {dark_class}", new_line)
        new_lines.append(new_line)
        
    new_content = '\n'.join(new_lines)
    
    if new_content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

def main():
    for d in SEARCH_DIRS:
        for root, dirs, files in os.walk(d):
            for file in files:
                if file.endswith('.tsx') or file.endswith('.jsx'):
                    process_file(os.path.join(root, file))

if __name__ == '__main__':
    main()
