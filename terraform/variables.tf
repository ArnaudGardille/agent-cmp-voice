variable "aws_region" {
  description = "AWS region (Connect available in us-east-1, us-west-2, eu-west-2…)"
  default     = "us-east-1"
}

variable "instance_alias" {
  description = "AWS Connect instance alias (globally unique)"
  default     = "cmp-voice-demo"
}

variable "phone_country_code" {
  description = "Country code for outbound DID number (US recommended for availability)"
  default     = "US"
}
