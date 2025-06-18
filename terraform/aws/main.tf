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
    Environment = "dev"
  }
}

# Data source to get current AWS Account ID for bucket naming & policies
data "aws_caller_identity" "current" {}

# --- Application Secrets ---
resource "random_password" "hasura_admin_password" {
  length  = 32
  special = false
}
resource "aws_secretsmanager_secret" "hasura_admin_secret" {
  name        = "${var.stack_name_prefix}-hasura-admin-secret"
  description = "Admin secret for Hasura GraphQL engine."
}
resource "aws_secretsmanager_secret_version" "hasura_admin_secret_version" {
  secret_id     = aws_secretsmanager_secret.hasura_admin_secret.id
  secret_string = random_password.hasura_admin_password.result
}
resource "random_password" "api_token" {
  length           = 40
  special          = true
  override_special = "_-"
}
resource "aws_secretsmanager_secret" "api_token_secret" {
  name        = "${var.stack_name_prefix}-api-token-secret"
  description = "Generic API Token for internal services."
}
resource "aws_secretsmanager_secret_version" "api_token_secret_version" {
  secret_id     = aws_secretsmanager_secret.api_token_secret.id
  secret_string = random_password.api_token.result
}
resource "aws_secretsmanager_secret" "openai_api_key_secret" {
  name        = "${var.stack_name_prefix}-openai-api-key"
  description = "Placeholder for OpenAI API Key - MUST BE MANUALLY UPDATED in AWS console."
}
resource "aws_secretsmanager_secret_version" "openai_api_key_secret_version" {
  secret_id     = aws_secretsmanager_secret.openai_api_key_secret.id
  secret_string = "ENTER_OPENAI_API_KEY_HERE"
}
resource "aws_secretsmanager_secret" "supertokens_db_conn_string_secret" {
  name        = "${var.stack_name_prefix}-supertokens-db-conn-string"
  description = "Placeholder for SuperTokens DB Connection String - Manually populate: postgresql://USER:PASS@HOST:PORT/DBNAME"
}
resource "aws_secretsmanager_secret_version" "supertokens_db_conn_string_secret_version" {
  secret_id     = aws_secretsmanager_secret.supertokens_db_conn_string_secret.id
  secret_string = "postgresql://DB_USER:DB_PASS@DB_HOST:DB_PORT/atomicdb" # Example placeholder
}
resource "aws_secretsmanager_secret" "hasura_db_conn_string_secret" {
  name        = "${var.stack_name_prefix}-hasura-db-conn-string"
  description = "Placeholder for Hasura DB Connection String - Manually populate: postgres://USER:PASS@HOST:PORT/DBNAME"
}
resource "aws_secretsmanager_secret_version" "hasura_db_conn_string_secret_version" {
  secret_id     = aws_secretsmanager_secret.hasura_db_conn_string_secret.id
  secret_string = "postgres://DB_USER:DB_PASS@DB_HOST:DB_PORT/atomicdb" # Example placeholder
}
resource "aws_secretsmanager_secret" "optaplanner_db_conn_string_secret" {
  name        = "${var.stack_name_prefix}-optaplanner-db-conn-string"
  description = "Placeholder for Optaplanner DB Connection String - Manually populate: jdbc:postgresql://HOST:PORT/DBNAME"
}
resource "aws_secretsmanager_secret_version" "optaplanner_db_conn_string_secret_version" {
  secret_id     = aws_secretsmanager_secret.optaplanner_db_conn_string_secret.id
  secret_string = "jdbc:postgresql://DB_HOST:DB_PORT/atomicdb?user=DB_USER&password=DB_PASSWORD" # Example placeholder
}
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

# IAM Roles and Policies
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.stack_name_prefix}-ecs-task-execution-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  tags = { Name = "${var.stack_name_prefix}-ecs-task-execution-role" }
}
resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role" "ecs_application_task_role" {
  name = "${var.stack_name_prefix}-ecs-application-task-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  tags = { Name = "${var.stack_name_prefix}-ecs-application-task-role" }
}
resource "aws_iam_policy" "ecs_application_task_policy" {
  name        = "${var.stack_name_prefix}-ecs-application-task-policy"
  description = "Policy for ECS application tasks to access AWS resources"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      { Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"], Effect = "Allow", Resource = [aws_s3_bucket.data_bucket.arn, "${aws_s3_bucket.data_bucket.arn}/*"] },
      { Action = ["secretsmanager:GetSecretValue"], Effect = "Allow", Resource = [
        "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.stack_name_prefix}-*",
        aws_secretsmanager_secret.db_credentials.arn
      ] },
      {
        Sid    = "OpenSearchAccess",
        Action = "es:ESHttp*",
        Effect = "Allow",
        Resource = [
          aws_opensearch_domain.main.arn,
          "${aws_opensearch_domain.main.arn}/*"
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
          aws_msk_serverless_cluster.main.arn,
          "arn:aws:kafka:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/${var.stack_name_prefix}-*/*"
        ]
      },
      { Action = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"], Effect = "Allow", Resource = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/${var.stack_name_prefix}-*:*"] }
    ]
  })
  tags = { Name = "${var.stack_name_prefix}-ecs-application-task-policy" }
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
    value = "disabled"
  }
  tags = { Name = "${var.stack_name_prefix}-ecs-cluster", Environment = "dev" }
}

# RDS Resources
resource "random_password" "db_master_password" {
  length           = 16
  special          = true
  override_special = "_%@"
}
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.stack_name_prefix}-rds-master-credentials"
  description = "Master credentials for RDS instance, managed by Terraform."
}
resource "aws_secretsmanager_secret_version" "db_credentials_version" {
  secret_id     = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({ username = var.db_master_username, password = random_password.db_master_password.result })
}
resource "aws_db_subnet_group" "default" {
  name       = "${var.stack_name_prefix}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${var.stack_name_prefix}-db-subnet-group" }
}
resource "aws_db_instance" "main" {
  identifier              = "${var.stack_name_prefix}-rds-postgres"
  allocated_storage       = var.db_allocated_storage
  instance_class          = var.db_instance_class
  engine                  = var.db_engine
  engine_version          = var.db_engine_version_postgres
  db_name                 = var.db_name
  username                = var.db_master_username
  password                = random_password.db_master_password.result
  db_subnet_group_name    = aws_db_subnet_group.default.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  publicly_accessible     = false
  skip_final_snapshot     = true
  backup_retention_period = var.db_backup_retention_period
  multi_az                = var.db_multi_az
  tags                    = { Name = "${var.stack_name_prefix}-rds-instance", Environment = "dev" }
}

# Networking
resource "aws_subnet" "public" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.stack_name_prefix}-public-subnet-${local.azs[count.index]}", Tier = "Public", Environment = "dev" }
}
resource "aws_subnet" "private" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + length(local.azs))
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.stack_name_prefix}-private-subnet-${local.azs[count.index]}", Tier = "Private", Environment = "dev" }
}
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.stack_name_prefix}-igw", Environment = "dev" }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
  tags = { Name = "${var.stack_name_prefix}-public-rt", Environment = "dev" }
}
resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_eip" "nat" {
  count  = var.enable_nat_gateway ? length(local.azs) : 0
  domain = "vpc"
  tags   = { Name = "${var.stack_name_prefix}-nat-eip-${local.azs[count.index]}" }
}
resource "aws_nat_gateway" "nat" {
  count         = var.enable_nat_gateway ? length(local.azs) : 0
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "${var.stack_name_prefix}-nat-gw-${local.azs[count.index]}", Environment = "dev" }
  depends_on    = [aws_internet_gateway.gw]
}
resource "aws_route_table" "private" {
  count  = var.enable_nat_gateway ? length(local.azs) : 0
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat[count.index].id
  }
  tags = { Name = "${var.stack_name_prefix}-private-rt-${local.azs[count.index]}", Environment = "dev" }
}
resource "aws_route_table_association" "private" {
  count          = var.enable_nat_gateway ? length(aws_subnet.private) : 0
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# Security Groups
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
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  tags = { Name = "${var.stack_name_prefix}-alb-sg" }
}
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.stack_name_prefix}-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = aws_vpc.main.id
  ingress {
    protocol        = "tcp"
    from_port       = 3567
    to_port         = 3567
    security_groups = [aws_security_group.alb.id]
    description     = "Allow SuperTokens traffic from ALB"
  }
  ingress {
    protocol        = "tcp"
    from_port       = 8080
    to_port         = 8080
    security_groups = [aws_security_group.alb.id]
    description     = "Allow Hasura traffic from ALB"
  }
  ingress {
    protocol        = "tcp"
    from_port       = 3000
    to_port         = 3000
    security_groups = [aws_security_group.alb.id]
    description     = "Allow Functions/App/Handshake/OAuth traffic from ALB on port 3000"
  }
  ingress {
    protocol        = "tcp"
    from_port       = 8081
    to_port         = 8081
    security_groups = [aws_security_group.alb.id]
    description     = "Allow Optaplanner traffic from ALB"
  }
  tags = { Name = "${var.stack_name_prefix}-ecs-tasks-sg" }
}

resource "aws_security_group_rule" "ecs_to_msk_egress" {
  type              = "egress"
  from_port         = 9098
  to_port           = 9098
  protocol          = "tcp"
  security_group_id = aws_security_group.ecs_tasks.id
  cidr_blocks       = aws_subnet.private[*].cidr_block # Changed to CIDR blocks of private subnets
  description       = "Allow outbound from ECS to MSK clients on TCP/9098"
}

