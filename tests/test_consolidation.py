import json
import os
import sys
from decimal import Decimal
import pytest
from moto import mock_aws
import boto3

# Garante que o Python encontre o código do serviço
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/consolidation-service')))
import app

@pytest.fixture(scope="function")
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["ConsolidatedTable"] = "LedgerConsolidated-test"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture(scope="function")
def setup_dynamo(aws_credentials):
    """Instancia a tabela de consolidação mockada."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName="LedgerConsolidated-test",
            KeySchema=[
                {'AttributeName': 'merchant_id', 'KeyType': 'HASH'},
                {'AttributeName': 'date', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'merchant_id', 'AttributeType': 'S'},
                {'AttributeName': 'date', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        yield dynamodb

def test_consolidation_batch_processing(setup_dynamo):
    """Simula um lote do SQS com 1 Crédito (200) e 1 Débito (50). Saldo deve ser 150."""
    sqs_event = {
        "Records": [
            {
                "messageId": "msg-001",
                "body": json.dumps({
                    "merchant_id": "merchant_abc",
                    "posting_id": "uuid-1",
                    "amount": "200.00",
                    "type": "CREDIT",
                    "timestamp": "2026-07-19T14:30:00Z"
                })
            },
            {
                "messageId": "msg-002",
                "body": json.dumps({
                    "merchant_id": "merchant_abc",
                    "posting_id": "uuid-2",
                    "amount": "50.00",
                    "type": "DEBIT",
                    "timestamp": "2026-07-19T15:00:00Z"
                })
            }
        ]
    }
    
    # Executa a função do consolidador passando o lote fake do SQS
    response = app.lambda_handler(sqs_event, None)
    assert response["statusCode"] == 200
    
    # Valida se o saldo consolidado final calculado no banco NoSQL está correto (200 - 50 = 150)
    table = setup_dynamo.Table("LedgerConsolidated-test")
    result = table.get_item(Key={"merchant_id": "merchant_abc", "date": "2026-07-19"})
    
    assert "Item" in result
    assert result["Item"]["daily_balance"] == Decimal("150.00")