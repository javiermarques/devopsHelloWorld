from troposphere import Base64, Join, GetAtt, Join, Output, Parameter, Ref, Template, Tags, Name

from troposphere import cloudformation, autoscaling
from troposphere.autoscaling import AutoScalingGroup, Tag, LaunchConfiguration, ScalingPolicy, Metadata
from troposphere.policies import (
    AutoScalingReplacingUpdate, AutoScalingRollingUpdate, UpdatePolicy, CreationPolicy, ResourceSignal
)
import troposphere.ec2 as ec2
from troposphere.ec2 import PortRange, NetworkAcl, Route, \
    VPCGatewayAttachment, SubnetRouteTableAssociation, Subnet, RouteTable, \
    VPC, NetworkInterfaceProperty, NetworkAclEntry, \
    SubnetNetworkAclAssociation, EIP, Instance, InternetGateway, \
    SecurityGroupRule, SecurityGroup
from troposphere.cloudwatch import Alarm, MetricDimension

from troposphere.rds import DBInstance, DBSubnetGroup

from troposphere.iam import Role, InstanceProfile, PolicyType
import troposphere.elasticloadbalancingv2 as elb
import json

def buildStack(bootstrap, env):
    t = Template()

    t.add_description("""\
    Configures autoscaling group for hello world app""")

    vpcCidr = t.add_parameter(Parameter(
        "VPCCidr",
        Type="String",
        Description="VPC cidr (x.x.x.x/xx)",
    ))

    publicSubnet1 = t.add_parameter(Parameter(
        "PublicSubnet1",
        Type="String",
        Description="A public VPC subnet ID for the api app load balancer.",
    ))

    publicSubnet2 = t.add_parameter(Parameter(
        "PublicSubnet2",
        Type="String",
        Description="A public VPC subnet ID for the api load balancer.",
    ))

    dbName = t.add_parameter(Parameter(
        "DBName",
        Default="HelloWorldApp",
        Description="The database name",
        Type="String",
        MinLength="1",
        MaxLength="64",
        AllowedPattern="[a-zA-Z][a-zA-Z0-9]*",
        ConstraintDescription=("must begin with a letter and contain only"
                            " alphanumeric characters.")
    ))

    dbUser = t.add_parameter(Parameter(
        "DBUser",
        NoEcho=True,
        Description="The database admin account username",
        Type="String",
        MinLength="1",
        MaxLength="16",
        AllowedPattern="[a-zA-Z][a-zA-Z0-9]*",
        ConstraintDescription=("must begin with a letter and contain only"
                            " alphanumeric characters.")
    ))

    dbPassword = t.add_parameter(Parameter(
        "DBPassword",
        NoEcho=True,
        Description="The database admin account password",
        Type="String",
        MinLength="8",
        MaxLength="41",
        AllowedPattern="[a-zA-Z0-9]*",
        ConstraintDescription="must contain only alphanumeric characters."
    ))

    dbType = t.add_parameter(Parameter(
        "DBType",
        Default="db.t2.medium",
        Description="Database instance class",
        Type="String",
        AllowedValues=[
        "db.m5.large", "db.m5.xlarge", "db.m5.2xlarge", "db.m5.4xlarge",
        "db.m5.12xlarge", "db.m5.24xlarge", "db.m4.large", "db.m4.xlarge",
        "db.m4.2xlarge", "db.m4.4xlarge", "db.m4.10xlarge", "db.m4.16xlarge",
        "db.r4.large", "db.r4.xlarge", "db.r4.2xlarge", "db.r4.4xlarge",
        "db.r4.8xlarge", "db.r4.16xlarge", "db.x1e.xlarge", "db.x1e.2xlarge",
        "db.x1e.4xlarge", "db.x1e.8xlarge", "db.x1e.16xlarge", "db.x1e.32xlarge",
        "db.x1.16xlarge", "db.x1.32xlarge", "db.r3.large", "db.r3.xlarge",
        "db.r3.2xlarge", "db.r3.4xlarge", "db.r3.8xlarge", "db.t2.micro",
        "db.t2.small", "db.t2.medium", "db.t2.large", "db.t2.xlarge",
        "db.t2.2xlarge"
        ],
        ConstraintDescription="must select a valid database instance type.",
    ))

    dbAllocatedStorage = t.add_parameter(Parameter(
        "DBAllocatedStorage",
        Default="5",
        Description="The size of the database (Gb)",
        Type="Number",
        MinValue="5",
        MaxValue="1024",
        ConstraintDescription="must be between 5 and 1024Gb.",
    ))

    whitelistedCIDR = t.add_parameter(Parameter(
        "WhitelistedCIDR",
        Description="CIDR whitelisted to be open on public instances",
        Type="String",
    ))

    #### NETWORK SECTION ####
    vpc = t.add_resource(VPC(
        "VPC",
        CidrBlock=Ref(vpcCidr),
        EnableDnsHostnames=True
    ))

    subnet1 = t.add_resource(Subnet(
        "Subnet1",
        CidrBlock=Ref(publicSubnet1),
        AvailabilityZone="eu-west-1a",
        VpcId=Ref(vpc)
    ))
    subnet2 = t.add_resource(Subnet(
        "Subnet2",
        CidrBlock=Ref(publicSubnet2),
        AvailabilityZone="eu-west-1b",
        VpcId=Ref(vpc)
    ))

    internetGateway = t.add_resource(InternetGateway(
        'InternetGateway'
    ))

    gatewayAttachment = t.add_resource(VPCGatewayAttachment(
        'AttachGateway',
        VpcId=Ref(vpc),
        InternetGatewayId=Ref(internetGateway)
    ))

    routeTable = t.add_resource(RouteTable(
        'RouteTable',
        VpcId=Ref(vpc)
    ))

    route = t.add_resource(Route(
        'Route',
        DependsOn='AttachGateway',
        GatewayId=Ref('InternetGateway'),
        DestinationCidrBlock='0.0.0.0/0',
        RouteTableId=Ref(routeTable),
    ))

    subnetRouteTableAssociation = t.add_resource(SubnetRouteTableAssociation(
        'SubnetRouteTableAssociation',
        SubnetId=Ref(subnet1),
        RouteTableId=Ref(routeTable),
    ))

    subnetRouteTableAssociation2 = t.add_resource(SubnetRouteTableAssociation(
        'SubnetRouteTableAssociation2',
        SubnetId=Ref(subnet2),
        RouteTableId=Ref(routeTable),
    ))

    #### SECURITY GROUP ####
    loadBalancerSg = t.add_resource(ec2.SecurityGroup(
        "LoadBalancerSecurityGroup",
        VpcId=Ref(vpc),
        GroupDescription="Enable SSH access via port 22",
        SecurityGroupIngress=[
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="80",
                ToPort="80",
                CidrIp="0.0.0.0/0",
            ),
        ],
    ))

    instanceSg = t.add_resource(ec2.SecurityGroup(
        "InstanceSecurityGroup",
        VpcId=Ref(vpc),
        GroupDescription="Enable SSH access via port 22",
        SecurityGroupIngress=[
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="22",
                ToPort="22",
                CidrIp=Ref(whitelistedCIDR),
            ),
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="8000",
                ToPort="8000",
                SourceSecurityGroupId=Ref(loadBalancerSg),
            ),
        ],
    ))

    rdsSg = t.add_resource(SecurityGroup(
        "RDSSecurityGroup",
        GroupDescription="Security group for RDS DB Instance.",
        VpcId=Ref(vpc),
        SecurityGroupIngress=[
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="5432",
                ToPort="5432",
                SourceSecurityGroupId=Ref(instanceSg),
            ),
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="5432",
                ToPort="5432",
                CidrIp=Ref(whitelistedCIDR),
            ),
        ]
    ))

    #### DATABASE SECTION ####
    subnetGroup = t.add_resource(DBSubnetGroup(
        "SubnetGroup",
        DBSubnetGroupDescription="Subnets available for the RDS DB Instance",
        SubnetIds=[Ref(subnet1), Ref(subnet2)],
    ))

    db = t.add_resource(DBInstance(
        "RDSHelloWorldApp",
        DBName=Join("", [Ref(dbName), env]),
        DBInstanceIdentifier=Join("", [Ref(dbName), env]),
        EnableIAMDatabaseAuthentication=True,
        PubliclyAccessible=True,
        AllocatedStorage=Ref(dbAllocatedStorage),
        DBInstanceClass=Ref(dbType),
        Engine="postgres",
        EngineVersion="10.4",
        MasterUsername=Ref(dbUser),
        MasterUserPassword=Ref(dbPassword),
        DBSubnetGroupName=Ref(subnetGroup),
        VPCSecurityGroups=[Ref(rdsSg)],
    ))

    t.add_output(Output(
        "RDSConnectionString",
        Description="Connection string for database",
        Value=GetAtt("RDSHelloWorldApp", "Endpoint.Address")
    ))

    if(bootstrap):
        return t

    #### INSTANCE SECTION ####
    keyName = t.add_parameter(Parameter(
        "KeyName",
        Type="String",
        Description="Name of an existing EC2 KeyPair to enable SSH access",
        MinLength="1",
        AllowedPattern="[\x20-\x7E]*",
        MaxLength="255",
        ConstraintDescription="can contain only ASCII characters.",
    ))

    scaleCapacityMin = t.add_parameter(Parameter(
        "ScaleCapacityMin",
        Default="1",
        Type="String",
        Description="Number of api servers to run",
    ))

    scaleCapacityMax = t.add_parameter(Parameter(
        "ScaleCapacityMax",
        Default="1",
        Type="String",
        Description="Number of api servers to run",
    ))

    scaleCapacityDesired = t.add_parameter(Parameter(
        "ScaleCapacityDesired",
        Default="1",
        Type="String",
        Description="Number of api servers to run",
    ))

    amiId = t.add_parameter(Parameter(
        "AmiId",
        Type="String",
        Default="ami-09693313102a30b2c",
        Description="The AMI id for the api instances",
    ))

    instanceType = t.add_parameter(Parameter(
        "InstanceType",
        Description="WebServer EC2 instance type",
        Type="String",
        Default="t2.medium",
        AllowedValues=[
            "t2.nano", "t2.micro", "t2.small", "t2.medium", "t2.large",
            "m3.medium", "m3.large", "m3.xlarge", "m3.2xlarge",
            "m4.large", "m4.xlarge", "m4.2xlarge", "m4.4xlarge", "m4.10xlarge",
            "c4.large", "c4.xlarge", "c4.2xlarge", "c4.4xlarge", "c4.8xlarge"
        ],
        ConstraintDescription="must be a valid EC2 instance type."
    ))


    assumeRole = t.add_resource(Role(
        "AssumeRole",
        AssumeRolePolicyDocument= json.loads("""\
{
  "Version": "2012-10-17",
  "Statement": [
    {
    "Action": "sts:AssumeRole",
    "Principal": {
      "Service": "ec2.amazonaws.com"
    },
    "Effect": "Allow",
    "Sid": ""
    }
  ]
}\
""")
    ))

    instanceProfile = t.add_resource(InstanceProfile(
        "InstanceProfile",
        Roles=[Ref(assumeRole)]
    ))

    rolePolicyType = t.add_resource(PolicyType(
        "RolePolicyType",
        Roles=[Ref(assumeRole)],
        PolicyName=Join("", ["CloudWatchHelloWorld", "-", env]),
        PolicyDocument= json.loads("""\
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:DescribeLogStreams",
        "logs:PutLogEvents"
      ],
    "Effect": "Allow",
    "Resource": [
        "arn:aws:logs:*:*:*"
      ]
    }
  ]
}\
""")
    ))

    appPassword = t.add_parameter(Parameter(
        "AppPassword",
        NoEcho=True,
        Description="The Password for the app user",
        Type="String",
        MinLength="8",
        MaxLength="41",
        AllowedPattern="[a-zA-Z0-9]*",
        ConstraintDescription="must contain only alphanumeric characters."
    ))

    launchConfig = t.add_resource(LaunchConfiguration(
        "LaunchConfiguration",
        Metadata=autoscaling.Metadata(
            cloudformation.Init({
                "config": cloudformation.InitConfig(
                    files=cloudformation.InitFiles({
                        "/home/app/environment": cloudformation.InitFile(
                            content=Join("", [
                                "SPRING_DATASOURCE_URL=",
                                "jdbc:postgresql://",
                                GetAtt("RDSHelloWorldApp", "Endpoint.Address"),
                                ":5432/HelloWorldApp" + env + "?currentSchema=hello_world",
                                "\n",
                                "SPRING_DATASOURCE_USERNAME=app",
                                "\n",
                                "SPRING_DATASOURCE_PASSWORD=",
                                Ref(appPassword),
                                "\n",
                                "SPRING_PROFILES_ACTIVE=",
                                env,
                                "\n"
                            ]),
                            mode="000600",
                            owner="app",
                            group="app"
                        )
                    }),
                )
            }),
        ),
        UserData=Base64(Join('', [
            "#!/bin/bash\n",
            "/opt/aws/bin/cfn-init",
            "    --resource LaunchConfiguration",
            "    --stack ", Ref("AWS::StackName"),
            "    --region ", Ref("AWS::Region"), "\n",
            "/opt/aws/bin/cfn-signal -e $? ",
            "         --stack ", { "Ref" : "AWS::StackName" },
            "         --resource AutoscalingGroup ",
            "         --region ", { "Ref" : "AWS::Region" }, "\n"
        ])),
        ImageId=Ref(amiId),
        KeyName=Ref(keyName),
        IamInstanceProfile=Ref(instanceProfile),
        BlockDeviceMappings=[
            ec2.BlockDeviceMapping(
                DeviceName="/dev/xvda",
                Ebs=ec2.EBSBlockDevice(
                    VolumeSize="8"
                )
            ),
        ],
        SecurityGroups=[Ref(instanceSg)],
        InstanceType=Ref(instanceType),
        AssociatePublicIpAddress='True',
    ))

    applicationElasticLB = t.add_resource(elb.LoadBalancer(
        "ApplicationElasticLB",
        Name="ApplicationElasticLB-" + env,
        Scheme="internet-facing",
        Type="application",
        SecurityGroups=[Ref(loadBalancerSg)],
        Subnets=[Ref(subnet1), Ref(subnet2)]
    ))

    targetGroup = t.add_resource(elb.TargetGroup(
        "TargetGroupHelloWorld",
        HealthCheckProtocol="HTTP",
        HealthCheckTimeoutSeconds="15",
        HealthyThresholdCount="5",
        Matcher=elb.Matcher(
            HttpCode="200,404"),
        Port="8000",
        Protocol="HTTP",
        UnhealthyThresholdCount="3",
        TargetGroupAttributes=[elb.TargetGroupAttribute(
            Key="deregistration_delay.timeout_seconds",
            Value="120",
        )],
        VpcId=Ref(vpc)
    ))

    listener = t.add_resource(elb.Listener(
        "Listener",
        Port="80",
        Protocol="HTTP",
        LoadBalancerArn=Ref(applicationElasticLB),
        DefaultActions=[elb.Action(
            Type="forward",
            TargetGroupArn=Ref(targetGroup)
        )]
    ))

    t.add_output(Output(
        "URL",
        Description="URL of the sample website",
        Value=Join("", ["http://", GetAtt(applicationElasticLB, "DNSName")])
    ))

    autoScalingGroup = t.add_resource(AutoScalingGroup(
        "AutoscalingGroup",
        DesiredCapacity=Ref(scaleCapacityDesired),
        LaunchConfigurationName=Ref(launchConfig),
        MinSize=Ref(scaleCapacityMin),
        MaxSize=Ref(scaleCapacityMax),
        VPCZoneIdentifier=[Ref(subnet1), Ref(subnet2)],
        TargetGroupARNs=[Ref(targetGroup)],
        HealthCheckType="ELB",
        HealthCheckGracePeriod=360,
        UpdatePolicy=UpdatePolicy(
            AutoScalingReplacingUpdate=AutoScalingReplacingUpdate(
                WillReplace=True,
            ),
            AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                PauseTime='PT5M',
                MinInstancesInService="1",
                MaxBatchSize='1',
                WaitOnResourceSignals=True
            )
        ),
        CreationPolicy=CreationPolicy(
            ResourceSignal=ResourceSignal(
                Timeout="PT15M",
                Count=Ref(scaleCapacityDesired)
            )
        )
    ))


    # print(t.to_json())
    return t
