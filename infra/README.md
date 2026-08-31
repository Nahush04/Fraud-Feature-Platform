# infra

## Local dev

```bash
docker compose up -d redis mysql
```

Redis backs the feature store's online side (`feature_store`, `serving`);
MySQL backs the analyst review app (`review_app`, M6).

## Kubernetes (minikube)

```
k8s/
  redis.yaml        Redis Deployment + Service (the online store, in-cluster)
  configmap.yaml     REDIS_URL / MODEL_DIR for fraud-serving
  deployment.yaml    fraud-serving Deployment: 2 replicas, resource requests/limits,
                      readiness probe (checks Redis), liveness probe (process only)
  service.yaml        NodePort Service exposing fraud-serving
  hpa.yaml             HorizontalPodAutoscaler: 2-8 replicas, 60% CPU target
```

See `../serving/README.md` for the full `minikube` deploy walkthrough and
`../load_testing/README.md` for driving load against it.
