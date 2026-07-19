import json
import os
import sys
import pytest
from moto import mock_aws
import boto3

# Garante que o Python encontre o código do serviço
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/posting-service')))
import app

@pytest.fixture(scope="function")
def aws_credentials():
    """Credenciais mockadas para o Moto evitar tocar na AWS real."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["PostingTable"] = "LedgerPostings-test"

@pytest.fixture(scope="function")
def setup_aws_resources(aws_credentials):
    """Cria a tabela DynamoDB e a fila SQS simuladas antes de cada teste."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        sqs = boto3.client('sqs', region_name='us-east-1')

        # Criar Tabela
        table = dynamodb.create_table(
            TableName="LedgerPostings-test",
            KeySchema=[
                {'AttributeName': 'merchant_id', 'KeyType': 'HASH'},
                {'AttributeName': 'posting_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'merchant_id', 'AttributeType': 'S'},
                {'AttributeName': 'posting_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Criar Fila
        queue = sqs.create_queue(QueueName="consolidation-queue-test")
        os.environ["ConsodidationQueueUrl"] = queue['QueueUrl']
        
        yield {'dynamodb': dynamodb, 'sqs': sqs, 'queue_url': queue['QueueUrl']}

def test_lambda_handler_success(setup_aws_resources):
    """Testa se um lançamento válido é processado, salvo e enviado à fila."""
    payload = {
        "merchant_id": "merchant_123",
        "amount": "150.50",
        "type": "CREDIT",
        "timestamp": "2026-07-19T10:00:00Z"
    }
    
    event = {"body": json.dumps(payload)}
    response = app.lambda_handler(event, None)
    
    assert response["statusCode"] == 201
    body_response = json.loads(response["body"])
    assert "posting_id" in body_response

    # Validar se foi salvo no DynamoDB
    table = setup_aws_resources['dynamodb'].Table("LedgerPostings-test")
    items = table.scan()["Items"]
    assert len(items) == 1
    assert items[0]["merchant_id"] == "merchant_123"
    assert items[0]["type"] == "CREDIT"

    # Validar se a mensagem foi parar no SQS
    sqs_client = setup_aws_resources['sqs']
    queue_msg = sqs_client.receive_message(QueueUrl=setup_aws_resources['queue_url'])
    assert "Messages" in queue_msg
    assert len(queue_msg["Messages"]) == 1

def test_lambda_handler_invalid_data(setup_aws_resources):
    """Testa a rejeição de payloads com dados ou tipos inválidos (Bad Request)."""
    payload = {
        "merchant_id": "merchant_123",
        "amount": "100.00",
        "type": "INVALID_TYPE", # Tipo incorreto (deve ser CREDIT ou DEBIT)
        "timestamp": "2026-07-19T10:00:00Z"
    }
    
    event = {"body": json.dumps(payload)}
    response = app.lambda_handler(event, None)
    
    assert response["statusCode"] == 400
    assert "Dados de entrada inválidos" in json.loads(response["body"])["error"]