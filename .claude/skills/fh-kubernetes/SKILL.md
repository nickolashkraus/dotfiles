---
name: fh-kubernetes
description: >
  Function Health GKE kubeconfig generation. Use when you need to generate or
  refresh `~/.kube/function.yaml` for the `dev`, `prod`, or `sandbox` clusters
  via `generate-fh-kubeconfig`. TRIGGER when: user needs kubectl access to an
  FH cluster, refresh of FH kubeconfig, or hits an auth/expiry error against
  the FH GKE control plane.
disable-model-invocation: false
allowed-tools: Bash, Read
---

Function Health GKE kubeconfig runbook. Invoke this skill when you
need cluster credentials for `function-health-dev-env`,
`function-health-prod-env`, or `function-health-sandbox-env`.

## GKE kubeconfig

Function Health GKE clusters live across `function-health-dev-env`,
`function-health-prod-env`, and `function-health-sandbox-env`. To generate or
refresh `~/.kube/function.yaml`, run:

```bash
generate-fh-kubeconfig --output $HOME/.kube/function.yaml
```

The script lives at
`~/nickolashkraus/bash-scripts/master/generate-fh-kubeconfig` and queries
`gcloud container clusters describe` for each cluster, so it requires
`Kubernetes Engine Admin` (or read-equivalent) on the relevant projects via
ConductorOne.
