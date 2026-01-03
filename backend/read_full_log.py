with open("verify_output.log", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()
    print("".join(lines[-30:]))
