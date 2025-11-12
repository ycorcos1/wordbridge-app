#!/usr/bin/env python3
"""
Test AWS Configuration for WordBridge

This script verifies that your AWS credentials and S3 bucket are configured correctly.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("❌ ERROR: boto3 not installed.")
    print("   Run: pip install boto3")
    sys.exit(1)


def test_aws_config():
    """Test AWS configuration."""
    print("🧪 Testing AWS Configuration\n")
    print("=" * 60)
    
    # Check environment variables
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    
    missing = []
    if not access_key:
        missing.append("AWS_ACCESS_KEY_ID")
    if not secret_key:
        missing.append("AWS_SECRET_ACCESS_KEY")
    if not bucket_name:
        missing.append("AWS_S3_BUCKET_NAME")
    
    if missing:
        print("❌ Missing environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\n   Add these to your .env file (see docs/AWS_SETUP.md)")
        return False
    
    print("✅ Environment variables found")
    print(f"   Access Key ID: {access_key[:8]}...")
    print(f"   Bucket Name: {bucket_name}\n")
    
    # Test S3 connection
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        
        # Test bucket access
        print("🔍 Testing S3 bucket access...")
        s3.head_bucket(Bucket=bucket_name)
        print(f"✅ Successfully connected to bucket: {bucket_name}")
        
        # List objects (should work even if empty)
        print("🔍 Testing list permissions...")
        response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        print("✅ List permissions working")
        
        # Test write permission (create a test object)
        print("🔍 Testing write permissions...")
        test_key = "test/connection-test.txt"
        s3.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=b"WordBridge connection test",
        )
        print("✅ Write permissions working")
        
        # Clean up test object
        print("🔍 Cleaning up test object...")
        s3.delete_object(Bucket=bucket_name, Key=test_key)
        print("✅ Cleanup complete")
        
        print("\n" + "=" * 60)
        print("✅ All AWS tests passed!")
        print("=" * 60)
        return True
        
    except NoCredentialsError:
        print("❌ Invalid AWS credentials")
        print("   Check your AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "403":
            print("❌ Access denied")
            print("   Check IAM user permissions")
        elif error_code == "404":
            print("❌ Bucket not found")
            print(f"   Verify bucket name: {bucket_name}")
        else:
            print(f"❌ Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = test_aws_config()
    sys.exit(0 if success else 1)

