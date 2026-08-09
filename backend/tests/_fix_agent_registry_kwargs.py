import glob
import re

files = glob.glob("tests/error_paths/*.py")
pat = re.compile(r"AgentRegistry\([^)]*\)", re.S)
changed = []
for f in files:
    src = open(f).read()
    orig = src

    def repl(m):
        text = m.group(0)
        if "module_path" in text:
            return text
        body = text[len("AgentRegistry(") : -1]
        stripped = body.rstrip()
        if stripped.endswith(","):
            return "AgentRegistry(" + body + 'module_path="test.module", class_name="TestAgent")'
        return "AgentRegistry(" + body + ', module_path="test.module", class_name="TestAgent")'

    src = pat.sub(repl, src)
    if src != orig:
        open(f, "w").write(src)
        changed.append(f)
print("changed:", changed)
