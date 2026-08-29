# Terraform — AWS EC2 for telegram-bots

Provisions a locked-down single-instance deployment for the monorepo.

## What it creates

- A fresh VPC (`10.0.0.0/16`) — not the default VPC.
- A single public subnet (`10.0.1.0/24`) with an Internet Gateway and route
  table (needed for outbound Telegram/Google API calls).
- One EC2 instance (Amazon Linux 2023, t3.micro by default) with an
  Elastic IP so the public address survives stop/start.
- A security group with exactly **one inbound rule**: TCP/22 from the CIDR
  you set in `terraform.tfvars`. Everything else inbound is dropped.
- Cloud-init `user_data` that installs Docker + the Compose plugin on
  first boot, so you can `make up` immediately after SSH'ing in.

## Prerequisites

1. AWS credentials configured (`aws configure` or `AWS_PROFILE`).
2. An SSH key pair on your laptop. Create a dedicated one:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/telegram_bots_ec2 -C "telegram-bots-ec2"
   ```
3. Your current public IP (`curl ifconfig.me`), formatted as a `/32` CIDR.

## Deploy

```bash
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars        # set public_key_path and allowed_ssh_cidr

terraform init
terraform plan
terraform apply
```

After ~2 minutes the outputs will include an `ssh_command` you can paste
directly.

## First-time bot bootstrap on the instance

```bash
# SSH in (use the ssh_command from terraform output)
ssh -i ~/.ssh/telegram_bots_ec2 ec2-user@<eip>

# Copy or clone the monorepo onto the box
# Option A: rsync from your laptop
#   rsync -avz --exclude='.git' --exclude='data' \
#     ~/Desktop/Pet/bots/monorepo/ ec2-user@<eip>:~/monorepo/
#
# Option B: git clone (requires the repo to be pushed somewhere)
#   git clone git@github.com:<you>/<repo>.git monorepo

cd ~/monorepo
make init
$EDITOR .env        # fill in all secrets
$EDITOR shared/logging_config.py   # implement the TODO
make up
make ps
make logs
```

## Refresh your SSH CIDR (if your IP changes)

```bash
# Update terraform.tfvars with the new CIDR
terraform apply
```

Only the security group rule changes — the instance keeps running.

## Teardown

```bash
terraform destroy
```

Everything in this stack (VPC, EC2, EIP, SG, key pair) is deleted. Data
stored on the instance is lost. If you care about the `bot_persistence`
pickle or `generated_petitions/`, scp them off the box first.

## Costs (rough, eu-central-1, as of 2025)

| Resource | ~Monthly |
|---|---|
| EC2 t3.micro on-demand | ~$8 |
| EBS gp3 20 GB | ~$2 |
| Elastic IP (attached) | $0 |
| Data transfer out | negligible for three polling bots |

Total: ~$10/month. An EIP is only billed when *not* attached to a running
instance, so don't `stop` the instance for long periods.

## Why not use the default VPC?

Because the default VPC has a pre-existing security group, route table,
and NACLs that you don't control. Using a fresh VPC means the security
posture of the deployment is 100% defined in this directory — nothing
leaks in from account-level defaults.
