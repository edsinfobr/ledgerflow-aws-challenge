import json
import os
import logging
from decimal import Decimal
import boto3

# Configuração de logging para observabilidade
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
CONSOLIDATED_TABLE = os.environ.get('ConsolidatedTable', 'LedgerConsolidated-prod')

def lambda_handler(event, context):
    """
    Consome mensagens em lote (Batch) do Amazon SQS.
    Cada mensagem representa um lançamento (CREDIT ou DEBIT).
    Atualiza o saldo consolidado do dia usando expressões atômicas do DynamoDB.
    """
    logger.info(f"Processando lote de {len(event['Records'])} mensagens do SQS.")
    table = dynamodb.Table(CONSOLIDATED_TABLE)
    
    # O SQS pode enviar até 10 mensagens por lote (conforme configurado no CloudFormation)
    for record in event['Records']:
        try:
            # 1. Parse do corpo da mensagem vinda do SQS
            posting = json.loads(record['body'])
            
            merchant_id = posting.get('merchant_id')
            amount_raw = posting.get('amount')
            entry_type = posting.get('type')
            timestamp = posting.get('timestamp') # Ex: "2026-07-19T03:44:00Z"
            
            if not merchant_id or not amount_raw or not entry_type or not timestamp:
                logger.error(f"Mensagem malformada descartada. ID do registro SQS: {record['messageId']}")
                continue
                
            # Extrai apenas a data (YYYY-MM-DD) para consolidação diária
            date_key = timestamp.split('T')[0]
            amount = Decimal(str(amount_raw))
            
            # Se for débito, o valor entra como negativo na agregação
            value_to_add = amount if entry_type == 'CREDIT' else -amount
            
            # 2. Atualização Atômica no DynamoDB (Evita concorrência de escrita / Race Conditions)
            # Se o registro não existir, o 'if_not_exists' inicializa o saldo com 0 e soma o valor.
            table.update_item(
                Key={
                    'merchant_id': merchant_id,
                    'date': date_key
                },
                UpdateExpression="SET daily_balance = if_not_exists(daily_balance, :zero) + :val, last_updated = :time",
                ExpressionAttributeValues={
                    ':val': value_to_add,
                    ':zero': Decimal('0'),
                    ':time': timestamp
                }
            )
            
            logger.info(f"Lançamento {posting.get('posting_id')} processado com sucesso para o comerciante {merchant_id}.")
            
        except Exception as e:
            logger.error(f"Erro ao processar o registro {record['messageId']}: {str(e)}")
            # Relança a exceção para que ESTA mensagem específica retorne para a fila (ou vá para a DLQ após 3 tentativas)
            raise e

    return {
        'statusCode': 200,
        'body': json.dumps('Lote de consolidação diária processado com sucesso.')
    }