import boto3

from troposphere import ec2
from troposphere import Base64, Join, Output, Parameter, Ref, Tags, Template
from troposphere.cloudformation import Init, InitFile, InitFiles, InitConfig, InitService, \
    InitServices
from troposphere.autoscaling import Metadata

import cloudformation.troposphere.utils as utils

STACK_NAME = 'bastion'

template = Template()
description = 'Stack containing a bastion host and all the needed resources'
template.add_description(description)
template.add_version('2010-09-09')

vpc_id = template.add_parameter(
    Parameter(
        'VpcId',
        Type='String',
        Default='vpc-8b708fec',
        Description='VPC ID',
    )
)

public_route_table = template.add_parameter(
    Parameter(
        'PublicRouteTable',
        Type='String',
        Default='rtb-1197ed76',
        Description='Routing Table used for Public subnets',
    )
)

ami_id = template.add_parameter(
    Parameter(
        'AMI',
        Type='String',
        Default='ami-d7b9a2b1',  # TODO check the latest AMI Amazon Linux
        Description='AMI ',
    )
)

instance_type = template.add_parameter(
    Parameter(
        'InstanceType',
        Type='String',
        Default='t2.micro',
        Description='AMI ',
    )
)

# Define Instance Metadata
instance_metadata = Metadata(
    Init({'config': InitConfig(
        commands={
            'update_yum_packages': {
                'command': 'yum update -y'
            },
            'download_miniconda': {
                'command': 'su - ec2-user -c "wget http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /home/ec2-user/miniconda.sh"',
            },
            'install_miniconda': {
                'command': 'su - ec2-user -c "bash /home/ec2-user/miniconda.sh -b -p /home/ec2-user/miniconda"',
            },
            'remove_installer': {
                'command': 'rm -rf /home/ec2-user/miniconda.sh',
            }
        },
        files=InitFiles({
            # setup .bashrc
            '/home/ec2-user/.ssh/authorized_keys': InitFile(
                content=Join('', [
                    'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCjKxODWLSrmQAemYnpvYchmy7bwWvIKNWpHtfRiD7UKqnUV0euoFWIr9j+OwiNyMp/iopZQh7A8c+B4TYI8pd///J7ZWPSipndJkWc4HrnU37X66mKInGYIaPZAfek69eeUkl5cekqkEd6l6WsBUlrjPvMYtyGdDtd42M+aNQoy1TWq2C/6x0gBQaY/CUvHFBrMHr5ObhZvN7ou6PSyBCGgQxFf5jmnwSzeBRc/iWxMBltM/SQSTAgyKWdolcgBNTOTre5z8R8FCv/CIsfLoqUFuWthrT3YfpG1iOWlL3GBm8XxXlgrmvMUhV1qvcO/1no6ZeSp8VQMiTYkvAOQ7Hd\n'
                ]),
                owner='ec2-user',
                mode='000400',
                group='ec2-user'),

            # setup .bashrc
            '/home/ec2-user/.bashrc': InitFile(
                content=Join('', [
                    'export PATH="/home/ec2-user/miniconda/bin:$PATH"\n'
                ]),
                owner='ec2-user',
                mode='000400',
                group='ec2-user'),
            # configure cfn-hup
            '/etc/cfn/cfn-hup.conf': InitFile(
                content=Join('',
                             ['[main]\n',
                              'stack=', Ref('AWS::StackId'),
                              '\n',
                              'region=', Ref('AWS::Region'),
                              '\n',
                              'interval=2',
                              '\n',
                              ]),
                mode='000400',
                owner='root',
                group='root'),
            # setup cfn-auto-reloader
            '/etc/cfn/hooks.d/cfn-auto-reloader.conf': InitFile(
                content=Join('',
                             ['[cfn-auto-reloader-hook]\n',
                              'triggers=post.update\n',
                              'path=Resources.Bastion.Metadata.AWS::CloudFormation::Init\n',
                              'action=/opt/aws/bin/cfn-init -v',
                              ' --stack ', Ref('AWS::StackId'),
                              ' --resource Bastion',
                              ' --region ', Ref('AWS::Region'),
                              '\n'
                              'runas=root\n',
                              ]
                             )
            )
        }),
        services={
            'sysvinit': InitServices({
                'cfn-hup': InitService(
                    enabled=True,
                    ensureRunning=True,
                    files=[
                        '/etc/cfn/cfn-hup.conf',
                        '/etc/cfn/hooks.d/cfn-auto-reloader.conf'
                    ])
            })}
    )
    })
)

