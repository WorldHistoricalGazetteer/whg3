# /validation/management/commands/run_process_lpf.py

import json
import time
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.http import JsonResponse
from django.conf import settings
from validation.views import validate_file
from validation.tasks import get_task_status

class Command(BaseCommand):
    help = 'Run the process_lpf function and poll the task status'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the file to process')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']

        request = RequestFactory().get('/')  # Create a mock request object
        
        # Call the validate_file function with the file path argument
        response = validate_file(request, file_path=file_path)
        
        # Print the response
        self.stdout.write(self.style.SUCCESS('Response content: %s' % response.content))
        
        # Decode the byte string response content to a regular string
        response_content = response.content.decode('utf-8')
        
        # Manually parse the JSON response content
        try:
            response_data = json.loads(response_content)
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR('Failed to decode JSON response.'))
            return
        
        task_id = response_data.get('task_id')
        if not task_id:
            self.stdout.write(self.style.ERROR('No task_id returned.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Started task with ID: {task_id}'))

        # Poll the task status until it is no longer "in_progress"
        while True:
            task_status_response = get_task_status(task_id)
            # Print the response
            self.stdout.write(self.style.SUCCESS('Response content: %s' % task_status_response.content))
        
            task_status_content = task_status_response.content.decode('utf-8')
            
            task_status_data = json.loads(task_status_content)

            status = task_status_data.get('task_status', {}).get('status')
            if status == 'complete':
                self.stdout.write(self.style.SUCCESS(f'Task completed successfully.'))
                break
            elif status == 'failed':
                self.stdout.write(self.style.ERROR(f'Task failed.'))
                break

            self.stdout.write(self.style.NOTICE('Task is still in progress...'))
            time.sleep(5)  # Wait for 5 seconds before polling again