resource "aws_security_group_rule" "ecs_all_outbound_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1" # All protocols
  security_group_id = aws_security_group.ecs_tasks.id
  cidr_blocks       = ["0.0.0.0/0"]
  description       = "Allow all outbound traffic from ECS tasks"
}

resource "aws_security_group" "rds" {
  name        = "${var.stack_name_prefix}-rds-sg"
  description = "Security group for RDS PostgreSQL instance"
  vpc_id      = aws_vpc.main.id
  ingress {
    protocol        = "tcp"
    from_port       = 5432
    to_port         = 5432
    security_groups = [aws_security_group.ecs_tasks.id]
    description     = "Allow PostgreSQL from ECS tasks"
  }
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  tags = { Name = "${var.stack_name_prefix}-rds-sg" }
}
resource "aws_security_group" "msk_client" {
  name        = "${var.stack_name_prefix}-msk-client-sg"
  description = "Security group for MSK cluster client connectivity"
  vpc_id      = aws_vpc.main.id
  ingress {
    protocol        = "tcp"
    from_port       = 9098
    to_port         = 9098
    security_groups = [aws_security_group.ecs_tasks.id]
    description     = "Allow inbound from ECS tasks to MSK"
  }
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  tags = { Name = "${var.stack_name_prefix}-msk-client-sg" }
}

# ECR Repositories
resource "aws_ecr_repository" "app" {
  name                 = "atomic-app"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = { Name = "${var.stack_name_prefix}-ecr-app" }
}
resource "aws_ecr_repository" "functions" {
  name                 = "atomic-functions"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = { Name = "${var.stack_name_prefix}-ecr-functions" }
}
resource "aws_ecr_repository" "handshake" {
  name                 = "atomic-handshake"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = { Name = "${var.stack_name_prefix}-ecr-handshake" }
}
resource "aws_ecr_repository" "oauth" {
  name                 = "atomic-oauth"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = { Name = "${var.stack_name_prefix}-ecr-oauth" }
}
resource "aws_ecr_repository" "optaplanner" {
  name                 = "atomic-optaplanner"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = { Name = "${var.stack_name_prefix}-ecr-optaplanner" }
}

# S3 Bucket
resource "aws_s3_bucket" "data_bucket" {
  bucket = "${var.stack_name_prefix}-data-bucket-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  tags   = { Name = "${var.stack_name_prefix}-data-bucket", Environment = "dev" }
}
resource "aws_s3_bucket_versioning" "data_bucket_versioning" {
  bucket = aws_s3_bucket.data_bucket.id
  versioning_configuration { status = "Disabled" }
}
resource "aws_s3_bucket_public_access_block" "data_bucket_public_access_block" {
  bucket                  = aws_s3_bucket.data_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "data_bucket_sse_config" {
  bucket = aws_s3_bucket.data_bucket.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# ALB, Listener, Default Target Group
resource "aws_lb" "main" {
  name                       = "${var.stack_name_prefix}-alb"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  enable_deletion_protection = false
  tags                       = { Name = "${var.stack_name_prefix}-alb", Environment = "dev" }
}
resource "aws_lb_target_group" "default" {
  name        = "${var.stack_name_prefix}-alb-default-tg"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    enabled             = true
    path                = "/"
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
  }
  tags = { Name = "${var.stack_name_prefix}-alb-default-tg" }
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.default.arn
  }
}

# --- SuperTokens Service ---
resource "aws_lb_target_group" "supertokens" {
  name        = "${var.stack_name_prefix}-supertokens-tg"
  port        = 3567
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    enabled             = true
    path                = "/hello"
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }
  tags = { Name = "${var.stack_name_prefix}-supertokens-tg" }
}
resource "aws_lb_listener_rule" "supertokens" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.supertokens.arn
  }
  condition {
    path_pattern {
      values = ["/v1/auth/*"]
    }
  }
}
resource "aws_cloudwatch_log_group" "supertokens_ecs_logs" {
  name              = "/ecs/${var.stack_name_prefix}-supertokens"
  retention_in_days = 30
  tags              = { Name = "${var.stack_name_prefix}-supertokens-ecs-logs" }
}
resource "aws_ecs_task_definition" "supertokens" {
  family                   = "${var.stack_name_prefix}-supertokens"
  cpu                      = "256"
  memory                   = "512"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_application_task_role.arn
  container_definitions = jsonencode([
    {
      name             = "${var.stack_name_prefix}-supertokens-container",
      image            = "supertokens/supertokens-postgresql:6.0",
      cpu              = 256,
      memory           = 512,
      essential        = true,
      portMappings     = [{ containerPort = 3567, protocol = "tcp" }],
      environment      = [{ name = "POSTGRESQL_TABLE_NAMES_PREFIX", value = "Supertokens" }],
      secrets          = [{ name = "POSTGRESQL_CONNECTION_URI", valueFrom = aws_secretsmanager_secret.supertokens_db_conn_string_secret.arn }],
      logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.supertokens_ecs_logs.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "ecs" } }
    }
  ])
  tags = { Name = "${var.stack_name_prefix}-supertokens-taskdef" }
}
resource "aws_ecs_service" "supertokens" {
  name            = "${var.stack_name_prefix}-supertokens-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.supertokens.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.supertokens.arn
    container_name   = "${var.stack_name_prefix}-supertokens-container"
    container_port   = 3567
  }
  tags = { Name = "${var.stack_name_prefix}-supertokens-service" }
}

