# Homelab DevOps: Zero to Hero Lesson Plan

## Your lab environment

| Node | Hostname | IP | Role |
|---|---|---|---|
| Control | kubeman.jay.home.arpa | 192.168.1.20 | k3s server, Argo CD, dev workstation |
| Worker 1 | k3s-worker-1 | 192.168.1.21 | Apps, observability |
| Worker 2 | k3s-worker-2 | 192.168.1.22 | ROS/sim, CI runner |

---

## Unit 1: What is a monorepo and why does it matter?

### The concept

A monorepo is a single Git repository that holds multiple projects, services, and infrastructure code. Instead of having `python-api-repo`, `cpp-node-repo`, `ros-packages-repo`, and `infra-repo` as separate repos, everything lives under one roof.

### Why companies use monorepos

When a robotics company has Python services, C++ components, ROS packages, Dockerfiles, Helm charts, and CI/CD pipelines, keeping them in separate repos creates real problems. A change to a shared library means opening pull requests across 5 repos, hoping they all merge in the right order, and praying nothing breaks in between. A monorepo lets you make a single commit that updates the library, fixes the services that use it, updates the Docker images, and adjusts the CI pipeline — all reviewed and merged atomically.

### What you built

```
homelab-devops/
├── services/
│   ├── python-api/        # A deployable microservice
│   └── cpp-node/          # Will hold C++ code later
├── ros/
│   └── robot_sim/         # ROS 2 simulation package
├── infra/
│   ├── helm/              # Kubernetes deployment definitions
│   └── k8s/               # Raw manifests (Argo CD app definitions)
├── scripts/               # Build, test, and automation scripts
└── .github/workflows/     # CI/CD pipeline definitions
```

### The key insight for interviews

The `paths:` filter in your GitHub Actions workflow is how monorepos stay fast. When you change a file in `services/python-api/`, only the `python-api.yml` workflow runs. The C++ pipeline doesn't trigger. The ROS pipeline doesn't trigger. This is called **selective CI** and it's one of the first things interviewers ask about when the job mentions monorepos.

### What to say in an interview

> "I structured the repo so each service owns its source code, tests, Dockerfile, and Helm chart in its own subtree. CI pipelines use path filters to only build what changed. This keeps build times fast even as the repo grows. For a production monorepo I'd consider Bazel or Turborepo for smarter caching across dependent packages."

### Key terms to know

- **Monorepo**: Single repository, multiple projects. Opposite of "polyrepo."
- **Path filtering**: CI only triggers when files in a specific directory change.
- **Atomic commits**: One commit touches multiple services, deployed together.
- **Build caching**: Reusing previous build outputs when inputs haven't changed.
- **Code ownership**: CODEOWNERS files define who reviews what part of the monorepo.

---

## Unit 2: Containers and Docker — packaging your software

### The concept

A container is a lightweight, portable package that bundles your application code with everything it needs to run: the OS libraries, the language runtime, the dependencies. When you write a Dockerfile, you're writing a recipe that says "start with Python 3.11, install these packages, copy my code, and here's how to run it."

### Why this matters for the job

The job description says "design, build, and maintain containerized environments for development, testing, and production." That means you'll own the Dockerfiles. If a developer says "it works on my machine but not in CI," you'll debug the container. If images are 2GB and taking 10 minutes to build, you'll optimize them.

### What you built

```dockerfile
FROM python:3.11-slim          # Base image — slim means minimal OS
WORKDIR /app                   # Set the working directory inside the container
COPY requirements.txt .        # Copy dependencies list first (layer caching trick)
RUN pip install --no-cache-dir -r requirements.txt  # Install dependencies
COPY src/ .                    # Copy application code
EXPOSE 8080                    # Document which port the app uses
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]  # Start command
```

### Breaking down each line — what it really does

**`FROM python:3.11-slim`** — Every container starts from a base image. `slim` means Debian with just enough to run Python, about 120MB instead of 900MB. In production you might use `python:3.11-alpine` (even smaller) or a custom base image your company maintains.

