# Advanced API Workflows

Multi-step examples that chain API calls to accomplish real tasks.

## Workflow: Chat Session → Feedback → Check Learning

End-to-end: send a message, give feedback, verify the router learned.

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user@example.com","password":"MySecurePass123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Send a message — capture the session_id
SESSION=$(curl -s -X POST http://localhost:8001/api/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Help me analyze my sales data","user_id":"default_user","session_id":"new","context":{}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id','unknown'))")

echo "Session: $SESSION"

# 3. Give thumbs-down feedback
curl -s -X POST http://localhost:8001/api/chat/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message_id\":\"msg_1\",\"feedback\":\"thumbs_down\",\"comment\":\"Too vague\"}"

# 4. Check routing stats
curl -s -H "Authorization: Bearer $TOKEN" \
     http://localhost:8001/api/chat/routing-stats | python3 -m json.tool
```

## Workflow: Excel Spreadsheet Lifecycle

Create a spreadsheet, add formulas, evaluate, insert rows, read results.

```bash
FILE="data/demo.xlsx"

# 1. Write data
curl -s -X POST http://localhost:8001/api/v1/office/excel \
  -H "Content-Type: application/json" \
  -d "{\"file_path\":\"$FILE\",\"cell_path\":\"/Sheet1/A1\",\"value\":100}"

curl -s -X POST http://localhost:8001/api/v1/office/excel \
  -H "Content-Type: application/json" \
  -d "{\"file_path\":\"$FILE\",\"cell_path\":\"/Sheet1/A2\",\"value\":200}"

# 2. Add a formula — response includes computed value
curl -s -X POST http://localhost:8001/api/v1/office/excel \
  -H "Content-Type: application/json" \
  -d "{\"file_path\":\"$FILE\",\"cell_path\":\"/Sheet1/A3\",\"value\":\"=SUM(A1:A2)\",\"is_formula\":true}"
# → {"success":true,"value":300,"formula":"=SUM(A1:A2)"}

# 3. Insert a row (formulas auto-update)
curl -s -X POST "http://localhost:8001/api/v1/office/excel/insert-rows?file_path=$FILE&sheet_name=Sheet1&row=2&count=1"

# 4. Read the evaluated result
curl -s "http://localhost:8001/api/v1/office/excel/formula-result?file_path=$FILE&cell_path=/Sheet1/A4"
```

## Workflow: Canvas Create → Update → Delete

Full canvas CRUD lifecycle via the API.

```bash
CANVAS="demo_$(date +%s)"

# 1. Create
curl -s -X PUT "http://localhost:8001/api/canvas/$CANVAS?canvas_type=sheets&title=Q4+Budget" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":[["Item","Amount"],["Rent","3000"]]}'

# 2. Read
curl -s -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8001/api/canvas/$CANVAS" | python3 -m json.tool

# 3. Update
curl -s -X PUT "http://localhost:8001/api/canvas/$CANVAS?canvas_type=sheets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":[["Item","Amount"],["Rent","3200"],["Marketing","5000"]]}'

# 4. History
curl -s -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8001/api/canvas/$CANVAS/history" | python3 -m json.tool

# 5. Delete
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8001/api/canvas/$CANVAS"
```

## Workflow: Local Model → Discover → Route

Register an Ollama model and verify it appears as a routing candidate.

```bash
# 1. Register Ollama
PROVIDER=$(curl -s -X POST http://localhost:8001/api/local-models \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Ollama","provider_type":"ollama","base_url":"http://localhost:11434/v1"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")

# 2. Discover models
curl -s -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8001/api/local-models/$PROVIDER/models" | python3 -m json.tool

# 3. Set capabilities
curl -s -X POST "http://localhost:8001/api/local-models/$PROVIDER/capabilities" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_id":"llama3:8b","supports_tools":true,"quality_score":0.7,"speed_score":0.8,"context_window":8192}'

# 4. Chat — check which model was used
curl -s -X POST http://localhost:8001/api/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","user_id":"default_user","session_id":"new","context":{}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Model: {d.get(\"model\")}')"
```

## Workflow: Federation Identity Lifecycle

Create a DID, issue a credential, verify a request.

```bash
# 1. Create a DID
DID=$(curl -s -X POST http://localhost:8001/api/federation/dids \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_type":"agent","entity_id":"agent_001"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('did',''))")

echo "DID: $DID"

# 2. Issue a credential
curl -s -X POST http://localhost:8001/api/federation/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"issuer_did\":\"$DID\",\"credential_type\":\"AgentIdentityCredential\",\"subject_did\":\"$DID\",\"claims\":{\"name\":\"Test Agent\"}}"

# 3. Verify a request
curl -s -X POST http://localhost:8001/api/federation/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"method":"GET","path":"/api/resource","action":"read","resource_type":"generic"}' \
  | python3 -m json.tool
```
