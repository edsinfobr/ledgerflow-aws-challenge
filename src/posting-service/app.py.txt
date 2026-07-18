import json
import os
import uuid
import boto3

dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

POSTING_TABLE = os.environ.get('PostingTable', 'LedgerPostings')
QUEUE_URL = os.environ.get('ConsodidationQueueUrl')

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Validação simples de contrato
        merchant_id = body.get('merchant_id')
        amount = body.get('amount')
        entry_type = body.get('type') # 'CREDIT' ou 'DEBIT'
        
        if not merchant_id or not amount or entry_type not in ['CREDIT', 'DEBIT']:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Dados de entrada inválidos ou incompletos.'})
            }
        
        posting_id = str(uuid.uuid4())
        
        item = {
            'merchant_id': merchant_id,
            'posting_id': posting_id,
            'amount': str(amount),
            'type': entry_type,
            'timestamp': body.get('timestamp')
        }
        
        # 1. Salva de forma síncrona no domínio de lançamentos
        table = dynamodb.Table(POSTING_TABLE)
        table.put_item(Item=item)
        
        # 2. Despacha evento assíncrono para a fila SQS (Desacoplamento Garantido)
        if QUEUE_URL:
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps(item)
            )
            
        return {
            'statusCode': 201,
            'body': json.dumps({'message': 'Lançamento registrado com sucesso!', 'posting_id': posting_id})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }