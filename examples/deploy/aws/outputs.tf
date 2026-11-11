output "audit_url" {
  value = "http://${aws_instance.joules.public_ip}:8080/audit/"
}

output "prefect_url" {
  value = "http://${aws_instance.joules.public_ip}:8080/prefect/"
}

output "ssh" {
  value = "ssh -i ${abspath(path.module)}/joules.pem ec2-user@${aws_instance.joules.public_ip}"
}

output "allowed_cidr" {
  value = local.allowed_cidr
}
