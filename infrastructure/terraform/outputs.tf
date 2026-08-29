output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.bots.id
}

output "public_ip" {
  description = "Elastic IP attached to the bots instance."
  value       = aws_eip.bots.public_ip
}

output "vpc_id" {
  description = "ID of the VPC that hosts the instance."
  value       = aws_vpc.main.id
}

output "ssh_command" {
  description = "Ready-to-paste SSH command."
  value       = "ssh -i ${replace(var.public_key_path, ".pub", "")} ec2-user@${aws_eip.bots.public_ip}"
}
