"""Lambda for the root."""
def lambda_handler(event, context):

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"message": "Welcome to the IMAP API. '
                'See [link to document for usage] for more information."}'
    }