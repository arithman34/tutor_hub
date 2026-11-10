# A separate task definition (not a service) for the weekly data export —
# same image, same env/secrets as the "api" container, but running
# `manage.py export_to_s3` once and exiting instead of serving traffic.
# Replaces the old FastAPI app's Celery-beat-scheduled export.
resource "aws_ecs_task_definition" "export" {
  family                   = "${local.name}-export"
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
      name        = "export"
      image       = local.image
      essential   = true
      command     = ["python", "manage.py", "export_to_s3"]
      environment = local.container_environment
      secrets     = local.container_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options   = merge(local.log_options, { awslogs-stream-prefix = "export" })
      }
    }
  ])
}

data "aws_iam_policy_document" "events_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduled_export" {
  name               = "${local.name}-scheduled-export"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json
}

data "aws_iam_policy_document" "scheduled_export" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = [replace(aws_ecs_task_definition.export.arn, "/:\\d+$/", ":*")]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.main.arn]
    }
  }

  statement {
    actions = ["iam:PassRole"]
    resources = [
      local.foundation.task_execution_role_arn,
      local.foundation.task_role_arn,
    ]
  }
}

resource "aws_iam_role_policy" "scheduled_export" {
  name   = "run-export-task"
  role   = aws_iam_role.scheduled_export.id
  policy = data.aws_iam_policy_document.scheduled_export.json
}

resource "aws_cloudwatch_event_rule" "weekly_export" {
  name                = "${local.name}-weekly-export"
  description         = "Runs the data export task once a week"
  schedule_expression = "cron(0 3 ? * MON *)"
}

resource "aws_cloudwatch_event_target" "weekly_export" {
  rule     = aws_cloudwatch_event_rule.weekly_export.name
  arn      = aws_ecs_cluster.main.arn
  role_arn = aws_iam_role.scheduled_export.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.export.arn
    task_count          = 1
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = local.foundation.public_subnet_ids
      security_groups  = [aws_security_group.app.id]
      assign_public_ip = true
    }
  }
}
