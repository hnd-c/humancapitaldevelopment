# Docker Usage Guide - Human Capital Development System

## 🚀 **Quick Start**

### **1. Basic Development Setup**
```bash
# Start core services (PostgreSQL + Redis)
docker-compose up -d postgres redis-cache redis-vectors

# Check service health
docker-compose ps
```

### **2. Full Development Environment**
```bash
# Start with API server
docker-compose --profile api up -d

# Start with development tools
docker-compose --profile tools up -d

# Start with Jupyter notebook
docker-compose --profile dev up -d

# Start with monitoring
docker-compose --profile monitoring up -d
```

### **3. Everything Together**
```bash
# Start all services
docker-compose --profile api --profile tools --profile monitoring --profile dev up -d
```

## 📊 **Service Profiles**

### **Core Services (Always Available)**
- `postgres` - PostgreSQL with pgvector (port 5432)
- `redis-cache` - Main Redis cache (port 6379)
- `redis-vectors` - Vector similarity cache (port 6380)

### **Profile: `api`**
- `hcd-api` - Main application API server (port 8000)

### **Profile: `tools`**
- `redis-commander` - Redis GUI management (port 8081)
- `pgadmin` - PostgreSQL GUI management (port 5050)

### **Profile: `monitoring`**
- `prometheus` - Metrics collection (port 9090)
- `grafana` - Monitoring dashboards (port 3000)

### **Profile: `dev`**
- `jupyter` - Jupyter notebook for data analysis (port 8888)

## 🔧 **Environment Configuration**

Create a `.env` file with:
```bash
# Database
POSTGRES_PASSWORD=your_secure_password_here

# Monitoring
GRAFANA_PASSWORD=admin_dev_password
PGADMIN_EMAIL=admin@humancapital.dev
PGADMIN_PASSWORD=admin_secure_password

# Security
SECRET_KEY=your_secret_key_here

# External APIs
OPENAI_API_KEY=your_openai_api_key_here
```

## 📈 **Service Access Points**

| Service | URL | Credentials |
|---------|-----|-------------|
| API Server | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |
| Health Check | http://localhost:8000/health | - |
| pgAdmin | http://localhost:5050 | See .env file |
| Redis Commander | http://localhost:8081 | admin/admin |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | See .env file |
| Jupyter | http://localhost:8888 | Token in logs |

## 🏗️ **Development vs Production**

### **Development (docker-compose.yml)**
- Source code mounted for live reload
- Debug mode enabled
- Lower resource limits
- Development-friendly settings
- All management tools available

### **Production (docker-compose.production.yml)**
- Built containers
- Optimized resource allocation
- Security hardened
- Load balancing with Nginx
- Background workers
- Production monitoring

## 🔄 **Common Commands**

### **Start/Stop Services**
```bash
# Start specific services
docker-compose up -d postgres redis-cache

# Stop all services
docker-compose down

# Stop and remove volumes (CAUTION: DATA LOSS)
docker-compose down -v

# Restart a service
docker-compose restart postgres
```

### **Logs and Debugging**
```bash
# View logs
docker-compose logs postgres
docker-compose logs hcd-api
docker-compose logs -f --tail=100 redis-cache

# Execute commands in containers
docker-compose exec postgres psql -U hcd_user -d human_capital_dev
docker-compose exec redis-cache redis-cli
```

### **Development Workflow**
```bash
# 1. Start core services
docker-compose up -d postgres redis-cache redis-vectors

# 2. Run your Python code locally (with .env file)
python main_system.py
python api_server.py

# OR run in container for full integration
docker-compose --profile api up -d
```

## 🐛 **Troubleshooting**

### **Common Issues**

1. **Port Conflicts**
   ```bash
   # Check what's using ports
   lsof -i :5432  # PostgreSQL
   lsof -i :6379  # Redis
   lsof -i :8000  # API
   ```

2. **Database Connection Issues**
   ```bash
   # Check PostgreSQL logs
   docker-compose logs postgres

   # Test connection
   docker-compose exec postgres psql -U hcd_user -d human_capital_dev
   ```

3. **Redis Connection Issues**
   ```bash
   # Check Redis
   docker-compose exec redis-cache redis-cli ping
   docker-compose exec redis-vectors redis-cli ping
   ```

4. **Permission Issues**
   ```bash
   # Fix volume permissions
   sudo chown -R $USER:$USER ./data
   sudo chown -R $USER:$USER ./logs
   ```

### **Reset Everything**
```bash
# Nuclear option - removes all data
docker-compose down -v
docker system prune -f
docker-compose up -d
```

## 📦 **Data Management**

### **Backup Database**
```bash
# Backup
docker-compose exec postgres pg_dump -U hcd_user human_capital_dev > backup.sql

# Restore
docker-compose exec -T postgres psql -U hcd_user human_capital_dev < backup.sql
```

### **Import Data**
```bash
# Run data migration
docker-compose exec hcd-api python main_system.py migrate

# Or manually import
docker-compose exec postgres psql -U hcd_user -d human_capital_dev -f /app/postgresql_migration.sql
```

This setup gives you a complete development environment that mirrors the production architecture while being developer-friendly! 🎯
