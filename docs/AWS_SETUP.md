# AWS Setup Guide for WordBridge

This guide walks you through setting up AWS resources needed for WordBridge:

- S3 bucket for file uploads
- SQS queue for background job processing (required for production)
- IAM user with appropriate permissions

## Prerequisites

1. **AWS Account**: Sign up at https://aws.amazon.com if you don't have one
2. **AWS CLI**: Install and configure AWS CLI

   ```bash
   # Install AWS CLI (macOS)
   brew install awscli

   # Or download from: https://aws.amazon.com/cli/

   # Configure with your credentials
   aws configure
   ```

   When prompted, enter:

   - AWS Access Key ID: (from your AWS account)
   - AWS Secret Access Key: (from your AWS account)
   - Default region: `us-east-1` (or your preferred region)
   - Default output format: `json`

## Step 1: Create S3 Bucket

### Option A: Using AWS Console (Easiest)

1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com/)
2. Click **"Create bucket"**
3. Configure:
   - **Bucket name**: `wordbridge-uploads-<your-unique-suffix>`
     - Example: `wordbridge-uploads-john-doe-2024`
     - Must be globally unique (lowercase letters, numbers, hyphens only)
   - **AWS Region**: Choose your region (e.g., `us-east-1`)
   - **Object Ownership**: ACLs disabled (recommended)
   - **Block Public Access**: ✅ **Keep all settings enabled** (for security)
   - **Bucket Versioning**: Enable (optional but recommended)
   - **Default encryption**: Enable (SSE-S3 is fine for development)
4. Click **"Create bucket"**

### Option B: Using AWS CLI

```bash
# Generate a unique bucket name
BUCKET_NAME="wordbridge-uploads-$(date +%s)"

# Create bucket
aws s3 mb s3://$BUCKET_NAME --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket $BUCKET_NAME \
  --versioning-configuration Status=Enabled

# Block public access (security)
aws s3api put-public-access-block \
  --bucket $BUCKET_NAME \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo "✅ Bucket created: $BUCKET_NAME"
echo "Add to .env: AWS_S3_BUCKET_NAME=$BUCKET_NAME"
```

## Step 2: Create SQS Queue (Required for Production)

**Note:** SQS is required for production deployments. For development, you can use the in-memory queue, but production needs SQS for reliability and scalability.

### Option A: Using AWS Console (Easiest)

1. Go to [AWS SQS Console](https://console.aws.amazon.com/sqs/)
2. Click **"Create queue"**
3. Configure:
   - **Name**: `wordbridge-upload-jobs`
   - **Type**: **Standard** (default)
   - **Visibility timeout**: `300` seconds (5 minutes - adjust based on your processing time)
   - **Message retention period**: `345600` seconds (4 days - default)
   - **Delivery delay**: `0` seconds
   - **Receive message wait time**: `0` seconds (short polling) or `20` seconds (long polling for cost savings)
   - **Encryption**: Enable (SSE-S3 is fine for development, KMS for production)
4. Click **"Create queue"**
5. After creation, click on the queue name
6. Copy the **Queue URL** (looks like: `https://sqs.us-east-1.amazonaws.com/123456789012/wordbridge-upload-jobs`)

### Option B: Using AWS CLI

```bash
# Create SQS queue
QUEUE_NAME="wordbridge-upload-jobs"
REGION="us-east-1"

aws sqs create-queue \
  --queue-name $QUEUE_NAME \
  --region $REGION \
  --attributes \
    VisibilityTimeout=300,MessageRetentionPeriod=345600

# Get queue URL
QUEUE_URL=$(aws sqs get-queue-url \
  --queue-name $QUEUE_NAME \
  --region $REGION \
  --query 'QueueUrl' \
  --output text)

echo "✅ Queue created: $QUEUE_NAME"
echo "Queue URL: $QUEUE_URL"
echo "Add to .env: AWS_SQS_QUEUE_URL=$QUEUE_URL"
```

## Step 3: Create IAM User for Application

We'll create a dedicated IAM user with minimal S3 and SQS permissions (security best practice).

### Option A: Using AWS Console

1. Go to [IAM Console](https://console.aws.amazon.com/iam/)
2. Click **"Users"** → **"Create user"**
3. **User name**: `wordbridge-app`
4. Click **"Next"**
5. **Set permissions**: Select **"Attach policies directly"**
6. Click **"Create policy"** (opens new tab)
   - Click **"JSON"** tab
   - Paste this policy (replace `wordbridge-uploads-*` with your actual bucket name and `123456789012` with your account ID):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:DeleteObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::wordbridge-uploads-*/*",
           "arn:aws:s3:::wordbridge-uploads-*"
         ]
       },
       {
         "Effect": "Allow",
         "Action": [
           "sqs:SendMessage",
           "sqs:ReceiveMessage",
           "sqs:DeleteMessage",
           "sqs:GetQueueAttributes",
           "sqs:GetQueueUrl"
         ],
         "Resource": ["arn:aws:sqs:*:123456789012:wordbridge-upload-jobs"]
       }
     ]
   }
   ```
   - Click **"Next"** → Name it `WordBridgeAccess`
   - Click **"Create policy"**
7. Go back to user creation tab, refresh, select `WordBridgeAccess` policy
8. Click **"Next"** → **"Create user"**
9. Click on the new user → **"Security credentials"** tab
10. Click **"Create access key"**
11. Select **"Application running outside AWS"**
12. Click **"Next"** → **"Create access key"**
13. **IMPORTANT**: Copy both:
    - **Access key ID**
    - **Secret access key** (shown only once!)

### Option B: Using AWS CLI

```bash
# Create IAM user
aws iam create-user --user-name wordbridge-app

# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create policy document
cat > /tmp/wordbridge-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::wordbridge-uploads-*/*",
        "arn:aws:s3:::wordbridge-uploads-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": [
        "arn:aws:sqs:*:${ACCOUNT_ID}:wordbridge-upload-jobs"
      ]
    }
  ]
}
EOF

