import boto3
import time
import datetime

#variables
instance_id   = 'instanceID'
region_source = 'sa-east-1'
region_dest   = 'us-east-1'
account_dev   = 'ACCOUNT'
account_prd   = 'ACCOUNT'
image_name    = 'VDAlfrescoCanais'
Private_subnet_1A = 'SUBNET'
access_key    = 'accesskey'
secret_key    = 'secretkey'


client = boto3.client('ec2', region_name=region_source,
                          aws_access_key_id=access_key,
                          aws_secret_access_key=secret_key,
                          verify=False)
clientDest   = boto3.client('ec2', region_name=region_dest,
                          aws_access_key_id=access_key,
                          aws_secret_access_key=secret_key,
                          verify=False)
client_dev = boto3.client('ec2', region_name=region_dest)

#Get instance type and tags
instance = client.describe_instances(
        Filters=[
        {
            'Name': 'instance-id',
            'Values': [
                instance_id,
            ]
        },
    ])

for reservations in instance['Reservations']:
    for inst in reservations['Instances']:
        instance_type = inst['InstanceType']
        instance_tags = inst['Tags']

print('Instance Type discovered as: '+ instance_type)
print('Got instance tags')

#Create AMI
image = (client.create_image(InstanceId=instance_id, Name=image_name)['ImageId'])
print('Generated AMI: '+ image)

#Waits for the AMI to be ready
image_state = client.describe_images(ImageIds = [image])['Images'][0]['State']
print('Image state: ' + image_state)

while image_state != 'available':
    print('Image not ready: ' + image_state)
    time.sleep(20)
    image_state = client.describe_images(ImageIds = [image])['Images'][0]['State']
else:
    print('Image ready, continuing')

#copy AMI to region
response = clientDest.copy_image(
   Name=image_name,
   SourceImageId=image,
   SourceRegion=region_source
)

#Get original SG ID
read_id_security_group = client.describe_instances(
    InstanceIds=[
        instance_id,
    ],
)
ler_sg_id = read_id_security_group["Reservations"][0]["Instances"][0]["SecurityGroups"][0]["GroupId"]

#Get original SG Rules
read_security_group = client.describe_security_groups(
     GroupIds=[
        ler_sg_id,
    ],
)
#Filter inbound rules
read_ingress = read_security_group["SecurityGroups"][0]["IpPermissions"]

for rule in read_ingress:
    if len(rule["UserIdGroupPairs"]) > 0:
        read_ingress.remove(rule)

#Create SG
create_security_group = client_dev.create_security_group(
    Description=image_name,
    GroupName=image_name,
    VpcId='vpc-05a52c04f02899e3a',
)
#Add rules to SG
add_ingress = client_dev.authorize_security_group_ingress(
    GroupId=create_security_group ["GroupId"],
    IpPermissions=read_ingress
)

#Get imageid in new region
img_region = clientDest.describe_images(
        Filters=[
        {
            'Name': 'name',
            'Values': [
                image_name,
            ]
        },
    ])["Images"][0]['ImageId']
print(img_region)

#Waits for the AMI to be ready
image_state = clientDest.describe_images(ImageIds = [img_region])['Images'][0]['State']
print('Image state: ' + image_state)

while image_state != 'available':
    print('Image not ready: ' + image_state)
    time.sleep(20)
    image_state = clientDest.describe_images(ImageIds = [img_region])['Images'][0]['State']
else:
    print('Image ready, continuing')

#Add permissions
clientDest.modify_image_attribute(ImageId=img_region, OperationType='add', Attribute='launchPermission', UserIds=[account_dev])

#Start Instance with AMI
start = (client_dev.run_instances(ImageId=img_region, MinCount=1, MaxCount=1,
                              InstanceType=instance_type, KeyName='dev', SecurityGroupIds=[create_security_group["GroupId"]],SubnetId=Private_subnet_1A ,TagSpecifications=[{'ResourceType':'instance', 'Tags':instance_tags}]))
print(start)