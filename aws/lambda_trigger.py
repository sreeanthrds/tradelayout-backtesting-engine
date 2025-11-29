"""
AWS Lambda Function - Auto Start/Stop EC2 Instance

Triggered by EventBridge:
- 8:45 AM IST (Mon-Fri) - Start instance
- 3:45 PM IST (Mon-Fri) - Stop instance
"""

import boto3
import os
import logging
from datetime import datetime

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
ec2 = boto3.client('ec2')
ssm = boto3.client('ssm')

# Configuration from environment variables
INSTANCE_ID = os.environ.get('INSTANCE_ID')
STARTUP_SCRIPT = '/opt/tradelayout-engine/aws/startup.sh'
SHUTDOWN_SCRIPT = '/opt/tradelayout-engine/aws/shutdown.sh'


def lambda_handler(event, context):
    """
    Lambda handler for EC2 instance management.
    
    Event structure:
    {
        "action": "start" | "stop",
        "instance_id": "i-xxxxx" (optional, uses env var if not provided)
    }
    """
    try:
        # Get action from event
        action = event.get('action', 'start')
        instance_id = event.get('instance_id', INSTANCE_ID)
        
        if not instance_id:
            raise ValueError("Instance ID not provided")
        
        logger.info(f"Action: {action}, Instance: {instance_id}")
        
        if action == 'start':
            return start_instance(instance_id)
        elif action == 'stop':
            return stop_instance(instance_id)
        else:
            raise ValueError(f"Invalid action: {action}")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'success': False,
                'error': str(e)
            }
        }


def start_instance(instance_id):
    """Start EC2 instance and run startup script."""
    try:
        logger.info(f"Starting instance {instance_id}...")
        
        # Check current state
        response = ec2.describe_instances(InstanceIds=[instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        
        if state == 'running':
            logger.info("Instance already running")
            return {
                'statusCode': 200,
                'body': {
                    'success': True,
                    'message': 'Instance already running',
                    'instance_id': instance_id
                }
            }
        
        # Start instance
        ec2.start_instances(InstanceIds=[instance_id])
        logger.info("Instance start initiated")
        
        # Wait for instance to be running
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])
        logger.info("Instance is running")
        
        # Wait additional time for system to be ready
        import time
        time.sleep(30)
        
        # Run startup script via SSM
        logger.info("Running startup script...")
        ssm_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [
                    f'sudo bash {STARTUP_SCRIPT}'
                ]
            },
            TimeoutSeconds=600
        )
        
        command_id = ssm_response['Command']['CommandId']
        logger.info(f"Startup script command ID: {command_id}")
        
        # Wait for command to complete
        time.sleep(10)
        
        # Check command status
        command_status = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id
        )
        
        if command_status['Status'] == 'Success':
            logger.info("Startup script completed successfully")
            return {
                'statusCode': 200,
                'body': {
                    'success': True,
                    'message': 'Instance started and application launched',
                    'instance_id': instance_id,
                    'command_id': command_id
                }
            }
        else:
            logger.warning(f"Startup script status: {command_status['Status']}")
            return {
                'statusCode': 200,
                'body': {
                    'success': False,
                    'message': f"Startup script failed: {command_status['Status']}",
                    'instance_id': instance_id,
                    'command_id': command_id
                }
            }
            
    except Exception as e:
        logger.error(f"Error starting instance: {str(e)}")
        raise


def stop_instance(instance_id):
    """Run shutdown script and stop EC2 instance."""
    try:
        logger.info(f"Stopping instance {instance_id}...")
        
        # Check current state
        response = ec2.describe_instances(InstanceIds=[instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        
        if state == 'stopped':
            logger.info("Instance already stopped")
            return {
                'statusCode': 200,
                'body': {
                    'success': True,
                    'message': 'Instance already stopped',
                    'instance_id': instance_id
                }
            }
        
        # Run shutdown script via SSM
        logger.info("Running shutdown script...")
        ssm_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [
                    f'sudo bash {SHUTDOWN_SCRIPT}'
                ]
            },
            TimeoutSeconds=600
        )
        
        command_id = ssm_response['Command']['CommandId']
        logger.info(f"Shutdown script command ID: {command_id}")
        
        # Wait for command to complete
        import time
        time.sleep(60)  # Give time for backup and cleanup
        
        # Check command status
        try:
            command_status = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id
            )
            logger.info(f"Shutdown script status: {command_status['Status']}")
        except Exception as e:
            logger.warning(f"Could not get command status: {str(e)}")
        
        # Stop instance
        ec2.stop_instances(InstanceIds=[instance_id])
        logger.info("Instance stop initiated")
        
        # Wait for instance to be stopped
        waiter = ec2.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=[instance_id])
        logger.info("Instance is stopped")
        
        return {
            'statusCode': 200,
            'body': {
                'success': True,
                'message': 'Instance stopped successfully',
                'instance_id': instance_id,
                'command_id': command_id
            }
        }
            
    except Exception as e:
        logger.error(f"Error stopping instance: {str(e)}")
        raise


def get_instance_status(instance_id):
    """Get current instance status."""
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        return state
    except Exception as e:
        logger.error(f"Error getting instance status: {str(e)}")
        return 'unknown'
