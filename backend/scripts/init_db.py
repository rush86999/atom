import sqlite3
import os

# Database file path
DB_FILE = "backend/atom_data.db"

def init_db():
    print(f"Initializing database: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Create users table (Adapted for SQLite)
    # Removing gen_random_uuid() default, will handle in app
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT,
        email_verified TIMESTAMP,
        image TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create password_reset_tokens table (Adapted for SQLite)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        used BOOLEAN DEFAULT 0
    );
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);")

    # Create test user if not exists
    cursor.execute("SELECT id FROM users WHERE email = 'test@example.com'")
    if not cursor.fetchone():
        print("Creating test user...")
        # Password is 'password' hashed (placeholder hash)
        # In real app, use bcrypt.hash("password")
        # For now, we'll use a dummy hash or rely on the mock auth in NextAuth
        # But since we are implementing real auth endpoints, we should use real hashing.
        # Let's import passlib if available, or just use a simple string for now since we are mocking login in NextAuth anyway.
        # Wait, the user wants REAL password reset flow. So we need real hashing.
        
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed_password = pwd_context.hash("password")
        except ImportError:
            print("passlib not found, using raw password (INSECURE - DEV ONLY)")
            hashed_password = "password"

        import uuid
        user_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO users (id, email, password_hash, name) VALUES (?, ?, ?, ?)",
            (user_id, "test@example.com", hashed_password, "Test User")
        )

    conn.commit()
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
