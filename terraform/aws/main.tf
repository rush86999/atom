# Fetch available AZs in the current region
data "aws_availability_zones" "available" {
  state = "available"
}

# Ensure we don't try to use more AZs than available or requested
locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.num_availability_zones)
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.stack_name_prefix}-vpc"
    Environment = "dev" # Example tag
  }
}

# --- Application Secrets ---

# Hasura Admin Secret (auto-generated)
resource "random_password" "hasura_admin_password" {
  length  = 32
  special = false # Typically admin secrets don't need special chars for URLs etc.
}
resource "aws_secretsmanager_secret" "hasura_admin_secret" {
  name        = "${var.stack_name_prefix}-hasura-admin-secret"
  description = "Admin secret for Hasura GraphQL engine."
}
resource "aws_secretsmanager_secret_version" "hasura_admin_secret_version" {
  secret_id     = aws_secretsmanager_secret.hasura_admin_secret.id
  secret_string = random_password.hasura_admin_password.result
}

# API Token Secret (auto-generated)
resource "random_password" "api_token" {
  length           = 40 # Longer for API tokens
  special          = true
  override_special = "_-" # Common for tokens
}
resource "aws_secretsmanager_secret" "api_token_secret" {
  name        = "${var.stack_name_prefix}-api-token-secret"
  description = "Generic API Token for internal services."
}
resource "aws_secretsmanager_secret_version" "api_token_secret_version" {
  secret_id     = aws_secretsmanager_secret.api_token_secret.id
  secret_string = random_password.api_token.result
}

# OpenAI API Key Secret (Placeholder)
resource "aws_secretsmanager_secret" "openai_api_key_secret" {
  name        = "${var.stack_name_prefix}-openai-api-key"
  description = "Placeholder for OpenAI API Key - MUST BE MANUALLY UPDATED in AWS console."
}
resource "aws_secretsmanager_secret_version" "openai_api_key_secret_version" {
  secret_id     = aws_secretsmanager_secret.openai_api_key_secret.id
  secret_string = "ENTER_OPENAI_API_KEY_HERE"
}

# SuperTokens DB Connection String (Placeholder)
resource "aws_secretsmanager_secret" "supertokens_db_conn_string_secret" {
  name        = "${var.stack_name_prefix}-supertokens-db-conn-string"
  description = "Placeholder for SuperTokens DB Connection String - Manually populate: postgresql://USER:PASS@HOST:PORT/DBNAME"
}
resource "aws_secretsmanager_secret_version" "supertokens_db_conn_string_secret_version" {
  secret_id     = aws_secretsmanager_secret.supertokens_db_conn_string_secret.id
  secret_string = "postgresql://DB_USER:DB_PASS@DB_HOST:DB_PORT/atomicdb" # Example placeholder
}

# Hasura DB Connection String (Placeholder)
resource "aws_secretsmanager_secret" "hasura_db_conn_string_secret" {
  name        = "${var.stack_name_prefix}-hasura-db-conn-string"
  description = "Placeholder for Hasura DB Connection String - Manually populate: postgres://USER:PASS@HOST:PORT/DBNAME"
}
resource "aws_secretsmanager_secret_version" "hasura_db_conn_string_secret_version" {
  secret_id     = aws_secretsmanager_secret.hasura_db_conn_string_secret.id
  secret_string = "postgres://DB_USER:DB_PASS@DB_HOST:DB_PORT/atomicdb" # Example placeholder
}

# Optaplanner DB Connection String (Placeholder)
resource "aws_secretsmanager_secret" "optaplanner_db_conn_string_secret" {
  name        = "${var.stack_name_prefix}-optaplanner-db-conn-string"
  description = "Placeholder for Optaplanner DB Connection String - Manually populate: jdbc:postgresql://HOST:PORT/DBNAME"
}
resource "aws_secretsmanager_secret_version" "optaplanner_db_conn_string_secret_version" {
  secret_id     = aws_secretsmanager_secret.optaplanner_db_conn_string_secret.id
  secret_string = "jdbc:postgresql://DB_HOST:DB_PORT/atomicdb?user=DB_USER&password=DB_PASSWORD" # Example placeholder
}

# Hasura JWT Secret (Placeholder)
resource "aws_secretsmanager_secret" "hasura_jwt_secret" {
  name        = "${var.stack_name_prefix}-hasura-jwt-secret"
  description = "Placeholder for Hasura JWT Secret JSON - Manually update with a strong key. Structure: {'type':'HS256','key':'YOUR_KEY','issuer':'supertokens'}"
}
resource "aws_secretsmanager_secret_version" "hasura_jwt_secret_version" {
  secret_id = aws_secretsmanager_secret.hasura_jwt_secret.id
  secret_string = jsonencode({
    type   = "HS256",
    key    = "REPLACE_WITH_A_STRONG_64_CHAR_HEX_SECRET_OR_MIN_32_CHAR_ASCII_WHEN_UPDATING_MANUALLY",
    issuer = "supertokens"
  })
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.stack_name_prefix}-ecs-task-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.stack_name_prefix}-ecs-task-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Application Tasks
resource "aws_iam_role" "ecs_application_task_role" {
  name = "${var.stack_name_prefix}-ecs-application-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.stack_name_prefix}-ecs-application-task-role"
  }
}

