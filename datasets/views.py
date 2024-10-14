# datasets.views
import ast
import chardet
import charset_normalizer as cn
import codecs
import json
import logging
import math
import mimetypes
import numpy as np
import os
import re
import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from shutil import copyfile

from celery import current_app as celapp
from deepdiff import DeepDiff as diff
from shapely import wkt

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.gis.geos import GEOSGeometry
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.core.serializers import serialize
from django.db import transaction
from django.db.models import Q, F, CharField, JSONField
from django.db.models.functions import Cast
from django.db.utils import DataError
from django.forms import modelformset_factory
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseServerError,
    JsonResponse
)
from django.shortcuts import redirect, get_object_or_404, render
from django.test import Client
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    ListView,
    UpdateView,
    DeleteView,
    DetailView
)
from django_celery_results.models import TaskResult

from areas.models import Area, Country
from collection.models import Collection, CollectionGroup
from elastic.es_utils import (
    makeDoc,
    removePlacesFromIndex,
    replaceInIndex,
    removeDatasetFromIndex
)
from main.choices import AUTHORITY_BASEURI
from main.models import Log, Comment
from places.models import *
from utils.regions_countries import get_regions_countries
from validation.views import validate_file
from validation.tasks import get_task_status

from .exceptions import (
    LPFValidationError,
    DelimValidationError,
    DelimInsertError,
    DataAlreadyProcessedError
)
from .forms import (
    HitModelForm,
    DatasetDetailModelForm,
    DatasetUploadForm,
    DatasetCreateEmptyModelForm
)
from .insert import (
    ds_insert_delim,
    failed_insert_notification
)
from .models import Dataset, Hit, DatasetFile
from .static.hashes import mimetypes_plus as mthash_plus
from .static.hashes.parents import ccodes as cchash
from .tasks import align_wdlocal, align_idx, maxID
from .utils import *

es = settings.ES_CONN
User = get_user_model()


class DatasetValidate(CreateView):
    logger = logging.getLogger('validation')

    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'
    template_name = 'datasets/dataset_validate.html'
    form_class = DatasetUploadForm

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['task_id'] = ''
        return context

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        uploaded_file = None
        uploaded_filepath = None
        try:
            user = self.request.user

            uploaded_file = form.cleaned_data.get('file')
            if uploaded_file is None:
                return self.handle_invalid_form(form, "No file uploaded.")

            uploaded_filepath = self.save_file_temporarily(uploaded_file)
            self.logger.debug(f'File saved to `{uploaded_filepath}`')

            validation_response = validate_file(self.request, {
                'title': form.cleaned_data.get('title'),
                'label': form.cleaned_data.get('label') or self.generate_unique_label(uploaded_file),
                'description': form.cleaned_data.get('description'),
                'creator': form.cleaned_data.get('creator'),
                'source': form.cleaned_data.get('source'),
                'contributors': form.cleaned_data.get('contributors'),
                'uri_base': form.cleaned_data.get('uri_base') or 'https://whgazetteer.org/api/db/?id=',
                'webpage': form.cleaned_data.get('webpage'),
                'pdf': form.cleaned_data.get('pdf'),
                'owner_id': user.id,
                'username': user.username,
                'uploaded_filepath': uploaded_filepath,
                'uploaded_filename': uploaded_file.name
            })

            if not validation_response:
                self.cleanup_uploaded_file(uploaded_filepath)
                return self.handle_invalid_form(form, "No response from validation service.")

            if isinstance(validation_response, JsonResponse):
                response_data = validation_response.content.decode('utf-8')
                response_data = json.loads(response_data)
                status = response_data.get("status")

                if status == "in_progress":
                    task_id = response_data.get("task_id")
                    context = self.get_context_data(form=form)
                    context['task_id'] = task_id
                    return self.render_to_response(context)

                elif status == "failed":
                    message = response_data.get("message", "Unknown error")
                    messages.error(self.request, f"Validation failed: {message}")
                    return self.form_invalid(form)

                else:
                    messages.error(self.request, "Unknown validation status received.")
                    self.cleanup_uploaded_file(uploaded_filepath)
                    return self.form_invalid(form)

        except Exception as e:
            self.logger.error(f"Error during file validation: {str(e)}", exc_info=True)
            self.cleanup_uploaded_file(uploaded_filepath)
            return self.handle_invalid_form(form,
                                            f"Sorry, there was an error while processing the uploaded file: {str(e)}")

        # finally:
        # return redirect('some_success_url') # <<< Dataset browse

    def handle_invalid_form(self, form, message):
        messages.error(self.request, message)
        return self.form_invalid(form)

    def save_file_temporarily(self, uploaded_file):
        original_file_name = uploaded_file.name
        _, file_extension = os.path.splitext(original_file_name)

        # Create a temporary file with the same extension
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            # Deletion is managed by validation.tasks.clean_tmp_files, triggered by beat_schedule in celery.py
            temp_file_path = temp_file.name
            try:
                # If the file is stored on disk (TemporaryUploadedFile)
                if hasattr(uploaded_file, 'temporary_file_path'):
                    shutil.copy(uploaded_file.temporary_file_path(), temp_file_path)
                else:
                    # If the file is in memory (InMemoryUploadedFile)
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
            except Exception as e:
                # Ensure file is removed in case of error
                self.cleanup_uploaded_file(temp_file_path)
                raise e

        return temp_file_path

    def cleanup_uploaded_file(self, uploaded_filepath):
        if uploaded_filepath is not None and os.path.exists(uploaded_filepath):
            os.remove(uploaded_filepath)

    def generate_unique_label(self, uploaded_file):
        min_length = 3
        max_length = 20

        # Initialise label from the file name
        base_label = slugify(os.path.splitext(uploaded_file.name)[0])

        # Helper function to ensure the label does not exceed max length
        def adjust_label_length(label):
            if len(label) > max_length:
                return label[-max_length:]
            return label

        # Adjust the base label length
        label = adjust_label_length(base_label)

        # Check if the label already exists and ensure uniqueness
        if Dataset.objects.filter(label=label).exists():
            # If the label already exists, append the user's surname
            label = f"{label}_{slugify(self.request.user.surname)}"
            label = adjust_label_length(label)  # Adjust length after appending surname

            count = 1
            # If the new label still exists, append "_v" and a number
            while Dataset.objects.filter(label=label).exists():
                label = f"{base_label}_v{count}"
                label = adjust_label_length(label)  # Adjust length after appending version
                count += 1

        return label


class VolunteeringView(ListView):
    template_name = 'datasets/volunteering.html'
    model = Dataset

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(volunteers_text__isnull=False).order_by('-create_date')

    def get_context_data(self, *args, **kwargs):
        context = super(VolunteeringView, self).get_context_data(*args, **kwargs)
        context['dataset_list'] = context.pop('object_list')

        return context


# TODO: in use?
class DatasetGalleryView(ListView):
    redirect_field_name = 'redirect_to'

    context_object_name = 'datasets'
    template_name = 'datasets/ds_gallery.html'
    model = Dataset

    def get_queryset(self):
        qs = super().get_queryset()
        # return qs.filter(public=True).order_by('title')
        # TODO: remove this exclude
        return qs.filter(public=True).exclude(owner_id=119).order_by('title')

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetGalleryView, self).get_context_data(*args, **kwargs)

        context['active_tab'] = self.kwargs.get('gallery_type',
                                                'datasets')  # datasets|collections: default to 'datasets' if not provided

        context['num_datasets'] = Dataset.objects.filter(public=True).count()
        context['num_collections'] = Collection.objects.filter(public=True).count()

        context['dropdown_data'] = get_regions_countries()

        country_feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        context['beta_or_better'] = True if self.request.user.groups.filter(
            name__in=['beta', 'admins']).exists() else False
        return context


"""
  TODO: replaced by new_emailer()??
  email various, incl. Celery down notice
  to ['whgazetteer@gmail.com','karl@kgeographer.org'],
"""


def emailer(subj, msg, from_addr, to_addr):
    print('subj, msg, from_addr, to_addr', subj, msg, from_addr, to_addr)
    send_mail(
        subj, msg, from_addr, to_addr,
        fail_silently=False,
    )


# check Celery process is running before initiating reconciliation task
def celeryUp():
    response = celapp.control.ping(timeout=1.0)
    return len(response) > 0


# append src_id to base_uri
def link_uri(auth, id):
    baseuri = AUTHORITY_BASEURI[auth]
    uri = baseuri + str(id)
    return uri


"""
  from datasets.views.review()
  indexes a db record upon a single hit match in align_idx review
  new record becomes child in the matched hit group
"""


# hotfix 17 June 2024
def indexMatch(pid, hit_pid=None, user=None, task=None):
    print(f'indexMatch(): pid {str(pid)}; hit_pid: {str(hit_pid)}')
    print(f'indexMatch(): user: {user}; task: {str(hit_pid)}')
    es = settings.ES_CONN
    idx = settings.ES_WHG
    place = get_object_or_404(Place, id=pid)

    # Check if this place is already indexed
    q_place = {"query": {"bool": {"must": [{"match": {"place_id": pid}}]}}}
    res = es.search(index=idx, body=q_place)
    if res['hits']['total']['value'] == 0:
        # Not indexed, create a new doc
        new_obj = makeDoc(place)
        p_hits = None
    else:
        # It's indexed, get parent
        p_hits = res['hits']['hits']
        place_parent = p_hits[0]['_source']['relation']['parent']

    if hit_pid is None and not p_hits:
        # No match and place is not already indexed, create new parent
        print('making ' + str(pid) + ' a parent')
        new_obj['relation'] = {"name": "parent"}

        # Increment a whg_id for it
        whg_id = maxID(es, idx) + 1
        new_obj['whg_id'] = whg_id

        # Index the new parent
        try:
            res = es.index(index=idx, id=str(whg_id), body=json.dumps(new_obj))
            place.indexed = True
            place.save()
            print('created parent:', pid, place.title)
        except Exception as e:
            print(f'failed indexing (as parent) {pid}: {e}')
            pass
    else:
        # There was a match or place is already indexed
        # Get hit record in index
        q_hit = {"query": {"bool": {"must": [{"match": {"place_id": hit_pid}}]}}}
        res = es.search(index=idx, body=q_hit)
        hit = res['hits']['hits'][0]

        # Determine if the hit is a parent or child
        if hit['_source']['relation']['name'] == 'child':
            parent_whgid = hit['_source']['relation']['parent']
        else:
            parent_whgid = hit['_id']

        # Mine new place for its names and create an index doc
        match_names = [p.toponym for p in place.names.all()]
        new_obj = makeDoc(place)
        new_obj['relation'] = {"name": "child", "parent": parent_whgid}

        # Index the new child and update the parent
        try:
            res = es.index(index=idx, id=place.id, routing=1, body=json.dumps(new_obj))
            # Update parent's fields with child's name variants
            q_update = {"script": {
                "source": "ctx._source.children.add(params.id); ctx._source.searchy.addAll(params.names)",
                "lang": "painless",
                "params": {"names": match_names, "id": str(place.id)}
            },
                "query": {"match": {"_id": parent_whgid}}}
            es.update_by_query(index=idx, body=q_update, conflicts='proceed')
            print('indexed? ', place.indexed)
            print(f'added {place.id} as child of {hit_pid}')

            # Update close_matches table in Django
            update_close_matches(pid, hit_pid, user, task)

        except Exception as e:
            print(f'failed indexing {pid} as child of {parent_whgid}: {e}', new_obj)
            pass


@transaction.atomic
# ensuring unique CloseMatch records
def update_close_matches(new_child_id, parent_place_id, user, task):
    # Normalize the tuple
    place_a_id, place_b_id = sorted([new_child_id, parent_place_id])

    # Record the new match in CloseMatch table
    print('Updating CloseMatch table')
    print(f'new_child_id: {new_child_id}, parent_place_id: {parent_place_id}')

    try:
        # Ensure that the user and task are valid instances
        assert isinstance(user, User), f'user is not a User instance: {type(user)}'
        assert isinstance(task, TaskResult), f'task is not a TaskResult instance: {type(task)}'

        # Check if a CloseMatch record already exists
        if not CloseMatch.objects.filter(
                Q(place_a_id=place_a_id) & Q(place_b_id=place_b_id)
        ).exists():
            # Print debug information
            print(f'User: {user} (ID: {user.id}), Task: {task} (ID: {task.id})')

            # Create the CloseMatch record
            CloseMatch.objects.create(
                place_a_id=place_a_id,
                place_b_id=place_b_id,
                created_by=user,
                task=task,
                basis='reviewed'
            )
            print('CloseMatch record created successfully')
        else:
            print(f'CloseMatch record already exists for {parent_place_id} and {new_child_id}')
    except Exception as e:
        print(f'Error creating CloseMatch record: {e}')
        print(f'Debug info: new_child_id={new_child_id}, parent_place_id={parent_place_id}, user={user}, task={task}')


"""
  from datasets.views.review()
  indexes a db record given multiple hit matches in align_idx review
  a LOT has to happen (see _notes/accession-psudocode.txt):
    - pick a single 'winner' among the matched hits (max score)
    - make new record its child
    - demote all non-winners in index from parent to child
      - whg_id and children[] ids (if any) added to winner
      - name variants added to winner's searchy[] and suggest.item[] lists
"""


# hotfix 17 June 2024
def indexMultiMatch(pid, matchlist, user, task):
    print('indexMultiMatch(): pid ' + str(pid) + ' matches ' + str(matchlist))
    from elasticsearch8 import RequestError
    es = settings.ES_CONN
    idx = settings.ES_WHG
    place = Place.objects.get(id=pid)
    from elastic.es_utils import makeDoc
    new_obj = makeDoc(place)

    # bins for new values going to winner
    addnames = []
    addkids = [str(pid)]  # pid will also be the new record's _id

    # max score is winner
    winner = max(matchlist, key=lambda x: x['score'])  # 14158663
    winner_place_id = winner['pid']  # This is the place_id of the winner
    print(f'winner_place_id: {winner_place_id}, incoming pid: {pid}')
    # this is multimatch so there is at least one demoted (list of whg_ids)
    demoted = [str(i['whg_id']) for i in matchlist if not (i['whg_id'] == winner['whg_id'])]  # ['14090523']
    print('demoted', demoted)

    # complete doc for new record
    new_obj['relation'] = {"name": "child", "parent": winner['whg_id']}
    # copy its toponyms into addnames[] for adding to winner later
    for n in new_obj['names']:
        addnames.append(n['toponym'])
    if place.title not in addnames:
        addnames.append(place.title)

    # New relationships for CloseMatch records
    new_relationships = [(pid, winner_place_id)]  # Add the initial relationship
    print('initial new_relationships', new_relationships)

    # generate script used to update winner w/kids and names
    # from new record and any kids of 'other' matched parents
    def q_updatewinner(addkids, addnames):
        return {"script": {
            "source": """ctx._source.children.addAll(params.newkids);
          ctx._source.searchy.addAll(params.names);
          """,
            "lang": "painless",
            "params": {
                "newkids": addkids,
                "names": addnames}
        }}

    # index the new record as child of winner
    try:
        es.index(index=idx, id=str(pid), routing=1, body=json.dumps(new_obj))
    except RequestError as rq:
        print('Error: ', rq.error, rq.info)

    # demote others
    for _id in demoted:
        print('find & demote whg_id', _id)
        # get index record stuff, to be altered then re-indexed
        # ES won't allow altering parent/child relations directly
        q_demote = {"query": {"bool": {"must": [{"match": {"whg_id": _id}}]}}}
        res = es.search(body=q_demote, index=idx)
        print('res for demoted - hits hits ', res)
        srcd = res['hits']['hits'][0]['_source']
        # add names in suggest to names[]
        sugs = srcd['searchy']
        for sug in sugs:
            addnames.append(sug)
        addnames = list(set(addnames))
        # _id of demoted (a whg_id) belongs in winner's children[]
        addkids.append(str(srcd['place_id']))

        haskids = len(srcd['children']) > 0
        # if demoted record has kids, add to addkids[] list
        # for 'adoption' by topdog later
        if haskids:
            morekids = srcd['children']
            for kid in morekids:
                addkids.append(str(kid))

        # update the 'winner' parent
        q = q_updatewinner(list(set(addkids)), list(set(addnames)))  # ensure only unique
        try:
            es.update(index=idx, id=winner['whg_id'], body=q)
        except RequestError as rq:
            print('q_updatewinner failed (whg_id)', winner['whg_id'])
            print('Error: ', rq.error, rq.info)

        from copy import deepcopy
        newsrcd = deepcopy(srcd)
        # update it to reflect demotion
        newsrcd['relation'] = {"name": "child", "parent": winner['whg_id']}
        newsrcd['children'] = []
        if 'whg_id' in newsrcd:
            newsrcd.pop('whg_id')

        # zap the demoted, reindex with same _id and modified doc (newsrcd)
        try:
            es.delete(index=idx, id=_id)
            es.index(index=idx, id=_id, body=newsrcd, routing=1)
        except RequestError as rq:
            print('reindex failed (demoted)', _id)
            print('Error: ', rq.error, rq.info)

        # re-assign parent for kids of all/any demoted parents
        print('addkids', addkids)
        if len(addkids) > 0:
            for kid in addkids:
                q_adopt = {"script": {
                    "source": "ctx._source.relation.parent = params.new_parent; ",
                    "lang": "painless",
                    "params": {"new_parent": winner['whg_id']}
                },
                    "query": {"match": {"place_id": kid}}}
                es.update_by_query(index=idx, body=q_adopt, conflicts='proceed')

                # Add new relationships for CloseMatch
                kid_place_id = kid  # Since addkids contains place_id values
                new_relationships.append((int(kid_place_id), int(winner_place_id)))

    # Create new CloseMatch records
    print('new_relationships', new_relationships)
    for place_a, place_b in new_relationships:
        update_close_matches(place_a, place_b, user, task)


"""
  GET   returns review.html for Wikidata, or accession.html for accessioning
  POST  for each record that got hits, process user matching decisions
  NB.   'passnum' is always a string: ['pass*' | 'def' | '0and1' (for idx)]
"""


