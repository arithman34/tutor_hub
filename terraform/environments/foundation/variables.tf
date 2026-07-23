variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-west-2"
}

variable "github_repository" {
  description = "GitHub repo (owner/name) allowed to assume the deploy role via OIDC."
  type        = string
  default     = "arithman34/tutor_hub"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "Application database name."
  type        = string
  default     = "tutor_hub"
}

variable "db_username" {
  description = "RDS master username (the app connects as this user)."
  type        = string
  default     = "tutorhub"
}

variable "db_publicly_accessible" {
  description = "Temporarily give RDS a public IP for admin access / data migration. Pair with admin_cidrs. Turn back off afterwards."
  type        = bool
  default     = false
}

variable "admin_cidrs" {
  description = "CIDRs allowed to reach Postgres directly (e.g. your home IP /32). Empty list = no direct access."
  type        = list(string)
  default     = []
}

variable "secret_key" {
  description = "JWT signing key for the app."
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key for embeddings + chat."
  type        = string
  sensitive   = true
}

variable "resend_api_key" {
  description = "Resend API key for outbound email."
  type        = string
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth client secret (Calendar integration)."
  type        = string
  sensitive   = true
}

variable "cloudflare_tunnel_token" {
  description = "Token for the Cloudflare Tunnel used by the cost-optimized environment's cloudflared sidecar. Not used by production. Create the tunnel in the Cloudflare Zero Trust dashboard (Networks > Tunnels) and paste its token here."
  type        = string
  sensitive   = true
  default     = ""
}
