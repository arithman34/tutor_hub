# Environments

Three independent Terraform root modules, each with its own local state:

- **`foundation/`** — VPC, RDS (with pgvector data), ECR, IAM roles, and all
  SSM secrets. This is the layer that's expensive/impossible to recreate
  without data loss or downtime. It is never destroyed as part of a
  production ↔ cost-optimized switch.
- **`production/`** — today's live shape: ALB + ACM cert, 3 separate ECS
  services (api / worker / beat), managed ElastiCache (Valkey). Kept as a
  reference/portfolio-quality config demonstrating the "proper" managed-HA
  architecture. Not intended to be applied day-to-day.
- **`cost-optimized/`** — the lean shape actually meant to run: a single
  Fargate task (api + worker + beat + a self-hosted Valkey container, all
  reachable over `localhost`) fronted by a Cloudflare Tunnel sidecar instead
  of an ALB. No managed cache, no load balancer, no public inbound ports.

`production` and `cost-optimized` each read `foundation`'s outputs via
`terraform_remote_state` (local backend, pointed at
`../foundation/terraform.tfstate`) — they never define the VPC/RDS/ECR/IAM
themselves. That's what makes switching between them safe: destroying
`production`'s resources only removes the ALB/ECS-services/ElastiCache;
`foundation` (and your data) is untouched.

**Only ever have one of `production` / `cost-optimized` applied at a time.**
Both default to the same resource names (`tutorhub` cluster, `tutorhub-app`
security group name, etc.) and the same domain, so applying both
concurrently will collide.

## Migrating the currently-live infrastructure into this layout

The old flat `terraform/*.tf` + `terraform/terraform.tfstate` at the repo
root is untouched by this restructuring — it's still the real source of
truth for what's running today. Nothing above has been applied yet. Moving
the live resources into `foundation` + `production` state is a separate,
deliberate step:

1. **Back up state first**: copy `terraform/terraform.tfstate` somewhere safe.
2. Init both `foundation/` and a temporary copy of the old root config, then
   use `terraform state mv -state-out=../foundation/terraform.tfstate <addr>`
   for each foundation-owned resource (`aws_vpc.main`, `aws_subnet.public`,
   `aws_subnet.private`, `aws_internet_gateway.main`, the route tables,
   `aws_db_subnet_group.main`, `aws_security_group.rds` + its admin ingress
   rules, `aws_db_instance.main`, `random_password.db`, `aws_ecr_repository.app`
   + lifecycle policy, all the IAM roles/policies, and the SSM parameters).
   What's left in the old state becomes `production`'s state — rename/move
   that state file into `environments/production/terraform.tfstate`.
3. Run `terraform plan` in **both** new directories and confirm each shows
   **no changes** before touching anything else. This is the checkpoint —
   don't proceed if either plan wants to create/destroy something.
4. Only then is it safe to delete the old root `terraform/*.tf` files.

Do this together, one command at a time, rather than scripting it — a
mistake here risks orphaning the RDS instance from Terraform's tracking.

## Cutting over from production to cost-optimized

Once the live state is split as above:

1. Set up the Cloudflare Tunnel in the Zero Trust dashboard (Networks >
   Tunnels), grab its token, put it in `foundation/terraform.tfvars` as
   `cloudflare_tunnel_token`, `terraform apply` in `foundation/` (only adds/
   updates an SSM parameter — harmless).
2. Point the tunnel's public hostname at `http://localhost:8000` (this
   resolves inside the task, i.e. the `api` container).
3. `terraform apply` in `cost-optimized/`.
4. Verify the app works end-to-end through the tunnel.
5. `terraform destroy` in `production/` (removes ALB, ACM cert, 3 ECS
   services, ElastiCache — nothing else).
6. Update `.github/workflows/deploy.yml`: it currently loops over
   `api worker beat` service names and assumes a `tutorhub` cluster with
   those three services — change the redeploy step to update the single
   `app` service instead.
