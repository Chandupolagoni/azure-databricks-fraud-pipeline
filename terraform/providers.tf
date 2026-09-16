terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "azurerm" {
    # Configure via `terraform init -backend-config=environments/<env>.backend.hcl`
    # resource_group_name  = "rg-tfstate"
    # storage_account_name = "sttfstatefraudplatform"
    # container_name       = "tfstate"
    # key                  = "fraud-platform.tfstate"
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}

# Configured after the Databricks workspace is created (see modules/databricks).
provider "databricks" {
  host = module.databricks.workspace_url
}