# Create policy
aws iam create-policy \
  --policy-name WordBridgeAccess \
  --policy-document file:///tmp/wordbridge-policy.json

# Attach policy to user
aws iam attach-user-policy \
  --user-name wordbridge-app \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/WordBridgeAccess

# Create access keys
aws iam create-access-key --user-name wordbridge-app

# Output will show AccessKeyId and SecretAccessKey
# Save these to your .env file!
```

## Step 4: Add Credentials to .env

Add these lines to your `.env` file:

```bash
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_S3_BUCKET_NAME=wordbridge-uploads-your-unique-name
AWS_SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/wordbridge-upload-jobs
```

**Replace with your actual values:**

- `AWS_ACCESS_KEY_ID`: From Step 3
- `AWS_SECRET_ACCESS_KEY`: From Step 3 (the secret key shown only once)
- `AWS_S3_BUCKET_NAME`: Your bucket name from Step 1
- `AWS_SQS_QUEUE_URL`: Your queue URL from Step 2

**Note:** `AWS_SQS_QUEUE_URL` is optional for development (uses in-memory queue), but **required for production**.

## Step 5: Verify Setup

Test your AWS configuration:

```bash
# Test S3 access
aws s3 ls s3://your-bucket-name

# Or test with Python
python3 -c "
import boto3
import os
from dotenv import load_dotenv

load_dotenv()
s3 = boto3.client('s3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)
print('✅ S3 connection successful!')
print(f'Bucket: {os.getenv(\"AWS_S3_BUCKET_NAME\")}')
"
```

## Security Notes

- ✅ **Never commit `.env` to git** (already in `.gitignore`)
- ✅ **IAM user has minimal permissions** (only S3 and SQS access)
- ✅ **Bucket blocks public access** (private by default)
- ✅ **SQS queue is private** (only accessible with IAM credentials)
- ✅ **Access keys are for application use only** (not your root account)

## Troubleshooting

### "Access Denied" errors

- Verify IAM policy is attached to the user
- Check bucket name matches policy resource ARN
- Ensure access keys are correct in `.env`

### "Bucket not found"

- Verify bucket name is correct (case-sensitive)
- Check you're using the right AWS region
- Ensure bucket exists in your account

### "Invalid credentials"

- Re-check `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`
- Verify no extra spaces or quotes
- Try creating new access keys if needed

## Next Steps

Once AWS is configured:

1. ✅ S3 bucket created
2. ✅ SQS queue created (for production)
3. ✅ IAM user with S3 and SQS permissions
4. ✅ Access keys added to `.env`
5. ✅ Queue URL added to `.env`
6. ✅ Test connection successful

**For Production:**

- Ensure `AWS_SQS_QUEUE_URL` is set in your production environment
- Run the background worker: `python -m app.jobs.worker`
- Consider using a process manager (systemd, supervisor) to keep the worker running

**For Development:**

- You can skip SQS setup and use the in-memory queue
- Still need to run the worker: `python -m app.jobs.worker`
