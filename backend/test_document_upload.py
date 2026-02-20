
import requests
import os
import datetime
import sys

# Try to import jose for token generation
try:
    from jose import jwt
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False
    print("Warning: python-jose not installed, cannot generate token")

BASE_URL = "http://localhost:8000"
SECRET_KEY = "atom_secure_secret_2025_fixed_key"
ALGORITHM = "HS256"

def generate_token():
    if not JOSE_AVAILABLE:
        return None
    
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    to_encode = {"sub": "00000000-0000-0000-0000-000000000000", "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def test_upload():
    print("Testing Document Upload...")
    
    token = generate_token()
    if not token:
        print("❌ Failed to generate token")
        return False

    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a dummy file
    with open("test_upload.txt", "w") as f:
        f.write("This is a test document for the Atom Knowledge Base.")

    try:
        with open("test_upload.txt", "rb") as f:
            files = {'file': ('test_upload.txt', f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/api/documents/upload", files=files, headers=headers)
        
        if response.status_code == 200:
            print("✅ Upload Success!")
            print(response.json())
            return True
        else:
            print(f"❌ Upload Failed: {response.status_code}")
            with open("upload_error.log", "w") as f:
                f.write(response.text)
            print("Error details saved to upload_error.log")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    finally:
        if os.path.exists("test_upload.txt"):
            os.remove("test_upload.txt")

if __name__ == "__main__":
    test_upload()