def review(request, dsid, tid, passnum):
    print('request.GET entering review()', request.GET)
    print(f'entering review(): dsid:{dsid}, tid:{tid}, passnum:{passnum}')
    pid = None
    if "pid" in request.GET:
        pid = request.GET["pid"]
    ds = get_object_or_404(Dataset, id=dsid)

    # get the task & its kwargs
    task = get_object_or_404(TaskResult, task_id=tid)
    auth = task.task_name[6:].replace("local", "")
    authname = "Wikidata" if auth == "wd" else "WHG"
    kwargs = ast.literal_eval(task.task_kwargs.strip('"'))
    print('task_kwargs in review()', kwargs)
    test = kwargs["test"] if "test" in kwargs else "off"

    # beta = "beta" in list(request.user.groups.all().values_list("name", flat=True))
    def get_pass_count(task_id, reviewed, query_pass):
        return Hit.objects.values("place_id").filter(task_id=task_id, reviewed=reviewed, query_pass=query_pass).count()

    # task_id='6e81ccdc-5bcc-403e-bda1-afac433d558c'
    # reviewed = False
    # query_pass = 'def'
    # foo=get_pass_count(task_id, reviewed, query_pass)

    # filter place records by passnum for those with unreviewed hits on this task
    # if request passnum is complete, increment
    # hit count for this pass
    cnt_pass = get_pass_count(tid, False, passnum)
    print(f'cnt_pass for {passnum}: {cnt_pass}')
    # hit counts for all numbered passes
    cnt_pass0 = get_pass_count(tid, False, "pass0")
    cnt_pass1 = get_pass_count(tid, False, "pass1")
    cnt_pass2 = get_pass_count(tid, False, "pass2")
    cnt_pass3 = get_pass_count(tid, False, "pass3")

    # calling link passnum may be 'pass*', 'def', or '0and1' (for idx)
    # if 'pass*', get place_ids for just that pass
    if passnum.startswith("pass"):
        print('passnum starts with "pass":', passnum)
        pass_int = int(passnum[4])
        # if no unreviewed left, go to next pass
        passnum = passnum if cnt_pass > 0 else "pass" + str(pass_int + 1)
        hitplaces = Hit.objects.values("place_id").filter(
            task_id=tid, reviewed=False, query_pass=passnum
        )
        print(f'{len(hitplaces)} hitplaces for {passnum}: {hitplaces}')
    else:
        print('passnum does not start with "pass":', passnum)
        # all unreviewed
        hitplaces = Hit.objects.values("place_id").filter(task_id=tid, reviewed=False)
        print(f'{len(hitplaces)} hitplaces for {passnum}: {hitplaces}')

    # set review page returned
    if auth in ["whg", "idx"]:
        review_page = "accession.html"
    else:
        review_page = "review.html"

    #
    review_field = (
        "review_whg"
        if auth in ["whg", "idx"]
        else "review_wd"
        if auth.startswith("wd")
        else "review_tgn"
    )
    lookup = "__".join([review_field, "in"])
    """
    2 = deferred; 1 = reviewed, 0 = unreviewed; NULL = no hits
    status = [2] if passnum == 'def' else [0,2]
    by default, don't return deferred
  """
    status = [2] if passnum == "def" else [0]

    # unreviewed place objects from place_ids (a single pass or all)
    record_list = ds.places.order_by("id").filter(**{lookup: status}, pk__in=hitplaces)
    if len(record_list) == 0:
        # no records left for pass (or in deferred queue)
        context = {
            "nohits": True,
            "ds_id": dsid,
            "task_id": tid,
            "passnum": passnum,
        }
        return render(request, "datasets/" + review_page, context=context)

    # manage pagination & urls
    # gets next place record as records[0]
    # TODO: manage concurrent reviewers; i.e. 2 people have same page 1
    paginator = Paginator(record_list, 1)
    # handle request for singleton (e.g. deferred from browse table)
    # if 'pid' in request.GET, bypass per-pass sequential loading
    if pid:
        print("pid in URI, just show that", pid)
        # get its index and add 1 to get page
        page = (*record_list,).index(Place.objects.get(id=pid)) + 1
        print("pagenum", page)
    else:
        # default action, sequence of all pages for the pass
        page = 1 if not request.GET.get("page") else request.GET.get("page")
    records = paginator.get_page(page)
    count = len(record_list)

    # get hits for this record
    placeid = records[0].id
    place = get_object_or_404(Place, id=placeid)
    print('passnum', passnum)
    dataset_details = {}  # needed for context in either case
    # if auth not in ["whg", "idx"]:
    if passnum.startswith("pass") and auth not in ["whg", "idx"]:
        # ***this is wdgn review*** raw_hits are only numered pass
        print('wdgn case in review(), raw_hits only for this pass', passnum)
        raw_hits = Hit.objects.filter(
            place_id=placeid, task_id=tid, query_pass=passnum).order_by("-authority", "-score")
        print(f'place_id:{placeid}; task_id:{tid}; query_pass: {passnum}')
        print('authorities:', [rh.authority for rh in raw_hits])
    elif passnum == "def":
        raw_hits = Hit.objects.filter(
            place_id=placeid, task_id=tid).order_by("-authority", "-score")
    else:
        # ***this is accessioning*** -> get all regardless of pass
        raw_hits = Hit.objects.filter(place_id=placeid, task_id=tid).order_by("-score")

        # Get details of datasets for popovers
        # in dev, some datasets referenced in hits by index labels may not exist in database
        for hit in raw_hits:
            for source in hit.json["sources"]:
                try:
                    dataset = Dataset.objects.get(label=source["dslabel"])
                    dataset_details[dataset.label] = {
                        "title": dataset.title or "N/A",
                        "description": dataset.description or "N/A",
                        "owner": dataset.owner.name or "N/A",
                        "creator": dataset.creator or "N/A"
                    }
                except Dataset.DoesNotExist:
                    dataset_details[source["dslabel"]] = {
                        "title": "Dataset not found",
                        "description": "The dataset with label {} does not exist.".format(source["dslabel"]),
                        "owner": "N/A",
                        "creator": "N/A"
                    }
        # print('dataset_details', dataset_details)

    # ??why? get pass contents for all of a place's hits
    passes = (
        list(
            set(
                [
                    item
                    for sublist in [
                    [s["pass"] for s in h.json["sources"]] for h in raw_hits
                ]
                    for item in sublist
                ]
            )
        )
        if auth in ["whg", "idx"]
        else None
    )
    print('passes', passes)

    # convert ccodes to names
    countries = []
    for r in place.ccodes:
        try:
            countries.append(
                cchash[0][r.upper()]["gnlabel"]
                + " ("
                + cchash[0][r.upper()]["tgnlabel"]
                + ")"
            )
        except:
            pass

    # prep some context
    context = {
        "ds_id": dsid,
        "ds_label": ds.label,
        "task_id": tid,
        "hit_list": raw_hits,
        "dataset_details": dataset_details,
        "passes": passes,
        "authority": task.task_name[6:8] if auth == "wdlocal" else task.task_name[6:],
        "records": records,
        "countries": countries,
        "passnum": passnum,
        "page": page if request.method == "GET" else str(int(page) - 1),
        "aug_geoms": kwargs["aug_geoms"],
        "count_pass0": cnt_pass0,
        "count_pass1": cnt_pass1,
        "count_pass2": cnt_pass2,
        "count_pass3": cnt_pass3,
        "deferred": True if passnum == "def" else False,
        "test": test,
    }

    # print('raw_hits at formset', [h.json['titles'] for h in raw_hits])
    # build formset from hits, add to context
    HitFormset = modelformset_factory(
        Hit,
        fields=("id", "authority", "authrecord_id", "query_pass", "score", "json"),
        form=HitModelForm,
        extra=0,
    )
    formset = HitFormset(request.POST or None, queryset=raw_hits)
    context["formset"] = formset
    # print('hit.json in review()', [h.json for h in raw_hits])
    # Create FeatureCollection for mapping
    index_offset = sum(1 for record in records for geom in
                       record.geoms.all().values('jsonb')) or 1  # Handle case where no geometries yet exist
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
                        {
                            "type": "Feature",
                            "properties": {
                                "record_id": record.id,
                                "ds": "dataset",
                                # "green": True,
                            },
                            "geometry": {"type": geom['jsonb']["type"],
                                         "coordinates": geom['jsonb'].get("coordinates")},
                            "id": idx
                        }
                        for idx, (record, geom) in
                        enumerate((record, geom) for record in records for geom in record.geoms.all().values('jsonb'))
                    ] +
                    [
                        {
                            "type": "Feature",
                            "properties": {
                                **{key: value for key, value in geom.items() if key not in ["coordinates", "type"]},
                                # "green": False,  # Set to True for green markers - following 2 lines are redundant v2 code
                                # (review_page=="accession.html" and geom["ds"]==ds.label) or
                                # (review_page=="review.html" and not geom["ds"] in ['tgn', 'wd', 'whg'])
                            },
                            "geometry": {"type": geom["type"], "coordinates": geom.get("coordinates")},
                            "id": idx + index_offset
                        }
                        for idx, (hit, geom) in
                        enumerate((hit, geom) for hit in raw_hits if 'geoms' in hit.json for geom in hit.json['geoms'])
                    ]
    }
    context["feature_collection"] = json.dumps(feature_collection)

    method = request.method

    '''
      POST processes closeMatch/no match/defer choices made by save in review or accession page
      Two very different cases:
       - For wikidata review, act on each hit considered (new place_geom and place_link records if matched)
       - For accession, act on index 'clusters'  
    '''
    if method == "GET":  # just displays
        print("review() GET, just displaying next")
    elif method == "POST":
        print('request.POST in review()', request.POST)

        place_post = get_object_or_404(Place, pk=placeid)
        review_status = getattr(place_post, review_field)
        # proceed with POST only if place is unreviewed or deferred; else return to a GET (and next place)
        # NB. other reviewer(s) are *not* notified
        if review_status == 1:
            context["already"] = True
            messages.success(
                request, ("Last record (" + place_post.title + ") reviewed by another")
            )
            return redirect(
                "/datasets/" + str(dsid) + "/review/" + task.task_id + "/" + passnum
            )
        elif formset.is_valid():
            hits = formset.cleaned_data
            # print('formset valid', hits)
            matches = 0
            matched_for_idx = []  # for accession
            # are any of the listed hits matches?
            for x in range(len(hits)):
                hit = hits[x]["id"]
                print("hit # " + str(hits[x]) + " reviewed")
                print("hit['json']", hits[x]["json"])
                # print("dataset", hits[x]["json"]["dataset"])
                # is this hit a match?
                if hits[x]["match"] not in ["none"]:
                    # print('json of matched hit/cluster (in review())', hits[x]['json'])
                    matches += 1
                    # if wd or tgn, write place_geom, place_link record(s) now
                    # IF someone didn't just review it!
                    if task.task_name[6:] in ["wdlocal", "wd", "tgn"]:
                        # print('task.task_name', task.task_name)
                        hasGeom = (
                                "geoms" in hits[x]["json"]
                                and len(hits[x]["json"]["geoms"]) > 0
                        )
                        hasNames = (
                                ("variants" in hits[x]["json"] and len(hits[x]["json"]["variants"]) > 0)
                                or
                                ("names" in hits[x]["json"] and len(hits[x]["json"]["names"]) > 0)
                        )
                        # GEOMS
                        # create place_geom records if 'accept geometries' was checked
                        if (
                                kwargs["aug_geoms"] == 'on'
                                and hasGeom
                                and tid not in place_post.geoms.all().values_list("task_id", flat=True)
                        ):
                            gtype = hits[x]["json"]["geoms"][0]["type"]
                            coords = hits[x]["json"]["geoms"][0]["coordinates"]
                            # TODO: build real postgis geom values
                            gobj = GEOSGeometry(
                                json.dumps({"type": gtype, "coordinates": coords})
                            )
                            PlaceGeom.objects.create(
                                place=place_post,
                                task_id=tid,
                                src_id=place.src_id,
                                geom=gobj,
                                reviewer=request.user,
                                jsonb={
                                    "type": gtype,
                                    "citation": {
                                        "id": auth + ":" + hits[x]["authrecord_id"],
                                        "label": authname,
                                    },
                                    "coordinates": coords,
                                },
                            )
                        # NAMES
                        print('hasNames', hasNames, hits[x]["json"]["variants"])
                        if ('aug_names' in kwargs and kwargs['aug_names'] == 'on'
                                and hasNames
                                and tid not in place_post.names.all().values_list('task_id', flat=True)
                        ):
                            print('aug_names was "on", doing names in review() now')
                            for n in hits[x]["json"]["variants"]:
                                # handle different name formats
                                # print('n has type', type(n))
                                if hits[x]["json"]['dataset'] == 'wikidata':
                                    name = n.split('@')[0]
                                elif hits[x]["json"]['dataset'] == 'geonames':
                                    name = n
                                else:
                                    print("failed to parse name", n)
                                    continue  # Skip if n is not in the expected format
                                print('place_post, name', place_post, name)
                                print('existing:', place_post.names.all().values_list("toponym", flat=True))
                                # exclude duplicates
                                if name not in place_post.names.all().values_list("toponym", flat=True):
                                    PlaceName.objects.create(
                                        place=place_post,
                                        task_id=tid,
                                        src_id=place.src_id,
                                        toponym=name,
                                        # reviewer=request.user,
                                        jsonb={
                                            "toponym": n,
                                            "citations": [{
                                                "id": auth + ":" + hits[x]["authrecord_id"],
                                                "label": authname,
                                            }],
                                        },
                                    )

                        # LINKS
                        # create single PlaceLink for matched wikidata record
                        if tid not in place_post.links.all().values_list(
                                "task_id", flat=True
                        ):
                            link = PlaceLink.objects.create(
                                place=place_post,
                                task_id=tid,
                                src_id=place.src_id,
                                reviewer=request.user,
                                jsonb={
                                    "type": hits[x]["match"],
                                    "identifier": link_uri(
                                        task.task_name,
                                        hits[x]["authrecord_id"]
                                        if hits[x]["authority"] != "whg"
                                        else hits[x]["json"]["place_id"],
                                    ),
                                },
                            )
                            print("created place_link instance:", link)

                        # create multiple PlaceLink records (e.g. Wikidata)
                        # TODO: filter duplicates
                        if "links" in hits[x]["json"]:
                            for l in hits[x]["json"]["links"]:
                                authid = re.search(": ?(.*?)$", l).group(1)
                                # print('authid, authids',authid, place.authids)
                                if l not in place.authids:
                                    # if authid not in place.authids:
                                    link = PlaceLink.objects.create(
                                        place=place_post,
                                        task_id=tid,
                                        src_id=place.src_id,
                                        jsonb={
                                            "type": hits[x]["match"],
                                            # "identifier": authid.strip()
                                            "identifier": l.strip(),
                                        },
                                        reviewer=request.user,
                                    )
                                    # print('PlaceLink record created',link.jsonb)
                                    # update totals
                                    ds.numlinked = (
                                        ds.numlinked + 1 if ds.numlinked else 1
                                    )
                                    ds.total_links = (
                                        ds.total_links + 1 if ds.total_links else 1
                                    )
                                    # ds.total_links = ds.total_links + 1
                                    ds.save()
                    # this is accessioning to whg index, add to matched[]
                    elif task.task_name == "align_idx":
                        if "links" in hits[x]["json"]:
                            links_count = len(hits[x]["json"])
                        matched_for_idx.append(
                            {
                                "whg_id": hits[x]["json"]["whg_id"],
                                "pid": hits[x]["json"]["pid"],
                                "score": hits[x]["json"]["score"],
                                "links": links_count,
                            }
                        )
                    # TODO: informational lookup on whg index?
                    # elif task.task_name == 'align_whg':
                    #   print('align_whg (non-accessioning) DOING NOTHING (YET)')
                # in any case, flag hit as reviewed...
                hitobj = get_object_or_404(Hit, id=hit.id)
                hitobj.reviewed = True
                hitobj.save()
                print("hit # " + str(hitobj.id) + " flagged reviewed")

            # handle accessioning match results
            if len(matched_for_idx) == 0 and task.task_name == "align_idx":
                # 0 matches during accession, indexMatch() makes it s seed (parent)
                print("no accession matches, index place_id " + str(pid) + " as seed (parent)")
                print("maxID() for seed in review()", maxID(es, "whg"))

                # mod 18 Jun 2024
                print(f'review()->parent. user: {request.user}, place_post: {place_post.id}, task: {task}')
                indexMatch(str(pid), user=request.user, task=task)

                place_post.indexed = True
                place_post.save()
            elif len(matched_for_idx) == 1:
                # 1 match - indexMatch() makes it a child of the match
                # mod 18 Jun 2024
                parent_id = matched_for_idx[0]["pid"]
                print(f'review()->child: {place_post.id}, parent: {parent_id}')
                print(f'user in review()->: {request.user}, task in review(): {task}')
                indexMatch(str(place_post.id), hit_pid=parent_id, user=request.user, task=task)

                place_post.indexed = True
                place_post.save()
            elif len(matched_for_idx) > 1:
                indexMultiMatch(place_post.id, matched_for_idx)
                place_post.indexed = True
                place_post.save()

            if ds.unindexed == 0:
                setattr(ds, "ds_status", "indexed")
                ds.save()

            # if none are left for this task, change status & email staff
            if auth in ["wd"] and ds.recon_status["wdlocal"] == 0:
                recon_complete(ds)
                # ds.ds_status = "wd-complete"
                # ds.save()
                # status_emailer(ds, "wd")
                # print("sent status email")
            # handled by signal now
            # elif auth == "idx" and ds.recon_status["idx"] == 0:
            #   ds.ds_status = "indexed"
            #   ds.save()
            #   status_emailer(ds, "idx")
            #   print("sent status email")

            print("review_field", review_field)
            setattr(place_post, review_field, 1)
            place_post.save()

            return redirect(
                "/datasets/"
                + str(dsid)
                + "/review/"
                + tid
                + "/"
                + passnum
                + "?page="
                + str(int(page))
            )
        else:
            print("formset is NOT valid. errors:", formset.errors)
            print("formset data:", formset.data)
    # print('context', context)
    return render(request, "datasets/" + review_page, context=context)


def recon_complete(ds):
    ds.ds_status = "wd-complete"
    ds.save()
    # status_emailer(ds, "wd")
    # print("sent status email")


"""
  write_wd_pass0(taskid)
  called from dataset_detail>status tab
  accepts all pass0 wikidata matches, writes geoms and links
"""


# kwargs = json.loads(task.task_kwargs.replace("'", '"'))
def write_wd_pass0(request, tid):
    print('task_id (tid) in write_wd_pass0()', tid)
    task = get_object_or_404(TaskResult, task_id=tid)
    print('task.task_kwargs', task.task_kwargs)
    try:
        kwargs = ast.literal_eval(task.task_kwargs.strip('"'))
        print('kwargs in write_wd_pass0()', kwargs, kwargs['ds'])
    except (ValueError, SyntaxError) as e:
        print(f"Error evaluating task_kwargs: {e}")
        # return  # Handle the error appropriately

    # kwargs_str = task.task_kwargs.replace("'", '"')
    # kwargs = json.loads(kwargs_str)
    # kwargs = ast.literal_eval(task.task_kwargs)
    print('kwargs in write_wd_pass0()', kwargs, kwargs['ds'])
    print('type kwargs', type(kwargs))
    referer = request.META.get('HTTP_REFERER') + '#reconciliation'
    auth = task.task_name[6:].replace('local', '')
    # ds = get_object_or_404(Dataset, pk=kwargs['ds'])
    ds = Dataset.objects.get(id=kwargs['ds'])

    print('Dataset found:', ds)

    referer = request.META.get('HTTP_REFERER') + '#reconciliation'
    auth = task.task_name[6:].replace('local', '')

    # get unreviewed pass0 hits
    hits = Hit.objects.filter(
        task_id=tid,
        query_pass='pass0',
        reviewed=False
    )
    # print('writing '+str(len(hits))+' pass0 matched records for', ds.label)
    for h in hits:
        hasGeom = 'geoms' in h.json and len(h.json['geoms']) > 0
        hasLinks = 'links' in h.json and len(h.json['links']) > 0
        place = h.place  # object
        # existing for the place
        authids = place.links.all().values_list('jsonb__identifier', flat=True)
        authname = 'Wikidata' if h.authority == 'wd' else 'GeoNames'
        # GEOMS
        # confirm another user hasn't just done this...
        if hasGeom and kwargs['aug_geoms'] == 'on' \
                and tid not in place.geoms.all().values_list('task_id', flat=True):
            for g in h.json['geoms']:
                pg = PlaceGeom.objects.create(
                    place=place,
                    task_id=tid,
                    src_id=place.src_id,
                    geom=GEOSGeometry(json.dumps({"type": g['type'], "coordinates": g['coordinates']})),
                    reviewer=request.user,
                    jsonb={
                        "type": g['type'],
                        "citation": {"id": auth + ':' + h.authrecord_id, "label": authname},
                        "coordinates": g['coordinates']
                    }
                )
            print('created place_geom instance in write_wd_pass0', pg)

        # LINKS
        link_counter = 0
        # add PlaceLink record for wikidata hit if not already there
        if 'wd:' + h.authrecord_id not in authids:
            link_counter += 1
            link = PlaceLink.objects.create(
                place=place,
                task_id=tid,
                src_id=place.src_id,
                reviewer=request.user,
                jsonb={
                    "type": "closeMatch",
                    "identifier": link_uri(task.task_name, h.authrecord_id)
                }
            )
            print('created wd place_link instance:', link)

        # create link for each wikidata concordance, if any
        if hasLinks:
            # authids=place.links.all().values_list(
            # 'jsonb__identifier',flat=True)
            for l in h.json['links']:
                link_counter += 1
                authid = re.search(":?(.*?)$", l).group(1)
                print(authid)
                # TODO: same no-dupe logic in review()
                # don't write duplicates
                if authid not in authids:
                    link = PlaceLink.objects.create(
                        place=place,
                        task_id=tid,
                        src_id=place.src_id,
                        reviewer=request.user,
                        jsonb={
                            "type": "closeMatch",
                            "identifier": authid
                        }
                    )
            print('created ' + str(len(h.json['links'])) + ' place_link instances')

        # only matters if autocomplete was the last review action
        if auth in ["wd"] and ds.recon_status["wdlocal"] == 0:
            recon_complete(ds)

        # update dataset totals for metadata page
        ds.numlinked = len(set(PlaceLink.objects.filter(place_id__in=ds.placeids).values_list('place_id', flat=True)))
        if ds.total_links is None:
            ds.total_links = link_counter
        else:
            ds.total_links += link_counter
        ds.save()

        # flag hit as reviewed
        h.reviewed = True
        h.save()

        # flag place as reviewed
        place.review_wd = 1
        place.save()

    return HttpResponseRedirect(referer)


