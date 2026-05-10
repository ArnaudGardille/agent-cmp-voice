# ── IAM role for the Lambda function ──────────────────────────────────────────

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_connect" {
  name               = "cmp-voice-demo-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_connect.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "cmp-voice-demo-bedrock"
  role = aws_iam_role.lambda_connect.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "*"
      }
    ]
  })
}

# ── Allow Connect to invoke the Lambda ────────────────────────────────────────

resource "aws_lambda_permission" "connect_invoke" {
  statement_id  = "AllowConnectInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connect_handler.function_name
  principal     = "connect.amazonaws.com"
  source_arn    = aws_connect_instance.demo.arn
}
