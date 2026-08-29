# ─────────────────────────────────────────────────────────────────────────────
# AWS infrastructure for the telegram-bots monorepo.
#
# Goal (per spec): a closed VPC with a single EC2 instance that accepts
# inbound traffic ONLY on SSH/22. The bots themselves make outbound
# long-polling calls to Telegram and Google — they never receive inbound
# traffic from the public internet.
#
# Architecture
# ────────────
#
#   Internet
#       │
#       ▼
#   ┌──────────────────┐
#   │ Internet Gateway │
#   └────────┬─────────┘
#            │
#   ┌────────┴────────────────────────── VPC 10.0.0.0/16 ──┐
#   │                                                      │
#   │   ┌──── public subnet 10.0.1.0/24 ─────────────┐    │
#   │   │                                             │    │
#   │   │   ┌─────────────────────────────────────┐   │    │
#   │   │   │ EC2 (Amazon Linux 2023, t3.micro)   │   │    │
#   │   │   │                                     │   │    │
#   │   │   │   • docker compose up → 3 bots      │   │    │
#   │   │   │   • Elastic IP attached             │   │    │
#   │   │   │                                     │   │    │
#   │   │   └─────────────────────────────────────┘   │    │
#   │   │         │                                   │    │
#   │   │         │  SG inbound:  TCP 22 ← var.allowed_ssh_cidr
#   │   │         │  SG outbound: ALL    → 0.0.0.0/0
#   │   └─────────┼───────────────────────────────────┘    │
#   └─────────────┼─────────────────────────────────────────┘
#                 ▼
#           Telegram API, Google APIs (outbound only)
#
# The security posture is: you can only reach the box over SSH, and only
# from the CIDR you explicitly whitelist in terraform.tfvars. Everything
# else inbound is dropped.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}

# ─── Networking ─────────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# One public subnet is enough — we only need a single EC2 instance and the
# bots only make outbound calls. A NAT gateway would cost money for no
# benefit here.
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-subnet"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ─── Security group ─────────────────────────────────────────────────────────
# THE entire security posture is in this block. Change with care.

resource "aws_security_group" "bots" {
  name        = "${var.project_name}-sg"
  description = "SSH-only inbound; unrestricted egress for Telegram/Google API calls"
  vpc_id      = aws_vpc.main.id

  # The ONLY inbound rule. Locked to a caller-supplied CIDR — do NOT set
  # this to 0.0.0.0/0 in terraform.tfvars unless you have a very good
  # reason (and even then, at least enable key-only auth on the instance).
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # Unrestricted egress — the bots need to reach api.telegram.org,
  # googleapis.com, generativelanguage.googleapis.com, etc. Locking egress
  # to specific destinations would be brittle (Telegram DC IPs rotate).
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-sg"
  }
}

# ─── SSH key pair ───────────────────────────────────────────────────────────

resource "aws_key_pair" "main" {
  key_name   = "${var.project_name}-key"
  public_key = file(var.public_key_path)
}

# ─── AMI lookup ─────────────────────────────────────────────────────────────
# Amazon Linux 2023 — rolling latest, officially supported, has docker in
# the default repos.

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-kernel-6.1-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ─── EC2 instance ───────────────────────────────────────────────────────────

resource "aws_instance" "bots" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.bots.id]
  key_name               = aws_key_pair.main.key_name

  root_block_device {
    volume_size           = var.root_volume_gb
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  # Cloud-init script that bootstraps docker + compose plugin on first boot.
  # After `terraform apply` finishes, you can SSH in, clone the monorepo,
  # and `make up` immediately — no manual package installs needed.
  user_data = <<-EOF
              #!/bin/bash
              set -euxo pipefail
              dnf update -y
              dnf install -y docker git
              systemctl enable --now docker
              usermod -aG docker ec2-user

              # Install docker compose plugin
              DOCKER_CONFIG=/usr/local/lib/docker
              mkdir -p $DOCKER_CONFIG/cli-plugins
              curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
                -o $DOCKER_CONFIG/cli-plugins/docker-compose
              chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
              EOF

  tags = {
    Name = "${var.project_name}-host"
  }
}

# Static public IP — survives stop/start and re-applies. Without this the
# public IP changes whenever the instance is stopped, which breaks DNS.
resource "aws_eip" "bots" {
  instance = aws_instance.bots.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }

  depends_on = [aws_internet_gateway.main]
}
