variable "project_id" { type=string }
variable "region" { type=string default="asia-south1" }
variable "environment" { type=string validation { condition=contains(["dev","staging","prod"],var.environment) error_message="environment must be dev, staging, or prod" } }
variable "apply_production" { type=bool default=false validation { condition=var.environment!="prod" || var.apply_production error_message="Production requires explicit apply_production=true acknowledgement" } }
variable "document_agent_image" { type=string description="Immutable Artifact Registry image for taxright-document-agent" }
variable "web_origins" { type=list(string) description="Exact browser origins allowed to upload to quarantine" }
