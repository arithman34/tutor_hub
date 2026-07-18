resource "aws_ssm_parameter" "database_url" {
  name  = "/${local.name}/database-url"
  type  = "SecureString"
  value = "postgresql+asyncpg://${var.db_username}:${random_password.db.result}@${aws_db_instance.main.address}:5432/${var.db_name}"
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
