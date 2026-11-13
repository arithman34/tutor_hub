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

  # The Django rewrite is a plain synchronous web app — no Celery broker/
  # worker/beat, so the redis sidecar from the FastAPI setup is gone too.
  container_environment = [
    { name = "GOOGLE_CLIENT_ID", value = var.google_client_id },
    { name = "GOOGLE_REDIRECT_URI", value = "https://${var.domain_name}/calendar/callback" },
    { name = "ZOOM_CLIENT_ID", value = var.zoom_client_id },
    { name = "ZOOM_REDIRECT_URI", value = "https://${var.domain_name}/api/v1/zoom/callback" },
    { name = "FROM_EMAIL", value = var.from_email },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "DJANGO_DEBUG", value = "false" },
    # "localhost" is needed because the container's own health check hits
    # http://localhost:8000/health — without it in ALLOWED_HOSTS, Django
    # returns 400 for that request and ECS marks the task unhealthy.
    { name = "DJANGO_ALLOWED_HOSTS", value = "${var.domain_name},localhost" },
    { name = "CSRF_TRUSTED_ORIGINS", value = "https://${var.domain_name}" },
    { name = "POSTGRES_HOST", value = local.foundation.rds_address },
    { name = "POSTGRES_PORT", value = "5432" },
    { name = "POSTGRES_USER", value = local.foundation.db_username },
    { name = "POSTGRES_DB", value = local.foundation.db_name_django },
    { name = "BACKUP_BUCKET", value = local.foundation.backup_bucket },
  ]

  container_secrets = [
    { name = "DJANGO_SECRET_KEY", valueFrom = local.foundation.ssm_parameter_arns.secret_key },
    { name = "POSTGRES_PASSWORD", valueFrom = local.foundation.ssm_parameter_arns.db_password },
    { name = "OPENAI_API_KEY", valueFrom = local.foundation.ssm_parameter_arns.openai_api_key },
    { name = "RESEND_API_KEY", valueFrom = local.foundation.ssm_parameter_arns.resend_api_key },
    { name = "GOOGLE_CLIENT_SECRET", valueFrom = local.foundation.ssm_parameter_arns.google_client_secret },
    { name = "ZOOM_CLIENT_SECRET", valueFrom = local.foundation.ssm_parameter_arns.zoom_client_secret },
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
        "gunicorn", "config.wsgi:application",
        "--bind", "0.0.0.0:8000",
        "--workers", "2",
        # TutorHub AI answers can take several LLM round trips (agent budget
        # 45s). Gunicorn's default 30s would kill those workers; 55s still sits
        # well inside Cloudflare's 100s proxy timeout.
        "--timeout", "55",
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

  # The deploy workflow registers a new revision of this family per commit,
  # pinned to that commit's image, and points the service at it. Without this,
  # the next apply would reset the service to the :latest revision above.
  # Edits to the task definition here are picked up on the next deploy.
  lifecycle {
    ignore_changes = [task_definition]
  }

  depends_on = [aws_ecs_cluster_capacity_providers.main]
}