"""
  ds_recon()
  initiates & monitors Celery tasks against Elasticsearch indexes
  i.e. align_[wdlocal | wd | builder] in tasks.py
  url: datasets/{ds.id}/reconcile ('ds_reconcile'; from ds_addtask.html)
  params: pk (dataset id), auth, region, userarea, geom, scope
  each align_{auth} task runs matching es_lookup_{auth}() and writes Hit instances
"""


def ds_recon(request, pk):
    ds = get_object_or_404(Dataset, id=pk)
    # TODO: handle multipolygons from "#area_load" and "#area_draw"
    user = request.user
    context = {"dataset": ds.title}
    if request.method == 'GET':
        print('ds_recon() GET')
    elif request.method == 'POST' and request.POST:
        print('ds_recon() request.POST:', request.POST)

        # return

        test = 'on' if 'test' in request.POST else 'off'  # for idx only
        auth = request.POST['recon']
        scope_geom = request.POST.get('scope_geom', False)
        aug_geoms = request.POST.get('accept_geoms', False)
        aug_names = request.POST.get('accept_names', False)
        geonames = request.POST.get('no_geonames', False)
        # print('ds_recon() aug_geoms', aug_geoms)
        # print('ds_recon() aug_names', aug_names)
        # print('ds_recon() geonames', geonames)  # on/off

        language = request.LANGUAGE_CODE
        if auth == 'idx' and ds.public == False and test == 'off':
            messages.add_message(request, messages.ERROR, """Dataset must be public before indexing!""")
            return redirect('/datasets/' + str(ds.id) + '/addtask')
        # previous successful task of this type?
        #   wdlocal? archive previous, scope = unreviewed
        #   idx? scope = unindexed
        # collection_id = request.POST.get('collection_id')
        previous = ds.tasks.filter(task_name='align_' + auth, status='SUCCESS')
        prior = request.POST.get('prior', 'na')
        if previous.count() > 0:  # there is a previous task
            if auth == 'idx':
                scope = "unindexed"
            else:  # wdlocal
                # get its id and archive it
                tid = previous.first().task_id
                task_archive(tid, prior)
                scope = 'unreviewed'
                print('recon(): archived previous task')
                print('ds_recon(): links & geoms were ' + ('kept' if prior == 'keep' else 'zapped'))
        else:
            # no existing task, submit all rows
            # print('ds_recon(): no previous, submitting all')
            scope = 'all'

        print('ds_recon() scope', scope)
        print('ds_recon() auth', auth)
        # which task? wdlocal, idx, builder. wdgn
        func = eval('align_' + auth)

        # TODO: let this vary per task?
        region = request.POST['region']  # pre-defined UN regions
        userarea = request.POST['userarea']  # from ccodes, or drawn
        # aug_geom = request.POST['geom'] if 'geom' in request.POST else ''  # on == write geom if matched
        bounds = {
            "type": ["region" if region != "0" else "userarea"],
            "id": [region if region != "0" else userarea]}

        # check Celery service
        if not celeryUp():
            print('Celery is down :^(')
            emailer('Celery is down :^(',
                    'if not celeryUp() -- look into it!',
                    'whg@kgeographer.org',
                    ['karlg@kgeographer.org'])
            messages.add_message(request, messages.INFO, """Sorry! The WHG reconciliation service appears to be down.
        The system administrator has been notified.""")
            return redirect('/datasets/' + str(ds.id) + '/reconcile')

        # 4ce548e4-b765-4f04-aaf6-2824da89f385

        # initiate celery/redis task
        # needs positional and declared ds.id; don't know why
        try:
            result = func.delay(
                ds.id,
                ds=ds.id,
                dslabel=ds.label,
                owner=ds.owner.id,
                user=user.id,
                bounds=bounds,
                aug_geoms=aug_geoms,  # accept geoms
                aug_names=aug_names,  # accept names
                scope=scope,  # all/unreviewed
                scope_geom=scope_geom,  # all/geom_free
                geonames=geonames,  # on/off
                lang=language,
                test=test,  # for idx only
            )
            messages.add_message(request, messages.INFO,
                                 "<span class='text-danger'>Your reconciliation task is under way.</span><br/>When complete, you will receive an email and if successful, results will appear below (you may have to refresh screen). <br/>In the meantime, you can navigate elsewhere.")
            return redirect('/datasets/' + str(ds.id) + '/reconcile')
        except:
            print('failed: align_' + auth)
            print(sys.exc_info())
            messages.add_message(request, messages.INFO,
                                 "Sorry! Reconciliation services appear to be down. The system administrator has been notified.<br/>" + str(
                                     sys.exc_info()))
            emailer('WHG recon task failed',
                    'a reconciliation task has failed for dataset #' + str(ds.id) + ', w/error: \n' + str(
                        sys.exc_info()) + '\n\n',
                    'whg@kgeographer.org',
                    'karl@kgeographer.org')

            return redirect('/datasets/' + str(ds.id) + '/reconcile')


"""
  task_delete(tid, scope)
  delete results of a reconciliation task:
  hits + any geoms and links added by review
  reset Place.review_{auth} to null
"""


# TODO: needs overhaul to account for ds.ds_status
def task_delete(request, tid, scope="foo"):
    hits = Hit.objects.all().filter(task_id=tid)
    tr = TaskResult.objects.get(task_id=tid)
    auth = tr.task_name[6:]  # wdlocal, idx
    dsid = int(tr.task_args[2:-3])
    kwargs = ast.literal_eval(tr.task_kwargs.strip('"'))
    test = kwargs["test"] if "test" in kwargs else "off"
    # test = json.loads(tr.task_kwargs[1:-1].replace("'", '"'))['test'] \
    #   if 'test' in tr.task_kwargs else 'off'
    ds = get_object_or_404(Dataset, pk=dsid)
    ds_status = ds.ds_status
    print('task_delete() dsid', dsid)
    # return HttpResponse(
    #   content='<h3>stopped task_delete()</h3>')

    # only the places that had hit(s) in this task
    places = Place.objects.filter(id__in=[h.place_id for h in hits])
    # links and geometry added by a task have the task_id
    placelinks = PlaceLink.objects.all().filter(task_id=tid)
    placegeoms = PlaceGeom.objects.all().filter(task_id=tid)
    placenames = PlaceName.objects.all().filter(task_id=tid)
    print('task_delete()', {'tid': tr, 'dsid': dsid, 'auth': auth})

    # reset Place.review_{auth} to null
    for p in places:
        if auth in ['whg', 'idx']:
            p.review_whg = None
        elif auth.startswith('wd'):
            p.review_wd = None
        else:
            p.review_tgn = None
        p.defer_comments.delete()
        p.save()

    # zap task record & its hits
    # or only geoms if that was the choice
    if scope == 'task':
        tr.delete()
        hits.delete()
        placelinks.delete()
        placegeoms.delete()
        placenames.delete()
    elif scope == 'geoms':
        placegeoms.delete()

    # delete dataset from index
    # undoes any acceessioning work
    if auth in ['whg', 'idx'] and test == 'off':
        removeDatasetFromIndex('whg', dsid)

    # set status
    print('ds.tasks.all()', ds.tasks.all())
    print('ds.file.file.name', ds.file.file.name)
    # last SUCCESS task is gone, back to 'uploaded' or 'remote'
    # 'remote' is new empty datasets created by API POST
    if ds.tasks.filter(status='SUCCESS').count() == 0:
        if ds.file.file.name.startswith('dummy'):
            ds.ds_status = 'remote'
        else:
            ds.ds_status = 'uploaded'
    ds.save()

    return redirect('/datasets/' + str(dsid) + '/status')


"""
  task_archive(tid, scope, prior)
  delete hits
  if prior = 'zap: delete geoms and links added by review
  reset Place.review_{auth} to null
  set task status to 'ARCHIVED'
"""


def task_archive(tid, prior):
    hits = Hit.objects.all().filter(task_id=tid)
    tr = get_object_or_404(TaskResult, task_id=tid)
    dsid = tr.task_args[1:-1]
    auth = tr.task_name[6:]
    places = Place.objects.filter(id__in=[h.place_id for h in hits])
    print('task_archive()', {'tid': tr, 'dsid': dsid, 'auth': auth})

    # reset Place.review_{auth} to null
    for p in places:
        p.defer_comments.delete()
        if auth in ['whg', 'idx'] and p.review_whg != 1:
            p.review_whg = None
        elif auth.startswith('wd') and p.review_wd != 1:
            p.review_wd = None
        elif auth == 'tgn' and p.review_tgn != 1:
            p.review_tgn = None
        p.save()

    # zap hits
    hits.delete()
    if prior == 'na':
        tr.delete()
    else:
        # flag task as ARCHIVED
        tr.status = 'ARCHIVED'
        tr.save()
        # zap prior links/geoms if requested
        if prior == 'zap':
            PlaceLink.objects.all().filter(task_id=tid).delete()
            PlaceGeom.objects.all().filter(task_id=tid).delete()


"""
  add collaborator to dataset in role
"""


def collab_add(request, dsid, v):
    print('collab_add() request, dsid', request, dsid)
    try:
        uid = get_object_or_404(User, email=request.POST['email']).id
        role = request.POST['role']
    except:
        # TODO: raise error to screen
        messages.add_message(
            request, messages.INFO, "Please check email, we don't have '" + request.POST['email'] + "'")
        if not v:
            return redirect('/datasets/' + str(dsid) + '/collab')
        else:
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    print('collab_add():', request.POST['email'], role, dsid, uid)
    DatasetUser.objects.create(user_id_id=uid, dataset_id_id=dsid, role=role)
    if v == '1':
        return redirect('/datasets/' + str(dsid) + '/collab')
    else:
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


"""
  collab_delete(uid, dsid)
  remove collaborator from dataset
"""


def collab_delete(request, uid, dsid, v):
    print('collab_delete() request, uid, dsid', request, uid, dsid)
    get_object_or_404(DatasetUser, user_id_id=uid, dataset_id_id=dsid).delete()
    if v == '1':
        return redirect('/datasets/' + str(dsid) + '/collab')
    else:
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


"""
  dataset_file_delete(ds)
  delete all uploaded files for a dataset
"""


def dataset_file_delete(ds):
    dsf_list = ds.files.all()
    for f in dsf_list:
        ffn = 'media/' + f.file.name
        if os.path.exists(ffn) and f.file.name != 'dummy_file.txt':
            os.remove(ffn)
            print('zapped file ' + ffn)
        else:
            print('did not find or ignored file ' + ffn)


"""
  update_rels_tsv(pobj, row) refactored 26 Nov 2022 (backup below)
  updates objects related to a Place (pobj)
  make new child objects of pobj: names, types, whens, related, descriptions
  for geoms and links, add from row if not there
  row is a pandas dict
"""


def update_rels_tsv(pobj, row):
    header = list(row.keys())
    # print('update_rels_tsv(): pobj, row, header', pobj, row, header)
    src_id = row['id']
    title = row['title']
    # TODO: leading parens problematic for search on title
    title = re.sub('^\(.*?\)', '', title).strip()
    title_source = row['title_source']
    title_uri = row['title_uri'] if 'title_uri' in header else ''
    variants = [x.strip() for x in row['variants'].split(';')] \
        if 'variants' in header and row['variants'] not in ['', 'None', None] else []

    types = [x.strip() for x in row['types'].split(';')] \
        if 'types' in header and str(row['types']) not in ['', 'None', None] else []

    aat_types = [x.strip() for x in row['aat_types'].split(';')] \
        if 'aat_types' in header and str(row['aat_types']) not in ['', 'None', None] else []

    parent_name = row['parent_name'] if 'parent_name' in header else ''

    parent_id = row['parent_id'] if 'parent_id' in header else ''

    # empty lon and lat are None
    coords = makeCoords(row['lon'], row['lat']) \
        if 'lon' in header and 'lat' in header and row['lon'] else []
    print('coords', coords)
    try:
        matches = [x.strip() for x in row['matches'].split(';')] \
            if 'matches' in header and row['matches'] else []
    except:
        print('matches, error', row['matches'], sys.exc_info())

    description = row['description'] \
        if row['description'] else ''

    # lists for associated objects
    objs = {"PlaceName": [], "PlaceType": [], "PlaceGeom": [], "PlaceWhen": [],
            "PlaceLink": [], "PlaceRelated": [], "PlaceDescription": []}

    # title as a PlaceName
    objs['PlaceName'].append(
        PlaceName(
            place=pobj,
            src_id=src_id,
            toponym=title,
            jsonb={"toponym": title, "citation": {"id": title_uri, "label": title_source}}
        ))

    # add variants as PlaceNames, if any
    if len(variants) > 0:
        for v in variants:
            haslang = re.search("@(.*)$", v.strip())
            new_name = PlaceName(
                place=pobj,
                src_id=src_id,
                toponym=v.strip(),
                jsonb={"toponym": v.strip(), "citation": {"id": "", "label": title_source}}
            )
            if haslang:
                new_name.jsonb['lang'] = haslang.group(1)
            objs['PlaceName'].append(new_name)
    print('objs after names', objs)
    #
    # PlaceType()
    print('types', types)
    if len(types) > 0:
        for i, t in enumerate(types):
            fclass_list = []
            # i always 0 in tsv
            aatnum = 'aat:' + aat_types[i] if len(aat_types) >= len(types) else None
            # get fclass(es) to add to Place (pobj)
            if aatnum and int(aatnum[4:]) in Type.objects.values_list('aat_id', flat=True):
                fc = get_object_or_404(Type, aat_id=int(aatnum[4:])).fclass
                fclass_list.append(fc)
            objs['PlaceType'].append(
                PlaceType(
                    place=pobj,
                    src_id=src_id,
                    jsonb={"identifier": aatnum,
                           "sourceLabel": t,
                           "label": aat_lookup(int(aatnum[4:])) if aatnum != 'aat:' else ''
                           }
                ))
        pobj.fclasses = fclass_list
        pobj.save()
    print('objs after types', objs)

    #
    # PlaceGeom()
    # TODO: test no existing identical geometry
    print('coords', coords)
    if len(coords) > 0:
        geom = {"type": "Point",
                "coordinates": coords,
                "geowkt": 'POINT(' + str(coords[0]) + ' ' + str(coords[1]) + ')'}
    elif 'geowkt' in header and row['geowkt'] not in ['', None]:  # some rows no geom
        geom = parse_wkt(row['geowkt'])
        print('from geowkt', geom)
    else:
        geom = None
    print('geom', geom)
    # TODO:
    # if pobj is existing place, add geom only if it's new
    # if pobj is new place and row has geom, always add it
    if geom:
        def trunc4(val):
            return round(val, 4)

        new_coords = list(map(trunc4, list(geom['coordinates'])))

        # if no geoms, add this one
        if pobj.geoms.count() == 0:
            objs['PlaceGeom'].append(
                PlaceGeom(
                    place=pobj,
                    src_id=src_id,
                    jsonb=geom,
                    geom=GEOSGeometry(json.dumps(geom))
                ))
        # otherwise only add if coords don't match
        elif pobj.geoms.count() > 0:
            try:
                for g in pobj.geoms.all():
                    print('exist. coords', list(map(trunc4, g.jsonb['coordinates'])))
                    print('new_coords', new_coords)
                    if list(map(trunc4, g.jsonb['coordinates'])) != new_coords:
                        objs['PlaceGeom'].append(
                            PlaceGeom(
                                place=pobj,
                                src_id=src_id,
                                jsonb=geom,
                                geom=GEOSGeometry(json.dumps(geom))
                            ))
            except:
                print('failed on ', pobj, sys.exc_info())
    print('objs after geom', objs)

    # PlaceLink() - all are closeMatch
    # Pandas turns nulls into NaN strings, 'nan'
    print('matches', matches)
    if len(matches) > 0:
        # any existing? only add new
        exist_links = list(pobj.links.all().values_list('jsonb__identifier', flat=True))
        print('matches, exist_links at create', matches, exist_links)
        if len(set(matches) - set(exist_links)) > 0:
            # one or more new matches; add 'em
            for m in matches:
                objs['PlaceLink'].append(
                    PlaceLink(
                        place=pobj,
                        src_id=src_id,
                        jsonb={"type": "closeMatch", "identifier": m}
                    ))
    # print('objs after matches', objs)

    #
    # PlaceRelated()
    if parent_name != '':
        objs['PlaceRelated'].append(
            PlaceRelated(
                place=pobj,
                src_id=src_id,
                jsonb={
                    "relationType": "gvp:broaderPartitive",
                    "relationTo": parent_id,
                    "label": parent_name}
            ))
    # print('objs after related', objs)

    # PlaceWhen()
    # timespans[{start{}, end{}}], periods[{name,id}], label, duration
    objs['PlaceWhen'].append(
        PlaceWhen(
            place=pobj,
            src_id=src_id,
            jsonb={
                "timespans": [{
                    "start": {"earliest": pobj.minmax[0]},
                    "end": {"latest": pobj.minmax[1]}}]
            }
        ))
    # print('objs after when', objs)

    #
    # PlaceDescription()
    # @id, value, lang
    print('description', description)
    if description != '':
        objs['PlaceDescription'].append(
            PlaceDescription(
                place=pobj,
                src_id=src_id,
                jsonb={
                    "@id": "", "value": description, "lang": ""
                }
            ))

    print('objs after all', objs)

    # what came from this row
    print('COUNTS:')
    print('PlaceName:', len(objs['PlaceName']))
    print('PlaceType:', len(objs['PlaceType']))
    print('PlaceGeom:', len(objs['PlaceGeom']))
    print('PlaceLink:', len(objs['PlaceLink']))
    print('PlaceRelated:', len(objs['PlaceRelated']))
    print('PlaceWhen:', len(objs['PlaceWhen']))
    print('PlaceDescription:', len(objs['PlaceDescription']))
    # no depictions in LP-TSV

    # TODO: update place.fclasses, place.minmax, place.timespans

    # bulk_create(Class, batch_size=n) for each
    PlaceName.objects.bulk_create(objs['PlaceName'], batch_size=10000)
    print('names done')
    PlaceType.objects.bulk_create(objs['PlaceType'], batch_size=10000)
    print('types done')
    PlaceGeom.objects.bulk_create(objs['PlaceGeom'], batch_size=10000)
    print('geoms done')
    PlaceLink.objects.bulk_create(objs['PlaceLink'], batch_size=10000)
    print('links done')
    PlaceRelated.objects.bulk_create(objs['PlaceRelated'], batch_size=10000)
    print('related done')
    PlaceWhen.objects.bulk_create(objs['PlaceWhen'], batch_size=10000)
    print('whens done')
    PlaceDescription.objects.bulk_create(objs['PlaceDescription'], batch_size=10000)
    print('descriptions done')


"""
  ds_update() refactored 26 Nov 2022 (backup below)
  perform updates to database and index, given ds_compare() results
  params: dsid, format, keepg, keepl, compare_data (json string)
"""
""" TEST VALUES
    from datasets.models import Dataset, DatasetFile
    from django.shortcuts import get_object_or_404
    ds=Dataset.objects.get(id=1460)
    dsid=1460
    ds_places = ds.places.all()
    from django.test import Client
    import pandas as pd
    import numpy as np
    import datetime, re
    file_format = 'delimited'
    keepg, keepl = [True, True]
    compare_data={'id': '1460', 'filename_cur': 'user_whgadmin/sample7h.txt', 'filename_new': 'user_whgadmin/sample7h_new.txt', 'format': 'delimited', 'validation_result': {'format': 'delimited', 'errors': [], 'columns': ['id', 'title', 'title_source', 'start', 'end', 'title_uri', 'ccodes', 'variants', 'types', 'aat_types', 'matches', 'lon', 'lat', 'geowkt', 'geo_source', 'geo_id', 'description'], 'count': 0}, 'tempfn': '/var/folders/w1/ms_2x6rj0ls88v79q33lvds80000gp/T/tmpo40rw66r', 'count_indexed': 7, 'count_links_added': 5, 'count_geoms_added': 5, 'compare_result': {'count_new': 7, 'count_diff': 0, 'count_replace': 6, 'cols_del': [], 'cols_add': ['title_uri', 'description'], 'header_new': ['id', 'title', 'title_source', 'start', 'end', 'title_uri', 'ccodes', 'variants', 'types', 'aat_types', 'matches', 'lon', 'lat', 'geowkt', 'geo_source', 'geo_id', 'description'], 'rows_add': ['717_4'], 'rows_del': ['717_2']}}

    compare_result = compare_data['compare_result']
    tempfn = compare_data['tempfn']
    filename_new = compare_data['filename_new']
    dsfobj_cur = ds.files.all().order_by('-rev')[0]
    rev_num = dsfobj_cur.rev
    from pathlib import Path
    from shutil import copyfile
    if Path('media/'+filename_new).exists():
      fn=os.path.splitext(filename_new)
      #filename_new=filename_new[:-4]+'_'+tempfn[-11:-4]+filename_new[-4:]
      filename_new=fn[0]+'_'+tempfn[-11:-4]+fn[1]
    filepath = 'media/'+filename_new
    copyfile(tempfn,filepath)
"""


