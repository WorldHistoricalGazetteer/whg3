from celery import shared_task # these are @task decorators
#from celery_progress.backend import ProgressRecorder
from django_celery_results.models import TaskResult
from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.db import transaction, connection
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
User = get_user_model()
from main.views import task_emailer

@shared_task(bind=True)
def request_tileset(self, dataset_id, tiletype='normal'):
    from main.views import send_tileset_request
    print('request_tileset', dataset_id, tiletype)
    response_data = send_tileset_request(dataset_id, tiletype)
    if response_data and response_data.get("status") == "success":
        # Tileset created successfully, send an email to the staff member
        task_emailer.delay(
            self.request.id,
            'Tileset creation',
            'Staff Member Name',
            'staff_member_email@example.com',
            'Tileset created successfully for dataset ' + str(dataset_id),
            'Tileset creation was successful.',
            'off'
        )
    else:
        # Tileset creation failed, send an email to the staff member
        task_emailer.delay(
            self.request.id,
            'Tileset creation',
            'Staff Member Name',
            'staff_member_email@example.com',
            'Tileset creation failed for dataset ' + str(dataset_id),
            'Tileset creation failed.',
            'off'
        )
    return tiletype + ' tileset requested for dataset ' + str(dataset_id)

@shared_task(name="task_emailer")
def task_emailer(tid, dslabel, name, email, counthit, totalhits, test):
  # TODO: sometimes a valid tid is not recognized (race?)
  time.sleep(15)
  try:
    task = get_object_or_404(TaskResult, task_id=tid) or False
    tasklabel = 'Wikidata' if task.task_name[6:8]=='wd' else \
      'Getty TGN' if task.task_name.endswith('tgn') else 'WHGazetteer'
    if task.status == "FAILURE":
      fail_msg = task.result['exc_message']
      text_content="Greetings "+name+"! Unfortunately, your "+tasklabel+" reconciliation task has completed with status: "+ \
        task.status+". \nError: "+fail_msg+"\nWHG staff have been notified. We will troubleshoot the issue and get back to you."
      html_content_fail="<h3>Greetings, "+name+"</h3> <p>Unfortunately, your <b>"+tasklabel+"</b> reconciliation task for the <b>"+dslabel+"</b> dataset has completed with status: "+ task.status+".</p><p>Error: "+fail_msg+". WHG staff have been notified. We will troubleshoot the issue and get back to you soon.</p>"
    elif test == 'off':
      text_content="Greetings "+name+"! Your "+tasklabel+" reconciliation task has completed with status: "+ \
        task.status+". \n"+str(counthit)+" records got a total of "+str(totalhits)+" hits.\nRefresh the dataset page and view results on the 'Reconciliation' tab."
      html_content_success="<h3>Greetings, "+name+"</h3> <p>Your <b>"+tasklabel+"</b> reconciliation task for the <b>"+dslabel+"</b> dataset has completed with status: "+ task.status+". "+str(counthit)+" records got a total of "+str(totalhits)+" hits.</p>" + \
        "<p>View results on the 'Reconciliation' tab (you may have to refresh the page).</p>"
    else:
      text_content="Greetings "+name+"! Your "+tasklabel+" TEST task has completed with status: "+ \
        task.status+". \n"+str(counthit)+" records got a total of "+str(totalhits)+".\nRefresh the dataset page and view results on the 'Reconciliation' tab."
      html_content_success="<h3>Greetings, "+name+"</h3> <p>Your <b>TEST "+tasklabel+"</b> reconciliation task for the <b>"+dslabel+"</b> dataset has completed with status: "+ task.status+". "+str(counthit)+" records got a total of "+str(totalhits)+" hits.</p>" + \
        "<p>View results on the 'Reconciliation' tab (you may have to refresh the page).</p>"
  except:
    print('task lookup in task_emailer() failed on tid', tid, 'how come?')
    text_content="Greetings "+name+"! Your reconciliation task for the <b>"+dslabel+"</b> dataset has completed.\n"+ \
      str(counthit)+" records got a total of "+str(totalhits)+" hits.\nRefresh the dataset page and view results on the 'Reconciliation' tab."
    html_content_success="<h3>Greetings, "+name+"</h3> <p>Your reconciliation task for the <b>"+dslabel+"</b> dataset has completed. "+str(counthit)+" records got a total of "+str(totalhits)+" hits.</p>" + \
      "<p>View results on the 'Reconciliation' tab (you may have to refresh the page).</p>"

  subject, from_email = 'WHG reconciliation result', 'whg@kgeographer.org'
  conn = mail.get_connection(
    host=settings.EMAIL_HOST,
    user=settings.EMAIL_HOST_USER,
    use_ssl=settings.EMAIL_USE_SSL,
    password=settings.EMAIL_HOST_PASSWORD,
    port=settings.EMAIL_PORT
  )
  # msg=EmailMessage(
  msg = EmailMultiAlternatives(
    subject,
    text_content,
    from_email,
    [email],
    connection=conn
  )
  msg.bcc = ['karl@kgeographer.org']
  msg.attach_alternative(html_content_success if task and task.status == 'SUCCESS' else html_content_fail, "text/html")
  msg.send(fail_silently=False)