# --- Hasura (graphql-engine) Service ---
resource "aws_lb_target_group" "hasura" {
  name        = "${var.stack_name_prefix}-hasura-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    enabled             = true
    path                = "/healthz"
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }
  tags = { Name = "${var.stack_name_prefix}-hasura-tg" }
}
resource "aws_lb_listener_rule" "hasura" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 20
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.hasura.arn
  }
  condition {
    path_pattern {
      values = ["/v1/graphql/*", "/console*", "/v1/metadata*"]
    }
  }
}
resource "aws_cloudwatch_log_group" "hasura_ecs_logs" {
  name              = "/ecs/${var.stack_name_prefix}-hasura"
  retention_in_days = 30
  tags              = { Name = "${var.stack_name_prefix}-hasura-ecs-logs" }
}
resource "aws_ecs_task_definition" "hasura" {
  family                   = "${var.stack_name_prefix}-hasura"
  cpu                      = "512"
  memory                   = "1024"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_application_task_role.arn
  container_definitions = jsonencode([
    {
      name         = "${var.stack_name_prefix}-hasura-container",
      image        = "hasura/graphql-engine:v2.38.0",
      cpu          = 512,
      memory       = 1024,
      essential    = true,
      portMappings = [{ containerPort = 8080, protocol = "tcp" }],
      environment = [
        { name = "HASURA_GRAPHQL_UNAUTHORIZED_ROLE", value = "public" },
        { name = "HASURA_GRAPHQL_LOG_LEVEL", value = "debug" },
        { name = "HASURA_GRAPHQL_ENABLE_CONSOLE", value = "true" },
        { name = "HASURA_GRAPHQL_DEV_MODE", value = "true" },
        { name = "HASURA_GRAPHQL_LIVE_QUERIES_MULTIPLEXED_REFETCH_INTERVAL", value = "1000" },
        { name = "HASURA_GRAPHQL_WEBSOCKETS_MAX_CONNECTIONS", value = "100" }
      ],
      secrets = [
        { name = "HASURA_GRAPHQL_DATABASE_URL", valueFrom = aws_secretsmanager_secret.hasura_db_conn_string_secret.arn },
        { name = "HASURA_GRAPHQL_ADMIN_SECRET", valueFrom = aws_secretsmanager_secret.hasura_admin_secret.arn },
        { name = "HASURA_GRAPHQL_JWT_SECRET", valueFrom = aws_secretsmanager_secret.hasura_jwt_secret.arn }
      ],
      logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.hasura_ecs_logs.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "ecs" } }
    }
  ])
  tags = { Name = "${var.stack_name_prefix}-hasura-taskdef" }
}
resource "aws_ecs_service" "hasura" {
  name                    = "${var.stack_name_prefix}-hasura-service"
  cluster                 = aws_ecs_cluster.main.id
  task_definition         = aws_ecs_task_definition.hasura.arn
  desired_count           = 1
  launch_type             = "FARGATE"
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.hasura.arn
    container_name   = "${var.stack_name_prefix}-hasura-container"
    container_port   = 8080
  }
  tags = { Name = "${var.stack_name_prefix}-hasura-service" }
}

# --- Functions Service ---
resource "aws_lb_target_group" "functions" {
  name        = "${var.stack_name_prefix}-functions-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    enabled             = true
    path                = "/v1/functions/healthz"
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200-299"
  }
  tags = { Name = "${var.stack_name_prefix}-functions-tg" }
}
resource "aws_lb_listener_rule" "functions" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 30
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.functions.arn
  }
  condition {
    path_pattern {
      values = ["/v1/functions/*"]
    }
  }
}
resource "aws_cloudwatch_log_group" "functions_ecs_logs" {
  name              = "/ecs/${var.stack_name_prefix}-functions"
  retention_in_days = 30
  tags              = { Name = "${var.stack_name_prefix}-functions-ecs-logs" }
}
resource "aws_ecs_task_definition" "functions" {
  family                   = "${var.stack_name_prefix}-functions"
  cpu                      = "512"
  memory                   = "1024"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_application_task_role.arn
  container_definitions = jsonencode([
    {
      name         = "${var.stack_name_prefix}-functions-container",
      image        = aws_ecr_repository.functions.repository_url,
      cpu          = 512,
      memory       = 1024,
      essential    = true,
      portMappings = [{ containerPort = 3000, protocol = "tcp" }],
      environment = [
        { name = "HASURA_GRAPHQL_GRAPHQL_URL", value = "http://${aws_lb.main.dns_name}/v1/graphql" },
        { name = "FUNCTION_SERVER_URL", value = "http://${aws_lb.main.dns_name}/v1/functions" },
        { name = "APP_CLIENT_URL", value = "http://${aws_lb.main.dns_name}" },
        { name = "S3_BUCKET", value = aws_s3_bucket.data_bucket.id },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "KAFKA_BOOTSTRAP_SERVERS", value = "PLACEHOLDER_MSK_BROKERS_FETCH_MANUALLY_OR_VIA_SECRET" }, # This will be manually updated post-deployment
        { name = "KAFKA_CLIENT_SECURITY_PROTOCOL", value = "SASL_SSL" },
        { name = "KAFKA_CLIENT_SASL_MECHANISM", value = "AWS_MSK_IAM" },
        { name = "OPENSEARCH_ENDPOINT", value = "https://${aws_opensearch_domain.main.endpoint}" },
        { name = "HANDSHAKE_URL", value = "http://${aws_lb.main.dns_name}/v1/handshake" },
        { name = "OPTAPLANNER_URL", value = "http://${aws_lb.main.dns_name}/v1/optaplanner" },
        { name = "OPTAPLANNER_USERNAME", value = "admin" },
      ],
      secrets = [
        { name = "HASURA_GRAPHQL_ADMIN_SECRET", valueFrom = aws_secretsmanager_secret.hasura_admin_secret.arn },
        { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_api_key_secret.arn },
        { name = "OPTAPLANNER_PASSWORD", valueFrom = aws_secretsmanager_secret.api_token_secret.arn }
      ],
      logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.functions_ecs_logs.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "ecs" } }
    }
  ])
  tags = { Name = "${var.stack_name_prefix}-functions-taskdef" }
}
resource "aws_ecs_service" "functions" {
  name                    = "${var.stack_name_prefix}-functions-service"
  cluster                 = aws_ecs_cluster.main.id
  task_definition         = aws_ecs_task_definition.functions.arn
  desired_count           = 1
  launch_type             = "FARGATE"
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.functions.arn
    container_name   = "${var.stack_name_prefix}-functions-container"
    container_port   = 3000
  }
  tags = { Name = "${var.stack_name_prefix}-functions-service" }
}

# --- App (Frontend) Service ---
resource "aws_lb_target_group" "app" {
  name        = "${var.stack_name_prefix}-app-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    enabled             = true
    path                = "/"
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200-399"
  }
  tags = { Name = "${var.stack_name_prefix}-app-tg" }
}
resource "aws_lb_listener_rule" "app" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}
resource "aws_cloudwatch_log_group" "app_ecs_logs" {
  name              = "/ecs/${var.stack_name_prefix}-app"
  retention_in_days = 30
  tags              = { Name = "${var.stack_name_prefix}-app-ecs-logs" }
}
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.stack_name_prefix}-app"
  cpu                      = "256"
  memory                   = "512"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_application_task_role.arn
  container_definitions = jsonencode([
    {
      name         = "${var.stack_name_prefix}-app-container",
      image        = aws_ecr_repository.app.repository_url,
      cpu          = 256,
      memory       = 512,
      essential    = true,
      portMappings = [{ containerPort = 3000, protocol = "tcp" }],
      environment = [
        { name = "NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_URL", value = "http://${aws_lb.main.dns_name}/v1/graphql" },
        { name = "NEXT_PUBLIC_HASURA_GRAPHQL_GRAPHQL_WS_URL", value = "ws://${aws_lb.main.dns_name}/v1/graphql" },
        { name = "NEXT_PUBLIC_SUPERTOKENS_API_DOMAIN", value = "http://${aws_lb.main.dns_name}/v1/auth" },
        { name = "NEXT_PUBLIC_EVENT_TO_QUEUE_AUTH_URL", value = "http://${aws_lb.main.dns_name}/v1/functions/schedule-event/publisherScheduleEvent/schedule-event-auth" },
        { name = "NEXT_PUBLIC_EVENT_TO_QUEUE_SHORT_AUTH_URL", value = "http://${aws_lb.main.dns_name}/v1/functions/schedule-event/publisherScheduleShortEvent/schedule-short-event-auth" },
        { name = "NEXT_PUBLIC_CALENDAR_TO_QUEUE_AUTH_URL", value = "http://${aws_lb.main.dns_name}/v1/functions/schedule-assist/publisherScheduleMeeting/schedule-meeting-to-queue-auth" },
        { name = "NEXT_PUBLIC_FEATURES_APPLY_TO_EVENTS_AUTH_URL", value = "http://${aws_lb.main.dns_name}/v1/functions/features-apply/publish-to-features-worker/features-worker-to-queue-auth" },
        { name = "NEXT_PUBLIC_METHOD_TO_SEARCH_INDEX_AUTH_URL", value = "http://${aws_lb.main.dns_name}/v1/functions/events-search/eventsSearch/events-search-auth" },
        { name = "NEXT_PUBLIC_HANDSHAKE_URL", value = "http://${aws_lb.main.dns_name}/v1/handshake/" },
        { name = "NEXT_PUBLIC_CHAT_WS_API_URL", value = "ws://${aws_lb.main.dns_name}/v1/functions" },
        { name = "NEXT_PUBLIC_GOOGLE_OAUTH_ATOMIC_WEB_API_START_URL", value = "http://${aws_lb.main.dns_name}/api/google/start-oauth" },
        { name = "NEXT_PUBLIC_GOOGLE_OAUTH_ATOMIC_WEB_REDIRECT_URL", value = "http://${aws_lb.main.dns_name}/api/google/oauth-callback" }
      ],
      logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.app_ecs_logs.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "ecs" } }
    }
  ])
  tags = { Name = "${var.stack_name_prefix}-app-taskdef" }
}
resource "aws_ecs_service" "app" {
  name                    = "${var.stack_name_prefix}-app-service"
  cluster                 = aws_ecs_cluster.main.id
  task_definition         = aws_ecs_task_definition.app.arn
  desired_count           = 1
  launch_type             = "FARGATE"
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "${var.stack_name_prefix}-app-container"
    container_port   = 3000
  }
  tags = { Name = "${var.stack_name_prefix}-app-service" }
}

# --- Handshake Service ---
resource "aws_lb_target_group" "handshake" {
  name        = "${var.stack_name_prefix}-handshake-tg"
  port        = 3000 # Assuming handshake also runs on 3000 like other Node.js apps
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health" # Placeholder health check path for handshake
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = {
    Name = "${var.stack_name_prefix}-handshake-tg"
  }
}

resource "aws_lb_listener_rule" "handshake" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 40 # Unique priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.handshake.arn
  }

  condition {
    path_pattern {
      values = ["/v1/handshake/*"]
    }
  }
}

resource "aws_ecs_task_definition" "handshake" {
  family                   = "${var.stack_name_prefix}-handshake"
  cpu                      = "256"
  memory                   = "512"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_application_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${var.stack_name_prefix}-handshake-container",
      image     = aws_ecr_repository.handshake.repository_url,
      cpu       = 256,
      memory    = 512,
      essential = true,
      portMappings = [
        {
          containerPort = 3000, # Assuming handshake runs on 3000
          protocol      = "tcp"
        }
      ],
      environment = [
        { name = "HASURA_GRAPHQL_GRAPHQL_URL", value = "http://${aws_lb.main.dns_name}/v1/graphql" },
        { name = "NEXT_PUBLIC_ATOMIC_HANDSHAKE_API", value = "http://${aws_lb.main.dns_name}/v1/functions/handshake-api/createRecurMeetAssists/create-recur-meet-assists-public" },
        { name = "MEETING_ASSIST_ADMIN_URL", value = "http://${aws_lb.main.dns_name}/v1/functions/schedule-assist/publisherScheduleMeeting/schedule-meeting-to-queue-admin" }
      ],
      secrets = [
        {
          name      = "API_TOKEN",
          valueFrom = aws_secretsmanager_secret.api_token_secret.arn
        },
        {
          name      = "HASURA_GRAPHQL_ADMIN_SECRET",
          valueFrom = aws_secretsmanager_secret.hasura_admin_secret.arn
        }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = "/ecs/${var.stack_name_prefix}-handshake",
          "awslogs-region"        = var.aws_region,
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Name = "${var.stack_name_prefix}-handshake-taskdef"
  }
}

resource "aws_cloudwatch_log_group" "handshake_ecs_logs" {
  name              = "/ecs/${var.stack_name_prefix}-handshake"
  retention_in_days = 30
  tags = {
    Name = "${var.stack_name_prefix}-handshake-ecs-logs"
  }
}

resource "aws_ecs_service" "handshake" {
  name                    = "${var.stack_name_prefix}-handshake-service"
  cluster                 = aws_ecs_cluster.main.id
  task_definition         = aws_ecs_task_definition.handshake.arn
  desired_count           = 1
  launch_type             = "FARGATE"
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.handshake.arn
    container_name   = "${var.stack_name_prefix}-handshake-container"
    container_port   = 3000
  }
  tags = {
    Name = "${var.stack_name_prefix}-handshake-service"
  }
}

