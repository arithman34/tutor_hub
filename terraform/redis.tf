resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name}-redis"
  description          = "Celery broker/backend"

  engine               = "valkey"
  engine_version       = "8.0"
  node_type            = var.redis_node_type
  num_cache_clusters   = 1
  parameter_group_name = "default.valkey8"
  port                 = 6379

  automatic_failover_enabled = false
  transit_encryption_enabled = false

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]
}
