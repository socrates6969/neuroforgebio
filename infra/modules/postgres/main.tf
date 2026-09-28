# Managed PostgreSQL 16 (BLUEPRINT §6). Private, KMS-encrypted, TLS forced.
# The master password is generated and stored by RDS in Secrets Manager
# (manage_master_user_password), so no password is ever in variables or state.
terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  type        = list(string)
  default     = []
  description = "Security groups allowed to connect on 5432"
}

variable "kms_key_arn" {
  type = string
}

variable "engine_version" {
  type    = string
  default = "16"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  type    = number
  default = 20
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  type    = bool
  default = true
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "db" {
  name        = "${var.name}-db"
  description = "PostgreSQL access from the platform services only"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "db" {
  count                        = length(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name}-pg16"
  family = "postgres16"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "this" {
  identifier                          = var.name
  engine                              = "postgres"
  engine_version                      = var.engine_version
  instance_class                      = var.instance_class
  allocated_storage                   = var.allocated_storage_gb
  storage_type                        = "gp3"
  storage_encrypted                   = true
  kms_key_id                          = var.kms_key_arn
  db_subnet_group_name                = aws_db_subnet_group.this.name
  vpc_security_group_ids              = [aws_security_group.db.id]
  parameter_group_name                = aws_db_parameter_group.this.name
  publicly_accessible                 = false
  username                            = "nf_admin"
  manage_master_user_password         = true
  master_user_secret_kms_key_id       = var.kms_key_arn
  iam_database_authentication_enabled = true
  backup_retention_period             = var.backup_retention_days
  deletion_protection                 = var.deletion_protection
  skip_final_snapshot                 = !var.deletion_protection
  final_snapshot_identifier           = var.deletion_protection ? "${var.name}-final" : null
  auto_minor_version_upgrade          = true
  copy_tags_to_snapshot               = true
}

output "endpoint" {
  value = aws_db_instance.this.address
}

output "master_user_secret_arn" {
  description = "ARN only; the secret value lives in Secrets Manager, never in state"
  value       = try(aws_db_instance.this.master_user_secret[0].secret_arn, null)
}

output "publicly_accessible" {
  value = aws_db_instance.this.publicly_accessible
}

output "storage_encrypted" {
  value = aws_db_instance.this.storage_encrypted
}