# --- OAuth Service ---
resource "aws_lb_target_group" "oauth" {
  name        = "${var.stack_name_prefix}-oauth-tg"
  port        = 3000 # Assuming oauth also runs on 3000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health" # Placeholder health check path for oauth
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = {
    Name = "${var.stack_name_prefix}-oauth-tg"
  }
}

resource "aws_lb_listener_rule" "oauth" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 50 # Unique priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.oauth.arn
  }

  condition {
    path_pattern {
      values = ["/v1/oauth/*"]
    }
  }
}

resource "aws_ecs_task_definition" "oauth" {
  family                   = "${var.stack_name_prefix}-oauth"
  cpu                      = "256"
  memory                   = "512"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_application_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${var.stack_name_prefix}-oauth-container",
      image     = aws_ecr_repository.oauth.repository_url,
      cpu       = 256,
      memory    = 512,
      essential = true,
      portMappings = [
        {
          containerPort = 3000, # Assuming oauth runs on 3000
          protocol      = "tcp"
        }
      ],
      environment = [
        { name = "HASURA_GRAPHQL_GRAPHQL_URL", value = "http://${aws_lb.main.dns_name}/v1/graphql" },
        { name = "NEXT_PUBLIC_APP_URL", value = "http://${aws_lb.main.dns_name}" },
        { name = "HANDSHAKE_URL", value = "http://${aws_lb.main.dns_name}/v1/handshake" },
        { name = "GOOGLE_CLIENT_ID_WEB", value = "PLACEHOLDER_GOOGLE_CLIENT_ID_WEB" },
        { name = "GOOGLE_CLIENT_SECRET_WEB", value = "PLACEHOLDER_GOOGLE_CLIENT_SECRET_WEB" },
        { name = "GOOGLE_REDIRECT_URL", value = "http://${aws_lb.main.dns_name}/v1/oauth/api/google-calendar-handshake/oauth2callback" },
        { name = "ZOOM_CLIENT_ID", value = "PLACEHOLDER_ZOOM_CLIENT_ID" },
        { name = "NEXT_PUBLIC_ZOOM_CLIENT_ID", value = "PLACEHOLDER_NEXT_PUBLIC_ZOOM_CLIENT_ID" },
        { name = "NEXT_PUBLIC_ZOOM_REDIRECT_URL", value = "http://${aws_lb.main.dns_name}/v1/oauth/zoom/mobile-callback" },
        { name = "ZOOM_CLIENT_SECRET", value = "PLACEHOLDER_ZOOM_CLIENT_SECRET" },
        { name = "ZOOM_WEBHOOK_SECRET_TOKEN", value = "PLACEHOLDER_ZOOM_WEBHOOK_SECRET_TOKEN" },
        { name = "ZOOM_IV_FOR_PASS", value = "PLACEHOLDER_ZOOM_IV_FOR_PASS" },
        { name = "ZOOM_SALT_FOR_PASS", value = "PLACEHOLDER_ZOOM_SALT_FOR_PASS" },
        { name = "ZOOM_PASS_KEY", value = "PLACEHOLDER_ZOOM_PASS_KEY" }
      ],
      secrets = [
        {
          name      = "HASURA_GRAPHQL_ADMIN_SECRET",
          valueFrom = aws_secretsmanager_secret.hasura_admin_secret.arn
        }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = "/ecs/${var.stack_name_prefix}-oauth",
          "awslogs-region"        = var.aws_region,
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Name = "${var.stack_name_prefix}-oauth-taskdef"
  }
}

resource "aws_cloudwatch_log_group" "oauth_ecs_logs" {
  name              = "/ecs/${var.stack_name_prefix}-oauth"
  retention_in_days = 30
  tags = {
    Name = "${var.stack_name_prefix}-oauth-ecs-logs"
  }
}

resource "aws_ecs_service" "oauth" {
  name                    = "${var.stack_name_prefix}-oauth-service"
  cluster                 = aws_ecs_cluster.main.id
  task_definition         = aws_ecs_task_definition.oauth.arn
  desired_count           = 1
  launch_type             = "FARGATE"
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.oauth.arn
    container_name   = "${var.stack_name_prefix}-oauth-container"
    container_port   = 3000
  }
  tags = {
    Name = "${var.stack_name_prefix}-oauth-service"
  }
}

# --- Optaplanner Service ---
resource "aws_lb_target_group" "optaplanner" {
  name        = "${var.stack_name_prefix}-optaplanner-tg"
  port        = 8081 # Optaplanner default port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/q/health" # Quarkus health check path
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10 # Quarkus apps can be slower to start/respond initially
    interval            = 45
    matcher             = "200"
  }

  tags = {
    Name = "${var.stack_name_prefix}-optaplanner-tg"
  }
}

resource "aws_lb_listener_rule" "optaplanner" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 60 # Unique priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.optaplanner.arn
  }

  condition {
    path_pattern {
      values = ["/v1/optaplanner/*"]
    }
  }
}

