"""Migración administrativa explícita. Scan paginado solo aquí, nunca en endpoints.

Añade approvalStatus e índices GSI2 sin cambiar permisos/versión. Puede repetirse;
una condición protege las mutaciones concurrentes. --dry-run no escribe.
"""
import argparse
import json
from botocore.exceptions import ClientError
from lambdas.shared.infrastructure.clients import DynamoDBAdapter
from lambdas.shared.storage.model import deserialize, make_item, serialize


def migrate(adapter, *, dry_run=False):
    counts = {'examinedProfiles':0,'updated':0,'unchanged':0,'concurrent':0,'dryRun':dry_run}
    start = None
    while True:
        args = {'FilterExpression':'#kind IN (:store, :courier)',
                'ExpressionAttributeNames':{'#kind':'entityType'},
                'ExpressionAttributeValues':serialize({':store':'STORE',':courier':'COURIER'}), 'Limit':100}
        if start:
            args['ExclusiveStartKey'] = start
        page = adapter.client.scan(TableName=adapter.settings.table_name, **args)
        for raw in page['Items']:
            old = deserialize(raw); counts['examinedProfiles'] += 1
            data = {k:v for k,v in old.items() if k not in {'PK','SK','GSI1PK','GSI1SK','GSI2PK','GSI2SK','entityType','schemaVersion'}}
            new = make_item(old['entityType'], **data)
            if all(old.get(k) == new[k] for k in ('approvalStatus','GSI2PK','GSI2SK')):
                counts['unchanged'] += 1;continue
            if not dry_run:
                names = {f'#f{i}':name for i,name in enumerate(('approvalStatus','GSI2PK','GSI2SK'))}
                values = {f':f{i}':new[name] for i,name in enumerate(('approvalStatus','GSI2PK','GSI2SK'))}
                names.update({'#version':'version','#enabled':'enabled','#approval':'approvalStatus','#pk':'PK'})
                values.update({':version':old['version'],':enabled':old['enabled']})
                condition='attribute_exists(#pk) AND #version = :version AND #enabled = :enabled'
                if 'approvalStatus' in old:
                    condition+=' AND #approval = :approval';values[':approval']=old['approvalStatus']
                else: condition+=' AND attribute_not_exists(#approval)'
                try:
                    adapter.update_item(Key=serialize({'PK':old['PK'],'SK':old['SK']}),
                        UpdateExpression='SET '+', '.join(f'#f{i} = :f{i}' for i in range(3)),
                        ConditionExpression=condition,ExpressionAttributeNames=names,ExpressionAttributeValues=serialize(values))
                except ClientError as exc:
                    if exc.response['Error']['Code'] != 'ConditionalCheckFailedException': raise
                    counts['concurrent'] += 1;continue
            counts['updated'] += 1
        start = page.get('LastEvaluatedKey')
        if not start: break
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    print(json.dumps(migrate(DynamoDBAdapter(),dry_run=args.dry_run)))


if __name__ == '__main__': main()
