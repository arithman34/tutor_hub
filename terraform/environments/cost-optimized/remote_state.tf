data "terraform_remote_state" "foundation" {
  backend = "local"

  config = {
    path = "${path.module}/../foundation/terraform.tfstate"
  }
}

locals {
  # Deliberately distinct from foundation/production's "tutorhub" — this
  # environment's ECS cluster, log group, and security group need to coexist
  # with production's during the overlap window (apply this, verify it works,
  # then destroy production), so they can't share those names.
  name       = "tutorhub-lean"
  foundation = data.terraform_remote_state.foundation.outputs
}