resource "aws_ecs_task_definition" "optaplanner" {
  family                   = "${var.stack_name_prefix}-optaplanner"
  cpu                      = "1024" # More for Java/Quarkus
  memory                   = "2048"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_application_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${var.stack_name_prefix}-optaplanner-container",
      image     = aws_ecr_repository.optaplanner.repository_url,
      cpu       = 1024,
      memory    = 2048,
      essential = true,
      portMappings = [
        {
          containerPort = 8081,
          protocol      = "tcp"
        }
      ],
      environment = [
        { name = "QUARKUS_DATASOURCE_DB_KIND", value = "postgresql" },
        { name = "USERNAME", value = "admin" }
      ],
      secrets = [
        {
          name      = "PASSWORD",
          valueFrom = aws_secretsmanager_secret.api_token_secret.arn
        },
        {
          name      = "QUARKUS_DATASOURCE_JDBC_URL",
          valueFrom = aws_secretsmanager_secret.optaplanner_db_conn_string_secret.arn
        },
        {
          name      = "QUARKUS_DATASOURCE_USERNAME",
          valueFrom = aws_secretsmanager_secret.db_credentials.arn
        },
        {
          name      = "QUARKUS_DATASOURCE_PASSWORD",
          valueFrom = aws_secretsmanager_secret.db_credentials.arn
        }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = "/ecs/${var.stack_name_prefix}-optaplanner",
          "awslogs-region"        = var.aws_region,
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Name = "${var.stack_name_prefix}-optaplanner-taskdef"
  }
}

resource "aws_cloudwatch_log_group" "optaplanner_ecs_logs" {
  name              = "/ecs/${var.stack_name_prefix}-optaplanner"
  retention_in_days = 30
  tags = {
    Name = "${var.stack_name_prefix}-optaplanner-ecs-logs"
  }
}

resource "aws_ecs_service" "optaplanner" {
  name                    = "${var.stack_name_prefix}-optaplanner-service"
  cluster                 = aws_ecs_cluster.main.id
  task_definition         = aws_ecs_task_definition.optaplanner.arn
  desired_count           = 1
  launch_type             = "FARGATE"
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.optaplanner.arn
    container_name   = "${var.stack_name_prefix}-optaplanner-container"
    container_port   = 8081
  }
  tags = {
    Name = "${var.stack_name_prefix}-optaplanner-service"
  }
}

# Amazon OpenSearch Service Domain
resource "aws_opensearch_domain" "main" {
  domain_name    = "${var.stack_name_prefix}-atomic-os" # Must be lowercase and unique
  engine_version = "OpenSearch_2.11"                    # Specify a recent, supported version

  cluster_config {
    instance_type  = "t3.small.search" # For dev/testing
    instance_count = 1                 # Single node for dev
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 10 # Minimum is 10 GiB
    volume_type = "gp2"
  }

  node_to_node_encryption {
    enabled = true
  }

  encrypt_at_rest {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https = true
  }

  advanced_security_options {
    enabled                        = true
    internal_user_database_enabled = false
  }

  access_policies = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          AWS = [
            aws_iam_role.ecs_application_task_role.arn
          ]
        },
        Action   = "es:ESHttp*",
        Resource = "arn:aws:es:${var.aws_region}:${data.aws_caller_identity.current.account_id}:domain/${var.stack_name_prefix}-atomic-os/*"
      }
    ]
  })

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_app_logs.arn
    log_type                 = "ES_APPLICATION_LOGS"
    enabled                  = true
  }
  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_slow_logs.arn
    log_type                 = "SEARCH_SLOW_LOGS"
    enabled                  = true
  }

  tags = {
    Name        = "${var.stack_name_prefix}-opensearch-domain"
    Environment = "dev"
  }
}

resource "aws_cloudwatch_log_group" "opensearch_app_logs" {
  name              = "/aws/opensearch/${var.stack_name_prefix}-atomic-os/application-logs"
  retention_in_days = 7
  tags              = { Name = "${var.stack_name_prefix}-os-app-logs" }
}
resource "aws_cloudwatch_log_group" "opensearch_slow_logs" {
  name              = "/aws/opensearch/${var.stack_name_prefix}-atomic-os/slow-logs"
  retention_in_days = 7
  tags              = { Name = "${var.stack_name_prefix}-os-slow-logs" }
}

# Amazon MSK Serverless Cluster
resource "aws_msk_serverless_cluster" "main" {
  cluster_name = "${var.stack_name_prefix}-atomic-msk-serverless"

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.msk_client.id]
  }

  client_authentication {
    sasl {
      iam {
        enabled = true
      }
    }
  }

  tags = {
    Name        = "${var.stack_name_prefix}-msk-serverless-cluster"
    Environment = "dev"
  }
}
