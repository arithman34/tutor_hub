output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "rds_address" {
  description = "Postgres hostname (reachable from ECS tasks; from admin_cidrs when db_publicly_accessible = true)."
  value       = aws_db_instance.main.address
}

output "rds_security_group_id" {
  description = "Attach an ingress rule from your compute environment's app security group to this — RDS itself only allows admin_cidrs by default."
  value       = aws_security_group.rds.id
}

output "ecr_repository_url" {
  description = "Push the app image here (tag: latest)."
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.app.arn
}

output "task_execution_role_arn" {
  value = aws_iam_role.task_execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "deploy_role_arn" {
  description = "Set as the AWS_DEPLOY_ROLE_ARN secret in the GitHub repo."
  value       = aws_iam_role.github_deploy.arn
}

output "ssm_parameter_arns" {
  description = "Map of secret name -> SSM parameter ARN, for use in ECS task definition `secrets` blocks."
  value = {
    database_url         = aws_ssm_parameter.database_url.arn
    secret_key            = aws_ssm_parameter.secret_key.arn
    openai_api_key        = aws_ssm_parameter.openai_api_key.arn
    resend_api_key        = aws_ssm_parameter.resend_api_key.arn
    google_client_secret  = aws_ssm_parameter.google_client_secret.arn
    cloudflare_tunnel_token = aws_ssm_parameter.cloudflare_tunnel_token.arn
  }
}
