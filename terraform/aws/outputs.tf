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

output "alb_dns_name" {
  description = "The DNS name of the Application Load Balancer."
  value       = aws_lb.main.dns_name
}

output "alb_arn" {
  description = "The ARN of the Application Load Balancer."
  value       = aws_lb.main.arn
}

output "alb_zone_id" {
  description = "The Zone ID of the Application Load Balancer (for Route53 alias records)."
  value       = aws_lb.main.zone_id
}

output "alb_http_listener_arn" {
  description = "The ARN of the ALB HTTP Listener."
  value       = aws_lb_listener.http.arn
}

output "alb_default_target_group_arn" {
  description = "The ARN of the ALB Default Target Group."
  value       = aws_lb_target_group.default.arn
}

output "supertokens_ecs_service_name" {
  description = "Name of the SuperTokens ECS service."
  value       = aws_ecs_service.supertokens.name
}

output "supertokens_task_definition_arn" {
  description = "ARN of the SuperTokens ECS task definition."
  value       = aws_ecs_task_definition.supertokens.arn
}

output "supertokens_target_group_arn" {
  description = "ARN of the SuperTokens ALB target group."
  value       = aws_lb_target_group.supertokens.arn
}

output "hasura_ecs_service_name" {
  description = "Name of the Hasura ECS service."
  value       = aws_ecs_service.hasura.name
}

output "hasura_task_definition_arn" {
  description = "ARN of the Hasura ECS task definition."
  value       = aws_ecs_task_definition.hasura.arn
}

output "hasura_target_group_arn" {
  description = "ARN of the Hasura ALB target group."
  value       = aws_lb_target_group.hasura.arn
}

output "functions_ecs_service_name" {
  description = "Name of the Functions ECS service."
  value       = aws_ecs_service.functions.name
}

output "functions_task_definition_arn" {
  description = "ARN of the Functions ECS task definition."
  value       = aws_ecs_task_definition.functions.arn
}

output "functions_target_group_arn" {
  description = "ARN of the Functions ALB target group."
  value       = aws_lb_target_group.functions.arn
}

output "app_ecs_service_name" {
  description = "Name of the App (frontend) ECS service."
  value       = aws_ecs_service.app.name
}

output "app_task_definition_arn" {
  description = "ARN of the App (frontend) ECS task definition."
  value       = aws_ecs_task_definition.app.arn
}

output "app_target_group_arn" {
  description = "ARN of the App (frontend) ALB target group."
  value       = aws_lb_target_group.app.arn
}

output "handshake_ecs_service_name" {
  description = "Name of the Handshake ECS service."
  value       = aws_ecs_service.handshake.name
}

output "handshake_task_definition_arn" {
  description = "ARN of the Handshake ECS task definition."
  value       = aws_ecs_task_definition.handshake.arn
}

output "handshake_target_group_arn" {
  description = "ARN of the Handshake ALB target group."
  value       = aws_lb_target_group.handshake.arn
}

output "oauth_ecs_service_name" {
  description = "Name of the OAuth ECS service."
  value       = aws_ecs_service.oauth.name
}

output "oauth_task_definition_arn" {
  description = "ARN of the OAuth ECS task definition."
  value       = aws_ecs_task_definition.oauth.arn
}

output "oauth_target_group_arn" {
  description = "ARN of the OAuth ALB target group."
  value       = aws_lb_target_group.oauth.arn
}

output "optaplanner_ecs_service_name" {
  description = "Name of the Optaplanner ECS service."
  value       = aws_ecs_service.optaplanner.name
}

output "optaplanner_task_definition_arn" {
  description = "ARN of the Optaplanner ECS task definition."
  value       = aws_ecs_task_definition.optaplanner.arn
}

output "optaplanner_target_group_arn" {
  description = "ARN of the Optaplanner ALB target group."
  value       = aws_lb_target_group.optaplanner.arn
}

output "opensearch_domain_arn" {
  description = "The ARN of the Amazon OpenSearch Service domain."
  value       = aws_opensearch_domain.main.arn
}

output "opensearch_domain_endpoint" {
  description = "The endpoint for the Amazon OpenSearch Service domain."
  value       = "https://${aws_opensearch_domain.main.endpoint}"
}

output "opensearch_domain_id" {
  description = "The ID of the Amazon OpenSearch Service domain."
  value       = aws_opensearch_domain.main.id
}

output "msk_serverless_cluster_arn" {
  description = "The ARN of the Amazon MSK Serverless cluster."
  value       = aws_msk_serverless_cluster.main.arn
}

output "msk_serverless_cluster_bootstrap_brokers_instruction" {
  description = "Command to fetch MSK Serverless bootstrap brokers using AWS CLI."
  value       = "aws kafka get-bootstrap-brokers --cluster-arn ${aws_msk_serverless_cluster.main.arn}"
}
