import json
import os
import uuid
import boto3

# Inicialização dos clientes fora do handler para reaproveitamento de container (Melhor prática AWS)
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

# Resgata os nomes gerados dinamicamente pelo CloudFormation
POSTING_TABLE = os.environ.get('PostingTable')
QUEUE_URL = os.environ.get('ConsodidationQueueUrl')

def lambda_handler(event, context):
    try:
        # Tratamento seguro caso o body venha vazio
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event.get('body', {})
        
        merchant_id = body.get('merchant_id')
        amount = body.get('amount')
        entry_type = body.get('type')  # 'CREDIT' ou 'DEBIT'
        timestamp = body.get('timestamp')
        
        # Validação estrita de Regra de Negócio
        if not merchant_id or not amount or entry_type not in ['CREDIT', 'DEBIT'] or not timestamp:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Dados de entrada inválidos, ausentes ou tipo incorreto.'})
            }
        
        posting_id = str(uuid.uuid4())
        
        item = {
            'merchant_id': merchant_id,
            'posting_id': posting_id,
            'amount': str(amount), # Armazenado como String/Decimal para evitar mutabilidade de float
            'type': entry_type,
            'timestamp': timestamp
        }
        
        # 1. Persistência síncrona no Domínio Core (Posting Table)
        table = dynamodb.Table(POSTING_TABLE)
        table.put_item(Item=item)
        
        # 2. Desacoplamento Assíncrono via SQS
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(item)
        )
            
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Lançamento registrado com sucesso e enviado para consolidação.', 
                'posting_id': posting_id
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Erro interno no servidor: {str(e)}'})
        }