**`COPY requirements.txt .` then `RUN pip install` before `COPY src/ .`** — This is a layer caching strategy. Docker builds images in layers, and if a layer hasn't changed, Docker reuses the cached version. By copying and installing dependencies before copying your source code, you only re-install dependencies when `requirements.txt` changes. If you only changed `main.py`, Docker skips the pip install entirely. This can save minutes on every build.

**`--no-cache-dir`** — Tells pip not to save downloaded packages. Inside a container there's no reason to cache them because you'll never pip install again — the image is immutable.

**`EXPOSE 8080`** — This doesn't actually open the port. It's documentation that tells other engineers (and Kubernetes) which port the app listens on.

### Commands you need to know cold

```bash
# Build an image and tag it
docker build -t jayjalil89/python-api:latest .

# Run a container from the image
docker run -d -p 8080:8080 jayjalil89/python-api:latest

# List running containers
docker ps

# Check container logs
docker logs <container-id>

# Get a shell inside a running container (for debugging)
docker exec -it <container-id> /bin/bash

# Push to Docker Hub
docker push jayjalil89/python-api:latest

# List images on your machine
docker images

# Remove old images to free disk space
docker image prune -a
```

### Optimization concepts for interviews

- **Multi-stage builds**: Use one stage to compile/build, copy only the output to a second minimal stage. Critical for C++ and Go where the build toolchain is huge but the binary is small.
- **Layer ordering**: Put things that change rarely (OS packages, dependencies) early in the Dockerfile, things that change often (your code) last.
- **Image scanning**: Tools like Trivy scan your images for known vulnerabilities in OS packages and dependencies. This is a production requirement at most companies.
- **Base image pinning**: Use `python:3.11.9-slim` not `python:3.11-slim` so your builds are reproducible.

### What to say in an interview

> "I follow a layered caching strategy — dependencies are installed before application code is copied so that code changes don't invalidate the pip install layer. For C++ services I use multi-stage builds to keep the final image small. I scan images with Trivy in CI before pushing to the registry. In production I'd pin base image digests for reproducibility."

---

## Unit 3: Kubernetes fundamentals — what you're actually controlling

### The concept

Kubernetes (k8s) is an orchestrator. You tell it "I want 2 copies of my Python API running at all times" and it figures out which machines to put them on, restarts them if they crash, and routes traffic to them. You don't SSH into servers and start processes — you declare what you want and Kubernetes makes it happen.

### The architecture — what's running on your VMs

**kubeman.jay.home.arpa (192.168.1.20)** runs the k3s **server**. This is the control plane — it stores the cluster state in etcd, runs the API server that `kubectl` talks to, and runs the scheduler that decides which node gets each pod. You never run application workloads here.

**k3s-worker-1 (192.168.1.21)** and **k3s-worker-2 (192.168.1.22)** run the k3s **agents**. These are the worker nodes where your actual containers run. Each agent has a kubelet (talks to the control plane), a container runtime (containerd — runs the actual containers), and a kube-proxy (handles networking).

### The resource hierarchy — from big to small

```
Cluster (your 3 VMs)
  └── Nodes (kubeman, k3s-worker-1, k3s-worker-2)
       └── Namespaces (apps, argocd, monitoring)
            └── Deployments (python-api)
                 └── ReplicaSets (managed automatically)
                      └── Pods (the actual running containers)
                           └── Containers (your Docker image running)
```

### Core resources explained

**Pod** — The smallest deployable unit. Usually one container, but can hold multiple containers that share networking and storage. When people say "my pod is crashing," they mean their container inside the pod is failing.

**Deployment** — Manages pods. You say "I want 2 replicas of python-api" and the Deployment creates a ReplicaSet that ensures 2 pods are always running. If one dies, it creates a replacement. When you update the image, it does a rolling update — creating new pods before killing old ones.

**Service** — A stable network endpoint for a set of pods. Pods get random IPs that change when they restart. A Service provides a fixed DNS name (`python-api.apps.svc.cluster.local`) and load-balances traffic across all matching pods.

**Namespace** — A virtual cluster inside your cluster. You have `apps` for your services, `argocd` for Argo CD, and you'll add `monitoring` for Prometheus/Grafana. Namespaces provide isolation — resources in one namespace don't see resources in another by default.

**ConfigMap / Secret** — Configuration data. ConfigMaps hold non-sensitive config (environment variables, config files). Secrets hold sensitive data (passwords, API keys). Both are injected into pods at runtime.

