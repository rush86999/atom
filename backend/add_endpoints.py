"""
Add health and root endpoints to main API
"""
lines_to_add = '''

# Add health endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "ATOM Platform Backend is running",
        "version": "1.0.0"
    }

# Add root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "ATOM Platform",
        "description": "Complete AI-powered automation platform",
        "status": "running",
        "docs": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5058)
'''

# Read current file
with open('main_api_app.py', 'r') as f:
    content = f.read()

# Add the new endpoints
content += lines_to_add

# Write back to file
with open('main_api_app.py', 'w') as f:
    f.write(content)

print("✅ Health and root endpoints added to main API")