bastion_subnet = template.add_resource(
    ec2.Subnet(
        'BastionHostSubnet',
        AvailabilityZone='eu-west-1a',
        CidrBlock='172.31.10.0/24',
        VpcId=Ref(vpc_id),
        Tags=Tags(
            StackName=Ref('AWS::StackName'),
            AZ='eu-west-1b',
            Name='bastion-public-eu-west-1a'
        )
    )
)

bastion_subnet_route_table_association = template.add_resource(
    ec2.SubnetRouteTableAssociation('BastionHostSubnetAssociation',
                                    RouteTableId=Ref(public_route_table),
                                    SubnetId=Ref(bastion_subnet)
                                    )
)

security_group = template.add_resource(
    ec2.SecurityGroup(
        'BastionSg',
        VpcId=Ref(vpc_id),
        GroupDescription='Allow SSH traffic',
        SecurityGroupIngress=[
            ec2.SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='22',
                ToPort='22',
                CidrIp='0.0.0.0/0'
            )
        ],
        Tags=Tags(
            StackName=Ref('AWS::StackName'),
            Name='bastion-sg'
        )
    )
)


# ec2 instance
ec2_instance = template.add_resource(ec2.Instance(
    'Bastion',
    InstanceType='t2.micro',
    ImageId=Ref(ami_id),
    NetworkInterfaces=[ec2.NetworkInterfaceProperty(
        AssociatePublicIpAddress=True,
        DeleteOnTermination=True,
        DeviceIndex=0,
        SubnetId=Ref(bastion_subnet),
        GroupSet=[Ref(security_group)],
        Description='Bastion Host Interface',
    )],
    InstanceInitiatedShutdownBehavior='stop',
    Monitoring=True,
    Metadata=instance_metadata,
    BlockDeviceMappings=[{
        'DeviceName': '/dev/xvda',  # "/dev/sda1" if the ami is ubuntu
        'Ebs': {
            'VolumeType': 'gp2',
            'DeleteOnTermination': 'true',
            'VolumeSize': '25'
        }
    }],
    UserData=Base64(
        Join(
            '',
            ['#!/bin/bash -xe\n',

             # cfn-init: install what is specified in the metadata section
             '/opt/aws/bin/cfn-init -v ',
             ' --stack ', Ref('AWS::StackName'),
             ' --resource Bastion',
             ' --region ', Ref('AWS::Region'), '\n',

             # cfn-hup
             # Start up the cfn-hup daemon to listen for changes to the server metadata
             'yum install -y aws-cfn-bootstrap\n',
             '/opt/aws/bin/cfn-hup || error_exit "Failed to start cfn-hup"',
             '\n',

             # cfn-signal
             '/opt/aws/bin/cfn-signal -e $? ',
             ' --stack ', Ref('AWS::StackName'),
             ' --resource Bastion',
             ' --region ', Ref('AWS::Region'),
             '\n'
             ])
    ),
    Tags=Tags(
        StackName=Ref('AWS::StackName'),
        Name='dev-server',
    )
)
)

# outputs
template.add_output([
    Output('Bastion',
           Description='EC2 Instance',
           Value=Ref(ec2_instance))
])

template_json = template.to_json(indent=4)
print(template_json)

stack_args = {
    'StackName': STACK_NAME,
    'TemplateBody': template_json,
    'Tags': [
        {
            'Key': 'Purpose',
            'Value': 'Bastion'
        }
    ]
}

cfn = boto3.client('cloudformation')
cfn.validate_template(TemplateBody=template_json)
utils.write_template(**stack_args)

# cfn.create_stack(**stack_args)
# cfn.update_stack(**stack_args)
# cfn.delete_stack(StackName=STACK_NAME)