# Custom IAM Policy for ECS Application Tasks
resource "aws_iam_policy" "ecs_application_task_policy" {
  name        = "${var.stack_name_prefix}-ecs-application-task-policy"
  description = "Policy for ECS application tasks to access AWS resources"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        Effect = "Allow",
        Resource = [
          aws_s3_bucket.data_bucket.arn,
          "${aws_s3_bucket.data_bucket.arn}/*"
        ]
      },
      {
        Action = ["secretsmanager:GetSecretValue"],
        Effect = "Allow",
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.stack_name_prefix}-*",
          aws_secretsmanager_secret.db_credentials.arn
        ]
      },
      {
        Sid    = "OpenSearchAccess",
        Action = ["es:ESHttp*"],
        Effect = "Allow",
        Resource = [
          "arn:aws:es:${var.aws_region}:${data.aws_caller_identity.current.account_id}:domain/${var.stack_name_prefix}-*/*"
        ]
      },
      {
        Sid = "MSKAccess",
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:AlterClusterPolicy",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData",
          "kafka-cluster:CreateTopic",
          "kafka-cluster:DeleteTopic",
          "kafka:GetBootstrapBrokers"
        ],
        Effect = "Allow",
        Resource = [
          "arn:aws:kafka:${var.aws_region}:${data.aws_caller_identity.current.account_id}:cluster/${var.stack_name_prefix}-*/*",
          "arn:aws:kafka:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/${var.stack_name_prefix}-*/*"
        ]
      },
      {
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ],
        Effect   = "Allow",
        Resource = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/${var.stack_name_prefix}-*:*"]
      }
    ]
  })
  tags = {
    Name = "${var.stack_name_prefix}-ecs-application-task-policy"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_application_task_role_custom_policy" {
  role       = aws_iam_role.ecs_application_task_role.name
  policy_arn = aws_iam_policy.ecs_application_task_policy.arn
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.stack_name_prefix}-ecs-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled" # Can be "enabled" or "disabled". Disabled for now to keep it simple.
  }

  tags = {
    Name        = "${var.stack_name_prefix}-ecs-cluster"
    Environment = "dev"
  }
}

# RDS PostgreSQL Instance

# Generate a random password for the DB master user
resource "random_password" "db_master_password" {
  length           = 16
  special          = true
  override_special = "_%@" # Specify allowed special characters
}

# Store the master password in AWS Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.stack_name_prefix}-rds-master-credentials"
  description = "Master credentials for RDS instance, managed by Terraform."
  #recovery_window_in_days = 0 # Set to 0 for immediate deletion without recovery (for dev only)
  # Default is 30 days.
}

resource "aws_secretsmanager_secret_version" "db_credentials_version" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_master_username,
    password = random_password.db_master_password.result
  })
}

# DB Subnet Group
resource "aws_db_subnet_group" "default" {
  name       = "${var.stack_name_prefix}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id # Use private subnets

  tags = {
    Name = "${var.stack_name_prefix}-db-subnet-group"
  }
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier        = "${var.stack_name_prefix}-rds-postgres"
  allocated_storage = var.db_allocated_storage
  instance_class    = var.db_instance_class
  engine            = var.db_engine
  engine_version    = var.db_engine_version_postgres
  db_name           = var.db_name
  username          = var.db_master_username
  password          = random_password.db_master_password.result # Reference the random password

  db_subnet_group_name   = aws_db_subnet_group.default.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible     = false
  skip_final_snapshot     = true # For dev only
  backup_retention_period = var.db_backup_retention_period
  multi_az                = var.db_multi_az

  # Apply changes immediately (for dev, can cause downtime)
  # apply_immediately = true

  tags = {
    Name        = "${var.stack_name_prefix}-rds-instance"
    Environment = "dev"
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index) # Example: /24 subnets if VPC is /16
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "${var.stack_name_prefix}-public-subnet-${local.azs[count.index]}"
    Tier        = "Public"
    Environment = "dev"
  }
}

# Private Subnets
resource "aws_subnet" "private" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + length(local.azs)) # Offset CIDR from public
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name        = "${var.stack_name_prefix}-private-subnet-${local.azs[count.index]}"
    Tier        = "Private"
    Environment = "dev"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "${var.stack_name_prefix}-igw"
    Environment = "dev"
  }
}

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }

  tags = {
    Name        = "${var.stack_name_prefix}-public-rt"
    Environment = "dev"
  }
}

# Associate Public Subnets with Public Route Table
resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# NAT Gateway(s) and Private Routing (if enabled)
resource "aws_eip" "nat" {
  count  = var.enable_nat_gateway ? length(local.azs) : 0
  domain = "vpc" # Ensures EIP is VPC-scoped (formerly 'vpc = true')
  tags = {
    Name = "${var.stack_name_prefix}-nat-eip-${local.azs[count.index]}"
  }
}