**Node labels** — Metadata you attach to nodes. You labeled `k3s-worker-1` with `workload=apps` and `k3s-worker-2` with `workload=robotics`. Your Helm chart uses `nodeSelector: workload: apps` to ensure Python API pods land on worker-1, not worker-2. This is how you manage **heterogeneous workloads** — different types of work on different machines.

### kubectl commands you need to know cold

```bash
# ----- Viewing things -----
kubectl get nodes                          # List all nodes
kubectl get pods -n apps                   # List pods in the apps namespace
kubectl get pods -n apps -o wide           # Same but with node and IP info
kubectl get svc -n apps                    # List services
kubectl get deployments -n apps            # List deployments
kubectl get all -n apps                    # List everything in a namespace
kubectl get namespaces                     # List all namespaces

# ----- Debugging -----
kubectl describe pod <pod-name> -n apps    # Detailed info + events (your go-to for debugging)
kubectl logs <pod-name> -n apps            # Container stdout/stderr
kubectl logs <pod-name> -n apps -f         # Follow logs in real-time
kubectl logs <pod-name> -n apps --previous # Logs from previous crashed container

# ----- Interacting -----
kubectl exec -it <pod-name> -n apps -- /bin/bash   # Shell into a pod
kubectl port-forward svc/python-api 8080:80 -n apps # Forward local port to service

# ----- Modifying -----
kubectl apply -f manifest.yaml             # Create or update resources from a file
kubectl delete pod <pod-name> -n apps      # Delete a pod (Deployment recreates it)
kubectl rollout restart deployment python-api -n apps  # Restart all pods in a deployment
kubectl scale deployment python-api --replicas=3 -n apps  # Scale up/down

# ----- Cluster info -----
kubectl get nodes --show-labels            # See node labels
kubectl top nodes                          # CPU/memory usage per node (needs metrics-server)
kubectl top pods -n apps                   # CPU/memory usage per pod
```

### The debugging flow — how you solved ErrImagePull

When your pods showed `ErrImagePull`, here's the systematic debugging approach you used:

1. **`kubectl get pods -n apps`** — See the status. `ErrImagePull` tells you the image can't be downloaded.
2. **`kubectl describe pod <name> -n apps`** — Read the Events section at the bottom. It told you exactly what image it was trying to pull and why it failed: "pull access denied, repository does not exist."
3. **Diagnose** — The image `jayjalil89/python-api:latest` didn't exist on Docker Hub because CI hadn't run yet.
4. **Fix** — Manually built and pushed the image, then restarted the deployment.

This is the exact debugging loop you'll use on the job. The `describe` command is your best friend — it shows events, conditions, and the full spec of any resource.

### What to say in an interview

> "I run a 3-node k3s cluster with one control plane node and two workers. I use node labels and nodeSelectors to schedule different workload types to appropriate nodes — general services on one worker, compute-heavy robotics simulations on another. For debugging, I start with `kubectl get pods` to see status, then `kubectl describe` for events, then `kubectl logs` for application output. The most common issues I've hit are image pull errors from registry auth, pods in CrashLoopBackOff from missing environment variables, and scheduling failures from node affinity misconfiguration."

---

## Unit 4: Helm — templating your Kubernetes deployments

### The concept

Without Helm, deploying a service to Kubernetes means writing a Deployment YAML, a Service YAML, maybe an Ingress, a ConfigMap, a ServiceAccount — each one with your service name, image, port, and resource limits hardcoded. If you have 10 services, you have 50 YAML files with a lot of copy-paste.

Helm solves this with templates. You write the YAML once with placeholders like `{{ .Values.image.repository }}`, and a `values.yaml` file that fills in the blanks. Each service gets its own `values.yaml` — same template, different configuration.

### What you built — the anatomy of a Helm chart

```
infra/helm/python-api/
├── Chart.yaml              # Metadata: chart name, version
├── values.yaml             # The knobs you turn: image, replicas, resources
└── templates/
    ├── deployment.yaml     # Deployment template with {{ }} placeholders
    └── service.yaml        # Service template
```

### values.yaml — the configuration surface

