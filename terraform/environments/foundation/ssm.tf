resource "aws_ssm_parameter" "database_url" {
  name  = "/${local.name}/database-url"
  type  = "SecureString"
  value = "postgresql+asyncpg://${var.db_username}:${random_password.db.result}@${aws_db_instance.main.address}:5432/${var.db_name}"
}

# The Django rewrite reads discrete POSTGRES_* vars rather than a single URL
# (it's not SQLAlchemy/asyncpg) and lives in its own database on the same RDS
# instance (var.db_name_django), so the FastAPI app's tables are untouched.
resource "aws_ssm_parameter" "db_password" {
  name  = "/${local.name}/db-password"
  type  = "SecureString"
  value = random_password.db.result
}

resource "aws_ssm_parameter" "secret_key" {
  name  = "/${local.name}/secret-key"
  type  = "SecureString"
  value = var.secret_key
}

resource "aws_ssm_parameter" "openai_api_key" {
  name  = "/${local.name}/openai-api-key"
  type  = "SecureString"
  value = var.openai_api_key
}

resource "aws_ssm_parameter" "resend_api_key" {
  name  = "/${local.name}/resend-api-key"
  type  = "SecureString"
  value = var.resend_api_key
}

resource "aws_ssm_parameter" "google_client_secret" {
  name  = "/${local.name}/google-client-secret"
  type  = "SecureString"
  value = var.google_client_secret
}

resource "aws_ssm_parameter" "zoom_client_secret" {
  name  = "/${local.name}/zoom-client-secret"
  type  = "SecureString"
  value = var.zoom_client_secret
}

# Only consumed by the cost-optimized environment's cloudflared sidecar.
# Kept here (not per-environment) so it survives a production -> cost-optimized
# cutover just like the other secrets.
resource "aws_ssm_parameter" "cloudflare_tunnel_token" {
  name  = "/${local.name}/cloudflare-tunnel-token"
  type  = "SecureString"
  value = var.cloudflare_tunnel_token != "" ? var.cloudflare_tunnel_token : "unset"
}
