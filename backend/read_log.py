try:
    with open("verification_log.txt", "r", encoding="utf-16") as f:
        print(f.read())
except Exception:
    try:
        with open("verification_log.txt", "r") as f:
            print(f.read())
    except Exception as e:
        print(e)