```yaml
image:
  repository: jayjalil89/python-api    # Which image to pull
  tag: latest                          # Which version
  pullPolicy: Always                   # Always check for new image

replicaCount: 2                        # How many pods to run

resources:
  requests:                            # Minimum guaranteed resources
    cpu: 100m                          # 100 millicores = 10% of one CPU core
    memory: 128Mi                      # 128 megabytes
  limits:                              # Maximum allowed resources
    cpu: 250m                          # Pod is throttled above this
    memory: 256Mi                      # Pod is killed (OOMKilled) above this

nodeSelector:
  workload: apps                       # Only schedule on nodes with this label
```

### Resource units explained

- **CPU**: Measured in millicores. `1000m` = 1 full CPU core. `100m` = 10% of a core. `requests` is what the scheduler guarantees; `limits` is the ceiling.
- **Memory**: `Mi` = mebibytes (1024-based), `Gi` = gibibytes. If a container exceeds its memory limit, Kubernetes kills it (OOMKilled).
- **Requests vs limits**: Requests are used for scheduling — the scheduler only places a pod on a node with enough free requested resources. Limits are enforced at runtime. Setting requests too high wastes capacity; setting limits too low causes kills.

### Helm commands you need to know

```bash
# Install a chart (first time)
helm install python-api infra/helm/python-api --namespace apps --create-namespace

# Upgrade (after changing values or templates)
helm upgrade python-api infra/helm/python-api --namespace apps

# See what's installed
helm list -A                           # All namespaces
helm list -n apps                      # Specific namespace

# See the actual YAML Helm would generate (without applying)
helm template python-api infra/helm/python-api

# Roll back to a previous version
helm rollback python-api 1 -n apps

# Uninstall
helm uninstall python-api -n apps
```

### The template syntax — how {{ }} works

```yaml
# In templates/deployment.yaml:
image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"

# Helm reads values.yaml and fills in:
image: "jayjalil89/python-api:latest"
```

`{{ .Release.Name }}` comes from the `helm install <name>` command. `{{ .Values.x }}` comes from `values.yaml`. `{{ .Release.Namespace }}` comes from the `--namespace` flag.

### What to say in an interview

> "I use Helm charts to template Kubernetes deployments. Each service has its own chart with a values.yaml that defines image, replicas, resource requests and limits, and node scheduling. For environment promotion I override values per environment — dev might have 1 replica with relaxed limits, production has 3 replicas with strict limits and pod disruption budgets. I use `helm template` to preview changes before applying, and Argo CD handles the actual deployment via GitOps."

---

## Unit 5: CI/CD with GitHub Actions — automating everything

### The concept

CI/CD stands for Continuous Integration / Continuous Deployment. CI means every code change is automatically tested. CD means every passing change is automatically deployed. Together, they mean a developer pushes code and it's live in production within minutes, with no manual steps.

### What you built — the pipeline stages

```
Developer pushes code to main
    │
    ▼
GitHub Actions triggers (path filter matches)
    │
    ▼
TEST: Install Python → pip install → pytest
    │
    ▼ (only on main branch, only if tests pass)
BUILD: docker build → docker push to Docker Hub
    │
    ▼
DEPLOY: Argo CD detects new image → syncs to cluster
```

### The workflow file explained

```yaml
name: python-api                        # Name shown in GitHub UI

on:
  push:
    branches: [main]                     # Only trigger on pushes to main
    paths:
      - 'services/python-api/**'         # Only trigger when these files change
      - '.github/workflows/python-api.yml'
  pull_request:
    paths:
      - 'services/python-api/**'         # Also run tests on PRs (but don't deploy)
```

The `on:` section is the trigger. `paths:` is the monorepo filter — this workflow ignores changes to `services/cpp-node/` or `ros/` entirely.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest               # Use GitHub's hosted runner
    ...

  build-and-push:
    needs: test                          # Only runs after test passes
    if: github.ref == 'refs/heads/main'  # Only on main, not on PRs
    ...
