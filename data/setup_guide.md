# 🎯 Langfuse v3.8.1 Observability Setup Guide

## 📦 Step 1: Install Dependencies

```bash
pip install langfuse>=3.8.1 opentelemetry-api opentelemetry-sdk
```

Or add to your `requirements.txt`:
```
langfuse>=3.8.1
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0
```

---

## 🔑 Step 2: Get Langfuse Credentials

### Option A: Cloud (Recommended)
1. Go to [https://cloud.langfuse.com](https://cloud.langfuse.com)
2. Sign up for free account
3. Create a new project
4. Go to Settings → API Keys
5. Copy your **Public Key** (`pk-lf-...`) and **Secret Key** (`sk-lf-...`)

### Option B: Self-Hosted
1. Deploy Langfuse: https://langfuse.com/docs/deployment/self-host
2. Get credentials from your instance

---

## ⚙️ Step 3: Configure Environment Variables

Create or update your `.env` file:

```bash
# Existing Google Configuration
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# Langfuse v3 Configuration
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key-here
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key-here
LANGFUSE_HOST=https://cloud.langfuse.com

# Optional: Enable/disable Langfuse (default: true)
LANGFUSE_ENABLED=true

# Optional: Sampling rate (0.0 to 1.0) - useful for production
LANGFUSE_SAMPLE_RATE=1.0

# Optional: Debug mode
LANGFUSE_DEBUG=false
```

---

## 🚀 Step 4: Update Your Application

### A. Add Startup Initialization

**Create: `src/utils/langfuse_startup.py`**

Use the file I provided in the artifacts above.

### B. Update Your `main.py`

**CRITICAL:** Initialize Langfuse BEFORE importing other modules:

```python
from fastapi import FastAPI

# ⚠️ MUST BE FIRST: Initialize Langfuse v3
from src.utils.langfuse_startup import initialize_langfuse_v3, get_langfuse_status

# Initialize (creates singleton)
initialize_langfuse_v3()

# Now import your routes (they can safely use get_client())
from src.routes import agent, storage, search

app = FastAPI()

@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shutdown Langfuse"""
    from langfuse import get_client
    client = get_client()
    if client:
        client.flush()
        client.shutdown()
```

### C. Update Import Statements

In ALL files that use Langfuse, change:

**❌ OLD (v2):**
```python
from langfuse.decorators import langfuse_context, observe
from langfuse.callback import CallbackHandler
```

**✅ NEW (v3.8.1):**
```python
from langfuse import observe, get_client
from langfuse.langchain import CallbackHandler  # If using LangChain
```

### D. Update Helper Functions

Use the updated files I provided:
- `src/utils/langfuse_helper.py` (v3 API)
- `src/utils/llm_helper.py` (v3 callback)
- All workflow node files (v3 decorators)

---

## ✅ Step 5: Verify Installation

### Test 1: Check Configuration
```bash
python -c "from src.utils.config import LANGFUSE_CONFIGURED; print('✅ OK' if LANGFUSE_CONFIGURED else '❌ Failed')"
```

### Test 2: Check Initialization
```bash
python -c "from src.utils.langfuse_startup import get_langfuse_status; import json; print(json.dumps(get_langfuse_status(), indent=2))"
```

Expected output:
```json
{
  "initialized": true,
  "configured": true,
  "enabled": true,
  "host": "https://cloud.langfuse.com"
}
```

### Test 3: Test Connection
```python
# test_langfuse.py
from src.utils.langfuse_startup import initialize_langfuse_v3
from langfuse import get_client

# Initialize
if initialize_langfuse_v3():
    print("✅ Langfuse initialized")
    
    # Get client
    client = get_client()
    if client:
        print("✅ Client accessible")
        
        # Test simple trace
        from langfuse import observe
        
        @observe(name="test_function")
        def test():
            return "Hello from Langfuse v3!"
        
        result = test()
        print(f"✅ Test function result: {result}")
        
        # Flush
        client.flush()
        print("✅ Events flushed")
        
        print("\n🎉 All tests passed! Check your Langfuse dashboard.")
    else:
        print("❌ Client not accessible")
else:
    print("❌ Initialization failed")
```

Run it:
```bash
python test_langfuse.py
```

---

## 🧪 Step 6: Test with Real Request

### Start Your Application:
```bash
uvicorn main:app --reload
```

Check startup logs for:
```
✅ Langfuse v3 initialized successfully (host: https://cloud.langfuse.com)
✅ Langfuse client connection verified
```

### Upload a Test File:
```bash
curl -X POST "http://localhost:8000/api/agent" \
  -F "file=@demo_report.pdf"
```

---

## 📊 Step 7: View Traces in Langfuse Dashboard

1. Go to https://cloud.langfuse.com
2. Select your project
3. Click **"Traces"** in the left sidebar
4. You should see your trace:

```
📊 process_single_report_direct
├── 📄 extraction_node
│   └── 🤖 gemini_extraction
├── ✅ content_validation
│   └── 🤖 validation_llm
├── 📊 analyze_demo_trial
│   └── 🤖 analysis_llm
├── 📈 graph_suggestion_generation
│   └── 🤖 graph_llm
└── ⚖️ output_evaluation
    └── 🤖 evaluation_llm
```

---

## 🎯 Key Differences from v2

### 1. **Initialization Pattern**
- **v3:** Explicit `Langfuse()` call at startup, then `get_client()` everywhere
- **v2:** Automatic initialization

### 2. **Import Location**
- **v3:** `from langfuse import observe, get_client`
- **v2:** `from langfuse.decorators import observe, langfuse_context`

### 3. **Client Access**
- **v3:** `langfuse = get_client()`
- **v2:** `langfuse_context`

### 4. **LangChain Callback**
- **v3:** `from langfuse.langchain import CallbackHandler`
- **v2:** `from langfuse.callback import CallbackHandler`

### 5. **Flush/Shutdown**
- **v3:** `get_client().flush()` and `get_client().shutdown()`
- **v2:** `langfuse_context.flush()`

---

## 🐛 Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'langfuse.decorators'`
**Solution:** You're using v3 but have v2 imports. Update all imports to v3 API.

### Issue: `AttributeError: 'NoneType' object has no attribute 'update_current_trace'`
**Solution:** `get_client()` returned `None`. Ensure `Langfuse()` is initialized at startup.

### Issue: Traces not appearing
**Solution:**
1. Check that `initialize_langfuse_v3()` is called BEFORE any route imports
2. Verify credentials in `.env`
3. Check logs for initialization errors
4. Call `client.flush()` before shutdown

### Issue: "Langfuse not initialized" warning
**Solution:** Import `langfuse_startup` at the top of `main.py` before other imports.

---

## 📚 Additional Resources

- **v3 Migration Guide:** https://langfuse.com/docs/sdk/python/upgrade-path
- **v3 Documentation:** https://langfuse.com/docs/sdk/python/example
- **Python Decorator Guide:** https://langfuse.com/docs/sdk/python/decorators
- **LangChain Integration (v3):** https://langfuse.com/docs/integrations/langchain/upgrade-paths

---

## 🎉 You're All Set!

Your application now has enterprise-grade observability with Langfuse v3.8.1:
- ✅ Full trace visibility
- ✅ LLM call tracking
- ✅ Token & cost monitoring
- ✅ Error tracking
- ✅ Performance analytics
- ✅ v3 OpenTelemetry foundation

Start processing files and watch your traces in the dashboard! 📊🚀