resource "aws_nat_gateway" "nat" {
  count         = var.enable_nat_gateway ? length(local.azs) : 0
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id # Place NAT in public subnet

  tags = {
    Name        = "${var.stack_name_prefix}-nat-gw-${local.azs[count.index]}"
    Environment = "dev"
  }

  depends_on = [aws_internet_gateway.gw]
}

resource "aws_route_table" "private" {
  count  = var.enable_nat_gateway ? length(local.azs) : 0
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat[count.index].id
  }

  tags = {
    Name        = "${var.stack_name_prefix}-private-rt-${local.azs[count.index]}"
    Environment = "dev"
  }
}

resource "aws_route_table_association" "private" {
  count = var.enable_nat_gateway ? length(aws_subnet.private) : 0
  # Ensure we associate the correct private subnet with its corresponding AZ's route table
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# Security Group for Application Load Balancer
resource "aws_security_group" "alb" {
  name        = "${var.stack_name_prefix}-alb-sg"
  description = "Security group for the Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    protocol    = "tcp"
    from_port   = 80
    to_port     = 80
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTP inbound"
  }
  ingress {
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTPS inbound"
  }

  egress {
    protocol    = "-1" # All protocols
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name = "${var.stack_name_prefix}-alb-sg"
  }
}

# Security Group for ECS Tasks/Services
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.stack_name_prefix}-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = aws_vpc.main.id

  # Ingress rules will be added later by services or ALB connections
  # For now, allow all outbound for services to reach internet via NAT or other AWS services
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name = "${var.stack_name_prefix}-ecs-tasks-sg"
  }
}

# Security Group for RDS Database Instance
resource "aws_security_group" "rds" {
  name        = "${var.stack_name_prefix}-rds-sg"
  description = "Security group for RDS PostgreSQL instance"
  vpc_id      = aws_vpc.main.id

  ingress {
    protocol        = "tcp"
    from_port       = 5432
    to_port         = 5432
    security_groups = [aws_security_group.ecs_tasks.id] # Allow from ECS tasks SG
    description     = "Allow PostgreSQL from ECS tasks"
  }
  # Ingress rules will be added later to allow from ecs_tasks_sg on port 5432
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name = "${var.stack_name_prefix}-rds-sg"
  }
}

# Security Group for MSK Cluster Clients (to be associated with MSK's VPC interface)
resource "aws_security_group" "msk_client" {
  name        = "${var.stack_name_prefix}-msk-client-sg"
  description = "Security group for MSK cluster client connectivity"
  vpc_id      = aws_vpc.main.id

  # Ingress rules will be added later to allow from ecs_tasks_sg on port 9098 (IAM)
  # Egress rule to allow MSK to respond (though MSK itself manages its outbound)
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  tags = {
    Name = "${var.stack_name_prefix}-msk-client-sg"
  }
}

# ECR Repositories
resource "aws_ecr_repository" "app" {
  name                 = "atomic-app" # Consistent with CDK and build scripts
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.stack_name_prefix}-ecr-app"
  }
}

resource "aws_ecr_repository" "functions" {
  name                 = "atomic-functions"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.stack_name_prefix}-ecr-functions"
  }
}

resource "aws_ecr_repository" "handshake" {
  name                 = "atomic-handshake"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.stack_name_prefix}-ecr-handshake"
  }
}

resource "aws_ecr_repository" "oauth" {
  name                 = "atomic-oauth"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.stack_name_prefix}-ecr-oauth"
  }
}

resource "aws_ecr_repository" "optaplanner" {
  name                 = "atomic-optaplanner"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.stack_name_prefix}-ecr-optaplanner"
  }
}

# Data source to get current AWS Account ID for bucket naming (if constructing full name)
data "aws_caller_identity" "current" {}

# S3 Bucket for Application Data
resource "aws_s3_bucket" "data_bucket" {
  # Bucket names must be globally unique. Using a prefix and letting AWS generate a unique suffix
  # is often safer, e.g., bucket_prefix = "${var.stack_name_prefix}-data-"
  # However, to try and match the CDK naming convention for learning:
  bucket = "${var.stack_name_prefix}-data-bucket-${data.aws_caller_identity.current.account_id}-${var.aws_region}"

  tags = {
    Name        = "${var.stack_name_prefix}-data-bucket"
    Environment = "dev"
  }
}

# Enable versioning (optional, but good practice)
resource "aws_s3_bucket_versioning" "data_bucket_versioning" {
  bucket = aws_s3_bucket.data_bucket.id
  versioning_configuration {
    status = "Disabled" # Can be "Enabled" or "Suspended". Disabled for simplicity.
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "data_bucket_public_access_block" {
  bucket = aws_s3_bucket.data_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Server-side encryption (SSE-S3)
resource "aws_s3_bucket_server_side_encryption_configuration" "data_bucket_sse_config" {
  bucket = aws_s3_bucket.data_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
