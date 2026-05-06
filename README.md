# homelab-devops

A homelab project covering CI/CD, Kubernetes, and robotics platform engineering.

## Cluster
| Node | Hostname | IP | Role |
|---|---|---|---|
| Control | kubeman.jay.home.arpa | 192.168.1.20 | k3s server, Argo CD |
| Worker 1 | k3s-worker-1 | 192.168.1.21 | Apps, observability |
| Worker 2 | k3s-worker-2 | 192.168.1.22 | ROS/sim, CI runner |
