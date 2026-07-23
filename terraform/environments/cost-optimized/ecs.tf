resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${local.name}"
  retention_in_days = 14
}

locals {
  image = "${local.foundation.ecr_repository_url}:latest"

  # Broker now runs as a sidecar container in the same task, reachable over
  # localhost since all containers share one ENI (awsvpc network mode).
  container_environment = [
    { name = "REDIS_URL", value = "redis://localhost:6379/0" },
    { name = "GOOGLE_CLIENT_ID", value = var.google_client_id },
    { name = "GOOGLE_REDIRECT_URI", value = "https://${var.domain_name}/calendar/callback" },
    { name = "FROM_EMAIL", value = var.from_email },
  ]

  container_secrets = [
    { name = "DATABASE_URL", valueFrom = local.foundation.ssm_parameter_arns.database_url },
    { name = "SECRET_KEY", valueFrom = local.foundation.ssm_parameter_arns.secret_key },
    { name = "OPENAI_API_KEY", valueFrom = local.foundation.ssm_parameter_arns.openai_api_key },
    { name = "RESEND_API_KEY", valueFrom = local.foundation.ssm_parameter_arns.resend_api_key },
    { name = "GOOGLE_CLIENT_SECRET", valueFrom = local.foundation.ssm_parameter_arns.google_client_secret },
  ]

  log_options = {
    awslogs-group  = aws_cloudwatch_log_group.ecs.name
    awslogs-region = var.aws_region
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${local.name}-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = local.foundation.task_execution_role_arn
  task_role_arn            = local.foundation.task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = local.image
      essential = true
      command = [
        "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--proxy-headers",
        "--forwarded-allow-ips", "*",
      ]
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment  = local.container_environment
      secrets      = local.container_secrets
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
      logConfiguration = {
        logDriver = "awslogs"
        options   = merge(local.log_options, { awslogs-stream-prefix = "api" })
      }
    },
    {
      name        = "worker"
      image       = local.image
      essential   = true
      command     = ["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info"]
      environment = local.container_environment
      secrets     = local.container_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options   = merge(local.log_options, { awslogs-stream-prefix = "worker" })
      }
    },
    {
      name        = "beat"
      image       = local.image
      essential   = true
      command     = ["celery", "-A", "app.worker.celery_app", "beat", "--loglevel=info"]
      environment = local.container_environment
      secrets     = local.container_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options   = merge(local.log_options, { awslogs-stream-prefix = "beat" })
      }
    },
    {
      name         = "redis"
      image        = "valkey/valkey:8-alpine"
      essential    = true
      portMappings = [{ containerPort = 6379, protocol = "tcp" }]
      logConfiguration = {
        logDriver = "awslogs"
        options   = merge(local.log_options, { awslogs-stream-prefix = "redis" })
      }
    },
    {
      name      = "cloudflared"
      image     = "cloudflare/cloudflared:latest"
      essential = true
      command   = ["tunnel", "--no-autoupdate", "run"]
      secrets = [
        { name = "TUNNEL_TOKEN", valueFrom = local.foundation.ssm_parameter_arns.cloudflare_tunnel_token },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options   = merge(local.log_options, { awslogs-stream-prefix = "cloudflared" })
      }
    }
  ])
}

resource "aws_ecs_service" "app" {
  name            = "app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1

  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }

  enable_execute_command = true

  network_configuration {
    subnets          = local.foundation.public_subnet_ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_ecs_cluster_capacity_providers.main]
}