```

`needs: test` creates a dependency chain — build won't start until tests pass. `if: github.ref == 'refs/heads/main'` means PRs run tests but don't build/push images. This is the standard pattern: test everything, deploy only from main.

### Secrets management

You stored `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` as GitHub repository secrets. These are encrypted, never shown in logs, and injected as environment variables only during the workflow run. In a production setting you'd also have secrets for:

- Kubernetes cluster credentials
- Cloud provider credentials (AWS/GCP keys)
- Slack webhook URLs for notifications
- Code signing keys

### Self-hosted runners

You installed a GitHub Actions runner on `k3s-worker-2`. This means you can write `runs-on: [self-hosted, robotics]` in a workflow, and the job executes directly on your own hardware instead of GitHub's cloud. This is essential for:

- Jobs that need to reach your private Kubernetes cluster
- Jobs that need specialized hardware (GPUs for ML, or a ROS environment)
- Jobs where you want to avoid GitHub's usage limits
- Jobs that handle sensitive data you don't want on third-party infrastructure

### What to say in an interview

> "I build CI/CD pipelines in GitHub Actions with path-filtered triggers for monorepo efficiency. Each pipeline follows a test → build → push → deploy pattern. Tests run on every PR, but image builds and deployments only happen on merges to main. I use self-hosted runners for jobs that need cluster access or specialized environments like ROS builds. Secrets are managed through GitHub's encrypted secrets and never hardcoded. For deployment I use a GitOps approach with Argo CD rather than running kubectl from CI."

---

## Unit 6: GitOps with Argo CD — how deployment actually works

### The concept

GitOps means your Git repository is the single source of truth for what should be running in your cluster. You never run `kubectl apply` manually in production. Instead, Argo CD watches your repo, compares what's defined in Git versus what's running in the cluster, and automatically syncs them.

The flow is:

1. Developer merges a PR that changes `values.yaml` (new image tag, more replicas, whatever)
2. Argo CD detects the change (it polls the repo every 3 minutes by default)
3. Argo CD runs `helm template` internally and compares the output to what's in the cluster
4. If there's a drift, Argo CD applies the changes

### What you installed

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application                       # This is an Argo CD resource
metadata:
  name: python-api
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/jayjalil89/homelab-devops
    path: infra/helm/python-api          # Where to find the Helm chart
  destination:
    server: https://kubernetes.default.svc  # Deploy to this cluster
    namespace: apps                         # Into this namespace
  syncPolicy:
    automated:
      prune: true                        # Delete resources removed from Git
      selfHeal: true                     # Revert manual changes in the cluster
```

**`prune: true`** — If you remove a resource from your Helm chart and push, Argo CD deletes it from the cluster. Without this, orphaned resources accumulate.

**`selfHeal: true`** — If someone runs `kubectl edit` and manually changes a deployment, Argo CD reverts it to match Git within seconds. This enforces discipline: all changes go through Git, with a PR, with a review.

### Why GitOps matters for interviews

The job description mentions "streamline development and release processes." GitOps is how modern teams do this. The benefits interviewers want to hear:

- **Audit trail**: Every deployment is a Git commit with an author, timestamp, and description.
- **Rollback**: Revert a deployment by reverting a commit. `git revert` is faster and safer than figuring out what `kubectl` commands to run.
- **Consistency**: Dev, staging, and production are defined in Git. No "it's configured differently in prod but nobody documented it."
- **Access control**: Developers don't need `kubectl` access to production. They merge PRs; Argo CD does the rest.

### What to say in an interview

> "I use Argo CD for GitOps-based deployment. The Helm charts in our repo are the source of truth — Argo CD continuously reconciles the cluster state against what's defined in Git. We use automated sync with self-heal enabled, so any manual cluster changes get reverted. This gives us a complete audit trail through Git history, instant rollback via git revert, and eliminates the need for developers to have direct kubectl access to production."

---

## Unit 7: Health checks and reliability — keeping things running

### The concept

Kubernetes doesn't just start your containers — it continuously monitors them. You tell Kubernetes how to check if your app is healthy, and it automatically restarts unhealthy containers, removes them from load balancing, and prevents bad deployments from going fully live.

### What you configured

```yaml
readinessProbe:                         # "Is this pod ready to receive traffic?"
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 5                # Wait 5 seconds after start before first check
  periodSeconds: 10                     # Check every 10 seconds

livenessProbe:                          # "Is this pod still alive?"
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 15               # Wait 15 seconds before first check
  periodSeconds: 20                     # Check every 20 seconds
```

