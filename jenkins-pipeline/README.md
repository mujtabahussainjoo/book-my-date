# Jenkins production pipelines

This folder contains two equivalent production pipelines for **Book My Date**:

- `Jenkinsfile.declarative` — Declarative Pipeline syntax.
- `Jenkinsfile.scripted` — Scripted Pipeline syntax.

Both build, test, scan, package, publish, approve, deploy, smoke-test, and monitor a Linux release. The deployable artifact is a native PyInstaller archive plus a Python wheel. Because this is a desktop application, production deployment targets a versioned S3 release bucket instead of Kubernetes; CloudWatch is used for release-health telemetry. If the application later gains a containerized service, replace the Build/Publish/Deploy stages with Docker, ECR, and EKS equivalents.

Windows and macOS archives are currently produced by `.github/workflows/build.yml`. Add platform-labelled agents and archive stages to Jenkins if all three native releases must be promoted from one pipeline. Snyk can be appended to the Security Checks stage when a licensed token is available; pip-audit and Trivy provide the default open-source gate.

## Pipeline stages

| Stage | What happens | Tooling |
|---|---|---|
| Checkout | Clean workspace and fetch source | Git |
| Dependencies | Create a clean venv and install pinned-range dependencies | `venv`, `pip` |
| Code Quality | Lint and byte-compile source | Ruff, `compileall` |
| Unit Tests | Run the full test suite with coverage | pytest, pytest-cov |
| Integration Tests | Exercise wizard HTTP server, SQLite, and reminders together | pytest |
| Security Checks | Audit dependencies and scan for vulnerabilities/secrets | pip-audit, Trivy |
| Quality Gate | Analyze code and enforce the SonarQube gate | SonarScanner, SonarQube |
| Build | Build the Linux PyInstaller release and wheel; verify tag/version | PyInstaller, pip |
| Publish | Upload staging artifact, checksum, wheel, and metadata | AWS CLI, S3 |
| Approval | Require release-manager authorization | Jenkins `input` |
| Deploy | Copy the approved artifact to the production prefix | AWS CLI, S3 |
| Smoke Test | Download production artifact, verify checksum, run headless `--version` | AWS CLI, `sha256sum`, `unzip` |
| Monitoring | Emit release metrics and fail if related CloudWatch alarms are active | AWS CLI, CloudWatch |

The stage order puts tests and security checks before the release artifact is built, so a broken revision cannot be published.

## Branch and tag behavior

- Pull requests and feature branches: checkout, dependencies, quality, tests, and scans only.
- `main`: additionally publishes the artifact to `s3://<bucket>/staging/<build-number>/`.
- `v*` tags: publish, request approval, deploy to production, smoke-test, and monitor.
- The tag must match the application version. For example, `VERSION = "1.0.0"` requires tag `v1.0.0`.

## Jenkins job setup

1. Create a **Multibranch Pipeline** job (recommended) or a Pipeline job using **Pipeline script from SCM**.
2. Point the job at this repository.
3. Set **Script Path** to one of:
   - `jenkins-pipeline/Jenkinsfile.declarative`
   - `jenkins-pipeline/Jenkinsfile.scripted`
4. Configure a Linux agent labelled `linux`. Change `agent { label 'linux' }` or `node('linux')` if your agent label differs.
5. Configure SCM webhooks so branch and tag events trigger builds.

### Required Jenkins plugins

- Pipeline
- Credentials Binding
- AWS Credentials
- SonarQube Scanner
- Sonar Quality Gates
- JUnit
- Workspace Cleanup
- Timestamper

### Credentials and access

| ID / name | Type | Purpose |
|---|---|---|
| `aws-release` | AWS Credentials | S3 publish/deploy, ECR access if added later, CloudWatch metrics |
| `SonarQube` | SonarQube server | Scanner endpoint and quality gate |
| `release-managers` | Jenkins group | Users allowed to approve production deployment |

Update these IDs in both Jenkinsfiles if your Jenkins uses different names.

### Agent prerequisites

The Linux agent must provide:

- Python 3.12 with `venv`
- Git and Bash
- `zip` / `unzip`
- AWS CLI v2
- Trivy
- SonarScanner
- Qt runtime libraries needed by the packaged smoke test:
  - `libegl1`
  - `libxkbcommon-x11-0`
  - `libxcb-cursor0`

The smoke test runs with `QT_QPA_PLATFORM=offscreen`, so no X server is required.

## S3 configuration

The pipeline defaults to:

```text
Bucket: book-my-date-releases
Region: us-east-1
Staging prefix: staging/<build-number>/
Production prefix: releases/<application-version>/
```

Change `S3_BUCKET` and `AWS_DEFAULT_REGION` in both Jenkinsfiles if needed. The bucket should have:

- Versioning enabled.
- Default encryption enabled.
- Public access blocked.
- Lifecycle rules for staging cleanup.
- Least-privilege IAM for the `aws-release` credential.

Minimum pipeline permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::book-my-date-releases"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectTagging"],
      "Resource": "arn:aws:s3:::book-my-date-releases/*"
    },
    {
      "Effect": "Allow",
      "Action": ["cloudwatch:PutMetricData", "cloudwatch:DescribeAlarms"],
      "Resource": "*"
    }
  ]
}
```

## Monitoring

After a successful smoke test, the pipeline writes these CloudWatch metrics in the `BookMyDate/Release` namespace:

- `SmokeTestSuccess`
- `ArtifactSizeBytes`

Both use dimensions `Version` and `Environment=production`. The Monitoring stage also checks alarms whose names start with `book-my-date` and fails the build if any are in `ALARM` state. Create those alarms in CloudWatch using these metrics and S3/release events.

## Pipeline parameters

Both pipelines expose:

- `RUN_SECURITY_SCANS` — toggles pip-audit and Trivy. Default: enabled.
- `RUN_SONAR` — toggles SonarQube analysis and the quality gate. Default: enabled.

Disable a parameter only for an explicitly diagnosed emergency; production releases should keep both enabled.

## Local validation

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest tests -q
.venv/bin/python packaging/build.py
```

The Jenkins pipelines install dependencies from `requirements.txt` and `requirements-dev.txt`; add pytest, pytest-cov, and pip-audit there when maintaining the CI contract.
