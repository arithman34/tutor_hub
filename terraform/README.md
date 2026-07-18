# TutorHub — AWS infrastructure

Terraform for running TutorHub on managed AWS services: ECS Fargate for compute,
RDS PostgreSQL (with pgvector) for data, ElastiCache (Valkey) as the Celery
broker, behind an ALB with an ACM certificate. DNS stays on Cloudflare.

## Design decisions

- **No NAT gateway (~$40/mo saved).** Tasks run in public subnets with public
  IPs, locked down by security groups (only the ALB can reach port 8000).
- **RDS sits in public subnets but has no public IP by default.** Flipping
  `db_publicly_accessible = true` plus `admin_cidrs = ["<your-ip>/32"]` gives
  temporary direct psql access without paying for a bastion. Flip it back after.
- **Worker and beat run on Fargate Spot** (~70% cheaper). An interruption only
  delays the daily alert email by a minute or two while ECS replaces the task.
- **Beat deploys with `minimum_healthy_percent = 0`** so two schedulers never
  run at once.
- **Valkey instead of Redis engine**: protocol-compatible (Celery unchanged),
  ~20% cheaper on ElastiCache.
- **Secrets live in SSM Parameter Store** (SecureString, free tier) and are
  injected by ECS at task start; they never appear in task definitions.
- **GitHub Actions deploys via an OIDC role** — no long-lived AWS keys stored
  in GitHub.

## Estimated monthly cost (eu-west-2, on-demand)

| Component | ~$/mo |
|---|---|
| ALB | 19 |
| Fargate: api (0.25 vCPU / 1 GB) | 12 |
| Fargate Spot: worker + beat (0.25 / 0.5 each) | 6 |
| RDS db.t4g.micro + 20 GB gp3 | 16 |
| ElastiCache Valkey cache.t4g.micro | 9 |
| Public IPv4 (2 ALB + 3 tasks × $3.65) | 18 |
| CloudWatch logs, data transfer | 2 |
| **Total** | **~82** |

Cost levers if this gets heavy: run the worker with `-B` (embedded beat) to
drop one service; or fall back to a single EC2 t4g.small running docker
compose (~$18/mo total).

## First deploy (order matters)

1. **Init and create the ECR repo + certificate first:**

   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars   # fill in real values
   terraform init
   terraform apply -target=aws_ecr_repository.app -target=aws_acm_certificate.main
   ```

2. **Validate the certificate.** `terraform output acm_validation_records`,
   then add that CNAME in Cloudflare with the proxy **off** (grey cloud,
   "DNS only").

3. **Push the first image** (later deploys are CI's job):

   ```bash
   aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-west-2.amazonaws.com
   docker build -t <ecr_repository_url>:latest ..
   docker push <ecr_repository_url>:latest
   ```

4. **Apply everything:** `terraform apply`. The api task boots, runs
   `alembic upgrade head` (which also creates the pgvector extension — the
   RDS master user is allowed to), and registers with the ALB. Check
   `/ecs/tutorhub` logs in CloudWatch if the target stays unhealthy.

5. **Cut over DNS.** In Cloudflare, point the `tutorhub` CNAME at
   `alb_dns_name` (orange cloud on), SSL/TLS mode **Full (strict)**.

6. **Restore data through the app.** RDS starts empty and the api task runs
   `alembic upgrade head` on boot, so the schema is already at head. Open the
   app, land on `/setup`, create a temporary admin, then use the admin JSON
   import to load an export from the app's own admin export (users — with their
   original password hashes — payees, students, sessions, payments). The import
   replaces the setup account with the real data. Google Calendar tokens and RAG
   documents are not in the export: reconnect Calendar and re-upload documents
   afterwards.

   > The `db_publicly_accessible` / `admin_cidrs` variables remain for one-off
   > direct psql access (open them to your `/32`, `terraform apply`, then revert),
   > but the normal restore path is the in-app JSON import above — no direct DB
   > access needed.

7. **Wire up CI.** Add `deploy_role_arn` as the `AWS_DEPLOY_ROLE_ARN` secret
   in the GitHub repo and switch the deploy workflow to: build → push to ECR
   (tags: git SHA + latest) → `aws ecs update-service --force-new-deployment`
   for api, worker, beat.

## Day-2 notes

- **Debug shell into a task:**
  `aws ecs execute-command --cluster tutorhub --task <task-id> --container api --interactive --command /bin/bash`
- **RDS is protected**: `deletion_protection = true` and a final snapshot on
  destroy. `terraform destroy` will (intentionally) refuse until you flip that.
- **State is local** until you enable the S3 backend stub in `versions.tf`.