### The difference between readiness and liveness

**Readiness probe** — "Should I send traffic to this pod?" If it fails, the pod is removed from the Service's load balancer. It stays running, it just doesn't receive new requests. This is for pods that are temporarily busy (loading data, warming caches) but not broken.

**Liveness probe** — "Is this pod stuck?" If it fails, Kubernetes kills the pod and starts a new one. This catches deadlocks, memory leaks, or any state where the process is running but not functioning.

**Why `initialDelaySeconds` matters** — Your app needs time to start. If the liveness probe fires at second 1 and the app isn't ready until second 3, Kubernetes kills it, restarts it, it starts again, gets killed again — `CrashLoopBackOff`. The `initialDelaySeconds` gives it breathing room.

### The Prometheus metrics endpoint

You also built a `/metrics` endpoint:

```python
from prometheus_client import Counter, generate_latest

REQUEST_COUNT = Counter("requests_total", "Total requests", ["endpoint"])

@app.get("/metrics")
def metrics():
    return generate_latest()
```

This exposes metrics in Prometheus format — a standardized text format that monitoring tools scrape. Your deployment has annotations that tell Prometheus where to find it:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"
  prometheus.io/path: "/metrics"
```

When you install Prometheus (next phase), it will automatically discover and scrape these endpoints. This is how you'll build dashboards showing request rates, error rates, and latency.

### What to say in an interview

> "Every service I deploy has readiness and liveness probes configured. Readiness gates traffic — a pod that fails readiness is pulled from the load balancer but kept running. Liveness catches stuck processes and triggers a restart. I instrument services with Prometheus client libraries and expose a /metrics endpoint with custom counters and histograms. The deployment annotations let Prometheus auto-discover targets through Kubernetes service discovery."

---

## Unit 8: Networking and troubleshooting — the skills that matter most

### What you actually debugged

Throughout this setup you hit real problems and solved them. This is the most valuable thing you can talk about in an interview, because it proves hands-on experience.

**Problem 1: `externally-managed-environment` error**
- Symptom: `pip install` refused to run on Ubuntu 24.04
- Root cause: PEP 668 — Ubuntu protects the system Python from pip modifications
- Fix: Created a virtual environment (`python3 -m venv .venv`)
- Lesson: Modern Linux distributions enforce isolation between system packages and user packages. This is a feature, not a bug.

**Problem 2: `ErrImagePull` on pods**
- Symptom: Pods stuck in `ErrImagePull` / `ImagePullBackOff`
- Debugging: `kubectl describe pod` → Events showed "pull access denied, repository does not exist"
- Root cause: The Docker image hadn't been pushed to Docker Hub yet — CI hadn't run
- Fix: Manually built and pushed the image, then restarted the deployment
- Lesson: Always verify the image exists in the registry before deploying. `kubectl describe` events tell you exactly what's wrong.

**Problem 3: Argo CD CRD too large for `kubectl apply`**
- Symptom: "metadata.annotations: Too long" error
- Root cause: Argo CD's ApplicationSet CRD exceeds the 262KB annotation limit used by client-side apply
- Fix: Used `kubectl apply --server-side=true --force-conflicts`
- Lesson: Server-side apply handles large resources. `--force-conflicts` takes ownership when multiple managers conflict. This is a known issue in the Kubernetes ecosystem, not something you did wrong.

**Problem 4: Port-forward not reachable from desktop**
- Symptom: `ERR_CONNECTION_REFUSED` when accessing from desktop browser
- Root cause: `kubectl port-forward` defaults to binding on `127.0.0.1` (localhost only)
- Fix: Added `--address 0.0.0.0` to bind on all interfaces
- Lesson: Port-forwarding is a dev/debug tool. In production, you use an Ingress controller to expose services properly.

### The debugging mental model

When something doesn't work in Kubernetes, follow this flow:

```
1. kubectl get pods -n <namespace>          → What's the STATUS?
     │
     ├── Pending         → Scheduling issue. kubectl describe pod → check Events
     │                      Common: node selector mismatch, insufficient resources
     │
     ├── ImagePullBackOff → Image doesn't exist or auth failed
     │                      Check: image name, registry credentials, network
     │
     ├── CrashLoopBackOff → Container starts then dies
     │                      Check: kubectl logs <pod> --previous
     │                      Common: missing env vars, bad config, port conflict
     │
     ├── Running but 0/1 Ready → Readiness probe failing
     │                      Check: is the app actually listening? Right port?
     │
     └── Running and 1/1 Ready → Pod is fine, problem is elsewhere
                               Check: Service selector matches pod labels?
                               Check: port numbers consistent?
