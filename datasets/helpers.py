# helpers.py

from django.core.mail import send_mail
from main.choices import AUTHORITY_BASEURI


def emailer(subj, msg, from_addr, to_addr):
    """
      TODO: replaced by new_emailer()??
      email various, incl. Celery down notice
      to ['whgazetteer@gmail.com','karl@kgeographer.org'],
    """
    print('subj, msg, from_addr, to_addr', subj, msg, from_addr, to_addr)
    send_mail(
        subj, msg, from_addr, to_addr,
        fail_silently=False,
    )


# append src_id to base_uri
def link_uri(auth, id):
    baseuri = AUTHORITY_BASEURI[auth]
    uri = baseuri + str(id)
    return uri