def ds_update(request):
    if request.method == 'POST':
        print('request.POST ds_update()', request.POST)
        dsid = request.POST['dsid']
        ds = get_object_or_404(Dataset, id=dsid)
        file_format = request.POST['format']

        # keep previous recon/review results?
        keepg = request.POST['keepg']
        keepl = request.POST['keepl']
        print('keepg, keepl', keepg, keepl)

        # comparison returned by ds_compare
        compare_data = json.loads(request.POST['compare_data'])
        compare_result = compare_data['compare_result']
        print('compare_data from ds_compare', compare_data)

        # tempfn has .tsv or .jsonld extension from validation step
        tempfn = compare_data['tempfn']
        filename_new = compare_data['filename_new']
        dsfobj_cur = ds.files.all().order_by('-rev')[0]
        rev_num = dsfobj_cur.rev

        # rename file if already exists in user area
        if Path('media/' + filename_new).exists():
            fn = os.path.splitext(filename_new)
            # filename_new=filename_new[:-4]+'_'+tempfn[-11:-4]+filename_new[-4:]
            filename_new = fn[0] + '_' + tempfn[-11:-4] + fn[1]

        # user said go...copy tempfn to media/{user} folder
        filepath = 'media/' + filename_new
        copyfile(tempfn, filepath)

        # and create new DatasetFile; increment rev
        DatasetFile.objects.create(
            dataset_id=ds,
            file=filename_new,
            rev=rev_num + 1,
            format=file_format,
            upload_date=datetime.date.today(),
            header=compare_result['header_new'],
            numrows=compare_result['count_new']
        )

        # reopen new file as panda dataframe bdf
        if file_format == 'delimited':
            try:
                bdf = pd.read_csv(filepath, delimiter='\t')

                # replace pandas NaN with None
                bdf = bdf.replace({np.nan: ''})
                # bdf = bdf.replace({np.nan: None})
                # force data types
                bdf = bdf.astype({"id": str, "ccodes": str, "types": str, "aat_types": str})
                print('reopened new file, # lines:', len(bdf))
            except:
                raise

            # CURRENT PLACES
            ds_places = ds.places.all()
            print('ds_places', ds_places)
            # pids of missing src_ids
            rows_delete = list(ds_places.filter(src_id__in=compare_result['rows_del']).values_list('id', flat=True))
            print('rows_delete', rows_delete)  # 6880702

            # CASCADE includes links & geoms
            try:
                ds_places.filter(id__in=rows_delete).delete()
            except:
                raise

            # for use below
            def delete_related(pid):
                # option to keep prior links and geoms matches; remove the rest
                if not keepg:
                    # keep no geoms
                    PlaceGeom.objects.filter(place_id=pid).delete()
                else:
                    # leave results of prior matches
                    PlaceGeom.objects.filter(place_id=pid, task_id__isnull=True).delete()
                if not keepl:
                    # keep no links
                    PlaceLink.objects.filter(place_id=pid).delete()
                else:
                    # leave results of prior matches
                    PlaceLink.objects.filter(place_id=pid, task_id__isnull=True).delete()
                PlaceName.objects.filter(place_id=pid).delete()
                PlaceType.objects.filter(place_id=pid).delete()
                PlaceWhen.objects.filter(place_id=pid).delete()
                PlaceRelated.objects.filter(place_id=pid).delete()
                PlaceDescription.objects.filter(place_id=pid).delete()

            # counts for report
            count_new, count_replaced, count_redo = [0, 0, 0]
            # pids for index operations
            rows_add = []
            idx_delete = []

            place_fields = {'id', 'title', 'ccodes', 'start', 'end', 'attestation_year'}
            alldiffs = []
            # bdfx=bdf.iloc[1:]
            # for index, row in bdfx.iterrows():
            for index, row in bdf.iterrows():
                # row=bdf.iloc[1]
                # new row as dict
                row = row.to_dict()
                print('row as dict', row)

                start = int(row['start']) if 'start' in row else int(row['attestation_year']) \
                    if ('attestation_year' in row) else None
                end = int(row['end']) if 'end' in row and str(row['end']) != 'nan' else start
                minmax_new = [start, end] if start else [None]

                # extract coords from upload file
                row_coords = makeCoords(row['lon'], row['lat']) \
                    if row['lon'] and row['lat'] else None
                if row['geowkt']:
                    gtype = wkt.loads(row['geowkt']).type
                    if 'Multi' not in gtype:
                        row_coords = [list(u) for u in wkt.loads(row['geowkt']).coords]
                    else:
                        row_coords = [list(u) for u in wkt.loads(row['geowkt']).xy]
                # all columns in mew file
                header = list(bdf.keys())
                # row_mapper = [{k: row[k]} for k in header]
                row_mapper = {
                    'src_id': row['id'],
                    'title': row['title'],
                    'minmax': minmax_new,
                    'title_source': row['title_source'] if 'title_source' in header else '',
                    'title_uri': row['title_uri'] if 'title_uri' in header else '',
                    'ccodes': row['ccodes'].split(';') if 'ccodes' in header and row['ccodes'] else [],
                    'matches': row['matches'].split(';') if 'matches' in header and row['matches'] else [],
                    'variants': row['variants'].split(';') if 'variants' in header and row['variants'] else [],
                    'types': row['types'].split(';') if 'types' in header and row['types'] else [],
                    'aat_types': row['aat_types'].split(';') if 'aat_types' in header and row['aat_types'] else [],
                    'parent_name': row['parent_name'] if 'parent_name' in header else '',
                    'parent_id': row['parent_id'] if 'parent_id' in header else '',
                    'geo_source': row['geo_source'] if 'geo_source' in header else '',
                    'geo_id': row['geo_id'] if 'geo_id' in header else '',
                    'description': row['description'] if 'description' in header else '',
                    'coords': row_coords or [],
                }

                try:
                    # is there corresponding current Place?
                    p = ds_places.get(src_id=row['id'])
                    # fetch existing API record
                    c = Client()
                    from datasets.utils import PlaceMapper
                    try:
                        # result = c.get('/api/place_compare/' + str(6873911) + '/')
                        result = c.get('/api/place_compare/' + str(p.id) + '/')
                        pobj = result.json()
                        pobj = {key: val for key, val in sorted(pobj.items(), key=lambda ele: ele[0])}
                    except:
                        print('pobj failed', p.id, sys.exc_info())

                    # build object for comparison
                    # TODO: build separate serializer(s) for this? performance?
                    p_mapper = PlaceMapper(
                        pobj['id'],
                        pobj['src_id'],
                        pobj['title'],
                    )

                    # id,title,title_source,title_uri,ccodes,matches,variants,types,aat_types,
                    # parent_name,parent_id,geo_source,geo_id,description
                    # add key:value pairs to consider
                    p_mapper['minmax'] = pobj['minmax']
                    title_name = next(n for n in pobj['names'] if n['toponym'] == pobj['title']) or None
                    p_mapper['title_source'] = title_name['citation']['label'] if \
                        'citation' in title_name and 'label' in title_name['citation'] else ''
                    p_mapper['title_id'] = title_name['citation']['id'] if \
                        'citation' in title_name and 'id' in title_name['citation'] else ''
                    p_mapper['ccodes'] = pobj['ccodes'] or []
                    p_mapper['types'] = [t['sourceLabel'] for t in pobj['types']] or []
                    p_mapper['aat_types'] = [t['identifier'][4:] for t in pobj['types']] or []
                    p_mapper['variants'] = [n['toponym'] for n in pobj['names'] if n['toponym'] != pobj['title']] or []
                    p_mapper['coords'] = [g['coordinates'] for g in pobj['geoms']] or []

                    p_mapper['geo_sources'] = [g['citation']['label'] for g in pobj['geoms'] \
                                               if 'citation' in g and 'label' in g['citation']] or []
                    p_mapper['geo_ids'] = [g['citation']['id'] for g in pobj['geoms'] \
                                           if 'citation' in g and 'id' in g['citation']] or []

                    p_mapper['links'] = [l['identifier'] for l in pobj['links']] or []
                    p_mapper['related'] = [r['label'] for r in pobj['related']]
                    p_mapper['related_id'] = [r['identifier'] for r in pobj['related']]
                    p_mapper['descriptions'] = [d['value'] for d in pobj['related']]

                    # diff incoming (row_mapper) & database (p_mapper)
                    # meaningful = title, variants, aat_types, links/matches, coords
                    diffs = []

                    # [:8] not meaningful (don't affect reconciliation)
                    diffs.append(
                        row_mapper['title_source'] == p_mapper['title_source'] if row_mapper['title_source'] else True)
                    diffs.append(row_mapper['title_uri'] == p_mapper['title_id'] if row_mapper['title_uri'] else True)
                    diffs.append(
                        row_mapper['parent_name'] in p_mapper['related'] if row_mapper['parent_name'] else True)
                    diffs.append(row_mapper['parent_id'] in p_mapper['related_id'] if row_mapper['parent_id'] else True)
                    diffs.append(
                        row_mapper['geo_source'] in p_mapper['geo_sources'] if row_mapper['geo_source'] != '' else True)
                    diffs.append(row_mapper['geo_id'] in p_mapper['geo_ids'] if row_mapper['geo_id'] != '' else True)
                    diffs.append(
                        row_mapper['description'] in p_mapper['descriptions'] if row_mapper['description'] else True)
                    diffs.append(row_mapper['minmax'] == p_mapper['minmax'])
                    diffs.append(sorted(row_mapper['types']) == sorted(p_mapper['types']))

                    # [9:] meaningful
                    diffs.append(row_mapper['title'] == p_mapper['title'])
                    diffs.append(sorted(row_mapper['variants']) == sorted(p_mapper['variants']))
                    diffs.append(sorted(row_mapper['aat_types']) == sorted(p_mapper['aat_types']))
                    diffs.append(sorted(row_mapper['matches']) == sorted(p_mapper['links']))
                    diffs.append(sorted(row_mapper['ccodes']) == sorted(p_mapper['ccodes']))
                    if row_mapper['coords'] != []:
                        diffs.append(row_mapper['coords'] == p_mapper['coords'])

                    print('diffs', diffs)
                    alldiffs.append({'title': row_mapper['title'], 'diffs': diffs})

                    # update Place record in all cases
                    count_replaced += 1
                    p.title = row_mapper['title']
                    p.ccodes = row_mapper['ccodes']
                    p.minmax = minmax_new
                    p.timespans = [minmax_new]

                    if False in diffs:
                        # there was SOME change(s) -> add to delete-from-index list
                        # (will be reindexed after re-reconciling)
                        idx_delete.append(p.id)
                    if False not in diffs[9:]:
                        # no meaningful changes
                        # replace related, preserving geoms & links if keepg, keepl
                        # leave review_wd and flag status intact
                        delete_related(p)
                        update_rels_tsv(p, row)
                    else:
                        # meaningful change(s) exist
                        count_redo += 1
                        # replace related, including geoms and links
                        keepg, keepl = [False, False]
                        delete_related(p)
                        update_rels_tsv(p, row)

                        # (re)set Place.review_wd & Place.flag (needs reconciliation)
                        p.review_wd = None
                        p.flag = True

                        # meaningful change, so
                        # add to list for index deletion
                        if p.id not in idx_delete:
                            idx_delete.append(p.id)

                    p.save()
                except:
                    # no corresponding Place, create new one
                    print('new place record needed from rdp', row)
                    count_new += 1
                    newpl = Place.objects.create(
                        src_id=row['id'],
                        title=re.sub('\(.*?\)', '', row['title']),
                        ccodes=[] if str(row['ccodes']) == 'nan' else row['ccodes'].replace(' ', '').split(';'),
                        dataset=ds,
                        minmax=minmax_new,
                        timespans=[minmax_new],
                        # flax for reconciling
                        flag=True
                    )
                    newpl.save()
                    pobj = newpl
                    rows_add.append(pobj.id)
                    print('new place, related:', newpl)
                    # add related rcords (PlaceName, PlaceType, etc.)
                    update_rels_tsv(pobj, row)
                # except:
                #   print('update failed on ', row)
                #   print('error', sys.exc_info())

            # update numrows
            ds.numrows = ds.places.count()
            ds.save()

            # initiate a result object
            result = {"status": "updated", "format": file_format,
                      "update_count": count_replaced, "redo_count": count_redo,
                      "new_count": count_new, "deleted_count": len(rows_delete),
                      "newfile": filepath}

            print('update result', result)
            print("compare_data['count_indexed']", compare_data['count_indexed'])

            #
            if compare_data['count_indexed'] > 0:
                result["indexed"] = True

                # surgically remove as req.
                # rows_delete(gone from db) + idx_delete(rows with meaningful change)
                idx_delete = rows_delete + idx_delete
                print('idx_delete', idx_delete)
                if len(idx_delete) > 0:
                    es = settings.ES_CONN
                    idx = settings.ES_WHG
                    print('pids to delete from index:', idx_delete)
                    removePlacesFromIndex(es, idx, idx_delete)
            else:
                print('not indexed, that is all')

            # write log entry
            Log.objects.create(
                # category, logtype, "timestamp", subtype, note, dataset_id, user_id
                category='dataset',
                logtype='ds_update',
                note=json.dumps(compare_result),
                dataset_id=dsid,
                # user_id = 1
                user_id=request.user.id
            )
            ds.ds_status = 'updated'
            ds.save()
            # return to update modal
            return JsonResponse(result, safe=False)
        elif file_format == 'lpf':
            print("ds_update for lpf; doesn't get here yet")


"""
  PublicListView()
  list public datasets and collections
"""


class PublicListsView(ListView):
    redirect_field_name = 'redirect_to'

    context_object_name = 'dataset_list'
    template_name = 'datasets/public_list.html'
    model = Dataset

    def get_queryset(self):
        # original qs
        qs = super().get_queryset()
        return qs.filter(public=True).order_by('core', 'title')

    def get_context_data(self, *args, **kwargs):
        context = super(PublicListsView, self).get_context_data(*args, **kwargs)

        # public datasets available as dataset_list
        # public collections
        context['coll_list'] = Collection.objects.filter(status='published').order_by('create_date')
        context['viewable'] = ['uploaded', 'inserted', 'reconciling', 'review_hits', 'reviewed', 'review_whg',
                               'indexed']

        context['beta_or_better'] = True if self.request.user.groups.filter(
            name__in=['beta', 'admins']).exists() else False
        return context


"""
  DatasetCreateEmptyView()
  initial create, no file; for remote, typically
"""


class DatasetCreateEmptyView(LoginRequiredMixin, CreateView):
    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'

    form_class = DatasetCreateEmptyModelForm
    template_name = 'datasets/dataset_create_empty.html'
    success_message = 'empty dataset created'

    def form_invalid(self, form):
        print('form invalid...', form.errors.as_data())
        context = {'form': form}
        return self.render_to_response(context=context)

    def form_valid(self, form):
        data = form.cleaned_data
        print('cleaned_data', data)
        context = {"format": "empty"}
        # context={"format":data['format']}
        user = self.request.user
        # validated -> create Dataset, DatasetFile, Log instances,
        # advance to dataset_detail
        # else present form again with errors
        # if len(result['errors']) == 0:
        context['status'] = 'format_ok'

        # print('validated, no errors')
        # print('validated, no errors; result:', result)
        nolabel = form.cleaned_data["label"] == ''
        # new Dataset record ('owner','id','label','title','description')
        dsobj = form.save(commit=False)
        dsobj.ds_status = 'format_ok'
        dsobj.numrows = 0
        clean_label = form.cleaned_data['label'].replace(' ', '_')
        if not form.cleaned_data['uri_base']:
            dsobj.uri_base = 'https://whgazetteer.org/api/db/?id='

        # links will be counted later on insert
        dsobj.numlinked = 0
        dsobj.total_links = 0
        try:
            dsobj.save()
            ds = Dataset.objects.get(id=dsobj.id)
            label = 'ds_' + str(ds.id)
            print('new dataset label', 'ds_' + label)
            # generate a unique label if none was entered
            if dsobj.label == '':
                ds.label = 'ds_' + str(dsobj.id)
                ds.save()
        except:
            # self.args['form'] = form
            return render(self.request, 'datasets/dataset_create.html', self.args)

        #
        # create user directory if necessary
        userdir = r'media/user_' + user.id + '/'
        if not Path(userdir).exists():
            os.makedirs(userdir)

        # build path, and rename file if already exists in user area
        # file_exists = Path(userdir+filename).exists()
        # if not file_exists:
        #   filepath = userdir+filename
        # else:
        #   splitty = filename.split('.')
        #   filename=splitty[0]+'_'+tempfn[-7:]+'.'+splitty[1]
        #   filepath = userdir+filename

        # write log entry
        Log.objects.create(
            # category, logtype, "timestamp", subtype, dataset_id, user_id
            category='dataset',
            logtype='ds_create_empty',
            subtype=data['datatype'],
            dataset_id=dsobj.id,
            user_id=user.id
        )

        # create initial DatasetFile record
        DatasetFile.objects.create(
            dataset_id=dsobj,
            file='dummy_file.txt',
            rev=1,
            format='delimited',
            delimiter='n/a',
            df_status='dummy',
            upload_date=None,
            header=[],
            numrows=0
        )

        # data will be written on load of dataset.html w/dsobj.status = 'format_ok'
        # return redirect('/datasets/'+str(dsobj.id)+'/detail')
        return redirect('/datasets/' + str(dsobj.id) + '/summary')

        # else:
        context['action'] = 'errors'
        # context['format'] = result['format']
        # context['errors'] = parse_errors_lpf(result['errors']) \
        #   if ext == 'json' else parse_errors_tsv(result['errors'])
        # context['columns'] = result['columns'] \
        #   if ext != 'json' else []

        # os.remove(tempfn)

        return self.render_to_response(
            self.get_context_data(
                form=form, context=context
            ))

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetCreateEmptyView, self).get_context_data(*args, **kwargs)
        # context['action'] = 'create'
        return context


"""
  DatasetCreate() helpers
  alternate bot-guided
"""


def get_file_type(file):
    """Determine the file type based on its MIME type."""
    mimetype = file.content_type
    return mthash_plus.mimetypes.get(mimetype, None)


def read_file_into_dataframe(file, ext):
    """
    Reads the given file into a pandas DataFrame based on the provided extension.
    """
    converters = {
        'id': str, 'start': str, 'end': str, 'aat_types': str
    }

    if ext == 'csv':
        df = pd.read_csv(file, sep=',', converters=converters)
    elif ext == 'tsv':
        df = pd.read_csv(file, sep='\t', converters=converters)
    elif ext == 'xlsx' or ext == 'ods':
        df = pd.read_excel(file, converters=converters)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    # Convert 'lon' and 'lat' with error handling, if they exist
    if 'lon' in df.columns:
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    if 'lat' in df.columns:
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')

    # Additional step to coerce 'attestation_year' to integers, with error handling
    if 'attestation_year' in df.columns:
        # df['attestation_year'] = pd.to_numeric(df['attestation_year'], errors='coerce', downcast='integer')
        df['attestation_year'] = pd.to_numeric(df['attestation_year'], errors='coerce').astype('Int64')
    print(df.dtypes)

    return df


