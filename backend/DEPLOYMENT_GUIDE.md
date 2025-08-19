# 🚀 Production Deployment Guide: S3 Image Serving

This guide explains how to deploy the Human Capital Development System with S3-based image serving for production.

## 📋 Overview

The system now supports **environment-based image serving**:
- **Development**: Local static files served by FastAPI
- **Production**: Images served from S3 bucket with optional CloudFront CDN

## 🏗️ Architecture

### Current Flow
```
Frontend Request → API (/questions/{id}/images) → Database (image paths) → ImageService → Environment-specific URLs → Frontend Composition
```

### Development
```
Database: ["p1_images/paper/page/image.png"]
↓
ImageService: "http://localhost:8000/static/images/paper/page/image.png"
↓
Frontend: Composes images client-side
```

### Production
```
Database: ["p1_images/paper/page/image.png"] (same data)
↓
ImageService: "https://your-bucket.s3.us-east-1.amazonaws.com/paper/page/image.png"
↓
Frontend: Composes images client-side (same code)
```

## 🔧 Setup Instructions

### Step 1: S3 Bucket Setup

1. **Create S3 Bucket**
```bash
aws s3 mb s3://your-hcd-images-bucket --region us-east-1
```

2. **Upload Images to S3**
```bash
# Sync your p1_images directory to S3
aws s3 sync ./p1_images s3://your-hcd-images-bucket/ --recursive

# Set public read permissions (adjust for your security needs)
aws s3api put-bucket-policy --bucket your-hcd-images-bucket --policy '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-hcd-images-bucket/*"
    }
  ]
}'
```

3. **Optional: Setup CloudFront CDN**
```bash
# Create CloudFront distribution for better performance
aws cloudfront create-distribution --distribution-config '{
  "CallerReference": "hcd-images-'$(date +%s)'",
  "Comment": "HCD Images CDN",
  "DefaultRootObject": "",
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-your-hcd-images-bucket",
        "DomainName": "your-hcd-images-bucket.s3.amazonaws.com",
        "S3OriginConfig": {
          "OriginAccessIdentity": ""
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-your-hcd-images-bucket",
    "ViewerProtocolPolicy": "redirect-to-https",
    "TrustedSigners": {
      "Enabled": false,
      "Quantity": 0
    },
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": {
        "Forward": "none"
      }
    }
  },
  "Enabled": true
}'
```

### Step 2: Environment Variables

Set these environment variables for production:

```bash
# Required for production
export ENVIRONMENT=production
export S3_BUCKET_NAME=your-hcd-images-bucket
export S3_REGION=us-east-1

# Optional: CloudFront CDN
export CLOUDFRONT_DOMAIN=d123456789.cloudfront.net

# Database and other configs
export PROD_DB_HOST=your-prod-db.amazonaws.com
export PROD_DB_PASSWORD=your-secure-password
export PROD_REDIS_PASSWORD=your-redis-password
export PROD_JWT_SECRET=your-32-character-secret
```

### Step 3: Database - No Changes Needed!

✅ **Your database doesn't need any changes!**

The image paths in your database remain exactly the same:
```json
{"images": ["p1_images/9702_w22_qp_13/page_16/image.png"]}
```

The `ImageService` automatically converts these to the correct URLs based on environment.

### Step 4: Frontend Integration

Use the new `/questions/{question_id}/images` endpoint:

```javascript
// Same frontend code works in both dev and production!
const response = await fetch(`/questions/${questionId}/images`);
const questionData = await response.json();

// questionData.images contains environment-appropriate URLs:
// Dev:  [{"url": "http://localhost:8000/static/images/..."}]
// Prod: [{"url": "https://your-bucket.s3.amazonaws.com/..."}]

questionData.images.forEach(image => {
    const img = document.createElement('img');
    img.src = image.url;  // Works in both environments!
    container.appendChild(img);
});
```

## 🔄 Migration Strategy

### Phase 1: Deploy New Endpoints (Backward Compatible)
```bash
# Deploy the new image service
# Old endpoints still work
# Frontend can start using new /images endpoint
```

### Phase 2: Remove Server-Side Rendering (Optional)
```bash
# Remove matplotlib rendering endpoints
# Keep only image URL serving
# Significant performance improvement
```

### Phase 3: Database Cleanup (Future)
```bash
# Eventually: Remove image paths from database entirely
# Store only question text and metadata
# Images referenced by question_id convention
```

## 📊 Performance Benefits

| Metric | Before (Server Rendering) | After (Frontend Composition) |
|--------|---------------------------|------------------------------|
| **Server CPU** | High (matplotlib) | Low (just URL generation) |
| **Response Time** | 1-2 seconds | 50-100ms |
| **Memory Usage** | High (image processing) | Low (just database queries) |
| **Scalability** | Limited by server resources | CDN-scale |
| **Caching** | Complex (full images) | Simple (static files) |

## 🛠️ Development Workflow

### Local Development
```bash
# No changes needed - images served locally
export ENVIRONMENT=development
python main.py --mode api
```

### Production Deployment
```bash
# Set production environment
export ENVIRONMENT=production
export S3_BUCKET_NAME=your-bucket
export S3_REGION=us-east-1

# Deploy
docker build -f Dockerfile.production -t hcd-api:prod .
docker run -d -p 8000:8000 --env-file .env.prod hcd-api:prod
```

## 🔍 Testing the Setup

### Test Development Environment
```bash
curl http://localhost:8000/questions/9702_w22_qp_13_38/images
# Should return URLs like: http://localhost:8000/static/images/...
```

### Test Production Environment
```bash
curl https://your-api.com/questions/9702_w22_qp_13_38/images
# Should return URLs like: https://your-bucket.s3.amazonaws.com/...
```

### Test Frontend Composition
```bash
# Open examples/frontend_image_composition.html in browser
# Should load and display images in both environments
```

## 🚨 Important Notes

1. **No Database Migration Required**: Existing image paths work as-is
2. **Gradual Migration**: Old endpoints remain functional during transition
3. **Environment Flexibility**: Same code works in dev/staging/production
4. **Cost Optimization**: S3 + CloudFront is cost-effective for image serving
5. **Performance**: Frontend composition is much faster than server rendering

## 🔧 Troubleshooting

### Images Not Loading in Production
```bash
# Check S3 permissions
aws s3api get-bucket-policy --bucket your-hcd-images-bucket

# Verify image exists
aws s3 ls s3://your-hcd-images-bucket/9702_w22_qp_13/ --recursive

# Test direct S3 URL
curl -I https://your-hcd-images-bucket.s3.us-east-1.amazonaws.com/path/to/image.png
```

### Environment Variable Issues
```bash
# Verify production environment detection
curl https://your-api.com/health
# Should show environment: "production"
```

## 📈 Next Steps

1. **Deploy to Staging**: Test with staging S3 bucket first
2. **Monitor Performance**: Use CloudWatch to monitor S3 requests
3. **Optimize Costs**: Set up S3 lifecycle policies for old images
4. **Security**: Consider S3 bucket policies and CloudFront signed URLs if needed
5. **Backup**: Set up S3 cross-region replication for disaster recovery

This architecture provides the scalability and performance you need for production while maintaining development simplicity! 🚀
