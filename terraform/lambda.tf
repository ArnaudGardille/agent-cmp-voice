# ── Package the Lambda ────────────────────────────────────────────────────────

data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/../demo/lambda_connect.zip"
  source_dir  = "${path.module}/../demo"
  excludes = [
    "demo.db", "__pycache__", "*.pyc", "*.zip",
    "run.py", "seed.py", "trigger.py", "analysis.py"
  ]
}

# ── Lambda function ───────────────────────────────────────────────────────────

resource "aws_lambda_function" "connect_handler" {
  function_name    = "cmp-voice-demo-connect-handler"
  description      = "Handler appelé par Connect à chaque tour de conversation"
  role             = aws_iam_role.lambda_connect.arn
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.12"
  handler          = "lambda_connect.lambda_handler"
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      BEDROCK_REGION = var.aws_region
      MODEL_ID       = "amazon.nova-lite-v1:0"
    }
  }
}
