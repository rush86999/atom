try:
    import bcrypt
    print("BCRYPT_AVAILABLE = True")
except ImportError:
    print("BCRYPT_AVAILABLE = False")
