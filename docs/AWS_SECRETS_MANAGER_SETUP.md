# AWS Secrets Manager — Setup Checklist

What the repo already has vs what you still need to do.

---

## Already in the repo

| Item | Location |
|------|----------|
| Loader | `src/core/secrets_loader.py` — loads secret JSON into env (only missing keys) |
| Startup | `main.py` — after `load_dotenv()`, if `USE_AWS_SECRETS=true` calls loader |
| JSON template | `config/aws-secret-template.json` — keys to put in the AWS secret |
| Env example | `config/env.example` — USE_AWS_SECRETS, AWS_SECRET_NAME, AWS_REGION, credentials |
| Dependency | `pyproject.toml` — `boto3` |

---

## What you still need to do

### 1. In AWS Console

- [ ] **Create the secret**  
  Secrets Manager → Store a new secret → Plaintext → paste JSON (from `config/aws-secret-template.json` with real values).  
  Name it e.g. `prod/agentic-evaluator/env`. Note the **secret name** and **region**.

- [ ] **Credentials to access the secret** (pick one):
  - **Option A — IAM user (local / first time):**
    - [ ] Create IAM user.
    - [ ] Create policy with `secretsmanager:GetSecretValue` on that secret (or `secret:*` in that region).
    - [ ] Attach policy to user.
    - [ ] Create **Access Key** for user → you get **Access Key ID** and **Secret Access Key**.
  - **Option B — IAM role (app on EC2/ECS/Lambda):**
    - [ ] Attach to instance/task/function an IAM role that has the same `GetSecretValue` policy.
    - No access keys needed; AWS injects credentials.

### 2. Environment variables (when you want to use Secrets Manager)

Set these where the app runs (e.g. `.env` for local, or platform env for production):

| Variable | Required | Example |
|----------|----------|---------|
| `USE_AWS_SECRETS` | Yes (to enable) | `true` |
| `AWS_SECRET_NAME` | Yes | `prod/agentic-evaluator/env` |
| `AWS_REGION` | Yes | `ap-southeast-1` |
| `AWS_ACCESS_KEY_ID` | If not using IAM role | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | If not using IAM role | `xxxx...` |

If using IAM role (EC2/ECS/Lambda), leave `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` unset.

### 3. Fill the secret JSON in AWS

Use the keys from `config/aws-secret-template.json`. Set real values in AWS for at least:

- `GEMINI_APIKEY`, `OPENROUTER_API_KEY`, `QDRANT_API_KEY`, `API_KEYS` (or `API_KEY`)
- `REDIS_URL` or `REDIS_PASSWORD` (+ optional `REDIS_USERNAME`)
- `POSTGRES_PASSWORD` or `POSTGRES_URL`
- Optional: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`

---

## Quick test (after setup)

1. Set in env: `USE_AWS_SECRETS=true`, `AWS_SECRET_NAME=...`, `AWS_REGION=...`, and credentials if not using a role.
2. Run the app; check logs for: `Loaded N secret(s) from AWS Secrets Manager (...)`.
3. If boto3 is missing or secret not found, the loader skips and the app still runs using only env.

---

## Summary: what was “missing” before

- **Env example:** Added `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` placeholders.
- **Docs:** This checklist so you know what’s in the repo vs what to do in AWS and in env.
- **Your side:** Create secret in AWS, set IAM (user + keys or role), set the env vars above when you want to use Secrets Manager.
