variable "aws_region" {
  description = "AWS region to deploy into. Must match the foundation environment's region."
  type        = string
  default     = "eu-west-2"
}

variable "domain_name" {
  description = "Public domain the app is served on. Used only for the Google OAuth redirect URI — ingress itself comes from the Cloudflare Tunnel's public hostname, configured in the Cloudflare Zero Trust dashboard, not here."
  type        = string
  default     = "tutorhub.arithman.dev"
}

variable "google_client_id" {
  description = "Google OAuth client ID."
  type        = string
}

variable "from_email" {
  description = "From address for outbound email."
  type        = string
}
