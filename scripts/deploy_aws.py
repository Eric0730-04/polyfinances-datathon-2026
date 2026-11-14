"""Build the container, push it to Amazon ECR and serve it from AWS Lambda behind a public HTTPS function URL.

Why Lambda: scales to zero when idle (no cost between demos), HTTPS out of the box, and reserved concurrency is a
hard cap on simultaneous requests (cost guard for a public demo). The AWS Lambda Web Adapter runs the unchanged
FastAPI app and streams responses, so agent progress still arrives live. (App Runner is blocked by the event's
service control policy.)

Usage: AWS_PROFILE=team10 python scripts/deploy_aws.py [--skip-build]
"""
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
REGION, NAME = "us-east-1", "secondlook"
sess = boto3.Session(region_name=REGION)
acct = sess.client("sts").get_caller_identity()["Account"]
cfg = json.loads((ROOT / "aws_resources.json").read_text())
ecr, iam, lam = sess.client("ecr"), sess.client("iam"), sess.client("lambda")
repo = f"{acct}.dkr.ecr.{REGION}.amazonaws.com/{NAME}"
tag = time.strftime("v%Y%m%d-%H%M%S")

# ---- image (single-platform manifest: Lambda does not accept attestation indexes)
try:
    ecr.create_repository(repositoryName=NAME, imageScanningConfiguration={"scanOnPush": True})
except ecr.exceptions.RepositoryAlreadyExistsException:
    pass
if "--skip-build" not in sys.argv:
    auth = ecr.get_authorization_token()["authorizationData"][0]
    user, pwd = base64.b64decode(auth["authorizationToken"]).decode().split(":")
    subprocess.run(["docker", "login", "-u", user, "--password-stdin", auth["proxyEndpoint"]], input=pwd.encode(), check=True)
    subprocess.run(["docker", "buildx", "build", "--platform", "linux/amd64", "--provenance=false", "--sbom=false",
                    "-t", f"{repo}:{tag}", "--push", str(ROOT)], check=True)
image = f"{repo}:{tag}"

# ---- IAM role: logs + Bedrock invoke + this guardrail + this bucket only
trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
rname = "secondlook-lambda"
try:
    role_arn = iam.create_role(RoleName=rname, AssumeRolePolicyDocument=json.dumps(trust))["Role"]["Arn"]
    time.sleep(10)
except iam.exceptions.EntityAlreadyExistsException:
    role_arn = iam.get_role(RoleName=rname)["Role"]["Arn"]
iam.attach_role_policy(RoleName=rname, PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
iam.put_role_policy(RoleName=rname, PolicyName="secondlook-app", PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [
    {"Effect": "Allow", "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], "Resource": "*"},
    {"Effect": "Allow", "Action": ["bedrock:ApplyGuardrail"], "Resource": f"arn:aws:bedrock:{REGION}:{acct}:guardrail/{cfg['guardrail_id']}"},
    {"Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject"], "Resource": f"arn:aws:s3:::{cfg['bucket']}/*"},
    {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": f"arn:aws:s3:::{cfg['bucket']}"}]}))

# ---- function
env = {"Variables": {"RATE_LIMIT": "1", "MAX_CONCURRENT_RUNS": "6"}}
try:
    lam.get_function(FunctionName=NAME)
    lam.update_function_code(FunctionName=NAME, ImageUri=image)
    lam.get_waiter("function_updated_v2").wait(FunctionName=NAME)
    lam.update_function_configuration(FunctionName=NAME, Environment=env, MemorySize=2048, Timeout=180)
    print("updated", NAME)
except lam.exceptions.ResourceNotFoundException:
    for attempt in range(5):  # new roles take a moment to become assumable
        try:
            lam.create_function(FunctionName=NAME, PackageType="Image", Code={"ImageUri": image}, Role=role_arn,
                                MemorySize=2048, Timeout=180, Architectures=["x86_64"], Environment=env,
                                Description="SecondLook - PolyFinances Datathon 2026 demo (simulation only)")
            break
        except lam.exceptions.InvalidParameterValueException as e:
            print("waiting for role…", str(e)[:80]); time.sleep(10)
    print("created", NAME)
lam.get_waiter("function_active_v2").wait(FunctionName=NAME)
lam.get_waiter("function_updated_v2").wait(FunctionName=NAME)
lam.put_function_concurrency(FunctionName=NAME, ReservedConcurrentExecutions=20)  # hard cap on simultaneous requests

# ---- public HTTPS URL with response streaming
try:
    url = lam.create_function_url_config(FunctionName=NAME, AuthType="NONE", InvokeMode="RESPONSE_STREAM")["FunctionUrl"]
except lam.exceptions.ResourceConflictException:
    url = lam.get_function_url_config(FunctionName=NAME)["FunctionUrl"]
for sid, kw in (("public-url", dict(Action="lambda:InvokeFunctionUrl", FunctionUrlAuthType="NONE")),
                ("public-invoke", dict(Action="lambda:InvokeFunction", InvokedViaFunctionUrl=True))):
    try:
        lam.add_permission(FunctionName=NAME, StatementId=sid, Principal="*", **kw)
    except lam.exceptions.ResourceConflictException:
        pass
    except Exception as e:  # older APIs without InvokedViaFunctionUrl
        print("permission note:", str(e)[:120])
cfg["app_url"] = url.rstrip("/")
(ROOT / "aws_resources.json").write_text(json.dumps(cfg, indent=2))
print("URL:", url)
