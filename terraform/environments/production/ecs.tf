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

  container_environment = [
    { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0" },
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
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
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
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  enable_execute_command            = true
  health_check_grace_period_seconds = 120

  network_configuration {
    subnets          = local.foundation.public_subnet_ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.https]
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = local.foundation.task_execution_role_arn
  task_role_arn            = local.foundation.task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "worker"
      image       = local.image
      essential   = true
      command     = ["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info"]
      environment = local.container_environment
      secrets     = local.container_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name            = "worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
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

resource "aws_ecs_task_definition" "beat" {
  family                   = "${local.name}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = local.foundation.task_execution_role_arn
  task_role_arn            = local.foundation.task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "beat"
      image       = local.image
      essential   = true
      command     = ["celery", "-A", "app.worker.celery_app", "beat", "--loglevel=info"]
      environment = local.container_environment
      secrets     = local.container_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "beat"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "beat" {
  name            = "beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.beat.arn
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
