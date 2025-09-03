import subprocess

def install_dependencies():
    """
    Installs the required dependencies for the personalized learning assistant feature.
    """
    dependencies = [
        "fastapi",
        "uvicorn",
        "requests",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
        "notion-client",
        "rake-nltk",
    ]
    for dependency in dependencies:
        subprocess.run(["pip", "install", dependency])
