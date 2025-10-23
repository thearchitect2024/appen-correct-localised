# AppenCorrect Migration Instructions

## Quick Transfer Methods

### Method 1: Direct Copy (Same VPC)
```bash
# On new instance:
rsync -avz ec2-user@OLD-INSTANCE-IP:/tmp/appencorrect_migration_* /tmp/
cd /tmp/appencorrect_migration_*
./deploy_on_new_instance.sh m5.xlarge
```

### Method 2: S3 Transfer
```bash
# On old instance:
tar -czf appencorrect_migration.tar.gz -C /tmp appencorrect_migration_*
aws s3 cp appencorrect_migration.tar.gz s3://your-bucket/

# On new instance:
aws s3 cp s3://your-bucket/appencorrect_migration.tar.gz .
tar -xzf appencorrect_migration.tar.gz
cd appencorrect_migration_*
./deploy_on_new_instance.sh m5.xlarge
```

### Method 3: SCP Transfer
```bash
# From your local machine:
scp -r ec2-user@OLD-IP:/tmp/appencorrect_migration_* .
scp -r appencorrect_migration_* ec2-user@NEW-IP:/tmp/
# Then SSH to new instance and run deploy script
```

## Configuration Optimization

The deploy script automatically optimizes for:
- **2 cores**: 50 workers
- **4 cores**: 80 workers  
- **8 cores**: 150 workers
- **16+ cores**: 20 workers per core

## Verification Steps

After migration:
1. Test API: `curl http://localhost:5006/health`
2. Monitor logs: `journalctl -u appencorrect -f`
3. Run load test: `python3 detailed_stats_test.py`
4. Check cache: `python3 test_cache.py`
