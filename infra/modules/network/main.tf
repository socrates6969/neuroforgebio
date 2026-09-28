# Private-only VPC for the platform. No internet gateway and no NAT in dev: AWS services are
# reached through VPC endpoints (S3 gateway endpoint; interface endpoints for ECR, logs, secrets).
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

variable "cidr_block" {
  type    = string
  default = "10.40.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "Passed in explicitly (no data source), so plans work against a mock provider"
}

variable "enable_interface_endpoints" {
  type        = bool
  default     = true
  description = "Interface endpoints have an hourly cost per AZ; needed for Fargate without NAT"
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = var.name }
}

# Lock down the default security group: no rules at all.
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_subnet" "private" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr_block, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name}-private-${count.index}" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-private" }
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
}

resource "aws_security_group" "endpoints" {
  count       = var.enable_interface_endpoints ? 1 : 0
  name        = "${var.name}-endpoints"
  description = "HTTPS from inside the VPC to interface endpoints"
  vpc_id      = aws_vpc.this.id
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_https" {
  count             = var.enable_interface_endpoints ? 1 : 0
  security_group_id = aws_security_group.endpoints[0].id
  cidr_ipv4         = var.cidr_block
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

locals {
  interface_services = var.enable_interface_endpoints ? toset(["ecr.api", "ecr.dkr", "logs", "secretsmanager", "kms"]) : toset([])
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = local.interface_services
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${var.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints[0].id]
}

output "vpc_id" {
  value = aws_vpc.this.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "cidr_block" {
  value = aws_vpc.this.cidr_block
}
