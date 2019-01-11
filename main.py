import yaml, boto3, sys, psycopg2
from utils import parseStackOutput, initDatabase
from template import buildStack
from botocore.exceptions import ClientError

if len(sys.argv) != 2 and len(sys.argv) != 3:
    print("You need to atleas input 1 argument")
    exit(1)

file = open("env.yml", 'r')
params = yaml.load(file.read())
env = ""
client = boto3.client('cloudformation')

if len(sys.argv) == 3 and sys.argv[1] == "delete":
    env = sys.argv[2]
    params = params[env]
    params["stackName"] = params["stackName"] + "-" + env
    response = client.delete_stack(
        StackName=params["stackName"]
    )
    exit(0)

bootstrap = False
if len(sys.argv) == 3 and sys.argv[1] == "bootstrap":
    bootstrap = True
    env = sys.argv[2]

if len(sys.argv) == 2:
    env = sys.argv[1]

params = params[env]
params["stackName"] = params["stackName"] + "-" +  env
print params

template = buildStack(bootstrap, env)

cloudFormationInput = []
for key, value in template.parameters.items():
    if key in params:
        cloudFormationInput.append({
                    'ParameterKey': key,
                    'ParameterValue': params[key],
                })
try:
    response = client.describe_stacks(
        StackName=params["stackName"]
    )
except ClientError:
    response = client.create_stack(
        StackName=params["stackName"],
        TemplateBody=template.to_json(),
        Parameters=cloudFormationInput,
        TimeoutInMinutes=30,
        Capabilities=[
            'CAPABILITY_IAM',
        ],
    )
    print "Started Creation. This will take a while"
    waiter = client.get_waiter('stack_create_complete')
    waiter.wait(
        StackName=params["stackName"]
    )
    print "Stack Creation succefully completed. Creating DB app user"
    response = client.describe_stacks(
        StackName=params["stackName"]
    )
    outputs = parseStackOutput(response)

    initDatabase(outputs['RDSConnectionString'], params['DBUser'], params['DBPassword'], params['AppPassword'], env)

    print "Stack and DB created"
else:
    try:
        template = buildStack(bootstrap, env)
        response = client.update_stack(
            StackName=params["stackName"],
            TemplateBody=template.to_json(),
            Parameters=cloudFormationInput,
            Capabilities=[
                'CAPABILITY_IAM'
            ],
        )
        print "Started Update. This can take some time"
        waiter = client.get_waiter('stack_update_complete')
        waiter.wait(
            StackName=params["stackName"]
        )
        print "Stack Update succefully completed."
        response = client.describe_stacks(
            StackName=params["stackName"]
        )
        outputs = parseStackOutput(response)
        print outputs
    except ClientError as ce:
        if ce.response['Error']['Message'] == "No updates are to be performed.":
            print(ce.response['Error']['Message'])
            response = client.describe_stacks(
                StackName=params["stackName"]
            )
            outputs = parseStackOutput(response)
            print outputs
            exit(0)
        raise
