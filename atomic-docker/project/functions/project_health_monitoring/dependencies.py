import subprocess

def install_dependencies():
    """
    Installs the required dependencies for the project health monitoring feature.
    """
    dependencies = [
        "fastapi",
        "uvicorn",
        "requests",
        "GitPython",
        "slack_sdk",
        "vaderSentiment",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
    ]
    for dependency in dependencies:
        subprocess.run(["pip", "install", dependency])
