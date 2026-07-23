resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.public[*].id
}

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "PostgreSQL"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name}-rds"
  }
}

# Ingress from whichever compute environment is live is added by that
# environment (aws_vpc_security_group_ingress_rule referencing this SG's id),
# not here — the app security group doesn't exist at this layer.
resource "aws_vpc_security_group_ingress_rule" "rds_from_admin" {
  for_each = toset(var.admin_cidrs)

  security_group_id = aws_security_group.rds.id
  description       = "Postgres admin access"
  cidr_ipv4         = each.value
  from_port         = 5432
  to_port           = 5432
  ip_protocol       = "tcp"
}

resource "aws_db_instance" "main" {
  identifier     = "${local.name}-db"
  engine         = "postgres"
  engine_version = "17"
  instance_class = var.db_instance_class

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = var.db_publicly_accessible
  multi_az               = false

  backup_retention_period   = 1
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name}-db-final"

  auto_minor_version_upgrade = true
  apply_immediately          = true
}
