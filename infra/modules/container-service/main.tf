# ECS Fargate service for one platform container (BLUEPRINT §7). Images are pinned by digest.
# desired_count defaults to 0: nothing runs (or costs compute) until the owner decides.
terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "image" {
  type        = string
  description = "Container image pinned by digest: registry/repo@sha256:<64 hex>"
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image))
    error_message = "image must be pinned by digest (…@sha256:<64 hex>)."
  }
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  type    = number
  default = 0
}

variable "container_port" {
  type    = number
  default = 8080
}

variable "environment" {
  type        = map(string)
  default     = {}
  description = "Non-secret settings only"
}

variable "secret_arns" {
  type        = map(string)
  default     = {}
  description = "ENV_NAME => Secrets Manager/SSM ARN; values are injected at runtime, never in state"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

locals {
  assume_ecs_tasks = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_ecs_cluster" "this" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/nf/${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "execution" {
  name               = "${var.name}-execution"
  assume_role_policy = local.assume_ecs_tasks
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  count = length(var.secret_arns) > 0 ? 1 : 0
  name  = "read-injected-secrets"
  role  = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue", "ssm:GetParameters"]
      Resource = values(var.secret_arns)
    }]
  })
}

# Application permissions are added per service (least privilege), not here.
resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  assume_role_policy = local.assume_ecs_tasks
}

resource "aws_security_group" "service" {
  name        = "${var.name}-service"
  description = "Platform service tasks"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_egress_rule" "https" {
  security_group_id = aws_security_group.service.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "postgres" {
  security_group_id = aws_security_group.service.id
  cidr_ipv4         = "10.0.0.0/8"
  ip_protocol       = "tcp"
  from_port         = 5432
  to_port           = 5432
}

resource "aws_ecs_task_definition" "this" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }
  container_definitions = jsonencode([{
    name                   = var.name
    image                  = var.image
    essential              = true
    readonlyRootFilesystem = true
    portMappings           = [{ containerPort = var.container_port, protocol = "tcp" }]
    environment            = [for k, v in var.environment : { name = k, value = v }]
    secrets                = [for k, v in var.secret_arns : { name = k, valueFrom = v }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.this.name
        awslogs-region        = var.region
        awslogs-stream-prefix = var.name
      }
    }
  }])
}

resource "aws_ecs_service" "this" {
  name            = var.name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}

output "cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "service_name" {
  value = aws_ecs_service.this.name
}

output "security_group_id" {
  value = aws_security_group.service.id
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "task_role_name" {
  value = aws_iam_role.task.name
}

output "assign_public_ip" {
  value = aws_ecs_service.this.network_configuration[0].assign_public_ip
}
