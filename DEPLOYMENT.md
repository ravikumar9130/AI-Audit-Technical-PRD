# Deployment Guide

## Local Development

### Prerequisites
- Docker and Docker Compose
- Git
- Make (optional)

### Quick Start

1. **Clone and setup:**
```bash
git clone <repo-url>
cd audit-ai
cp .env.example .env
# Edit .env with your configuration
```

2. **Start services:**
```bash
make up
# or
docker-compose up -d
```

3. **Run database migrations:**
```bash
make migrate
# or
docker-compose exec api alembic upgrade head
```

4. **Access services:**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

### Creating Admin User

```bash
docker-compose exec api python -c "
from core.database import get_db_context
from core.security import get_password_hash
from models import User
with get_db_context() as db:
    user = User(
        email='admin@auditai.io',
        password_hash=get_password_hash('admin123'),
        first_name='Admin',
        last_name='User',
        role='Admin'
    )
    db.add(user)
    db.commit()
    print(f'Admin user created with ID: {user.user_id}')
"
```

## Production Deployment (Kubernetes)

### Prerequisites
- Kubernetes cluster (1.24+)
- kubectl configured
- Helm 3.x
- cert-manager (for TLS)
- NGINX Ingress Controller
- NVIDIA GPU Operator (for GPU nodes)

### Option 1: Using Helm (Recommended)

1. **Add secrets:**
```bash
kubectl create namespace auditai
kubectl create secret generic auditai-secrets \
  --from-literal=DATABASE_URL='postgresql://auditai:PASSWORD@postgres-service:5432/auditai' \
  --from-literal=JWT_SECRET='YOUR_SECRET_KEY_MIN_32_CHARS' \
  --from-literal=ENCRYPTION_KEY='YOUR_ENCRYPT_KEY_MIN_32' \
  -n auditai
```

2. **Install chart:**
```bash
make k8s-helm-install
# or
helm install audit-ai kubernetes/helm-charts/ -n auditai
```

3. **Upgrade:**
```bash
make k8s-helm-upgrade
```

### Option 2: Using kubectl

```bash
# Apply all manifests
kubectl apply -f kubernetes/manifests/

# Check status
kubectl get pods -n auditai
kubectl get svc -n auditai
kubectl get ingress -n auditai
```

### GPU Node Setup

Ensure your GPU nodes have the NVIDIA device plugin:

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
```

Label GPU nodes:
```bash
kubectl label nodes <node-name> accelerator=nvidia-gpu
```

### Monitoring

Deploy Prometheus and Grafana for monitoring:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
```

## SSL/TLS Configuration

The ingress is configured to use cert-manager with Let's Encrypt. Ensure you have:

1. **cert-manager installed:**
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

2. **ClusterIssuer configured:**
```bash
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@company.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

## Backup and Recovery

### Database Backup

```bash
# Create backup
kubectl exec -n auditai postgres-0 -- pg_dump -U auditai auditai > backup.sql

# Restore
kubectl cp backup.sql auditai/postgres-0:/tmp/backup.sql
kubectl exec -n auditai postgres-0 -- psql -U auditai -d auditai -f /tmp/backup.sql
```

### MinIO Backup

```bash
# Install mc client
kubectl run minio-client --rm -i --restart=Never --image=minio/mc -- \
  mc alias set myminio http://minio-service:9000 ACCESS_KEY SECRET_KEY

# Backup
kubectl run minio-client --rm -i --restart=Never --image=minio/mc -- \
  mc mirror myminio/auditai-calls /backup
```

## Troubleshooting

### Check logs
```bash
# API logs
kubectl logs -n auditai -l app=auditai-api --tail=100

# Worker logs
kubectl logs -n auditai -l app=auditai-worker --tail=100

# Frontend logs
kubectl logs -n auditai -l app=auditai-frontend --tail=100
```

### Common Issues

1. **GPU not available:**
   - Check NVIDIA device plugin is installed
   - Verify node has `accelerator=nvidia-gpu` label

2. **Database connection errors:**
   - Check postgres pod is running
   - Verify DATABASE_URL in secrets

3. **Ingress not working:**
   - Check NGINX ingress controller is installed
   - Verify DNS records point to ingress IP

## Security Considerations

1. **Change default secrets** in production
2. **Enable MFA** for admin accounts
3. **Use TLS 1.3** minimum
4. **Regular security audits**
5. **Keep dependencies updated**
6. **Monitor audit logs**

## Scaling

### Horizontal Scaling

```bash
# Scale API
kubectl scale deployment auditai-api -n auditai --replicas=10

# Scale Workers
kubectl scale deployment auditai-worker -n auditai --replicas=5
```

### Vertical Scaling

Edit resource limits in values.yaml or manifests:
```yaml
resources:
  worker:
    requests:
      memory: "16Gi"
      cpu: "4000m"
      nvidia.com/gpu: 2
    limits:
      memory: "32Gi"
      cpu: "8000m"
      nvidia.com/gpu: 2
```

## Support

For issues or questions:
- Documentation: https://docs.auditai.io
- Issues: https://github.com/auditai/audit-ai/issues
- Email: support@auditai.io
