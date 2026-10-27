# Joule on a throwaway EC2 instance

One `t3.small` (Amazon Linux 2023, 20 GB gp3) in the default VPC, running the whole Docker Compose
stack. SSH and port 8080 are open only to your current public IP. About $0.70 per day; terraform
destroy removes everything, including the disk.

## Prerequisites

- Terraform (or OpenTofu) installed.
- Working AWS credentials with EC2 permissions: check with `aws sts get-caller-identity`.
  For SSO run `aws sso login` yourself; an agent can't do the browser step.

## By hand

```sh
cd infra/aws
terraform init
terraform apply            # ~5 min: boots, installs Docker, copies the project, builds, starts
# open the audit_url / prefect_url it prints
terraform destroy          # when done, so billing stops
```

Override size or region with `-var instance_type=t3.micro -var region=eu-west-1`. If your IP changes
mid-session, `terraform apply` again to update the security group (or pass `-var allowed_cidr=1.2.3.4/32`).

After the stack is up, trigger runs on the instance:

```sh
$(terraform output -raw ssh) 'cd joule && docker compose exec -T prefect-worker python -c "
from prefect.deployments import run_deployment
run_deployment(name=\"ingest-instruments/ingest-instruments\", timeout=0)" </dev/null'
```

## Prompting an agent

Apply:

> Read infra/aws/README.md. Check AWS credentials with `aws sts get-caller-identity` (stop and tell me
> if they fail). Then in infra/aws run `terraform init` and `terraform plan`, show me a summary of what
> will be created, and wait for my OK. After I approve, run `terraform apply -auto-approve`, then curl
> the `audit_url` output to confirm it responds, trigger 5 ingest runs on the instance, and give me
> the URLs.

Destroy:

> In infra/aws run `terraform destroy`, show me the plan, and after I OK it run
> `terraform destroy -auto-approve`. Afterwards confirm nothing is left with
> `aws ec2 describe-instances --filters Name=tag:Project,Values=joule Name=instance-state-name,Values=pending,running,stopped --query 'Reservations[].Instances[].InstanceId'`
> (it should print `[]`).

Pave from scratch (destroy then apply, e.g. to test a clean deploy):

> In infra/aws, destroy the existing instance, then apply again, with a confirmation from me before each
> step. Report the new URLs.

## Notes

- State is local (`terraform.tfstate` here, git-ignored). Lose it and you'll have to delete the
  tagged resources (`Project=joule`) by hand.
- The private key is written to `infra/aws/joule.pem` (git-ignored).
- The project is copied from your working tree at apply time (not `.git`, `.venv`, `.env` or `infra`).
  Edit code and `terraform apply` again to redeploy (the tarball hash triggers the copy and
  `docker compose up -d --build`).
- Everything is HTTP on a single-IP allowlist; the Prefect UI has no auth.
