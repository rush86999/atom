
import os

try:
    with open('verification_result.txt', 'rb') as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - 2000))
        content = f.read()
        
    # specific decode for utf-16-le which is common on windows redirection
    try:
        text = content.decode('utf-16', errors='ignore')
    except:
        text = content.decode('utf-8', errors='ignore')

    print(text)
    
except Exception as e:
    print(f"Error: {e}")
