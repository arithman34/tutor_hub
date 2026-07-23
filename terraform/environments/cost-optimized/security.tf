resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "ECS task (api + worker + beat + valkey + cloudflared, all one task)"
  vpc_id      = local.foundation.vpc_id

  tags = {
    Name = "${local.name}-app"
  }
}

# No ingress rules at all: cloudflared makes an outbound-only connection to
# Cloudflare's edge, so nothing needs to accept inbound traffic from the
# internet. This is a smaller attack surface than the ALB path.
resource "aws_vpc_security_group_egress_rule" "app_all" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_app" {
  security_group_id            = local.foundation.rds_security_group_id
  description                  = "Postgres from ECS task (cost-optimized)"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}
