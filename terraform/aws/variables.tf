variable "aws_region" {
  description = "The AWS region to deploy resources in."
  type        = string
  default     = "us-east-1"
}

variable "stack_name_prefix" {
  description = "A prefix for naming resources to ensure uniqueness and grouping."
  type        = string
  default     = "atomic"
}

variable "vpc_cidr_block" {
  description = "The CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "num_availability_zones" {
  description = "Number of Availability Zones to use for subnets."
  type        = number
  default     = 2
  validation {
    condition     = var.num_availability_zones >= 1 && var.num_availability_zones <= 3 # Max 3 for simplicity here
    error_message = "Number of AZs must be between 1 and 3."
  }
}

variable "enable_nat_gateway" {
  description = "Enable NAT gateway for outbound internet access from private subnets."
  type        = bool
  default     = true
}

variable "db_instance_class" {
  description = "The instance class for the RDS instance."
  type        = string
  default     = "db.t3.micro" # Or db.t4g.micro for Graviton
}

variable "db_allocated_storage" {
  description = "The allocated storage for the RDS instance (in GB)."
  type        = number
  default     = 20
}

variable "db_engine" {
  description = "The database engine for the RDS instance."
  type        = string
  default     = "postgres"
}

variable "db_engine_version_postgres" {
  description = "The PostgreSQL engine version."
  type        = string
  default     = "15.6" # Specify a recent minor version
}

variable "db_name" {
  description = "The name of the initial database to create."
  type        = string
  default     = "atomicdb"
}

variable "db_master_username" {
  description = "The master username for the RDS instance."
  type        = string
  default     = "postgresadmin"
  # Add validation for username if needed (e.g. length, allowed characters)
}

variable "db_backup_retention_period" {
  description = "The backup retention period for the RDS instance (in days). 0 to disable automated backups."
  type        = number
  default     = 0 # Disabled for dev/cost savings
}

variable "db_multi_az" {
  description = "Specifies if the RDS instance is multi-AZ."
  type        = bool
  default     = false # For dev/cost savings
}

variable "aws_account_id" {
  description = "The AWS Account ID to deploy resources in. For resource naming and ARNs."
  type        = string
  # No default, should be passed in or determined by data source if needed by TF config itself
  # For now, primarily for script use.
}
