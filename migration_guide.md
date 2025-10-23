# AppenCorrect Migration Guide
## Moving to Higher Performance Instance (4-core or 8-core)

This guide helps you migrate your optimized AppenCorrect setup to a more powerful EC2 instance.

## 🎯 Target Instance Recommendations

### **m5.xlarge (4 vCPUs, 16GB RAM)**
- **Recommended workers**: 80-100
- **Expected performance**: 60-80 req/sec
- **Concurrent users**: 300-400 users
- **Cost**: ~2x current

### **m5.2xlarge (8 vCPUs, 32GB RAM)**  
- **Recommended workers**: 150-200
- **Expected performance**: 120-160 req/sec
- **Concurrent users**: 600-800 users
- **Cost**: ~4x current

### **c5.xlarge (4 vCPUs, 8GB RAM, CPU Optimized)**
- **Recommended workers**: 100-120
- **Expected performance**: 80-100 req/sec
- **Best for**: CPU-intensive AI workloads
- **Cost**: Similar to m5.xlarge

## 📋 Migration Process

### **Phase 1: Prepare New Instance**
1. **Launch new EC2 instance** (m5.xlarge or m5.2xlarge)
2. **Same VPC/subnet** as current instance (for ElastiCache access)
3. **Same security groups** (ports 5006, 22, etc.)
4. **Install base dependencies**

### **Phase 2: Copy Application & Configuration**
1. **Copy application files**
2. **Copy environment configuration**
3. **Copy database files**
4. **Install Python dependencies**

### **Phase 3: Optimize for New Hardware**
1. **Update worker configuration**
2. **Test performance**
3. **Update DNS/load balancer**
4. **Decommission old instance**

## 🛠️ Detailed Migration Steps

### **Step 1: Launch New Instance**
- **Instance type**: m5.xlarge or m5.2xlarge
- **AMI**: Same as current (Amazon Linux 2023)
- **VPC**: Same VPC (for ElastiCache connectivity)
- **Security groups**: Copy from current instance
- **Key pair**: Same SSH key

### **Step 2: Initial Setup on New Instance**
```bash
# Connect to new instance
ssh -i your-key.pem ec2-user@NEW-INSTANCE-IP

# Create directory structure
mkdir -p /home/ec2-user/apps

# Install Python virtual environment
python3 -m venv /home/ec2-user/autocase_env
source /home/ec2-user/autocase_env/bin/activate
```

### **Step 3: Copy Files from Current Instance**
```bash
# On new instance, copy from current instance
rsync -avz ec2-user@CURRENT-INSTANCE-IP:/home/ec2-user/apps/AppenCorrect/ /home/ec2-user/apps/AppenCorrect/
rsync -avz ec2-user@CURRENT-INSTANCE-IP:/home/ec2-user/autocase_env/lib/python3.9/site-packages/ /home/ec2-user/autocase_env/lib/python3.9/site-packages/

# Or use S3 for transfer
# aws s3 sync /home/ec2-user/apps/AppenCorrect s3://your-bucket/appencorrect-backup
```

## ⚙️ Optimized Configurations

### **For m5.xlarge (4 vCPUs, 16GB RAM):**
```env
# .env configuration
WORKERS=80
TIMEOUT=45
MAX_REQUESTS=2000
MAX_REQUESTS_JITTER=100

# Expected performance
# - 60-80 req/sec throughput
# - 2-4s average response time
# - Handle 300-400 concurrent users
```

### **For m5.2xlarge (8 vCPUs, 32GB RAM):**
```env
# .env configuration  
WORKERS=150
TIMEOUT=45
MAX_REQUESTS=3000
MAX_REQUESTS_JITTER=150

# Expected performance
# - 120-160 req/sec throughput
# - 1-3s average response time  
# - Handle 600-800 concurrent users
```

### **For c5.xlarge (4 vCPUs, 8GB RAM, CPU Optimized):**
```env
# .env configuration
WORKERS=100
TIMEOUT=30
MAX_REQUESTS=2500
MAX_REQUESTS_JITTER=125

# Expected performance
# - 80-100 req/sec throughput
# - 1.5-3s average response time
# - Handle 400-500 concurrent users  
```

## 🔄 Quick Migration Option

If instances are in same VPC, you can also:
1. **Create AMI** from current instance
2. **Launch new instance** from AMI
3. **Update worker configuration** for new hardware
4. **Test and switch traffic**

This preserves everything exactly and just requires configuration tuning.
