data "terraform_remote_state" "foundation" {
  backend = "local"

  config = {
    path = "${path.module}/../foundation/terraform.tfstate"
  }
}

locals {
  name       = "tutorhub"
  foundation = data.terraform_remote_state.foundation.outputs
}
