import boto3
from pkg_resources import resource_string
import yaml

from troposphere.elasticsearch import Domain, ElasticsearchClusterConfig, EBSOptions
from troposphere.elasticsearch import SnapshotOptions
from awacs.aws import Action, Allow, Policy, Statement, AWSPrincipal
from troposphere import GetAtt, Join, Output, Ref, Template

import cloudformation.troposphere.utils as utils

# load config
cfg = yaml.load(resource_string('config', 'boilerplate_config.yml'))

STACK_NAME = 'Storage-Elastichsearch-Stack'

template = Template()
description = 'Storage Stack containing a Elastic Search'
template.add_description(description)
template.add_version('2010-09-09')

access_policy = Policy(
    Statement=[
        Statement(
            Sid='FullAccess',
            Principal=AWSPrincipal('*'),
            Effect=Allow,
            Action=[Action('es', '*'),
                    ],
            Resource=[
                'arn:aws:es:eu-west-1:749785218022:domain/nicor88-es-dev/*'
            ],
            # Condition=Condition(
            #     IpAddress({
            #         'aws:SourceIp': '...../24'
            #     }),
            # )
        ),
    ]
)

elasticsearch_domain = template.add_resource(
    Domain('ElasticsearchDomain',
           DomainName='nicor88-es-dev',
           AccessPolicies=access_policy,
           ElasticsearchVersion='5.3',
           ElasticsearchClusterConfig=ElasticsearchClusterConfig(
               InstanceCount=1,
               InstanceType='t2.small.elasticsearch',
               ZoneAwarenessEnabled=False,
           ),
           EBSOptions=EBSOptions(EBSEnabled=True,
                                 VolumeSize='10',
                                 VolumeType='gp2',  # General Purpose SSD
                                 Iops=0
                                 ),
           SnapshotOptions=SnapshotOptions(AutomatedSnapshotStartHour=0),
           AdvancedOptions={
               'rest.action.multi.allow_explicit_index': 'true'
           }
           )
)

# Outputs
template.add_output([
    Output('ElasticsearchDomain',
           Description='Elasticsearch Domain',
           Value=Ref(elasticsearch_domain)),

    Output('ElasticsearchDomainEndpoint',
           Description='Elasticsearch Domain Endpoint',
           Value=GetAtt(elasticsearch_domain, 'DomainEndpoint')
           ),

    Output('ElasticsearchDomainURL',
           Description='Elasticsearch URL',
           Value=Join('', ['https://', GetAtt(elasticsearch_domain, 'DomainEndpoint')])
           ),

    Output('ElasticsearchKibanaURL',
           Description='Elasticsearch Kibana URL',
           Value=Join('', ['https://', GetAtt(elasticsearch_domain, 'DomainEndpoint'), '/_plugin/kibana/'])
           ),
])

template_json = template.to_json(indent=4)
print(template_json)

stack_args = {
    'StackName': STACK_NAME,
    'TemplateBody': template_json,
    'Tags': [
        {
            'Key': 'Purpose',
            'Value': 'Elasticsearch'
        }
    ]
}

cfn = boto3.client('cloudformation')
cfn.validate_template(TemplateBody=template_json)
utils.write_template(**stack_args)

# cfn.create_stack(**stack_args)
# cfn.update_stack(**stack_args)
# cfn.delete_stack(StackName=STACK_NAME)
