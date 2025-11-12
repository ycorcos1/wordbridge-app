#!/usr/bin/env python3
"""
AWS Resource Setup Script for WordBridge

This script helps automate AWS resource creation:
- S3 bucket for file uploads
- SQS queue for background job processing (optional but recommended for production)
- IAM user with minimal S3 and SQS permissions
- Outputs credentials for .env file

Prerequisites:
- AWS CLI installed and configured (aws configure)
- boto3 installed (pip install boto3)
"""

import json
import secrets
import sys
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("❌ ERROR: boto3 not installed.")
    print("   Run: pip install boto3")
    sys.exit(1)


def generate_bucket_name() -> str:
    """Generate a unique S3 bucket name."""
    random_suffix = secrets.token_hex(4)
    return f"wordbridge-uploads-{random_suffix}"


def create_s3_bucket(bucket_name: str, region: str = "us-east-1") -> dict:
    """Create an S3 bucket for file uploads."""
    s3 = boto3.client("s3", region_name=region)
    
    try:
        if region == "us-east-1":
            # us-east-1 doesn't require LocationConstraint
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region}
            )
        
        # Enable versioning (optional but recommended)
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": "Enabled"}
        )
        
        # Block public access (security best practice)
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        )
        
        print(f"✅ S3 bucket '{bucket_name}' created successfully in {region}")
        return {"bucket_name": bucket_name, "region": region}
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "BucketAlreadyExists":
            print(f"⚠️  Bucket '{bucket_name}' already exists. Using existing bucket.")
            return {"bucket_name": bucket_name, "region": region}
        else:
            print(f"❌ Error creating S3 bucket: {e}")
            raise


def create_sqs_queue(queue_name: str, region: str = "us-east-1") -> dict:
    """Create an SQS queue for background job processing."""
    sqs = boto3.client("sqs", region_name=region)
    
    try:
        # Create queue with appropriate attributes
        response = sqs.create_queue(
            QueueName=queue_name,
            Attributes={
                "VisibilityTimeout": "300",  # 5 minutes
                "MessageRetentionPeriod": "345600",  # 4 days
                "ReceiveMessageWaitTimeSeconds": "0",  # Short polling (change to 20 for long polling)
            }
        )
        queue_url = response["QueueUrl"]
        print(f"✅ SQS queue '{queue_name}' created successfully in {region}")
        return {"queue_name": queue_name, "queue_url": queue_url, "region": region}
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "QueueAlreadyExists":
            # Queue exists, get its URL
            response = sqs.get_queue_url(QueueName=queue_name)
            queue_url = response["QueueUrl"]
            print(f"⚠️  Queue '{queue_name}' already exists. Using existing queue.")
            return {"queue_name": queue_name, "queue_url": queue_url, "region": region}
        else:
            print(f"❌ Error creating SQS queue: {e}")
            raise


def create_iam_user(username: str = "wordbridge-app", queue_name: str = None) -> dict:
    """Create IAM user with S3 and SQS access permissions."""
    iam = boto3.client("iam")
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    
    # Create user
    try:
        iam.create_user(UserName=username)
        print(f"✅ IAM user '{username}' created")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"⚠️  IAM user '{username}' already exists. Using existing user.")
        else:
            print(f"❌ Error creating IAM user: {e}")
            raise
    
    # Create policy with S3 and SQS permissions
    policy_statements = [
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
        }
    ]
    
    # Add SQS permissions if queue name provided
    if queue_name:
        policy_statements.append({
            "Effect": "Allow",
            "Action": [
                "sqs:SendMessage",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes",
                "sqs:GetQueueUrl"
            ],
            "Resource": [
                f"arn:aws:sqs:*:{account_id}:{queue_name}"
            ]
        })
    
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": policy_statements
    }
    
    policy_name = f"{username}-policy"
    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
    
    try:
        # Create policy
        iam.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_doc),
            Description="WordBridge S3 and SQS access"
        )
        print(f"✅ IAM policy '{policy_name}' created")
    except ClientError as e:
        if "EntityAlreadyExists" in str(e):
            print(f"⚠️  Policy already exists. Attaching to user...")
        else:
            print(f"⚠️  Policy creation issue: {e}")
    
    # Attach policy to user
    try:
        iam.attach_user_policy(UserName=username, PolicyArn=policy_arn)
        print(f"✅ Policy attached to user")
    except ClientError as e:
        if "EntityAlreadyExists" not in str(e):
            print(f"⚠️  Policy attachment issue: {e}")
    
    # Create access keys
    try:
        # Check existing keys first
        existing_keys = iam.list_access_keys(UserName=username)
        if len(existing_keys.get("AccessKeyMetadata", [])) >= 2:
            print("⚠️  User already has 2 access keys (maximum).")
            print("   Please delete one in AWS Console or use existing keys.")
            response = existing_keys["AccessKeyMetadata"][0]
            return {
                "access_key_id": response["AccessKeyId"],
                "secret_access_key": "*** (retrieve from AWS Console - IAM → Users → Security credentials)",
            }
        
        response = iam.create_access_key(UserName=username)
        access_key = response["AccessKey"]
        print(f"✅ Access keys created for '{username}'")
        return {
            "access_key_id": access_key["AccessKeyId"],
            "secret_access_key": access_key["SecretAccessKey"],
        }
    except ClientError as e:
        print(f"❌ Error creating access keys: {e}")
        raise


