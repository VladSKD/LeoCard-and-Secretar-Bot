variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Used as a prefix for all resource names and as the value of the Project tag."
  type        = string
  default     = "telegram-bots"
}

variable "instance_type" {
  description = "EC2 instance type. t3.micro is usually enough for three low-traffic bots."
  type        = string
  default     = "t3.micro"
}

variable "root_volume_gb" {
  description = "Root EBS volume size in GB. 20 leaves room for Docker images, logs, generated petitions, and a few months of PicklePersistence growth."
  type        = number
  default     = 20
}

variable "allowed_ssh_cidr" {
  description = <<-EOT
    CIDR block allowed to reach SSH on the instance. This is THE security
    boundary — keep it as narrow as possible. Use "A.B.C.D/32" to restrict
    to a single IP (find yours with `curl ifconfig.me`).

    Do NOT set this to 0.0.0.0/0 unless you understand the consequences.
  EOT
  type        = string

  validation {
    condition     = var.allowed_ssh_cidr != "0.0.0.0/0"
    error_message = "Refusing to open SSH to the whole internet. Narrow allowed_ssh_cidr to your IP (e.g. A.B.C.D/32)."
  }
}

variable "public_key_path" {
  description = "Path to the SSH public key that will be installed on the EC2 instance (e.g. ~/.ssh/id_ed25519.pub)."
  type        = string
}