```

### What to say in an interview

> "My debugging approach is systematic: start with pod status, move to describe for events, then logs for application errors. The most common issues I've dealt with are image pull failures from registry authentication, CrashLoopBackOff from missing configuration, and scheduling failures from resource constraints or node affinity mismatches. I've also dealt with infrastructure-level issues like CRD size limits requiring server-side apply, and network binding issues with port-forwarding."

---

## Unit 9: Putting it all together — the full deployment lifecycle

### The end-to-end flow you built

Here is the complete lifecycle of a code change in your homelab, from keyboard to running in the cluster:

```
1. Developer writes code on kubeman.jay.home.arpa
2. Developer pushes to GitHub (git push origin main)
3. GitHub Actions detects the push, checks path filters
4. CI job runs: installs Python, runs pytest
5. If tests pass AND on main branch:
   a. Docker builds the image
   b. Docker pushes to Docker Hub (jayjalil89/python-api:v1.2.3)
6. Argo CD polls the Git repo, sees the new commit
7. Argo CD renders the Helm template with the updated values
8. Argo CD compares rendered manifests to live cluster state
9. Argo CD applies the diff (rolling update)
10. Kubernetes creates new pods with the new image
11. Readiness probe passes → new pods receive traffic
12. Old pods are terminated
13. Prometheus scrapes /metrics from the new pods
14. Grafana dashboards show the deployment (next phase)
```

Every step is automated. The developer's only action is step 1 and 2.

### How this maps to the job description

| Job requirement | What you built |
|---|---|
| "Develop and maintain CI/CD pipelines using GitHub Actions" | python-api.yml workflow with test, build, push stages |
| "Support multiple software stacks including Python, C++, ROS, Docker" | Monorepo with separate service directories and path-filtered pipelines |
| "Design, build, and maintain containerized environments" | Dockerfiles with layer caching, slim base images, health endpoints |
| "Deploy and manage workloads on Kubernetes clusters" | 3-node k3s cluster with Helm deployments and node scheduling |
| "Maintain and optimize monorepo build workflows" | Path-filtered CI, dependency caching, selective builds |
| "Build automation to support testing, packaging, and deployment" | Automated pytest → Docker build → push → Argo CD sync pipeline |
| "Monitor system performance and deployment health" | Prometheus annotations, /metrics endpoint, health probes (Grafana next) |
| "Improve developer productivity through tooling and automation" | Self-hosted runner, GitOps (no manual kubectl), automated deployments |

---

## Unit 10: What's next — the skills to add

### Phase 2: Observability (your next build)

Install the `kube-prometheus-stack` Helm chart on k3s-worker-1. This gives you Prometheus (metrics collection), Grafana (dashboards), Alertmanager (notifications), and Loki (log aggregation). Build a dashboard showing your Python API's request rate, error rate, and pod resource usage. Set up an alert that fires when a pod restarts more than 3 times.

### Phase 3: ROS 2 pipeline

Build a Dockerfile based on `osrf/ros:humble-desktop` that runs a TurtleBot3 simulation in Gazebo headlessly. Create a GitHub Actions workflow that builds the ROS workspace, pushes the image, and deploys a Kubernetes Job on k3s-worker-2 (using the `robotics` label). The job runs the simulation, records a ROS bag, and uploads it as a CI artifact.

### Phase 4: Advanced Kubernetes

Add Ingress (ingress-nginx) so you can hit services at `http://python-api.jay.home.arpa` instead of port-forwarding. Add `HorizontalPodAutoscaler` to auto-scale based on CPU. Add `PodDisruptionBudget` to ensure availability during node maintenance. Add `NetworkPolicy` to restrict pod-to-pod communication.

### Phase 5: Developer productivity tooling