# known MIME types for supported file formats
MIME_TYPE_MAPPING = {
    'application/json': 'json',
    'text/csv': 'csv',
    'text/tab-separated-values': 'tsv',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.oasis.opendocument.spreadsheet': 'ods'
}


# brute force check for JSON file
def is_json_file(file):
    try:
        file.seek(0)  # Ensure file pointer is at the start
        json.load(file)
        file.seek(0)  # Reset file pointer after reading
        return True
    except (ValueError, UnicodeDecodeError):
        file.seek(0)  # Reset file pointer on failure
        return False


# """
#   DatasetCreate()
#   2024-06-25; refactored
#   2023-08; replaces DatasetCreateView()
#   - validates form
#   - checks file encoding, gets mimetype
#   - initiates content validation (validation.py)
#   - initiates database writes (insert.py)
#   - raises errors from each stage to dataset_create.html form
# """
# class DatasetCreate(CreateView):
#     login_url = '/accounts/login/'
#     redirect_field_name = 'redirect_to'
#
#     template_name = 'datasets/dataset_create.html'
#     form_class = DatasetUploadForm
#
#     def form_invalid(self, form):
#         # Implement custom logic for invalid form submissions
#         return self.render_to_response(self.get_context_data(form=form))
#
#     def form_valid(self, form):
#
#         user = self.request.user
#         uploaded_file = form.cleaned_data['file']
#
#         temp_file, temp_filepath = None, None
#         try:        
#
#             temp_file, temp_filepath = tempfile.mkstemp()
#             try:
#                 for chunk in uploaded_file.chunks():
#                     os.write(temp_file, chunk)
#             except Exception as e:
#                 messages.error(self.request, f"Error processing the uploaded file: {str(e)}")
#                 return self.form_invalid(form)
#
#             # Check content type of uploaded_file
#             content_type = self.detect_content_type(uploaded_file)
#             if content_type not in ['json', 'csv', 'tsv', 'xlsx', 'ods']:
#                 messages.error(self.request, f"The detected uploaded file content type is not supported. Detected content type: <b>{content_type}</b>")
#                 return self.form_invalid(form)
#
#             if content_type == 'json':
#                 # Check encoding of uploaded_file
#                 try:
#                     uploaded_file.seek(0)
#                     detected_encoding = cn.detect(uploaded_file.read())
#                     print(f"Detected encoding: {detected_encoding['encoding']}, Confidence: {detected_encoding['confidence']}")
#                     allowed_encodings = ['ascii', 'utf-8'] # NOT ANSI; database does not permit 'utf-16', 'utf-32'
#                     if detected_encoding['encoding'].lower() not in allowed_encodings:
#                         messages.error(self.request, f"Sorry, the file does not appear to be UTF or ASCII encoded, and so cannot be processed. Detected encoding: <b>{detected_encoding['encoding']}</b>")
#                         return self.form_invalid(form)
#                 except Exception as e:
#                     print(f"Error detecting file encoding: {e}")
#                     messages.error(self.request, f"Sorry, there was an error while trying to detect encoding in the uploaded file: {str(e)}")
#                     return self.form_invalid(form)
#                 finally:
#                     uploaded_file.seek(0)
#
#                 try:
#                     with open(temp_filepath, 'r', encoding='utf-8') as jsonfile:
#                         jdata = json.load(jsonfile)          
#
#                     result = validate_lpf(jdata, 'coll')
#                 except LPFValidationError as e:
#                     error_list = e.args[0]
#                     message = self.construct_error_message(error_list, "in your file")
#                     messages.error(self.request, message)
#                     return self.form_invalid(form)
#                 except Exception as e:
#                     messages.error(self.request, f"Sorry, there was an error while processing the JSON file: {str(e)}")
#
#                 dataset = form.save(commit=False)
#                 dataset.owner_id = user.id
#                 dataset.uri_base = dataset.uri_base or 'https://whgazetteer.org/api/db/?id='
#                 dataset.save()
#
#                 try:
#                     result = ds_insert_json(jdata, dataset.pk, user)
#                 except Exception as e:
#                     dataset.delete()
#                     messages.error(self.request, f"Failed to insert data into dataset: {str(e)}")
#                     return self.form_invalid(form)
#
#             else: # if delimited text
#                 # Check encoding of uploaded_file   
#                 try:
#                     df = read_file_into_dataframe(temp_filepath, content_type)
#                 except UnicodeDecodeError as e:
#                     messages.error(self.request, f"Sorry, the file does not appear to be UTF-8 encoded, and so cannot be processed.")
#                     return self.form_invalid(form)
#                 except Exception as e:
#                     print("Sorry, the uploaded file could not be processed. Error: {}".format(str(e)))
#                     messages.error(self.request, f"Sorry, the uploaded file cannot be processed as a table.")
#                     return self.form_invalid(form)
#
#                 try:
#                     validate_delim(df)
#                 except DelimValidationError as e:
#                     print("Sorry, the uploaded file could not be processed. Error: {}".format(str(e)))
#                     messages.error(self.request, self.construct_error_message(e.args[0], "in your file"))
#                     return self.form_invalid(form)
#                 except Exception as e:
#                     messages.error(self.request, f"Error validating data: {str(e)}")
#                     return self.form_invalid(form)
#
#                 print('Validation successful.')
#
#                 dataset = form.save(commit=False)
#                 dataset.owner_id = user.id
#                 dataset.uri_base = dataset.uri_base or 'https://whgazetteer.org/api/db/?id='
#                 dataset.save()
#
#                 try:
#                     with transaction.atomic():
#                         skipped_rows = ds_insert_delim(df, dataset.pk)
#                 except DataAlreadyProcessedError:
#                     dataset.delete()
#                     messages.info(self.request, "The data appears already to have been processed.")
#                     return self.form_invalid(form)
#                 except DelimInsertError as e:
#                     dataset.delete()
#                     error_list = e.args[0]
#                     message = self.construct_error_message(error_list, "insertion")
#                     messages.error(self.request, message)
#                     failed_insert_notification(user, file, ds=None)
#                     return self.form_invalid(form)
#
#         except Exception as e:
#             dataset.delete()
#             messages.error(self.request, f"Sorry, there was an error while processing the uploaded file: {str(e)}")
#             return self.form_invalid(form)
#
#         finally:
#             # Ensure temporary file cleanup in case of success or failure
#             if temp_file is not None:
#                 os.close(temp_file)
#             if temp_filepath is not None and os.path.exists(temp_filepath):
#                 os.remove(temp_filepath)
#
#         # If all processing is successful, continue with dataset creation
#         if dataset:
#             dataset.ds_status = 'uploaded'
#             dataset.save()
#
#             DatasetFile.objects.create(
#                 dataset_id=dataset,
#                 file=form.cleaned_data['file'],
#                 rev=1,
#                 format=content_type,
#                 delimiter='\t' if content_type in ['tsv', 'xlsx', 'ods'] else ',' if content_type == 'csv' else 'n/a',
#                 upload_date=timezone.now(),
#                 header=df.columns.tolist() if content_type != 'json' else None,
#                 numrows=len(df) if content_type != 'json' else result['numrows'],
#                 df_status='uploaded'
#             )
#
#             Log.objects.create(
#                 category='dataset',
#                 logtype='ds_create',
#                 subtype='place',
#                 dataset_id=dataset.id,
#                 user_id=user.id
#             )
#
#             return redirect(self.get_success_url(dataset.id))
#         else:
#             messages.error(self.request, "Sorry, there was an error while processing the uploaded file.")
#             return self.form_invalid(form)
#
#     def get_success_url(self, dataset_id):
#         return reverse_lazy('datasets:ds_status', kwargs={'id': dataset_id})
#
#     def detect_content_type(self, uploaded_file):
#         try:
#             mimetype = uploaded_file.content_type
#             content_type = MIME_TYPE_MAPPING.get(mimetype, None)
#
#             print(mimetype, content_type)
#
#             # If the content type has not been determined by MIME type, use file inspection
#             if not content_type:
#               if is_json_file(uploaded_file):
#                 content_type = 'json'
#               else:
#                 content_type = os.path.splitext(uploaded_file.name)[1][1:].lower()
#
#             return content_type
#
#         except Exception as e:
#             print(f"Error detecting content_type: {e}")
#             return None
#
#     def construct_error_message(self, error_list, context):
#         if len(error_list) > 1:
#             message = f"<b>Several errors were found {context}; the first of these are</b>:<ul class='no-indent'>"
#         else:
#             message = f"<b>Errors were found {context}</b>:<ul class='no-indent'>"
#
#         for err in error_list[:15]:
#             row = err.get('row', "Unknown")
#             reason = err.get('error', "Unknown error")
#             message += f"<li>Row {row}: {reason}</li>"
#
#         if len(error_list) > 15:
#             message += "<li>...</li>"
#
#         message += "</ul>"
#         return message

"""
  returns public dataset 'meta' (summary) page
"""


class DatasetPublicView(DetailView):
    template_name = 'datasets/ds_meta.html'

    model = Dataset

    def get_context_data(self, **kwargs):
        context = super(DatasetPublicView, self).get_context_data(**kwargs)
        print('self, kwargs', self, self.kwargs)

        ds = get_object_or_404(Dataset, id=self.kwargs['pk'])
        file = ds.file

        placeset = ds.places.all()

        if file:
            context['current_file'] = file
            context['format'] = file.format
            context['numrows'] = file.numrows
            context['filesize'] = round(file.file.size / 1000000, 1)

            context['links_added'] = PlaceLink.objects.filter(
                place_id__in=placeset, task_id__contains='-').count()
            context['geoms_added'] = PlaceGeom.objects.filter(
                place_id__in=placeset, task_id__contains='-').count()

        return context


"""
  loads page for confirm ok on delete
    - delete dataset, with CASCADE to DatasetFile, places, place_name, etc
    - also deletes from index if indexed (fails silently if not)
    - also removes dataset_file records
"""


# TODO: delete other stuff: disk files; archive??
class DatasetDeleteView(DeleteView):
    template_name = 'datasets/dataset_delete.html'

    def delete_complete(self):
        ds = get_object_or_404(Dataset, pk=self.kwargs.get("id"))
        dataset_file_delete(ds)
        if ds.ds_status == 'indexed':
            pids = list(ds.placeids)
            removePlacesFromIndex(es, 'whg', pids)

    def get_object(self):
        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)
        return (ds)

    def get_context_data(self, **kwargs):
        context = super(DatasetDeleteView, self).get_context_data(**kwargs)
        ds = get_object_or_404(Dataset, id=self.kwargs.get("id"))
        context['owners'] = ds.owners
        return context

    def get_success_url(self):
        self.delete_complete()
        return reverse('dashboard')


"""
  fetch places in specified dataset
  utility used for place collections
"""


def ds_list(request, label):
    print('in ds_list() for', label)
    qs = Place.objects.all().filter(dataset=label)
    geoms = []
    for p in qs.all():
        feat = {"type": "Feature",
                "properties": {"src_id": p.src_id, "name": p.title},
                "geometry": p.geoms.first().jsonb}
        geoms.append(feat)
    return JsonResponse(geoms, safe=False)


"""
  undo last review match action
  - delete any geoms or links created
  - reset flags for hit.reviewed and place.review_xxx
"""


def match_undo(request, ds, tid, pid):
    print('in match_undo() ds, task, pid:', ds, tid, pid)
    from django_celery_results.models import TaskResult
    geom_matches = PlaceGeom.objects.filter(task_id=tid, place_id=pid)
    link_matches = PlaceLink.objects.filter(task_id=tid, place_id=pid)
    geom_matches.delete()
    link_matches.delete()

    # reset place.review_xxx to 0
    tasktype = TaskResult.objects.get(task_id=tid).task_name[6:]
    print('tasktype', tasktype)
    place = Place.objects.get(pk=pid)
    # remove any defer comments
    place.defer_comments.delete()
    # TODO: variable field name?
    if tasktype.startswith('wd'):
        place.review_wd = 0
    elif tasktype == 'tgn':
        place.review_tgn = 0
    else:
        place.review_whg = 0
    place.save()

    # match task_id, place_id in hits; set reviewed = false
    Hit.objects.filter(task_id=tid, place_id=pid).update(reviewed=False)

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


"""
  returns dataset owner summary page
"""


class DatasetStatusView(LoginRequiredMixin, UpdateView):
    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'

    form_class = DatasetDetailModelForm

    template_name = 'datasets/ds_status.html'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Dataset, id=id_)

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetStatusView, self).get_context_data(*args, **kwargs)

        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)
        place_count = ds.places.count()
        wdgn_status = {
            "rows": place_count,
            "got_hits": ds.places.exclude(review_wd=None).count(),
            "reviewed": ds.places.filter(review_wd=1).count(),
            "remain": ds.places.filter(review_wd=0).count() + ds.places.filter(review_wd=2).count(),
            "deferred": ds.places.filter(review_wd=2).count(),
        }

        idx_status = {
            "rows": place_count,
            "got_hits": ds.places.exclude(review_whg=None).count(),
            "reviewed": ds.places.filter(review_whg=1).count(),
            "remain": ds.places.filter(review_whg=0).count(),
            "deferred": ds.places.filter(review_whg=2).count() or 'none',
        }

        context['wdgn_status'] = wdgn_status
        context['idx_status'] = idx_status

        def placecounter(th):
            pcounts = {}
            count0 = th.filter(query_pass='pass0').values('place_id').distinct().count()
            count1 = th.filter(query_pass='pass1').values('place_id').distinct().count()
            count2 = th.filter(query_pass='pass2').values('place_id').distinct().count()
            count0and1 = th.filter(query_pass='pass1, pass0').values('place_id').distinct().count()

            pcounts['p0'] = count0
            pcounts['p1'] = count1
            pcounts['p2'] = count2
            pcounts['p0and1'] = count0and1
            return pcounts

        # omits FAILURE and ARCHIVED
        ds_tasks = ds.tasks.exclude(status='FAILURE').exclude(status='ARCHIVED')
        context['tasks'] = ds_tasks
        # most recent successful, non-archived task for each type
        task_wdgn = ds_tasks.filter(task_name__startswith='align_wd').order_by('-date_done').first()
        context['task_wdgn'] = task_wdgn
        task_idx = ds_tasks.filter(task_name__startswith='align_idx').order_by('-date_done').first()
        context['task_idx'] = task_idx

        # remaining_wdgn = Hit.objects.filter(task_id=task_wdgn.task_id, reviewed=False)
        if task_wdgn is not None:
            remaining_wdgn = Hit.objects.filter(task_id=task_wdgn.task_id, reviewed=False)
            context['wdgn_passes'] = placecounter(remaining_wdgn)
        else:
            context['wdgn_passes'] = {}

        if task_idx is not None:
            remaining_idx = Hit.objects.filter(task_id=task_idx.task_id, reviewed=False)
            context['idx_passes'] = placecounter(remaining_idx)
        else:
            context['idx_passes'] = {}

        me = self.request.user
        placeset = ds.places.all()

        context['updates'] = {}
        context['ds'] = ds
        context['is_collaborator'] = ds.collaborators.filter(id=me.id).exists()
        context['is_owner'] = ds.owners.filter(id=me.id).exists()
        context['is_admin'] = me.groups.filter(name='whg_admins').exists()
        context['is_editorial'] = me.groups.filter(name='editorial').exists()

        # initial (non-task)
        context['num_names'] = PlaceName.objects.filter(place_id__in=placeset).count()
        context['num_links'] = PlaceLink.objects.filter(
            place_id__in=placeset, task_id=None).count()
        context['num_geoms'] = PlaceGeom.objects.filter(
            place_id__in=placeset, task_id=None).count()
        context['numrows'] = ds.places.count()

        # augmentations (has task_id)
        context['links_added'] = PlaceLink.objects.filter(
            place_id__in=placeset, task_id__contains='-').count()
        context['geoms_added'] = PlaceGeom.objects.filter(
            place_id__in=placeset, task_id__contains='-').count()
        context['names_added'] = PlaceName.objects.filter(
            place_id__in=placeset, task_id__contains='-').count()

        context['beta_or_better'] = True if self.request.user.groups.filter(
            name__in=['beta', 'admins']).exists() else False

        vis_parameters = ds.vis_parameters
        # if vis_parameters is None:
        if not vis_parameters:
            vis_parameters = {
                'seq': {'tabulate': False, 'temporal_control': 'none', 'trail': False},
                'min': {'tabulate': False, 'temporal_control': 'none', 'trail': False},
                'max': {'tabulate': False, 'temporal_control': 'none', 'trail': False}
            }
        # context['visParameters'] = json.dumps(vis_parameters)
        context['vis_parameters_dict'] = vis_parameters

        return context


"""
  vis_parameters on ds_status page
"""


@require_POST
def update_vis_parameters(request, *args, **kwargs):
    try:
        ds_id = request.POST.get('ds_id')
        checked = bool(request.POST.get('checked') == 'true')

        if checked:
            vis_parameters = {
                'seq': {'tabulate': False, 'temporal_control': 'none', 'trail': False},
                'min': {'tabulate': 'initial', 'temporal_control': 'filter', 'trail': False},
                'max': {'tabulate': True, 'temporal_control': 'filter', 'trail': False}
            }
        else:
            vis_parameters = {
                'seq': {'tabulate': False, 'temporal_control': 'none', 'trail': False},
                'min': {'tabulate': False, 'temporal_control': 'none', 'trail': False},
                'max': {'tabulate': False, 'temporal_control': 'none', 'trail': False}
            }

        # Update the vis_parameters field of the dataset
        dataset = get_object_or_404(Dataset, pk=ds_id)
        dataset.vis_parameters = vis_parameters
        dataset.save()

        return JsonResponse(
            {'message': 'Visualisation parameters updated successfully', 'vis_parameters': json.dumps(vis_parameters)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


"""
  volunteers request on ds_status page
"""


@csrf_exempt
def update_volunteers_text(request):
    if request.method == 'POST':
        dataset_id = request.POST.get('dataset_id')
        volunteers_text = request.POST.get('volunteers_text')
        reset = request.POST.get('reset', 'false') == 'true'

        dataset = Dataset.objects.get(id=dataset_id)

        if reset:
            dataset.volunteers_text = None
        else:
            dataset.volunteers_text = volunteers_text

        dataset.save()
        return JsonResponse({'status': 'success'})


"""
  returns dataset owner metadata page
  (formerly DatasetSummaryView)
"""


class DatasetMetadataView(LoginRequiredMixin, UpdateView):
    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'

    form_class = DatasetDetailModelForm

    template_name = 'datasets/ds_metadata.html'

    # Dataset has been edited, form submitted
    def form_valid(self, form):
        data = form.cleaned_data
        ds = get_object_or_404(Dataset, pk=self.kwargs.get("id"))
        dsid = ds.id
        user = self.request.user
        file = data['file']
        filerev = ds.files.all().order_by('-rev')[0].rev
        # print('DatasetSummaryView kwargs',self.kwargs)
        print('DatasetSummaryView form_valid() data->', data)
        if data["file"] == None:
            print('data["file"] == None')
            # no file, updating dataset only
            ds.title = data['title']
            ds.description = data['description']
            ds.uri_base = data['uri_base']
            ds.save()

        # # TODO: Should test `needs_tileset` first - see Issue #227
        # if ds.public:
        #     print(f"Updating mapdata cache (if required).")
        #     task = mapdata_task.delay('datasets', ds.id, 'standard', 'refresh')

        return super().form_valid(form)

    def form_invalid(self, form):
        print('kwargs', self.kwargs)
        context = {}
        print('form not valid; errors:', form.errors)
        print('cleaned_data', form.cleaned_data)
        return super().form_invalid(form)

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Dataset, id=id_)

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetMetadataView, self).get_context_data(*args, **kwargs)

        # print('DatasetSummaryView get_context_data() kwargs:',self.kwargs)
        # print('DatasetSummaryView get_context_data() request.user',self.request.user)
        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)

        """
          when coming from DatasetCreateView() (file.df_status == format_ok)
          runs ds_insert_tsv() or ds_insert_lpf()
          using most recent dataset file
        """
        file = ds.file

        # build context for rendering ds_status.html
        me = self.request.user
        placeset = ds.places.all()

        context['updates'] = {}
        context['ds'] = ds
        context['collaborators'] = ds.collaborators.all()
        context['owners'] = ds.owners
        context['is_admin'] = True if me.groups.filter(name__in=['whg_admins']).exists() else False
        context['editorial'] = True if me.groups.filter(name__in=['editorial']).exists() else False

        # excludes datasets w/o an associated DatasetFile
        if file and hasattr(file, 'file') and os.path.exists(file.file.path):
            context['current_file'] = file
            context['format'] = file.format
            context['numrows'] = file.numrows
            context['filesize'] = round(file.file.size / 1000000, 1)

        # initial (non-task)
        context['num_names'] = PlaceName.objects.filter(place_id__in=placeset).count()
        context['num_links'] = PlaceLink.objects.filter(
            place_id__in=placeset, task_id=None).count()
        context['num_geoms'] = PlaceGeom.objects.filter(
            place_id__in=placeset, task_id=None).count()

        # augmentations (has task_id)
        context['links_added'] = PlaceLink.objects.filter(
            place_id__in=placeset, task_id__contains='-').count()
        context['geoms_added'] = PlaceGeom.objects.filter(
            place_id__in=placeset, task_id__contains='-').count()

        context['beta_or_better'] = True if self.request.user.groups.filter(
            name__in=['beta', 'admins']).exists() else False

        # print('context from DatasetSummaryView', context)
        return context


