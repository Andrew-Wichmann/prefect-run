variable "region" {
  type    = string
  default = "us-east-1"
}

variable "instance_type" {
  description = "t3.small (2 GB) is the smallest that runs the whole stack comfortably."
  type        = string
  default     = "t3.small"
}

variable "disk_gb" {
  type    = number
  default = 20
}

variable "allowed_cidr" {
  description = "CIDR allowed to reach SSH and the web UI. Defaults to this machine's public IP."
  type        = string
  default     = null
}
