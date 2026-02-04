import os
import string


def sanitize_env_file(file_path):
    try:
        print(f"Sanitizing {file_path}...")
        with open(file_path, 'rb') as f:
            content = f.read()
            
        # Decode with ignore to drop bad bytes
        text = content.decode('utf-8', errors='ignore')
        
        # Split into lines
        lines = text.splitlines()
        
        clean_lines = []
        printable = set(string.printable)
        
        for line in lines:
            # Remove null bytes explicitly
            line = line.replace('\x00', '')
            
            # Filter non-printable characters (except newline which is stripped by splitlines)
            clean_line = ''.join(filter(lambda x: x in printable, line))
            
            if clean_line.strip():
                clean_lines.append(clean_line)
        
        # Join with proper newlines
        new_content = '\n'.join(clean_lines)
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"Sanitized {len(lines)} lines to {len(clean_lines)} clean lines.")
        
    except Exception as e:
        print(f"Error sanitizing .env file: {e}")

if __name__ == "__main__":
    if os.path.exists('backend/.env'):
        sanitize_env_file('backend/.env')
    if os.path.exists('.env'):
        sanitize_env_file('.env')
