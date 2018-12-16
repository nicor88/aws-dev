from pkg_resources import resource_string

import boto3
import yaml

from troposphere import s3
from troposphere import Output, Ref, Template

import cloudformation.troposphere.utils as utils

# load config
cfg = yaml.load(resource_string('config', 'dev_config.yml'))

STACK_NAME = cfg['s3']['stack_name']

template = Template()
description = 'S3 Developments Buckets'
template.add_description(description)
# AWSTemplateFormatVersion
template.add_version('2010-09-09')

s3_dev_bucket = template.add_resource(
    s3.Bucket('S3DevBucket',
              BucketName='nicor-dev',
              DeletionPolicy='Retain'
              )
)

s3_data_bucket = template.add_resource(
    s3.Bucket('S3DataBucket',
              BucketName='nicor-data',
              DeletionPolicy='Retain'
              )
)

# stack outputs
template.add_output([
    Output('S3DevBucket',
           Description='S3 bucket for development',
           Value=Ref(s3_dev_bucket))])

template.add_output([
    Output('S3DataBucket',
           Description='S3 bucket to put data',
           Value=Ref(s3_data_bucket))])


template_json = template.to_json(indent=4)
print(template_json)

stack_args = {
    'StackName': STACK_NAME,
    'TemplateBody': template_json,
    'Tags': [
        {
            'Key': 'Purpose',
            'Value': 'DevS3Buckets'
        }
    ]
}

cfn = boto3.client('cloudformation')
cfn.validate_template(TemplateBody=template_json)
utils.write_template(**stack_args)

# cfn.create_stack(**stack_args)
# cfn.update_stack(**stack_args)
# cfn.delete_stack(StackName=STACK_NAME)