"""
  returns dataset owner's browse table
"""


class DatasetBrowseView(LoginRequiredMixin, DetailView):
    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'

    model = Dataset
    template_name = 'datasets/ds_browse.html'

    def get_success_url(self):
        id_ = self.kwargs.get("id")
        user = self.request.user
        print('messages:', messages.get_messages(self.kwargs))
        return '/datasets/' + str(id_) + '/browse'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Dataset, id=id_)

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetBrowseView, self).get_context_data(*args, **kwargs)

        print('DatasetBrowseView get_context_data() kwargs:', self.kwargs)
        print('DatasetBrowseView get_context_data() request.user', self.request.user)
        id_ = self.kwargs.get("id")

        ds = get_object_or_404(Dataset, id=id_)
        me = self.request.user
        ds_tasks = [t for t in ds.recon_status]

        context['collaborators'] = ds.collaborators.all()
        context['owners'] = ds.owners
        context['is_admin'] = True if me.groups.filter(name__in=['whg_admins']).exists() else False
        context['updates'] = {}
        context['ds'] = ds
        context['num_places'] = ds.num_places
        context['tgntask'] = 'tgn' in ds_tasks
        context['whgtask'] = len(set(['whg', 'idx']) & set(ds_tasks)) > 0
        context['wdtask'] = len(set(['wd', 'wdlocal']) & set(ds_tasks)) > 0

        return context


"""
  returns public dataset browse table
"""


class DatasetPlacesView(DetailView):
    login_url = "/accounts/login/"
    redirect_field_name = "redirect_to"

    model = Dataset
    template_name = "datasets/ds_places.html"
    unavailable_template_name = "main/503.html"

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Dataset, id=id_)

    def get(self, request, *args, **kwargs):
        ds = self.get_object()

        if ds.num_places > settings.DATASETS_PLACES_LIMIT:
            message = f"Sorry, this dataset cannot be viewed on this page because it has too many places."
            return render(
                request,
                self.unavailable_template_name,
                {"message": message},
                status=503
            )

        return super().get(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)
        me = self.request.user

        context.update(
            {
                "URL_FRONT": settings.URL_FRONT,
                "ds": ds,
                "num_places": ds.num_places,
                "is_admin": me.groups.filter(name__in=["whg_admins"]).exists(),
                "loggedin": "true" if not me.is_anonymous else "false",
                "coordinate_density": "{:.15f}".format(ds.coordinate_density_value),
                "visParameters": ds.vis_parameters
                                 or (
                                     # Populate with default values:
                                     # tabulate: 'initial'|true|false - include sortable table column, 'initial' indicating the initial sort column
                                     # temporal_control: 'player'|'filter'|null - control to be displayed when sorting on this column
                                     # trail: true|false - whether to include ant-trail motion indicators on map
                                     "{'seq': {'tabulate': false, 'temporal_control': null, 'trail': true},"
                                     "'min': {'tabulate': false, 'temporal_control': null, 'trail': true},"
                                     "'max': {'tabulate': false, 'temporal_control': null, 'trail': false}}"
                                 ),
                "my_collections": Collection.objects.filter(
                    collection_class="place",
                    **(
                        {"owner": me}
                        if not me.groups.filter(name="whg_admins").exists()
                        else {}
                    )
                )
                if not me.is_anonymous
                else None,
            }
        )

        return context


# class DatasetPlacesView(DetailView):
#   login_url = '/accounts/login/'
#   redirect_field_name = 'redirect_to'
#
#   model = Dataset
#   template_name = 'datasets/ds_places.html'
#
#   def get_object(self):
#     id_ = self.kwargs.get("id")
#     return get_object_or_404(Dataset, id=id_)
#
#   def get_context_data(self, *args, **kwargs):
#     context = super(DatasetPlacesView, self).get_context_data(*args, **kwargs)
#     context['URL_FRONT'] = settings.URL_FRONT
#
#     print('DatasetPlacesView get_context_data() kwargs:', self.kwargs)
#     print('DatasetPlacesView get_context_data() request.user', self.request.user)
#     id_ = self.kwargs.get("id")
#
#     ds = get_object_or_404(Dataset, id=id_)
#     me = self.request.user
#     if not me.is_anonymous:
#       if me.groups.filter(name='whg_admins').exists():
#         context['my_collections'] = Collection.objects.filter(collection_class='place')
#       else:
#         context['my_collections'] = Collection.objects.filter(owner=me, collection_class='place')
#
#     context['loggedin'] = 'true' if not me.is_anonymous else 'false'
#
#     context['updates'] = {}
#     context['ds'] = ds
#     context['num_places'] = ds.num_places
#     context['is_admin'] = True if me.groups.filter(name__in=['whg_admins']).exists() else False
#
#     if not ds.vis_parameters:
#       # Populate with default values:
#       # tabulate: 'initial'|true|false - include sortable table column, 'initial' indicating the initial sort column
#       # temporal_control: 'player'|'filter'|null - control to be displayed when sorting on this column
#       # trail: true|false - whether to include ant-trail motion indicators on map
#       ds.vis_parameters = "{'seq': {'tabulate': false, 'temporal_control': null, 'trail': true},'min': {'tabulate': false, 'temporal_control': null, 'trail': true},'max': {'tabulate': false, 'temporal_control': null, 'trail': false}}"
#     context['visParameters'] = ds.vis_parameters
#
#     # context['coordinate_density'] = ds.coordinate_density_value
#     # force decimal
#     context['coordinate_density'] = "{:.15f}".format(ds.coordinate_density_value)
#     context['filter'] = None
#
#     return context


"""
  returns dataset owner "Linking" tab listing reconciliation tasks
"""


class DatasetReconcileView(LoginRequiredMixin, DetailView):
    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'

    model = Dataset
    template_name = 'datasets/ds_reconcile.html'

    def get_success_url(self):
        id_ = self.kwargs.get("id")
        user = self.request.user
        print('messages:', messages.get_messages(self.kwargs))
        return '/datasets/' + str(id_) + '/reconcile'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Dataset, id=id_)

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetReconcileView, self).get_context_data(*args, **kwargs)

        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)

        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)
        place_count = ds.places.count()
        wdgn_status = {
            "rows": place_count,
            "got_hits": ds.places.exclude(review_wd=None).count(),
            "reviewed": ds.places.filter(review_wd=1).count(),
            "deferred": ds.places.filter(review_wd=2).count(),
            "remain": ds.places.filter(review_wd=0).count() + ds.places.filter(review_wd=2).count(),
        }
        print('wdgn_status', wdgn_status)

        idx_status = {
            "rows": place_count,
            "got_hits": ds.places.exclude(review_whg=None).count(),
            "reviewed": ds.places.filter(review_whg=1).count(),
            "remain": ds.places.filter(review_whg=0).count(),
            "deferred": ds.places.filter(review_whg=2).count() or 'none',
        }

        context['wdgn_status'] = wdgn_status
        context['idx_status'] = idx_status
        context['is_admin'] = True if self.request.user.groups.filter(name__in=['whg_admins']).exists() else False

        # build context for rendering dataset.html
        me = self.request.user

        # omits FAILURE and ARCHIVED
        ds_tasks = ds.tasks.filter(status='SUCCESS')

        context['ds'] = ds
        context['tasks'] = ds_tasks

        context['beta_or_better'] = True if self.request.user.groups.filter(
            name__in=['beta', 'whg_admins']).exists() else False

        return context


"""
  returns dataset owner "Collaborators" tab
"""


class DatasetCollabView(LoginRequiredMixin, DetailView):
    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'

    model = DatasetUser
    template_name = 'datasets/ds_collab.html'

    def get_success_url(self):
        id_ = self.kwargs.get("id")
        user = self.request.user
        print('messages:', messages.get_messages(self.kwargs))
        return '/datasets/' + str(id_) + '/collab'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Dataset, id=id_)

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetCollabView, self).get_context_data(*args, **kwargs)

        print('DatasetCollabView get_context_data() kwargs:', self.kwargs)
        print('DatasetCollabView get_context_data() request.user:', self.request.user)
        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)

        # build context for rendering dataset.html
        me = self.request.user

        context['ds'] = ds

        context['is_admin'] = True if me.groups.filter(name__in=['whg_admins']).exists() else False
        context['editorial'] = True if me.groups.filter(name__in=['editorial']).exists() else False
        context['collabs'] = ds.collabs.all()
        context['collaborators'] = ds.collaborators.all()
        context['owners'] = ds.owners

        context['beta_or_better'] = True if self.request.user.groups.filter(
            name__in=['beta', 'admins']).exists() else False

        return context


"""
  returns add (reconciliation) task page
"""


class DatasetAddTaskView(LoginRequiredMixin, DetailView):
    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'

    model = Dataset
    template_name = 'datasets/ds_addtask.html'

    def get_success_url(self):
        id_ = self.kwargs.get("id")
        user = self.request.user
        print('messages:', messages.get_messages(self.kwargs))
        return '/datasets/' + str(id_) + '/log'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Dataset, id=id_)

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetAddTaskView, self).get_context_data(*args, **kwargs)

        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)

        # build context for rendering ds_addtask.html
        me = self.request.user
        area_types = ['ccodes', 'copied', 'drawn']

        is_admin = self.request.user.groups.filter(name__in=['whg_admins']).exists()

        # user study areas
        userareas = Area.objects.filter(
            type__in=area_types,
            **({} if is_admin else {'owner_id': me.id})
        ).values('id', 'title').order_by('-created')

        # pre-defined UN regions
        predefined = Area.objects.all().filter(type='predefined').values('id', 'title')

        gothits = {}
        for t in ds.tasks.filter(status='SUCCESS', task_name__startswith='align_'):
            gothits[t.task_id] = int(json.loads(t.result)['got_hits'])

        # deliver status message(s) to template
        msg_unreviewed = """There is a <span class='strong'>%s</span> task in progress,
      and all %s records that got hits remain unreviewed. <span class='text-danger strong'>Starting this new task
      will delete the existing one</span>, with no impact on your dataset."""
        msg_inprogress = """<p class='mb-1'>There is a <span class='strong'>%s</span> task in progress,
      and %s of the %s records that had hits have been reviewed. <span class='text-danger strong'>Starting this new task
      will archive the existing task and submit only unreviewed records.</span>.
      If you proceed, you can keep or delete prior match results (links and/or geometry):</p>"""
        msg_done = """All records have been submitted for reconciliation to %s and reviewed.
      To begin the step of accessioning to the WHG index, please <a href="%s">contact our editorial team.</a>"""

        for i in ds.taskstats.items():
            # auth = 'Wikidata+GeoNames' if i[0].startswith('align_wd') else 'WHG index'
            auth = i[0][6:]  # strip 'align_'
            auth_name = 'Wikidata+GeoNames' if auth == 'wdlocal' else 'WHG index'
            if len(i[1]) > 0:  # there's a SUCCESS task
                tid = i[1][0]['tid']
                remaining = i[1][0]['total']
                hadhits = gothits[tid]
                reviewed = hadhits - remaining
                print('auth, tid, remaining, hadhits', auth, tid, remaining, hadhits)
                if remaining == 0 and ds.ds_status != 'updated':
                    # if remaining == 0:
                    context['msg_' + auth] = {
                        'msg': msg_done % (auth_name, "/contact"),
                        'type': 'done'}
                elif remaining < hadhits and ds.ds_status != 'updated':
                    context['msg_' + auth] = {
                        'msg': msg_inprogress % (auth_name, reviewed, hadhits),
                        'type': 'inprogress'}
                else:
                    context['msg_' + auth] = {
                        'msg': msg_unreviewed % (auth_name, hadhits),
                        'type': 'unreviewed'
                    }
            else:
                context['msg_' + auth] = {
                    # 'msg': "no current tasks of this type",
                    'msg': "",
                    'type': 'none'
                }

        active_tasks = dict(filter(lambda elem: len(elem[1]) > 0, ds.taskstats.items()))
        remaining = {}
        for t in active_tasks.items():
            remaining[t[0][6:]] = t[1][0]['total']

        context['region_list'] = predefined
        context['area_list'] = userareas

        # Retrieve any userarea from query parameters
        userarea = self.request.GET.get('userarea')
        if userarea:
            context['userarea'] = userarea

        context['ds'] = ds
        context['numrows'] = ds.places.count()
        context['collaborators'] = ds.collabs.all()
        context['owners'] = ds.owners
        context['remain_to_review'] = remaining
        context['missing_geoms'] = ds.missing_geoms
        context['is_admin'] = is_admin
        # context['beta_or_better'] = True if self.request.user.groups.filter(name__in=['beta', 'admins']).exists() else False

        return context


"""
  returns dataset owner "Log & Comments" tab
"""


class DatasetLogView(LoginRequiredMixin, DetailView):
    login_url = '/accounts/login/'
    redirect_field_name = 'redirect_to'

    model = Dataset
    template_name = 'datasets/ds_log.html'

    def get_success_url(self):
        id_ = self.kwargs.get("id")
        user = self.request.user
        print('messages:', messages.get_messages(self.kwargs))
        return '/datasets/' + str(id_) + '/log'

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Dataset, id=id_)

    def get_context_data(self, *args, **kwargs):
        context = super(DatasetLogView, self).get_context_data(*args, **kwargs)

        print('DatasetLogView get_context_data() kwargs:', self.kwargs)
        print('DatasetLogView get_context_data() request.user:', self.request.user)
        id_ = self.kwargs.get("id")
        ds = get_object_or_404(Dataset, id=id_)

        me = self.request.user

        context['ds'] = ds
        context['log'] = ds.log.filter(category='dataset').order_by('-timestamp')
        context['comments'] = Comment.objects.filter(place_id__dataset=ds).order_by('-created')
        context['beta_or_better'] = True if self.request.user.groups.filter(
            name__in=['beta', 'admins']).exists() else False

        return context


def dataset_citation(request, id):
    try:
        dataset = Dataset.objects.get(id=id)
        citation_data = dataset.citation_csl
        return JsonResponse(citation_data, safe=False)
    except Dataset.DoesNotExist:
        return JsonResponse({'error': 'Dataset not found'}, status=404)


"""
  REPLACED by insert.ds_insert_json()
"""
# def ds_insert_lpf(request, pk):
#   import json
#   [countrows, countlinked, total_links] = [0, 0, 0]
#   ds = get_object_or_404(Dataset, id=pk)
#   user = request.user
#   # latest file
#   dsf = ds.files.all().order_by('-rev')[0]
#   uribase = ds.uri_base
#   print('new dataset, uri_base', ds.label, uribase)
#
#   # TODO: lpf can get big; support json-lines
#
#   # insert only if empty
#   dbcount = Place.objects.filter(dataset=ds.label).count()
#   print('dbcount', dbcount)
#
#   if dbcount == 0:
#     errors = []
#     try:
#       infile = dsf.file.open(mode="r")
#       print('ds_insert_lpf() for dataset', ds)
#       print('ds_insert_lpf() request.GET, infile', request.GET, infile)
#       with infile:
#         jdata = json.loads(infile.read())
#
#         print('count of features', len(jdata['features']))
#         # print('0th feature',jdata['features'][0])
#
#         for feat in jdata['features']:
#           # create Place, save to get id, then build associated records for each
#           objs = {"PlaceNames": [], "PlaceTypes": [], "PlaceGeoms": [], "PlaceWhens": [],
#                   "PlaceLinks": [], "PlaceRelated": [], "PlaceDescriptions": [],
#                   "PlaceDepictions": []}
#           countrows += 1
#
#           # build attributes for new Place instance
#           title = re.sub('\(.*?\)', '', feat['properties']['title'])
#
#           # geometry
#           geojson = feat['geometry'] if 'geometry' in feat.keys() else None
#
#           # ccodes
#           if 'ccodes' not in feat['properties'].keys():
#             if geojson:
#               # a GeometryCollection
#               ccodes = ccodesFromGeom(geojson)
#               print('ccodes', ccodes)
#             else:
#               ccodes = []
#           else:
#             ccodes = feat['properties']['ccodes']
#
#           # temporal
#           # send entire feat for time summary
#           # (minmax and intervals[])
#           datesobj = parsedates_lpf(feat)
#
#           # TODO: compute fclasses
#           try:
#             newpl = Place(
#               # strip uribase from @id
#               src_id=feat['@id'] if uribase in ['', None] else feat['@id'].replace(uribase, ''),
#               dataset=ds,
#               title=title,
#               ccodes=ccodes,
#               minmax=datesobj['minmax'],
#               timespans=datesobj['intervals']
#             )
#             newpl.save()
#             print('new place: ', newpl.title)
#           except:
#             print('failed id' + title + 'datesobj: ' + str(datesobj))
#             print(sys.exc_info())
#
#           # PlaceName: place,src_id,toponym,task_id,
#           # jsonb:{toponym, lang, citation[{label, year, @id}], when{timespans, ...}}
#           # TODO: adjust for 'ethnic', 'demonym'
#           for n in feat['names']:
#             if 'toponym' in n.keys():
#               # if comma-separated listed, get first
#               objs['PlaceNames'].append(PlaceName(
#                 place=newpl,
#                 src_id=newpl.src_id,
#                 toponym=n['toponym'].split(', ')[0],
#                 jsonb=n
#               ))
#
#           # PlaceType: place,src_id,task_id,jsonb:{identifier,label,src_label}
#           # try:
#           if 'types' in feat.keys():
#             fclass_list = []
#             for t in feat['types']:
#               if 'identifier' in t.keys() and t['identifier'][:4] == 'aat:' \
#                 and int(t['identifier'][4:]) in Type.objects.values_list('aat_id', flat=True):
#                 fc = get_object_or_404(Type, aat_id=int(t['identifier'][4:])).fclass \
#                   if t['identifier'][:4] == 'aat:' else None
#                 fclass_list.append(fc)
#               else:
#                 fc = None
#               print('from feat[types]:', t)
#               print('PlaceType record newpl,newpl.src_id,t,fc', newpl, newpl.src_id, t, fc)
#               objs['PlaceTypes'].append(PlaceType(
#                 place=newpl,
#                 src_id=newpl.src_id,
#                 jsonb=t,
#                 fclass=fc
#               ))
#             newpl.fclasses = fclass_list
#             newpl.save()
#
#           # PlaceWhen: place,src_id,task_id,minmax,jsonb:{timespans[],periods[],label,duration}
#           if 'when' in feat.keys() and feat['when'] != {}:
#             objs['PlaceWhens'].append(PlaceWhen(
#               place=newpl,
#               src_id=newpl.src_id,
#               jsonb=feat['when'],
#               minmax=newpl.minmax
#             ))
#
#           # PlaceGeom: place,src_id,task_id,jsonb:{type,coordinates[],when{},geo_wkt,src}
#           # if 'geometry' in feat.keys() and feat['geometry']['type']=='GeometryCollection':
#           if geojson and geojson['type'] == 'GeometryCollection':
#             # for g in feat['geometry']['geometries']:
#             for g in geojson['geometries']:
#               # print('from feat[geometry]:',g)
#               objs['PlaceGeoms'].append(PlaceGeom(
#                 place=newpl,
#                 src_id=newpl.src_id,
#                 jsonb=g
#                 , geom=GEOSGeometry(json.dumps(g))
#               ))
#           elif geojson:
#             objs['PlaceGeoms'].append(PlaceGeom(
#               place=newpl,
#               src_id=newpl.src_id,
#               jsonb=geojson
#               , geom=GEOSGeometry(json.dumps(geojson))
#             ))
#
#           # PlaceLink: place,src_id,task_id,jsonb:{type,identifier}
#           if 'links' in feat.keys() and len(feat['links']) > 0:
#             countlinked += 1  # record has *any* links
#             # print('countlinked',countlinked)
#             for l in feat['links']:
#               total_links += 1  # record has n links
#               objs['PlaceLinks'].append(PlaceLink(
#                 place=newpl,
#                 src_id=newpl.src_id,
#                 # alias uri base for known authorities
#                 jsonb={"type": l['type'], "identifier": aliasIt(l['identifier'].rstrip('/'))}
#               ))
#
#           # PlaceRelated: place,src_id,task_id,jsonb{relationType,relationTo,label,when{}}
#           if 'relations' in feat.keys():
#             for r in feat['relations']:
#               objs['PlaceRelated'].append(PlaceRelated(
#                 place=newpl, src_id=newpl.src_id, jsonb=r))
#
#           # PlaceDescription: place,src_id,task_id,jsonb{@id,value,lang}
#           if 'descriptions' in feat.keys():
#             for des in feat['descriptions']:
#               objs['PlaceDescriptions'].append(PlaceDescription(
#                 place=newpl, src_id=newpl.src_id, jsonb=des))
#
#           # PlaceDepiction: place,src_id,task_id,jsonb{@id,title,license}
#           if 'depictions' in feat.keys():
#             for dep in feat['depictions']:
#               objs['PlaceDepictions'].append(PlaceDepiction(
#                 place=newpl, src_id=newpl.src_id, jsonb=dep))
#
#           # throw errors into user message
#           def raiser(model, e):
#             print('Bulk load for ' + model + ' failed on', newpl)
#             errors.append({"field": model, "error": e})
#             print('error', e)
#             raise DataError
#
#           # create related objects
#           try:
#             PlaceName.objects.bulk_create(objs['PlaceNames'])
#           except DataError as e:
#             raiser('Name', e)
#
#           try:
#             PlaceType.objects.bulk_create(objs['PlaceTypes'])
#           except DataError as de:
#             raiser('Type', e)
#
#           try:
#             PlaceWhen.objects.bulk_create(objs['PlaceWhens'])
#           except DataError as de:
#             raiser('When', e)
#
#           try:
#             PlaceGeom.objects.bulk_create(objs['PlaceGeoms'])
#           except DataError as de:
#             raiser('Geom', e)
#
#           try:
#             PlaceLink.objects.bulk_create(objs['PlaceLinks'])
#           except DataError as de:
#             raiser('Link', e)
#
#           try:
#             PlaceRelated.objects.bulk_create(objs['PlaceRelated'])
#           except DataError as de:
#             raiser('Related', e)
#
#           try:
#             PlaceDescription.objects.bulk_create(objs['PlaceDescriptions'])
#           except DataError as de:
#             raiser('Description', e)
#
#           try:
#             PlaceDepiction.objects.bulk_create(objs['PlaceDepictions'])
#           except DataError as de:
#             raiser('Depiction', e)
#
#           # TODO: compute newpl.ccodes (if geom), newpl.fclasses, newpl.minmax
#           # something failed in *any* Place creation; delete dataset
#
#         print('new dataset:', ds.__dict__)
#         infile.close()
#
#       return ({"numrows": countrows,
#                "numlinked": countlinked,
#                "total_links": total_links})
#     except:
#       # drop the (empty) database
#       # ds.delete()
#       # email to user, admin
#       subj = 'World Historical Gazetteer error followup'
#       msg = 'Hello ' + user.name + ', \n\nWe see your recent upload for the ' + ds.label + \
#             ' dataset failed, very sorry about that!' + \
#             '\nThe likely cause was: ' + str(errors) + '\n\n' + \
#             "If you can, fix the cause. If not, please respond to this email and we will get back to you soon.\n\nRegards,\nThe WHG Team"
#       emailer(subj, msg, 'whg@kgeographer.org', [user.email, 'whgadmin@kgeographer.com'])
#
#       # return message to 500.html
#       # messages.error(request, "Database insert failed, but we don't know why. The WHG team has been notified and will follow up by email to <b>"+user.username+'</b> ('+user.email+')')
#       # return redirect(request.GET.get('from'))
#       return HttpResponseServerError()
#
#   else:
#     print('insert_ skipped, already in')
#     messages.add_message(request, messages.INFO, 'data is uploaded, but problem displaying dataset page')
#     return redirect('/mydata')
#