Write a CLI tool (shell script or Python) that wraps common operations: `./lab status` shows cluster health, `./lab deploy python-api v1.2.3` triggers a deployment, `./lab logs python-api` streams logs. This is the "improve developer productivity through tooling" part of the job description.

---

## Interview cheat sheet — terms and definitions

| Term | Definition | Your example |
|---|---|---|
| CI/CD | Automated testing and deployment pipeline | GitHub Actions runs tests on every PR, deploys on merge to main |
| GitOps | Git as the source of truth for cluster state | Argo CD syncs cluster to match Helm charts in the repo |
| Monorepo | Single repo holding multiple services/projects | services/, ros/, infra/ all in one repo with path-filtered CI |
| Container | Portable package with app + dependencies | Dockerfile builds your Python API into a runnable image |
| Pod | Smallest Kubernetes unit, wraps one or more containers | Your python-api pods running on k3s-worker-1 |
| Deployment | Manages pod replicas and rolling updates | 2 replicas of python-api with health checks |
| Service | Stable network endpoint for a set of pods | python-api Service load-balances across 2 pods |
| Namespace | Virtual cluster for isolation | apps, argocd, monitoring |
| Helm | Kubernetes package manager with templating | Chart that generates Deployment + Service from values.yaml |
| Node selector | Schedule pods to specific nodes by label | workload=apps routes pods to k3s-worker-1 |
| Readiness probe | Checks if a pod should receive traffic | HTTP GET /health every 10 seconds |
| Liveness probe | Checks if a pod is alive or stuck | HTTP GET /health every 20 seconds |
| Rolling update | Replace pods one at a time with zero downtime | Default Deployment strategy |
| Image registry | Storage for Docker images | Docker Hub (jayjalil89/python-api) |
| Self-hosted runner | CI executor on your own infrastructure | GitHub Actions runner on k3s-worker-2 |
| Server-side apply | Kubernetes apply method for large resources | Used for Argo CD CRDs that exceeded annotation limits |
| Resource requests | Minimum guaranteed CPU/memory for a pod | 100m CPU, 128Mi memory |
| Resource limits | Maximum allowed CPU/memory before throttle/kill | 250m CPU, 256Mi memory |
| CrashLoopBackOff | Pod keeps crashing and Kubernetes keeps restarting it | Caused by missing config, bad image, or failing health checks |
| ErrImagePull | Kubernetes can't download the container image | Image doesn't exist in registry, or auth failed |
| k3s | Lightweight Kubernetes distribution | Your cluster runs k3s instead of full Kubernetes |
| Argo CD Application | Resource that tells Argo CD what to sync | Points at your Helm chart path in GitHub |
| Prune | Delete cluster resources that were removed from Git | Argo CD syncPolicy.automated.prune: true |
| Self-heal | Revert manual cluster changes to match Git | Argo CD syncPolicy.automated.selfHeal: true |

---

## Interview questions you should be ready for

**"Walk me through what happens when a developer pushes code."**
Answer using Unit 9 — the full 13-step lifecycle.

**"How do you handle a failing deployment?"**
Answer: "I check pod status, describe for events, logs for errors. If the new image is broken, I revert the Git commit and Argo CD rolls back automatically. If it's a config issue, I fix the values.yaml and push. I never fix production by running kubectl — everything goes through Git."

**"How do you manage secrets?"**
Answer: "In CI, GitHub encrypted secrets. In the cluster, Kubernetes Secrets, ideally backed by an external secret manager like HashiCorp Vault or AWS Secrets Manager for production. Secrets are never committed to the repo."

**"How would you add a new service to this setup?"**
Answer: "Create a new directory under services/, write the code and Dockerfile, add a Helm chart under infra/helm/, create a GitHub Actions workflow with the right path filter, create an Argo CD Application manifest, and push. The entire pipeline is templatized — adding a service takes under an hour."

**"What would you do differently in production?"**
Answer: "I'd add network policies, pod security standards, image scanning in CI with Trivy, a private container registry instead of Docker Hub, proper TLS with cert-manager, horizontal pod autoscaling, pod disruption budgets, and centralized logging with Loki. I'd also use sealed-secrets or external-secrets-operator instead of plain Kubernetes Secrets."
