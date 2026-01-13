# Scalable Browser Agent

![](https://img.shields.io/badge/-BrowserUse-black?style=flat&logo=github)
![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-success?style=flat&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?style=flat&logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7-red?style=flat&logo=redis)


This platform is designed to deploy and operate a scalable **queue-based browser agent (browser-use)** execution environment on Kubernetes. 

By processing **self-hosted browser-use requests** through an **Asynchronous (job) + Queue (queue) + Worker (worker)** architecture, it minimizes operational issues such as **concurrent request spikes**, **long-running executions**, **failure tracking**, and **horizontal scaling** with a minimal configuration.

### Features (MVP)

* **Queue-based async execution**: The API returns a `job_id` immediately, while the actual execution is handled asynchronously by the Worker.
* **Horizontal scalability**: Automatically scales Worker replicas via KEDA based on Redis Streams consumer group lag.
* **Job tracking**: Permanently store job status (QUEUED/RUNNING/SUCCEEDED/FAILED) along with results/errors (including tracebacks) in PostgreSQL.
* **Queue consumer-group**: Ensures safe job distribution across multiple Worker instances.
* **Kubernetes deployment**: Supports standard K8s operational workflows including rollouts, restarts, and scaling.

## Architecture
<img width="2086" height="678" alt="image" src="https://github.com/user-attachments/assets/287e2a59-7d5c-46b8-b053-10ce9cf09ab3" />


### Core Stack

* **API / Orchestrator**: FastAPI
* **Queue**: Redis Streams
* **Worker**: Python Worker + browser-use + Playwright (Chromium, headless)
* **Database**: PostgreSQL (Stores job status/result/error)

> **Goal**: "Queue agent requests → Process safely via Workers → Provide results/status in a searchable format."

## Prerequisites

#### **Kubernetes**

* A Kubernetes cluster (k3s, kind, EKS, GKE, etc., are all supported)
* `kubectl` access
* KEDA (installed in the cluster) for event-driven autoscaling
* Prometheus + Grafana (for metrics and autoscaling observability)
* Loki + Alloy (for centralized log collection)

#### **Credentials / Secrets**

* LLM Provider API Key (e.g., `GOOGLE_API_KEY` for Google Gemini)
* (Recommended) Inject via Secrets/Environment Variables

> **Note**: The Worker runs Playwright Chromium in headless mode. The Worker image must include the necessary dependencies for running a browser within the cluster.

## Quickstart

This repository is designed to be installed and operated using the deployment manifests located in `k8s/`.

### 1) Install

```bash
git clone https://github.com/squatboy/scalable-browser-agent.git
cd scalable-browser-agent
```

### 2) Create namespace

```bash
kubectl create ns sba
```

### 3) Create secrets

Please check the `env/secretRef` configuration in the deployment manifest for required secret keys. Generally, the following values are required:

```bash
kubectl -n sba create secret generic sba-secrets \
  --from-literal=GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY" \
  --from-literal=POSTGRES_PASSWORD="YOUR_POSTGRES_PASSWORD"
```

> **Note**: Actual key names and secret names must match the manifests in `k8s/`.

### 4) Apply manifests

```bash
kubectl apply -k k8s/base
```

### 5) Verify

```bash
kubectl -n sba get pods -o wide
kubectl -n sba get svc
```

## Accessing the API

* **NodePort (Current MVP Stage)**
* Service type: If exposed as a NodePort, you can access the API via `NODE_IP:<nodePort>` of the cluster node.
* For external access, you can expose the Orchestrator via NodePort and access it as `http://<NODE_PUBLIC_IP>:<NODEPORT>` (e.g., `/docs`, `/healthz`). For production, consider Ingress + TLS + Auth.


```bash
kubectl -n sba get svc orchestrator
# PORT(S): 8000:<nodePort>/TCP
```

## API Reference

### 1) Run an agent job

**POST** `/v1/run-agent`

* **Request**

```bash
curl -s -X POST http://127.0.0.1:8000/v1/run-agent \
  -H "Content-Type: application/json" \
  -d '{
  "task":"Go to https://news.ycombinator.com/ and return top 5 stories."
  }'
```

* **Response**

```json
{ "job_id": "..." }
```

### 2) Get job status/result

**GET** `/v1/jobs/{job_id}`

* **Request**

```bash
curl -s http://127.0.0.1:8000/v1/jobs/<JOB_ID>
```

* **Response (example)**

```json
{
  "job_id": "...",
  "agent_id": "browser-use-generic",
  "status": "SUCCEEDED",
  "result": { "raw": "..." },
  "error": null
}
```

> **Tip**: In the MVP, `browser-use-generic` stores the result directly in `result.raw` without parsing. If you need structured (JSON) results, specify a format like "Return ONLY JSON ..." in your task.

## Troubleshooting

### 1) relation "jobs" does not exist

* **Symptom**: Orchestrator returns a 500 error indicating the `jobs` table does not exist.
* **Cause**: PostgreSQL schema (tables) have not been created yet.
* **Resolution**: Check if the DB migration job has completed.

```bash
kubectl -n sba get job
kubectl -n sba logs job/db-migrate
```

### 2) API Key not set

* **Symptom**: `GOOGLE_API_KEY is not set` appears in Worker logs.
* **Resolution**: Check Kubernetes Secret/Env settings and redeploy.

### 3) Job stuck in RUNNING

* **Cause**: Site response delay / Browser execution issues / No external network access / Worker hang.
* **Action**: Check Worker logs and GC CronJob logs.  
  A GC CronJob periodically enforces job timeouts (e.g., `JOB_TIMEOUT_SECONDS`), expires stale QUEUED jobs, and cleans up old finished jobs based on retention policy.


## Roadmap

* [x] KEDA-based autoscaling (Automatic worker scaling based on Redis backlog)
* [ ] Helm chart support
* [x] Observability: metrics / tracing / structured logs
* [ ] Retry/backoff, timeout, cancellation, DLQ
* [ ] Ingress + TLS + Auth (production-ready access)
* [ ] Multi-tenant / per-tenant quota / budget-aware scheduling