"""
  REPLACED by insert.ds_insert_delim()
  insert tsv into database
  file is validated, dataset exists
  if insert fails anywhere, delete dataset + any related objects
"""
# def ds_insert_tsv(request, pk):
#   import csv, re
#   csv.field_size_limit(300000)
#   ds = get_object_or_404(Dataset, id=pk)
#   user = request.user
#   print('ds_insert_tsv()', ds)
#   # retrieve just-added file
#   dsf = ds.files.all().order_by('-rev')[0]
#   print('ds_insert_tsv(): ds, file', ds, dsf)
#   # insert only if empty
#   dbcount = Place.objects.filter(dataset=ds.label).count()
#   # print('dbcount',dbcount)
#   insert_errors = []
#   if dbcount == 0:
#     try:
#       infile = dsf.file.open(mode="r")
#       reader = csv.reader(infile, delimiter=dsf.delimiter)
#
#       infile.seek(0)
#       header = next(reader, None)
#       header = [col.lower().strip() for col in header]
#       # print('header.lower()',[col.lower() for col in header])
#
#       # strip BOM character if exists
#       header[0] = header[0][1:] if '\ufeff' in header[0] else header[0]
#       print('header', header)
#
#       objs = {"PlaceName": [], "PlaceType": [], "PlaceGeom": [], "PlaceWhen": [],
#               "PlaceLink": [], "PlaceRelated": [], "PlaceDescription": []}
#
#       # TODO: what if simultaneous inserts?
#       countrows = 0
#       countlinked = 0
#       total_links = 0
#       for r in reader:
#         # build attributes for new Place instance
#         src_id = r[header.index('id')]
#         title = r[header.index('title')].strip()  # don't try to correct incoming except strip()
#         # strip anything in parens for title only
#         # title = re.sub('\(.*?\)', '', title)
#         title_source = r[header.index('title_source')]
#         title_uri = r[header.index('title_uri')] if 'title_uri' in header else ''
#         ccodes = r[header.index('ccodes')] if 'ccodes' in header else []
#         variants = [x.strip() for x in r[header.index('variants')].split(';')] \
#           if 'variants' in header and r[header.index('variants')] != '' else []
#         types = [x.strip() for x in r[header.index('types')].split(';')] \
#           if 'types' in header else []
#         aat_types = [x.strip() for x in r[header.index('aat_types')].split(';')] \
#           if 'aat_types' in header else []
#         parent_name = r[header.index('parent_name')] if 'parent_name' in header else ''
#         parent_id = r[header.index('parent_id')] if 'parent_id' in header else ''
#         coords = makeCoords(r[header.index('lon')], r[header.index('lat')]) \
#           if 'lon' in header and 'lat' in header else None
#         geowkt = r[header.index('geowkt')] if 'geowkt' in header else None
#         geosource = r[header.index('geo_source')] if 'geo_source' in header else None
#         geoid = r[header.index('geo_id')] if 'geo_id' in header else None
#         geojson = None  # zero it out
#         print('geosource:', geosource)
#         print('geoid:', geoid)
#         # make Point geometry from lon/lat if there
#         if coords and len(coords) == 2:
#           geojson = {"type": "Point", "coordinates": coords,
#                      "geowkt": 'POINT(' + str(coords[0]) + ' ' + str(coords[1]) + ')'}
#         # else make geometry (any) w/Shapely if geowkt
#         if geowkt and geowkt not in ['']:
#           geojson = parse_wkt(geowkt)
#         if geojson and (geosource or geoid):
#           geojson['citation'] = {'label': geosource, 'id': geoid}
#
#         # ccodes; compute if missing and there is geometry
#         if len(ccodes) == 0:
#           if geojson:
#             try:
#               ccodes = ccodesFromGeom(geojson)
#             except:
#               pass
#           else:
#             ccodes = []
#         else:
#           ccodes = [x.strip().upper() for x in r[header.index('ccodes')].split(';')]
#
#         # TODO: assign aliases if wd, tgn, pl, bnf, gn, viaf
#         matches = [aliasIt(x.strip()) for x in r[header.index('matches')].split(';')] \
#           if 'matches' in header and r[header.index('matches')] != '' else []
#
#         start = r[header.index('start')] if 'start' in header else None
#         # validate_tsv() ensures there is always a start
#         has_end = 'end' in header and r[header.index('end')] != ''
#         end = r[header.index('end')] if has_end else start
#
#         datesobj = parsedates_tsv(start, end)
#         # returns {timespans:[{}],minmax[]}
#
#         description = r[header.index('description')] \
#           if 'description' in header else ''
#
#         print('title, src_id (pre-newpl):', title, src_id)
#
#         # create new Place object
#         # TODO: generate fclasses
#         newpl = Place(
#           src_id=src_id,
#           dataset=ds,
#           title=title,
#           ccodes=ccodes,
#           minmax=datesobj['minmax'],
#           timespans=[datesobj['minmax']]  # list of lists
#         )
#         newpl.save()
#         countrows += 1
#
#         # build associated objects and add to arrays #
#         #
#         # PlaceName(); title, then variants
#         #
#         objs['PlaceName'].append(
#           PlaceName(
#             place=newpl,
#             src_id=src_id,
#             toponym=title,
#             jsonb={"toponym": title, "citations": [{"id": title_uri, "label": title_source}]}
#           ))
#         # variants if any; assume same source as title toponym
#         if len(variants) > 0:
#           for v in variants:
#             try:
#               haslang = re.search("@(.*)$", v.strip())
#               if len(v.strip()) > 200:
#                 # print(v.strip())
#                 pass
#               else:
#                 # print('variant for', newpl.id, v)
#                 new_name = PlaceName(
#                   place=newpl,
#                   src_id=src_id,
#                   toponym=v.strip(),
#                   jsonb={"toponym": v.strip(), "citations": [{"id": "", "label": title_source}]}
#                 )
#                 if haslang:
#                   new_name.jsonb['lang'] = haslang.group(1)
#
#                 objs['PlaceName'].append(new_name)
#             except:
#               print('error on variant', sys.exc_info())
#               print('error on variant for newpl.id', newpl.id, v)
#
#         #
#         # PlaceType()
#         #
#         if len(types) > 0:
#           fclass_list = []
#           for i, t in enumerate(types):
#             aatnum = 'aat:' + aat_types[i] if len(aat_types) >= len(types) and aat_types[i] != '' else None
#             print('aatnum in insert_tsv() PlaceTypes', aatnum)
#             if aatnum:
#               try:
#                 fclass_list.append(get_object_or_404(Type, aat_id=int(aatnum[4:])).fclass)
#               except:
#                 # report type lookup issue
#                 insert_errors.append(
#                   {'src_id': src_id,
#                    'title': newpl.title,
#                    'field': 'aat_type',
#                    'msg': aatnum + ' not in WHG-supported list;'}
#                 )
#                 raise
#                 # messages.add_message(request, messages.INFO, 'choked on an invalid AAT place type id')
#                 # return redirect('/mydata')
#                 # continue
#             objs['PlaceType'].append(
#               PlaceType(
#                 place=newpl,
#                 src_id=src_id,
#                 jsonb={"identifier": aatnum if aatnum else '',
#                        "sourceLabel": t,
#                        "label": aat_lookup(int(aatnum[4:])) if aatnum else ''
#                        }
#               ))
#           newpl.fclasses = fclass_list
#           newpl.save()
#
#         #
#         # PlaceGeom()
#         #
#         print('geojson', geojson)
#         if geojson:
#           objs['PlaceGeom'].append(
#             PlaceGeom(
#               place=newpl,
#               src_id=src_id,
#               jsonb=geojson
#               , geom=GEOSGeometry(json.dumps(geojson))
#             ))
#
#         #
#         # PlaceWhen()
#         # via parsedates_tsv(): {"timespans":[{start{}, end{}}]}
#         if start != '':
#           objs['PlaceWhen'].append(
#             PlaceWhen(
#               place=newpl,
#               src_id=src_id,
#               # jsonb=datesobj['timespans']
#               jsonb=datesobj
#             ))
#
#         #
#         # PlaceLink() - all are closeMatch
#         #
#         if len(matches) > 0:
#           countlinked += 1
#           for m in matches:
#             total_links += 1
#             objs['PlaceLink'].append(
#               PlaceLink(
#                 place=newpl,
#                 src_id=src_id,
#                 jsonb={"type": "closeMatch", "identifier": m}
#               ))
#
#         #
#         # PlaceRelated()
#         #
#         if parent_name != '':
#           objs['PlaceRelated'].append(
#             PlaceRelated(
#               place=newpl,
#               src_id=src_id,
#               jsonb={
#                 "relationType": "gvp:broaderPartitive",
#                 "relationTo": parent_id,
#                 "label": parent_name}
#             ))
#
#         #
#         # PlaceDescription()
#         # @id, value, lang
#         if description != '':
#           objs['PlaceDescription'].append(
#             PlaceDescription(
#               place=newpl,
#               src_id=src_id,
#               jsonb={
#                 # "@id": "", "value":description, "lang":""
#                 "value": description
#               }
#             ))
#
#       # bulk_create(Class, batch_size=n) for each
#       PlaceName.objects.bulk_create(objs['PlaceName'], batch_size=10000)
#       PlaceType.objects.bulk_create(objs['PlaceType'], batch_size=10000)
#       try:
#         PlaceGeom.objects.bulk_create(objs['PlaceGeom'], batch_size=10000)
#       except:
#         print('geom insert failed', newpl, sys.exc_info())
#         pass
#       PlaceLink.objects.bulk_create(objs['PlaceLink'], batch_size=10000)
#       PlaceRelated.objects.bulk_create(objs['PlaceRelated'], batch_size=10000)
#       PlaceWhen.objects.bulk_create(objs['PlaceWhen'], batch_size=10000)
#       PlaceDescription.objects.bulk_create(objs['PlaceDescription'], batch_size=10000)
#
#       infile.close()
#       print('insert_errors', insert_errors)
#       # print('rows,linked,links:', countrows, countlinked, total_links)
#     except:
#       print('tsv insert failed', newpl, sys.exc_info())
#       # drop the (empty) dataset if insert wasn't complete
#       ds.delete()
#       # email to user, admin
#       failed_upload_notification(user, dsf.file.name, ds.label)
#
#       # return message to 500.html
#       messages.error(request,
#                      "Database insert failed, but we don't know why. The WHG team has been notified and will follow up by email to <b>" + user.name + '</b> (' + user.email + ')')
#       return HttpResponseServerError()
#   else:
#     print('insert_tsv skipped, already in')
#     messages.add_message(request, messages.INFO, 'data is uploaded, but problem displaying dataset page')
#     return redirect('/mydata')
#
#   return ({"numrows": countrows,
#            "numlinked": countlinked,
#            "total_links": total_links})
#

""" REPLACED UPDATE FUNCTIONS Nov/Dec 2022 """
"""
  DEPRECATED
  update_rels_tsv(pobj, row)
  backup 26 Nov 2022
"""
# def update_rels_tsv_bak(pobj, row):
#   header = list(row.keys())
#   # print('update_rels_tsv(): pobj, row, header', pobj, row, header)
#   # dies somewhere after this
#   src_id = row['id']
#   title = row['title']
#   # for PlaceName insertion, strip anything in parens
#   title = re.sub('\(.*?\)', '', title)
#   title_source = row['title_source']
#   title_uri = row['title_uri'] if 'title_uri' in header else ''
#   variants = [x.strip() for x in row['variants'].split(';')] \
#     if 'variants' in header and row['variants'] else []
#
#   types = [x.strip() for x in row['types'].split(';')] \
#     if 'types' in header and str(row['types']) != '' else []
#
#   aat_types = [x.strip() for x in row['aat_types'].split(';')] \
#     if 'aat_types' in header and str(row['aat_types']) != '' else []
#
#   parent_name = row['parent_name'] if 'parent_name' in header else ''
#
#   parent_id = row['parent_id'] if 'parent_id' in header else ''
#
#   # empty lon and lat are None
#   coords = makeCoords(row['lon'], row['lat']) \
#     if 'lon' in header and 'lat' in header and row['lon'] else []
#   print('coords', coords)
#   try:
#     matches = [x.strip() for x in row['matches'].split(';')] \
#       if 'matches' in header and row['matches'] else []
#   except:
#     print('matches, error', row['matches'], sys.exc_info())
#
#   description = row['description'] \
#     if row['description'] else ''
#
#   # build associated objects and add to arrays
#   objs = {"PlaceName":[], "PlaceType":[], "PlaceGeom":[], "PlaceWhen":[],
#           "PlaceLink":[], "PlaceRelated":[], "PlaceDescription":[], "PlaceDepiction":[]}
#
#   # title as a PlaceName
#   objs['PlaceName'].append(
#     PlaceName(
#       place=pobj,
#       src_id = src_id,
#       toponym = title,
#       jsonb={"toponym": title, "citation": {"id":title_uri,"label":title_source}}
#   ))
#
#   # add variants as PlaceNames, if any
#   if len(variants) > 0:
#     for v in variants:
#       haslang = re.search("@(.*)$", v.strip())
#       new_name = PlaceName(
#         place=pobj,
#         src_id = src_id,
#         toponym = v.strip(),
#         jsonb={"toponym": v.strip(), "citation": {"id":"","label":title_source}}
#       )
#       if haslang:
#         new_name.jsonb['lang'] = haslang.group(1)
#       objs['PlaceName'].append(new_name)
#   print('objs after names', objs)
#
#   #
#   # PlaceType()
#   # TODO: parse t
#   if len(types) > 0:
#     fclass_list = []
#     for i,t in enumerate(types):
#       # i always 0 in tsv
#       aatnum='aat:'+aat_types[i] if len(aat_types) >= len(types) else None
#       print(aat_types[i])
#       if aatnum:
#         fc = get_object_or_404(Type, aat_id=aat_types[i])
#         print('fclass', fc.fclass)
#         fclass_list.append(fc.fclass)
#       objs['PlaceType'].append(
#         PlaceType(
#           place=pobj,
#           src_id = src_id,
#           jsonb={ "identifier":aatnum,
#                   "sourceLabel":t,
#                   "label":aat_lookup(int(aatnum[4:])) if aatnum !='aat:' else ''
#                 },
#           fclass = fc.fclass
#       ))
#   if len(fclass_list) >0:
#     pobj.fclasses = fclass_list
#     pobj.save()
#   print('objs after types', objs)
#
#
#   #
#   # PlaceGeom()
#   # TODO: test geometry type or force geojson
#   if len(coords) > 0:
#     geom = {"type": "Point",
#             "coordinates": coords,
#             "geowkt": 'POINT('+str(coords[0])+' '+str(coords[1])+')'}
#   elif 'geowkt' in header and row['geowkt'] not in ['',None]: # some rows no geom
#     geom = parse_wkt(row['geowkt'])
#     print('from geowkt', geom)
#   else:
#     geom = None
#   print('geom', geom)
#   # TODO:
#   # if pobj is existing place, add geom only if it's new
#   # if pobj is new place and row has geom, always add it
#   if geom:
#     def trunc4(val):
#       return round(val,4)
#
#     new_coords = list(map(trunc4,list(geom['coordinates'])))
#
#     # if no geoms at all, add this one
#     if pobj.geoms.count() == 0:
#       objs['PlaceGeom'].append(
#         PlaceGeom(
#           place=pobj,
#           src_id=src_id,
#           jsonb=geom,
#           geom=GEOSGeometry(json.dumps(geom))
#         ))
#     # otherwise only add if coords don't match
#     elif pobj.geoms.count() > 0:
#       # add only if coords don't match
#       try:
#         for g in pobj.geoms.all():
#           if list(map(trunc4, g.jsonb['coordinates'])) != new_coords:
#             objs['PlaceGeom'].append(
#                 PlaceGeom(
#                   place=pobj,
#                   src_id = src_id,
#                   jsonb=geom,
#                   geom=GEOSGeometry(json.dumps(geom))
#               ))
#       except:
#         print('failed geom on pobj:', pobj, sys.exc_info())
#   print('objs after geom', objs)
#
#   # PlaceLink() - all are closeMatch
#   # Pandas turns nulls into NaN strings, 'nan'
#   print('matches', matches)
#   if len(matches) > 0:
#     # any existing? only add new
#     exist_links = list(pobj.links.all().values_list('jsonb__identifier',flat=True))
#     print('matches, exist_links at create', matches, exist_links)
#
#     if len(set(matches)-set(exist_links)) > 0:
#       # one or more new matches; add 'em
#       for m in matches:
#         objs['PlaceLink'].append(
#           PlaceLink(
#             place=pobj,
#             src_id = src_id,
#             jsonb={"type":"closeMatch", "identifier":m}
#         ))
#
#   # print('objs after matches', objs)
#   #
#   # PlaceRelated()
#   if parent_name != '':
#     objs['PlaceRelated'].append(
#       PlaceRelated(
#         place=pobj,
#         src_id=src_id,
#         jsonb={
#           "relationType": "gvp:broaderPartitive",
#           "relationTo": parent_id,
#           "label": parent_name}
#     ))
#
#   # print('objs after related', objs)
#
#   # PlaceWhen()
#   # timespans[{start{}, end{}}], periods[{name,id}], label, duration
#   objs['PlaceWhen'].append(
#     PlaceWhen(
#       place=pobj,
#       src_id = src_id,
#       jsonb={
#             "timespans": [{
#               "start":{"earliest":pobj.minmax[0]},
#               "end":{"latest":pobj.minmax[1]}}]
#           }
#   ))
#
#   # print('objs after when', objs)
#   #
#   # PlaceDescription()
#   # @id, value, lang
#   print('description', description)
#   if description != '':
#     objs['PlaceDescription'].append(
#       PlaceDescription(
#         place=pobj,
#         src_id = src_id,
#         jsonb={
#           "@id": "", "value":description, "lang":""
#         }
#       ))
#
#   print('objs after all', objs)
#
#   # what came from this row
#   print('COUNTS:')
#   print('PlaceName:', len(objs['PlaceName']))
#   print('PlaceType:', len(objs['PlaceType']))
#   print('PlaceGeom:', len(objs['PlaceGeom']))
#   print('PlaceLink:', len(objs['PlaceLink']))
#   print('PlaceRelated:', len(objs['PlaceRelated']))
#   print('PlaceWhen:', len(objs['PlaceWhen']))
#   print('PlaceDescription:', len(objs['PlaceDescription']))
#   # no depictions in LP-TSV
#
#   # TODO: update place.fclasses, place.minmax, place.timespans
#
#   # bulk_create(Class, batch_size=n) for each
#   # PlaceName.objects.create(objs['PlaceName'][0])
#   PlaceName.objects.bulk_create(objs['PlaceName'],batch_size=10000)
#   print('names done')
#   PlaceType.objects.bulk_create(objs['PlaceType'],batch_size=10000)
#   print('types done')
#   PlaceGeom.objects.bulk_create(objs['PlaceGeom'],batch_size=10000)
#   print('geoms done')
#   PlaceLink.objects.bulk_create(objs['PlaceLink'],batch_size=10000)
#   print('links done')
#   PlaceRelated.objects.bulk_create(objs['PlaceRelated'],batch_size=10000)
#   print('related done')
#   PlaceWhen.objects.bulk_create(objs['PlaceWhen'],batch_size=10000)
#   print('whens done')
#   PlaceDescription.objects.bulk_create(objs['PlaceDescription'],batch_size=10000)
#   print('descriptions done')

