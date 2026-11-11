data "http" "my_ip" {
  url = "https://checkip.amazonaws.com"
}

locals {
  allowed_cidr = coalesce(var.allowed_cidr, "${chomp(data.http.my_ip.response_body)}/32")
  project_root = "${path.module}/../../.."
}

# Amazon Linux 2023, current AMI for the region.
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_vpc" "default" {
  default = true
}

resource "tls_private_key" "ssh" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "joules" {
  key_name_prefix = "joules-"
  public_key      = tls_private_key.ssh.public_key_openssh
}

resource "local_sensitive_file" "ssh_key" {
  content         = tls_private_key.ssh.private_key_openssh
  filename        = "${path.module}/joules.pem"
  file_permission = "0600"
}

resource "aws_security_group" "joules" {
  name_prefix = "joules-"
  description = "Joules demo: SSH and web UI from one CIDR"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "ssh"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [local.allowed_cidr]
  }
  ingress {
    description = "nginx (audit app + Prefect UI)"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [local.allowed_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "joules" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.instance_type
  key_name                    = aws_key_pair.joules.key_name
  vpc_security_group_ids      = [aws_security_group.joules.id]
  associate_public_ip_address = true

  root_block_device {
    volume_size           = var.disk_gb
    volume_type           = "gp3"
    delete_on_termination = true
  }

  metadata_options {
    http_tokens = "required"
  }

  user_data = <<-EOT
    #!/bin/bash
    set -eux
    dnf install -y docker
    systemctl enable --now docker
    usermod -aG docker ec2-user
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  EOT

  tags = { Name = "joules-demo" }
}

# Ship the working tree (not .git, .venv or this directory) and start the stack.
data "archive_file" "project" {
  type        = "tar.gz"
  source_dir  = local.project_root
  output_path = "${path.module}/.project.tar.gz"
  excludes    = [".git", ".venv", ".claude", "examples/deploy/aws", "__pycache__", ".env"]
}

resource "terraform_data" "deploy" {
  triggers_replace = [aws_instance.joules.id, data.archive_file.project.output_sha256]

  connection {
    type        = "ssh"
    host        = aws_instance.joules.public_ip
    user        = "ec2-user"
    private_key = tls_private_key.ssh.private_key_openssh
    timeout     = "5m"
  }

  provisioner "file" {
    source      = data.archive_file.project.output_path
    destination = "/tmp/joules.tar.gz"
  }

  provisioner "remote-exec" {
    inline = [
      "cloud-init status --wait",
      "mkdir -p ~/joules && tar -xzf /tmp/joules.tar.gz -C ~/joules",
      "cd ~/joules/examples/deploy && sg docker -c 'docker compose up -d --build'",
    ]
  }
}
