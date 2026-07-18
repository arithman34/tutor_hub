output "alb_dns_name" {
  description = "Point the Cloudflare CNAME for the app domain here (proxied, SSL mode Full strict)."
  value       = aws_lb.main.dns_name
}

output "acm_validation_records" {
  description = "Add these as DNS-only CNAME records in Cloudflare to validate the certificate."
  value = [
    for o in aws_acm_certificate.main.domain_validation_options : {
      name  = o.resource_record_name
      type  = o.resource_record_type
      value = o.resource_record_value
    }
  ]
}

output "ecr_repository_url" {
  description = "Push the app image here (tag: latest)."
  value       = aws_ecr_repository.app.repository_url
}

output "rds_address" {
  description = "Postgres hostname (reachable from ECS tasks; from admin_cidrs when db_publicly_accessible = true)."
  value       = aws_db_instance.main.address
}

output "deploy_role_arn" {
  description = "Set as the AWS_DEPLOY_ROLE_ARN secret in the GitHub repo."
  value       = aws_iam_role.github_deploy.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_names" {
  value = {
    api    = aws_ecs_service.api.name
    worker = aws_ecs_service.worker.name
    beat   = aws_ecs_service.beat.name
  }
}
