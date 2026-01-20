
try:
    with open("server_v4.log", "rb") as f:
        content = f.read().decode("utf-16-le", errors="replace")
    
    with open("crash.txt", "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Converted server.log to crash.txt")
except Exception as e:
    print(f"Failed: {e}")