def main():
    """Main setup function."""
    print("🚀 WordBridge AWS Setup\n")
    print("=" * 60)
    
    # Test AWS credentials
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        account_id = identity["Account"]
        print(f"✅ AWS credentials verified")
        print(f"   Account ID: {account_id}")
        print(f"   User/Role: {identity.get('Arn', 'N/A')}\n")
    except NoCredentialsError:
        print("❌ ERROR: AWS credentials not found.")
        print("   Run 'aws configure' first to set up your credentials.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)
    
    # Get region
    region = input("Enter AWS region (default: us-east-1): ").strip() or "us-east-1"
    
    # Create S3 bucket
    print(f"\n📦 Creating S3 bucket...")
    use_custom_name = input("Use custom bucket name? (y/N): ").strip().lower()
    if use_custom_name == "y":
        bucket_name = input("Enter bucket name: ").strip()
        if not bucket_name:
            print("❌ Bucket name cannot be empty")
            sys.exit(1)
    else:
        bucket_name = generate_bucket_name()
        print(f"   Generated name: {bucket_name}")
    
    try:
        bucket_info = create_s3_bucket(bucket_name, region)
    except Exception as e:
        print(f"❌ Failed to create bucket: {e}")
        sys.exit(1)
    
    # Create SQS queue (optional)
    print(f"\n📬 Creating SQS queue for background jobs...")
    create_queue = input("Create SQS queue? (Y/n): ").strip().lower()
    queue_info = None
    queue_name = None
    
    if create_queue != "n":
        use_custom_queue = input("Use custom queue name? (y/N, default: wordbridge-upload-jobs): ").strip().lower()
        if use_custom_queue == "y":
            queue_name = input("Enter queue name: ").strip()
            if not queue_name:
                print("❌ Queue name cannot be empty")
                sys.exit(1)
        else:
            queue_name = "wordbridge-upload-jobs"
        
        try:
            queue_info = create_sqs_queue(queue_name, region)
        except Exception as e:
            print(f"❌ Failed to create queue: {e}")
            print("⚠️  Continuing without SQS (will use in-memory queue)")
    
    # Create IAM user
    print(f"\n👤 Creating IAM user for application access...")
    use_custom_user = input("Use custom IAM user name? (y/N, default: wordbridge-app): ").strip().lower()
    username = "wordbridge-app"
    if use_custom_user == "y":
        username = input("Enter IAM user name: ").strip() or username
    
    try:
        iam_creds = create_iam_user(username, queue_name)
    except Exception as e:
        print(f"❌ Failed to create IAM user/keys: {e}")
        sys.exit(1)
    
    # Output summary
    print("\n" + "=" * 60)
    print("✅ AWS Setup Complete!")
    print("=" * 60)
    print("\n📝 Add these to your .env file:\n")
    print(f"AWS_ACCESS_KEY_ID={iam_creds['access_key_id']}")
    if iam_creds['secret_access_key'].startswith("***"):
        print(f"AWS_SECRET_ACCESS_KEY={iam_creds['secret_access_key']}")
        print("\n⚠️  You need to retrieve the secret key from AWS Console:")
        print(f"   IAM → Users → {username} → Security credentials → Access keys")
    else:
        print(f"AWS_SECRET_ACCESS_KEY={iam_creds['secret_access_key']}")
        print("\n⚠️  IMPORTANT: Save the AWS_SECRET_ACCESS_KEY securely!")
        print("   It will not be shown again. If lost, create new keys in AWS Console.")
    print(f"AWS_S3_BUCKET_NAME={bucket_info['bucket_name']}")
    if queue_info:
        print(f"AWS_SQS_QUEUE_URL={queue_info['queue_url']}")
        print("\n✅ SQS queue configured - ready for production!")
    else:
        print("\n⚠️  No SQS queue created - will use in-memory queue (development only)")
    print("\n" + "=" * 60)
    print("\n✅ Next steps:")
    print("   1. Copy the values above to your .env file")
    print("   2. Test connection: python3 -c \"import boto3; print('✅ AWS ready')\"")
    print("   3. See docs/AWS_SETUP.md for manual setup instructions")
    if queue_info:
        print("   4. Run background worker: python -m app.jobs.worker")


if __name__ == "__main__":
    main()

