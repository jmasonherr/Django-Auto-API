import json

from django.db import models
from django.http import HttpResponse, QueryDict
from django.forms.models import model_to_dict

from conversion.modelconversion import DataEncoder
from conversion.conversionmap import conversionmap as cm

cxe = DataEncoder()

DEFAULT_EXCLUDE = ['password', 'user_permissions', 'is_staff', 'groups', 'last_login', 'is_superuser', 'date_joined']


class RESTRequest(object):
    """
        Model that augments the default Django request

        Has a DATA attribute that contains both the JSON data passed and the request parameters

    """
    def __init__(self, request):
        self._req = request
        self._data = QueryDict({}).copy()
        if request.method == 'GET':
            self._data.update(request.GET.copy())
        if request.method == 'POST':
            request.POST = request.POST.copy()
            self._data.update(request.POST.copy())
        if request.method == 'PUT':
            request.PUT = QueryDict({}).copy()
        if request.method == 'DELETE':
            request.DELETE = QueryDict({}).copy()
        if 'json' in request.META.get('CONTENT_TYPE', ''):
            try:
                js = json.loads(request.body)
                self._data.update(js)
                getattr(request, request.method).update(js)
            except ValueError:
                pass

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except:
            # Default behaviour
            return object.__getattribute__(self._req, name)

    @property
    def DATA(self):
        return self._data


def nestedSerialize(obj):
    """ Covers the bases of dealing with User objects"""
    if hasattr(obj, 'serialize'):
        return obj.serialize() # request=request)
    model_dict = model_to_dict(obj, exclude=DEFAULT_EXCLUDE)
    model_dict['unicode'] = obj.__unicode__()
    return model_dict


def serializeQuery(qry, request=None):
    """
        Make the query return everything in 1-2 calls, instead of multiple for each
        returns a list of the objects returned, and their serialized data as well

        Takes Django Query as argument
        TODO: Add hashing and caching
    """

    cls = qry.model

    # Fields that will not be serialized
    exclude_fields = set()

    # Objects that will be serialized with the target model as nested objects
    related_objs = set()

    # Fields you want the count of.  Named as fieldname__count
    counted_relationships = set()

    # Fields not accessible through API
    if hasattr(cls, 'get_exclude_fields'):
        exclude_fields = set(cls.cls_exclude_fields(request))

    # Prefetch fields allow you to prevent unneccessary extra queries
    prefetch_fields = set([x[0].name for x in cls._meta.get_m2m_with_model()])
    prefetch_fields.difference_update(exclude_fields)

    # Objects that should be nested in serialization
    if hasattr(cls, 'get_related_objs'):
        related_objs = set(cls.get_related_objs())
        # Speed up accession of any related objects by including them in the query
        if related_objs:
            qry = qry.select_related(*related_objs)

    ok_fields = set()
    for x in cls._meta.fields:
        # Change foreign keys to key_id unless they're to be serialized
        ok_fields.add(x.name + '_id' if getattr(x, 'rel') and x.name not in related_objs else x.name)
    ok_fields.difference_update(exclude_fields)

    # Counts of relationships
    if hasattr(cls, 'get_count_of'):
        counted_relationships = set(cls.get_count_of())
        if counted_relationships:
            count_list = []
            for x in counted_relationships:
                count_list.append(models.Count(x))
                ok_fields.add(x + '__count')
            qry = qry.annotate(*count_list)

    if hasattr(cls, 'get_avg_of'):
        avg_relationships = set(cls.get_avg_of())
        if avg_relationships:
            avg_list = []
            for x in avg_relationships:
                avg_list.append(models.Avg(x))
                ok_fields.add(x + '__avg')
            qry = qry.annotate(*avg_list)

    # Execute query with many to many prefetched
    objs = list(qry.prefetch_related(*prefetch_fields).all())

    # Final list of dictionaries to be returned
    all_data = []

    # Iterate over results, populating dictionaries
    for obj in objs:
        serialized_data = {}
        for field in ok_fields:
            field_name = field.replace('_id', '') if field.endswith('_id') and field != 'stripe_id' else field

            val = getattr(obj, field_name) if field_name in related_objs else getattr(obj, field)
            if val:

                if field == 'app_user':
                    # Get its excluded fields, serialize it
                    val = nestedSerialize(val)

                # Nest the object if its a relationship
                if isinstance(val, models.Model):
                    # Get its excluded fields, serialize it
                    val = nestedSerialize(val)

            serialized_data[field_name] = val


        for field in prefetch_fields:
            serialized_data[field] = [x.pk for x in getattr(obj, field).all()]
        all_data.append(serialized_data)

    return objs, all_data


def serializeInstanceLikeQry(model, request=None):
    """ Return the model serialized as if it were a query, so that hidden fields are absent and nested fields are present"""
    return serializeQuery(model.__class__.objects.filter(pk=model.pk), request=request)[1][0]


def qryToJSResponse(qry, resave=False, request=None):
    """ Got tired of writing this over and over again, so I made a method"""
    objs, data = serializeQuery(qry, request=request)
    if resave:
        for o in objs:
            o.save()
    return HttpResponse(cxe.encode(data), content_type='application/json')

