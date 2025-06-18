output "vpc_id" {
  description = "The ID of the VPC."
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "The CIDR block of the VPC."
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "List of IDs of public subnets."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "List of IDs of private subnets."
  value       = aws_subnet.private[*].id
}

output "availability_zones_used" {
  description = "List of Availability Zones used for the subnets."
  value       = local.azs
}

output "alb_security_group_id" {
  description = "The ID of the ALB Security Group."
  value       = aws_security_group.alb.id
}

output "ecs_tasks_security_group_id" {
  description = "The ID of the ECS Tasks Security Group."
  value       = aws_security_group.ecs_tasks.id
}

output "rds_security_group_id" {
  description = "The ID of the RDS Security Group."
  value       = aws_security_group.rds.id
}

output "msk_client_security_group_id" {
  description = "The ID of the MSK Client Security Group."
  value       = aws_security_group.msk_client.id
}

output "ecr_app_repository_url" {
  description = "The URL of the ECR repository for the 'app' service."
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_functions_repository_url" {
  description = "The URL of the ECR repository for the 'functions' service."
  value       = aws_ecr_repository.functions.repository_url
}

output "ecr_handshake_repository_url" {
  description = "The URL of the ECR repository for the 'handshake' service."
  value       = aws_ecr_repository.handshake.repository_url
}

output "ecr_oauth_repository_url" {
  description = "The URL of the ECR repository for the 'oauth' service."
  value       = aws_ecr_repository.oauth.repository_url
}

output "ecr_optaplanner_repository_url" {
  description = "The URL of the ECR repository for the 'optaplanner' service."
  value       = aws_ecr_repository.optaplanner.repository_url
}

output "s3_data_bucket_id" {
  description = "The ID (name) of the S3 data bucket."
  value       = aws_s3_bucket.data_bucket.id
}

output "s3_data_bucket_arn" {
  description = "The ARN of the S3 data bucket."
  value       = aws_s3_bucket.data_bucket.arn
}

output "s3_data_bucket_domain_name" {
  description = "The domain name of the S3 data bucket."
  value       = aws_s3_bucket.data_bucket.bucket_domain_name
}

output "db_instance_address" {
  description = "The connection endpoint for the RDS instance."
  value       = aws_db_instance.main.address
}

output "db_instance_port" {
  description = "The connection port for the RDS instance."
  value       = aws_db_instance.main.port
}

output "db_instance_name" {
  description = "The database name."
  value       = aws_db_instance.main.db_name
}

output "db_master_username" {
  description = "The master username for the RDS instance."
  value       = aws_db_instance.main.username # Or var.db_master_username
}

output "db_credentials_secret_arn" {
  description = "The ARN of the AWS Secrets Manager secret holding DB master credentials."
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "ecs_cluster_name" {
  description = "The name of the ECS cluster."
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "The ARN of the ECS cluster."
  value       = aws_ecs_cluster.main.arn
}

output "ecs_task_execution_role_arn" {
  description = "The ARN of the ECS Task Execution Role."
  value       = aws_iam_role.ecs_task_execution_role.arn
}

output "ecs_application_task_role_arn" {
  description = "The ARN of the ECS Application Task Role."
  value       = aws_iam_role.ecs_application_task_role.arn
}

output "hasura_admin_secret_arn" {
  description = "ARN of the Hasura Admin Secret."
  value       = aws_secretsmanager_secret.hasura_admin_secret.arn
}
output "api_token_secret_arn" {
  description = "ARN of the API Token Secret."
  value       = aws_secretsmanager_secret.api_token_secret.arn
}
output "openai_api_key_secret_arn" {
  description = "ARN of the OpenAI API Key Secret (Placeholder)."
  value       = aws_secretsmanager_secret.openai_api_key_secret.arn
}
output "supertokens_db_conn_string_secret_arn" {
  description = "ARN of the SuperTokens DB Connection String Secret (Placeholder)."
  value       = aws_secretsmanager_secret.supertokens_db_conn_string_secret.arn
}
output "hasura_db_conn_string_secret_arn" {
  description = "ARN of the Hasura DB Connection String Secret (Placeholder)."
  value       = aws_secretsmanager_secret.hasura_db_conn_string_secret.arn
}
output "optaplanner_db_conn_string_secret_arn" {
  description = "ARN of the Optaplanner DB Connection String Secret (Placeholder)."
  value       = aws_secretsmanager_secret.optaplanner_db_conn_string_secret.arn
}
output "hasura_jwt_secret_arn" {
  description = "ARN of the Hasura JWT Secret (Placeholder)."
  value       = aws_secretsmanager_secret.hasura_jwt_secret.arn
}
