output "connect_instance_id" {
  description = "AWS Connect instance ID → CONNECT_INSTANCE_ID"
  value       = aws_connect_instance.demo.id
}

output "connect_instance_arn" {
  description = "AWS Connect instance ARN"
  value       = aws_connect_instance.demo.arn
}

output "contact_flow_id" {
  description = "Contact flow ID → CONTACT_FLOW_ID"
  value       = aws_connect_contact_flow.outbound_demo.contact_flow_id
}

output "source_phone_number" {
  description = "Claimed DID number → CONNECT_SOURCE_PHONE"
  value       = aws_connect_phone_number.demo.phone_number
}

output "lambda_arn" {
  description = "Lambda ARN (invoked by Connect for dynamic prompts)"
  value       = aws_lambda_function.connect_handler.arn
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}
