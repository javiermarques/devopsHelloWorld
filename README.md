This is the infra as code needed to deploy devops helloworld java app  
https://github.com/scm-spain/devops-test-helloworld-app


### Requirements  
* [boto3](https://github.com/boto/boto3#quick-start)
* [troposphere](https://github.com/cloudtools/troposphere#installation)
* [packer](https://www.packer.io/downloads.html)

### Getting Started
Before proceding with this cli application you will need two thing to be set up:
1. You will need an aws profile with enough permissions to create everything needed
2. You will need to create an AMI with the application packed in  


To do this change directroy into packer directory and run
```
packer build packer.json
```

This will create an ami containing the built jar for our app.
This image will be used as an artifact for our application
Copy AMI id to the env.yml variable

### Infra
This application is designed to work with a cloudformation template. This cloudformation template defines the resources that it uses:  
**Bootstrap:**
* VPC
* Security Groups
* RDS

**Complete:**
* *bootstrap*
* ALB
* AutoScalingGroup
* CloudWatch LogGroup

### Usage
This app has 3 main entry points
Remember to fill the env.yml with desired vars

```
python main.py bootstrap <env>
```  
Bootstrap parameter is meant to be run only on creation, when the cloudformation still hasn't been set up. It will take care of the creation of the Bootstrap part of the infra metnioned above. After the template has been submited and succefully created, the script will connect to the database and grant permissions to the app user.  
```
python main.py <env>
```  
This is the main entrypoint meant to be executed everytime an update wants to be applied, it will generate the complete cloudformation stack. When the ami id is changed, a rolling update will be applied
Because the template is generated on top of the bootstrap part, any change to *VPC*, *RDS* or *Security Groups* will also be applied.  
```
python main.py delete <env>
```  
This will destroy the cloudformation template, and the whole infra with it

### Outcome
Updated to the Autoscaling Group follows the next procedure:  
When an update is triggered, one instance at a time is beign deregistered from de LoadBalancer with a connection draining of 120s. Also a new instance from the new AMI is created and added, cloudformation waits for the instance to send a signal with a timeout of 5 minutes, if no signal is recibed, the rollback procedure starts.  
Precooked with packer, Amazon AMIs are beign used follwing an inmutable desing, always replacing the instances to new ones, no changes are never applied directly to a running instance  
The cloudformation creates 2 subnets on different AWS AZs and the Autoscaling Group attempts to distribute instances evenly between the Availability Zones, so with an AutoScaling group of 2 or more instances we are beign fault tolerant to an AWS failure. Also the usage of Autoscaling Group enable us to use scaling policies to easily scale up and down the app based on a metric  
The app can be accessed on port 80 on the LoadBalancer DNS. Direct, public instance access is only enabled for ssh  
Logs are sent to Cloudwatch via awslogs daemon