"""
  DEPRECATED
  ds_update_bak() backup copy 5 Dec 2022; pre-refactor
  perform updates to database and index, given new datafile
  params: dsid, format, keepg, keepl, compare_data (json string)
"""
# def ds_update_bak(request):
#   if request.method == 'POST':
#     print('request.POST ds_update()', request.POST)
#     dsid=request.POST['dsid']
#     ds = get_object_or_404(Dataset, id=dsid)
#     file_format=request.POST['format']
#     # keep previous recon/review results?
#     keepg = request.POST['keepg']
#     keepl = request.POST['keepl']
#
#     print('keepg, type in ds_update() request', keepg, type(keepg))
#     print('keepl, type in ds_update() request', keepg, type(keepl))
#
#     # compare_data = comparison
#     # compare_result = compare_data['compare_result']
#     compare_data = json.loads(request.POST['compare_data']) # comparison returned by ds_compare
#     compare_result = compare_data['compare_result']
#     print('compare_data from ds_compare', compare_data)
#     # tempfn has .tsv or .jsonld extension from validation step
#     tempfn = compare_data['tempfn']
#     filename_new = compare_data['filename_new']
#     # dsfobj_cur = 'user_whgadmin/sample7c.txt'
#     dsfobj_cur = ds.files.all().order_by('-rev')[0]
#     rev_cur = dsfobj_cur.rev
#
#     # rename file if already exists in user area
#     if Path('media/'+filename_new).exists():
#       fn=os.path.splitext(filename_new)
#       #filename_new=filename_new[:-4]+'_'+tempfn[-11:-4]+filename_new[-4:]
#       filename_new=fn[0]+'_'+tempfn[-11:-4]+fn[1]
#
#     # user said go...copy tempfn to media/{user} folder
#     filepath = 'media/'+filename_new
#     copyfile(tempfn,filepath)
#
#     # and create new DatasetFile instance
#     DatasetFile.objects.create(
#       dataset_id = ds,
#       file = filename_new,
#       rev = rev_cur + 1,
#       format = file_format,
#       upload_date = datetime.date.today(),
#       header = compare_result['header_new'],
#       numrows = compare_result['count_new']
#     )
#
#     # (re-)open files as panda dataframes; a = current, b = new
#     if file_format == 'delimited':
#       adf = pd.read_csv('media/'+compare_data['filename_cur'],
#                         delimiter='\t',
#                         dtype={'id':'str','ccodes':'str'})
#       # TODO: account for geoms and links added by reconciliation
#
#       bdf = pd.read_csv(filepath, delimiter='\t')
#
#       # replace NaN with None
#       adf = adf.replace({np.nan: None})
#       bdf = bdf.replace({np.nan: None})
#
#       bdf = bdf.astype({"id":str,"ccodes":str,"types":str,"aat_types":str})
#       print('reopened old file, # lines:',len(adf))
#       print('reopened new file, # lines:',len(bdf))
#       ids_a = adf['id'].tolist()
#       ids_b = bdf['id'].tolist()
#
#       # delete_srcids = [str(x) for x in (set(ids_a)-set(ids_b))]
#       # TODO: limit these to rows that have changed
#       # OR...flag changed places so they can be omitted from
#       # remaining_srcids = set.intersection(set(ids_b),set(ids_a))
#       # replace_srcids = set.intersection(set(ids_b),set(ids_a))
#
#       # CURRENT PLACES
#       ds_places = ds.places.all()
#       # Place.id list to delete
#       rows_delete = list(ds_places.filter(src_id__in=compare_result['rows_del']).values_list('id',flat=True))
#       # new src_ids list
#       # rows_add = compare_result['rows_add'] # src_ids, no pid yet
#
#       # delete places with (src_)ids missing in new data (CASCADE includes links & geoms)
#       ds_places.filter(id__in=rows_delete).delete()
#
#       def delete_related(pid):
#         # option to keep prior links and geoms matches; remove the rest
#         if not keepg:
#           # keep no geoms
#           PlaceGeom.objects.filter(place_id=pid).delete()
#         else:
#           # leave results of prior matches
#           PlaceGeom.objects.filter(place_id=pid, task_id__isnull=True).delete()
#         if not keepl:
#           # keep no links
#           PlaceLink.objects.filter(place_id=pid).delete()
#         else:
#           # leave results of prior matches
#           PlaceLink.objects.filter(place_id=pid, task_id__isnull=True).delete()
#         PlaceName.objects.filter(place_id=pid).delete()
#         PlaceType.objects.filter(place_id=pid).delete()
#         PlaceWhen.objects.filter(place_id=pid).delete()
#         PlaceRelated.objects.filter(place_id=pid).delete()
#         PlaceDescription.objects.filter(place_id=pid).delete()
#
#       count_updated, count_new = [0,0]
#       # set Place.flag = True *IF CHANGED ONLY*
#       # update place instances w/data from new file
#       rows_replace = []
#       rows_add = []
#       place_fields = {'id', 'title', 'ccodes','start','end'}
#       for index, row in bdf.iterrows():
#         # is there an existing place.src_id?
#         p = ds_places.filter(src_id=row['id']) or None
#         # if so, get a json representation of it
#
#         # new row as json
#         row_dict = row.to_dict()
#         # print(row_dict)
#
#         row_bdf_sorted = {key: val for key, val in sorted(row_dict.items(), key=lambda ele: ele[0])}
#         print('incoming row in ds_update', row_bdf_sorted)
#         # working subset of new row
#         rdp = {key:row_bdf_sorted[key] for key in place_fields}
#         print('rdp subset of row', rdp)
#
#         # some Place attributes
#         start = int(rdp['start']) if 'start' in rdp else None
#         end = int(rdp['end']) if 'end' in rdp and str(rdp['end']) != 'nan' else start
#         minmax_new = [start, end] if start else [None]
#
#         try:
#           # is there corresponding current Place?
#           p = ds_places.get(src_id=rdp['id'])
#           # there is, so build a json object from adf (previous file) dataframe
#           row_adf = adf.loc[adf['id'] == p.src_id]
#           row_adf_json=json.loads((row_adf.to_json(orient='records')))[0]
#           # no particular reason to sort here except for inspection
#           row_adf_sorted = {key: val for key, val in sorted(row_adf_json.items(), key=lambda ele: ele[0])}
#           print('row_adf_sorted', row_adf_sorted)
#           print('row_bdf_sorted', row_bdf_sorted)
#
#           # diff adf and bdf rows
#           # used in reconciliation: title, matches, aat_types, ccodes, lon, lat, geowkt
#           # ignore changes to the rest
#           diffs = diff(row_adf_sorted, row_bdf_sorted, exclude_paths=[
#             "root['description']",
#             "root['title_uri']",
#             "root['title_source']",
#             "root['parent_name']",
#             "root['start']",
#             "root['end']",
#             "root['geo_id']",
#             "root['geo_source']"
#           ])
#           # print('diffs', diffs)
#           # rebuild and flag Place p if *any* changes
#           if row_adf_sorted != row_bdf_sorted:
#             print('re-build Place '+p.title+'('+str(p.src_id)+')')
#             count_updated += 1
#             p.title = rdp['title']
#             p.ccodes = [] if str(rdp['ccodes']) == 'nan' else rdp['ccodes'].replace(' ', '').split(';')
#             p.minmax = minmax_new
#             p.timespans = [minmax_new]
#             # replace related records (PlaceName, PlaceType, etc.)
#             delete_related(p)
#             update_rels_tsv(p, row_bdf_sorted)
#           if diffs:
#             # TODO: is Place.flag necessary?
#             print('significant diffs, set review_wd=None, flag=True')
#             # rows_replace.append(p.id)
#             p.review_wd = None
#             p.flag = True
#           p.save()
#         except:
#           # no corresponding Place, create new one
#           print('new place record needed from rdp', rdp)
#           count_new +=1
#           newpl = Place.objects.create(
#             src_id = rdp['id'],
#             title = re.sub('\(.*?\)', '', rdp['title']),
#             ccodes = [] if str(rdp['ccodes']) == 'nan' else rdp['ccodes'].replace(' ','').split(';'),
#             dataset = ds,
#             minmax = minmax_new,
#             timespans = [minmax_new],
#             flag = True
#           )
#           newpl.save()
#           pobj = newpl
#           rows_add.append(pobj.id)
#           print('new place, related:', newpl)
#           # add related rcords (PlaceName, PlaceType, etc.)
#           update_rels_tsv(pobj, row_bdf_sorted)
#
#       # update numrows
#       ds.numrows = ds.places.count()
#       ds.save()
#
#       # initiate a result object
#       result = {"status": "updated", "update_count":count_updated ,
#                 "new_count":count_new, "del_count": len(rows_delete), "newfile": filepath,
#                 "format":file_format, "rows_add": rows_add}
#       print('update result', result)
#       print("compare_data['count_indexed']", compare_data['count_indexed'])
#
#       #
#       # TODO: reindex
#       # if dataset status is 'accessioning' or 'indexed',
#       # alternately?: if ds.ds_status in ['accessioning', 'indexed']
#       if compare_data['count_indexed'] > 0:
#         es = settings.ES_CONN
#         idx='whg'
#
#         result["indexed"] = True
#
#         # surgically remove as req.
#         if len(rows_delete) > 0:
#           print('rows to delete from index:', rows_delete)
#           # deleteFromIndex(es, idx, rows_delete)
#
#         # update others
#         if len(rows_replace) > 0:
#           print('rows to replace in index:', rows_replace)
#           # replaceInIndex(es, idx, rows_replace)
#
#         # process new
#         if len(rows_add) > 0:
#           print('new rows need reconciliation, then add to index:', rows_add)
#           # notify need to reconcile & accession them
#       else:
#         print('not indexed, that is all')
#
#       # write log entry
#       Log.objects.create(
#         # category, logtype, "timestamp", subtype, note, dataset_id, user_id
#         category = 'dataset',
#         logtype = 'ds_update',
#         note = json.dumps(compare_result),
#         dataset_id = dsid,
#         user_id = request.user.id
#       )
#       ds.ds_status = 'updated'
#       ds.save()
#       # return to update modal
#       return JsonResponse(result, safe=False)
#     elif file_format == 'lpf':
#       print("ds_update for lpf; doesn't get here yet")

"""
  DEPRECATED ds_compare_bak() backup copy 5 Dec 2022; pre-refactor
"""
# def ds_compare_bak():
#   if request.method == 'POST':
#     print('ds_compare() request.POST', request.POST)
#     print('ds_compare() request.FILES', request.FILES)
#     dsid = request.POST['dsid']
#     user = request.user.name
#     format = request.POST['format']
#     ds = get_object_or_404(Dataset, id=dsid)
#     ds_status = ds.ds_status
#
#     # wrangling names
#     # current (previous) file
#     file_cur = ds.files.all().order_by('-rev')[0].file
#     filename_cur = file_cur.name
#
#     # new file
#     file_new = request.FILES['file']
#     tempf, tempfn = tempfile.mkstemp()
#     # write new file as temporary to /var/folders/../...
#     try:
#       for chunk in file_new.chunks():
#         os.write(tempf, chunk)
#     except:
#       raise Exception("Problem with the input file %s" % request.FILES['file'])
#     finally:
#       os.close(tempf)
#
#     print('tempfn,filename_cur,file_new.name', tempfn, filename_cur, file_new.name)
#
#     # validation (tempfn is file path)
#     if format == 'delimited':
#       print('format:', format)
#       try:
#         vresult = validate_tsv(tempfn, 'delimited')
#       except:
#         print('validate_tsv() failed:', sys.exc_info())
#
#     elif format == 'lpf':
#       # TODO: feed tempfn only?
#       # TODO: accept json-lines; only FeatureCollections ('coll') now
#       vresult = validate_lpf(tempfn, 'coll')
#       # print('format, vresult:',format,vresult)
#
#     # if validation errors, stop and return them to modal
#     # which expects {validation_result{errors['','']}}
#     print('vresult', vresult)
#     if len(vresult['errors']) > 0:
#       errormsg = {"failed": {
#         "errors": vresult['errors']
#       }}
#       return JsonResponse(errormsg, safe=False)
#
#     # give new file a path
#     # filename_new = 'user_'+user+'/'+'sample7cr_new.tsv'
#     filename_new = 'user_' + user + '/' + file_new.name
#     # temp files were given extensions in validation functions
#     tempfn_new = tempfn + '.tsv' if format == 'delimited' else tempfn + '.jsonld'
#     print('tempfn_new', tempfn_new)
#
#     # begin report
#     comparison = {
#       "id": dsid,
#       "filename_cur": filename_cur,
#       "filename_new": filename_new,
#       "format": format,
#       "validation_result": vresult,
#       "tempfn": tempfn,
#       "count_indexed": ds.status_idx['idxcount'],
#     }
#     # create pandas (pd) objects, then perform comparison
#     # a = existing, b = new
#     fn_a = 'media/' + filename_cur
#     fn_b = tempfn
#     if format == 'delimited':
#       adf = pd.read_csv(fn_a, file_cur.delimiter)
#       try:
#         bdf = pd.read_csv(fn_b, delimiter='\t')
#       except:
#         print('bdf read failed', sys.exc_info())
#
#       ids_a = adf['id'].tolist()
#       ids_b = bdf['id'].tolist()
#       print('ids_a, ids_b', ids_a[:10], ids_b[:10])
#       # new or removed columns?
#       cols_del = list(set(adf.columns) - set(bdf.columns))
#       cols_add = list(set(bdf.columns) - set(adf.columns))
#
#       # count of *added* links
#       comparison['count_links_added'] = ds.links.filter(task_id__isnull=False).count()
#       # count of *added* geometries
#       comparison['count_geoms_added'] = ds.geometries.filter(task_id__isnull=False).count()
#
#       comparison['compare_result'] = {
#         "count_new": len(ids_b),
#         'count_diff': len(ids_b) - len(ids_a),
#         'count_replace': len(set.intersection(set(ids_b), set(ids_a))),
#         'cols_del': cols_del,
#         'cols_add': cols_add,
#         'header_new': vresult['columns'],
#         'rows_add': [str(x) for x in (set(ids_b) - set(ids_a))],
#         'rows_del': [str(x) for x in (set(ids_a) - set(ids_b))]
#       }
#     # TODO: process LP format, collections + json-lines
#     elif format == 'lpf':
#       # print('need to compare lpf files:',fn_a,fn_b)
#       comparison['compare_result'] = "it's lpf...tougher row to hoe"
#
#     print('comparison (compare_data)', comparison)
#     # back to calling modal
#     return JsonResponse(comparison, safe=False)

"""
DEPRECATED Aug 2022: all pass0 must be reviewed for accessioning
write_idx_pass0(taskid)
called from dataset_detail>reconciliation tab
accepts all pass0 whg matches, indexes new child doc for each
if >1 match, compute parent winner and merge others as children
"""
# def write_idx_pass0(request, tid):
#   task = get_object_or_404(TaskResult,task_id=tid)
#   kwargs=json.loads(task.task_kwargs.replace("'",'"'))
#   ds = get_object_or_404(Dataset, pk=kwargs['ds'])
#   referer = request.META.get('HTTP_REFERER')
#   # get unreviewed pass0 hits
#   hits = Hit.objects.filter(
#     task_id=tid,
#     query_pass='pass0',
#     reviewed=False
#   )
#   # some have more than one hit
#   pids = set([h.place_id for h in hits])
#   chosen = [] # gather parent _ids
#   for pid in pids:
#     hset = [h for h in hits if h.place_id == pid]
#     doc = makeDoc(get_object_or_404(Place, pk=pid))
#     if len(hset) == 1:
#       # index as child
#       parent_id = hset[0].json['whg_id']
#       doc['relation'] = {"name":"child", "parent": parent_id}
#       names = list(set([n['toponym'] for n in doc['names']]))
#       chosen.append(parent_id)
#       pass
#     else:
#       #
#       parent_ids = [h.json['whg_id'] for h in hset]
#       # calc weight as len(sources) + len(links)
#       # create (whg_id, weight) sets
#       parents = [(h.json['whg_id'], len(h.json['sources']) + \
#                   len(h.json['links'])) for h in hset]
#       already = len(set(chosen) & set([p[0] for p in parent_ids])) > 0
#       names = list(set([n['toponym'] for n in doc['names']]))
#       winner_id = topParent(parents,'set')
#       doc['relation'] = {"name":"child", "parent": winner_id}
#
#       demoted = parent_ids.remove(winner_id)
#       demoteParents(demoted, winner_id, pid)
#
#       # log this winner, may be needed
#       chosen.append(winner_id)
#
#     print(len(hset), hset)
#   print('write_idx_pass0(); process '+str(hits.count())+' hits')
#   return HttpResponseRedirect(referer)
