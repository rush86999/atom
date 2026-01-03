
try:
    with open("git_log.txt", "r", encoding="utf-16-le") as f:
        content = f.read()
except Exception as e:
    print(f"Failed to read utf-16-le: {e}")
    # Try default encoding if that failed, maybe it wasn't utf-16
    with open("git_log.txt", "r") as f:
        content = f.read()

with open("git_log_utf8.txt", "w", encoding="utf-8") as f:
    f.write(content)
print("Conversion complete")
