#!/bin/bash

sudo yum -y install python-pip
sudo yum -y install java java-devel
sudo yum -y install git
sudo yum -y install awslogs

sudo mv /tmp/app.service /etc/systemd/system/helloworld.service
sudo mv /tmp/awscli.conf /etc/awslogs/awscli.conf
sudo mv /tmp/awslogs.conf /etc/awslogs/awslogs.conf

sudo systemctl enable awslogsd
sudo systemctl enable helloworld.service

git clone https://github.com/scm-spain/devops-test-helloworld-app
cd devops-test-helloworld-app/
./gradlew build

sudo useradd -s /usr/bin/false app
sudo mkdir /var/log/hello-world
sudo chown app: /var/log/hello-world
sudo mv /home/ec2-user/devops-test-helloworld-app/build/libs/helloworld-0.0.1-SNAPSHOT.jar /usr/bin/helloworld.jar
sudo chown app: /usr/bin/helloworld.jar
