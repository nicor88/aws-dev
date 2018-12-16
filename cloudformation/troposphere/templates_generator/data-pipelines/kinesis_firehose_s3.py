from pkg_resources import resource_string

from awacs.aws import Statement, Allow, Action
import boto3
import yaml
from troposphere import awslambda, iam, kinesis, firehose
from troposphere import Template, Tags, Ref, GetAtt

# load config
cfg = yaml.load(resource_string('config', 'kinesis_firehose_s3.yml'))

STACK_NAME = cfg['stack_name']

template = Template()
description = 'Stack containing kinesis and firehose writing to S3'
template.add_description(description)
# AWSTemplateFormatVersion
template.add_version('2010-09-09')

kinesis_stream = template.add_resource(
    kinesis.Stream('DevStream',
                   Name=cfg['kinesis_stream_name'],
                   ShardCount=cfg['kinesis_shard_count'],
                   Tags=Tags(
                       StackName=Ref('AWS::StackName'),
                       Name='DevStream'
                   )
                   )
)

firehose_delivery_role = template.add_resource(
    iam.Role(
        'FirehoseRole',
        AssumeRolePolicyDocument={
            'Statement': [{
                'Effect': 'Allow',
                'Principal': {
                    'Service': [
                        'firehose.amazonaws.com'
                    ]
                },
                'Action': ['sts:AssumeRole']
            }]
        },
        Policies=[
            iam.Policy(
                PolicyName='AccessToS3andLogs',
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        Statement(
                            Sid='S3Access',
                            Effect=Allow,
                            Action=[
                                Action('s3', '*')
                            ],
                            Resource=[
                                "arn:aws:s3:::{}".format(cfg['s3_destination_bucket']),
                                "arn:aws:s3:::{}/*".format(cfg['s3_destination_bucket'])
                            ]
                        ),
                        Statement(
                            Sid='Logs',
                            Effect=Allow,
                            Action=[
                                Action('logs', '*'),
                            ],
                            Resource=['*']
                        )
                    ]
                }
            )
        ]
    ))

kinesis_delivery_stream = template.add_resource(
    firehose.DeliveryStream('DeliveryStream',
                            DeliveryStreamName=cfg['kinesis_delivery_stream_name'],
                            S3DestinationConfiguration=
                            firehose.S3DestinationConfiguration('DestinationBucketConfig',
                                                                BucketARN="arn:aws:s3:::{}".format(
                                                                    cfg['s3_destination_bucket']),
                                                                CompressionFormat='UNCOMPRESSED',
                                                                Prefix='delivery_stream/',
                                                                RoleARN=GetAtt(
                                                                    firehose_delivery_role, 'Arn'),
                                                                BufferingHints=
                                                                firehose.BufferingHints(
                                                                    'BufferingSetup',
                                                                    IntervalInSeconds=cfg[
                                                                        'firehose_interval_secs'],
                                                                    SizeInMBs=cfg[
                                                                        'firehose_buffer_mb'])
                                                                ),

                            )
)

# lambda section
lambda_execution_role = template.add_resource(
    iam.Role(
        'ExecutionRole',
        Path='/',
        Policies=[
            iam.Policy(
                PolicyName='KinesisToFirehosePolicy',
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        Statement(
                            Sid='Logs',
                            Effect=Allow,
                            Action=[
                                Action('logs', 'CreateLogGroup'),
                                Action('logs', 'CreateLogStream'),
                                Action('logs', 'PutLogEvents')
                            ],
                            Resource=['arn:aws:logs:*:*:*']
                        ),
                        Statement(
                            Sid='KinesisStream',
                            Effect=Allow,
                            Action=[
                                Action('kinesis', '*'),
                            ],
                            Resource=[GetAtt(kinesis_stream, 'Arn')]
                        ),
                        Statement(
                            Sid='DeliveryStream',
                            Effect=Allow,
                            Action=[
                                Action('firehose', '*'),
                            ],
                            Resource=['arn:aws:firehose:*:*:deliverystream/{}'.format(
                                cfg['kinesis_delivery_stream_name'])]
                        )
                    ]
                }
            )
        ],
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {"Action": ["sts:AssumeRole"],
                 "Effect": "Allow",
                 "Principal": {"Service": ["lambda.amazonaws.com"]}
                 }
            ]},
    ))

lambda_stream_to_firehose = template.add_resource(
    awslambda.Function(
        'KinesisStreamToFirehose',
        FunctionName=cfg['lambda_function_name'],
        Description='Lambda function to read kinesis stream and put to firehose',
        Handler='lambda_function.lambda_handler',
        Role=GetAtt('ExecutionRole', 'Arn'),
        Code=awslambda.Code(
            S3Bucket=cfg['s3_deployment_bucket'],
            S3Key=cfg['s3_key_lambda'],
        ),
        Runtime='python3.6',
        Timeout=cfg['lambda_timeout'],
        MemorySize=cfg['lambda_memory_size'],
        Environment=awslambda.Environment('LambdaVars',
                                          Variables=
                                          {'DELIVERY_STREAM': cfg['kinesis_delivery_stream_name'],
                                           'ADD_NEWLINE': 'True'})
    )
)

add_kinesis_trigger_for_lambda = template.add_resource(
    awslambda.EventSourceMapping('KinesisLambdaTrigger',
                                 BatchSize=cfg['lambda_batch_size'],
                                 Enabled=cfg['lambda_enabled'],
                                 FunctionName=Ref(lambda_stream_to_firehose),
                                 StartingPosition=cfg['lambda_starting_position'],
                                 EventSourceArn=GetAtt(kinesis_stream, 'Arn')
                                 )
)

template_json = template.to_json(indent=4)
print(template_json)

stack_args = {
    'StackName': STACK_NAME,
    'TemplateBody': template_json,
    'Capabilities': [
        'CAPABILITY_IAM',
    ],
    'Tags': [
        {
            'Key': 'Purpose',
            'Value': 'StreamExamples'
        }
    ]
}

cfn = boto3.client('cloudformation')
cfn.validate_template(TemplateBody=template_json)
# utils.write_template(**stack_args)

# cfn.create_stack(**stack_args)
# cfn.update_stack(**stack_args)
# cfn.delete_stack(StackName=STACK_NAME)
