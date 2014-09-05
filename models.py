from django.db import models

# Create your models here.

import logging
import random
import inspect
import datetime
from dateutil.relativedelta import relativedelta
from django.forms.models import model_to_dict
from django.db import models, IntegrityError
from django.http import HttpResponse, Http404
from django.conf import settings
from django.utils.timezone import make_aware, make_naive, utc, localtime

from pytz import timezone

from conversion.conversionmap import conversionmap
from conversion.conversionmethods import convertFk
from conversion.modelconversion import DataEncoder
from auto_api.filter import build_filters
from auto_api.serialization import serializeQuery

cxe = DataEncoder()

IGNORE_TYPES = [None, [None,], 'None', ['None',]]



def _get_or_create(cls, **kwargs):
    """ Better get or create method for django objects """
    try:
        obj = cls.objects.get(**kwargs)
        return obj, False
    except cls.DoesNotExist:
        obj = cls(**dict((k,v) for (k,v) in kwargs.items() if '__' not in k))
        return obj, True
    except cls.MultipleObjectsReturned:
        return cls.objects.filter(**kwargs)[0], True

class UpdateableMixin(object):

    """ 
        Overloadable methods to allow control of fields and permission
    
    """
    exclude_fields = [] # Control which fields to exclude
    
    @classmethod
    def cls_exclude_fields(cls, request):
        """ Should return a list, allows fine grain control of which to exclude based on request/user/etc.. for queries and lists"""
        return cls.exclude_fields

    def get_exclude_fields(self, request=None):
        """ Should return a list, allows fine grain control of which to exclude based on request/user/etc.. for individual models"""
        return self.__class__.exclude_fields

    @classmethod
    def get_related_objs(cls):
        """ All related objects that should be prefetched in a query focusing on this object"""
        return []

    @classmethod
    def get_count_of(cls):
        """ All related objects that a count should be returned for.  ['purchases'] will add field 'purchases__count' """
        return []

    @classmethod
    def has_POST_create_permission(cls, request):
        """ Customize access POST for creation purposes"""
        return False

    def has_POST_permission(self, request):
        """ Customize access to POST for custom actions on the model"""
        return False

    @classmethod
    def has_GET_permission_list(cls, request):
        """ Customize access on GET requests"""
        return True

    def has_PUT_permission(self, request):
        """ Customize edit on specific objects"""
        return False

    def has_PATCH_permission(self, request):
        return self.has_PUT_permission(request)

    def has_GET_permission(self, request):
        """ Customize access on GET requests for custom actions on the model"""
        return True

    def has_DELETE_permission(self, request):
        """ Delete request permission"""
        return False

    @classmethod
    def api_pre_create_hook(cls, request):
        """ This should return None or a new instance of the class itself"""
        return cls()

    def api_post_create_hook(self, request):
        """ No expected return value"""
        pass
    
    def api_pre_update_hook(self, request):
        """ No expected return value"""
        pass

    def api_post_update_hook(self, request):
        """ No expected return value"""
        pass

    def api_pre_delete_hook(self, request):
        """ No expected return value"""
        pass

    @classmethod
    def api_post_delete_hook(cls, request):
        """ No expected return value"""
        pass


    @classmethod
    def get_or_create(cls, **kwargs):
        """ Puts a more tolerant 'get_or_create' directly on class """
        return _get_or_create(cls, **kwargs)


    def update_m2m(self, d, nested_update=False, m2mc=None, request=None):
        """ 
            Update many to many fields
            Builds a name to object manager dictionary - {'categories': <django category related object manager>} so that you can look up each relationship by its common name
        """
        excluded = self.get_exclude_fields(request)

        if not m2mc:
            m2mc = dict([(x.name, x) for x in self._meta.many_to_many])

        for k in d:
            v = d[k]
            # Deal with querydicts
            if hasattr(d, 'getlist'):
                if isinstance(d.get(k), list):
                    v = d.get(k)
                else:
                    v = d.getlist(k)

            if k in IGNORE_TYPES:
                continue
            if v in IGNORE_TYPES:
                continue

            # Don't allow people to update private fields with the api
            if k in excluded:
                continue
            ## its a many to many
            if k in ['pk', 'id']:
                continue

            # Sometimes a list comes in as unicode
            if type(v) == unicode:
                v = [v]

            if k in m2mc:
                m2m_manager = getattr(self, k)
                existing = set([str(r.pk) for r in list(m2m_manager.all())])
                newList = set()

            
                for x in v:
                    # this is a whole object with other attributes, we just want the id
                    if type(x) == dict:
                        x = convertFk(x)
                        if x != 0 and x != '0':
                            newList.add(str(x))
                    # this is just an id, add it
                    else:
                        if x and str(x) != '0':
                            newList.add(str(x))

                toDelete = existing.difference(newList)
                toAdd = newList.difference(existing)

                for a in toDelete:
                    if a:
                        m2m_manager.remove(a)

                for a in toAdd:
                    try:
                        if a:
                            m2m_manager.add(a)
                    except IntegrityError:
                        logging.info(v)
                        logging.info(x)
                        logging.info('Integrity error adding field %s' % (str(k)))

    def update_fields(self, d, fc=None, request=None):
        """ Update all fields that are NOT many to many"""
        # make a dictionary of field names to fields
        excluded = self.get_exclude_fields(request)

        if not fc:
            fc = dict([(x.name, x) for x in self._meta.fields])
        for k, v in d.iteritems():

            # Prevent fields that should not be public to the API from being edited
            if k in IGNORE_TYPES or v in IGNORE_TYPES or k in excluded:
                continue

            # Iterate over all fields
            if k in fc:
                # Check for values coming in as lists
                if type(v) == list:
                    if len(v) == 1:
                        v = v[0]
                    else:
                        logging.info(k)
                        logging.info(v)
                        raise Exception, 'Single value %s given multiple values %s' % (k, v)

                fld = fc[k]
                if fld.editable:
                
                    # Get the type of the field we're going to populate
                    t = type(fld)
                    
                    # Stripe objects need to be a dict first
                    if hasattr(v, 'to_dict'):
                        v = v.to_dict()


                    if t in conversionmap:

                        # Watch for empty date/times, they are a problem
                        if t in [models.DateTimeField, models.DateField, models.TimeField] and not v:
                            continue
                        try:
                            convertedValue = conversionmap[t]['fromRequest'](v)
                        except Exception, e:
                            logging.info('convertion failed for %s from %s' % (k, v))
                            logging.info(v)
                            logging.info(e)
                            continue
                        
                        if t == models.ForeignKey or t == models.OneToOneField:
                            if convertedValue:
                                thrumodel = fld.rel.to
                                # PATCH.  Checks for existence.   Likely final version
                                if not thrumodel.objects.filter(pk=convertedValue).exists():
                                    logging.info('Addition of foreign key failed for ')
                                    logging.info(thrumodel)
                                    logging.info('on')
                                    logging.info(k)
                                    logging.info(v)
                                    logging.info('for')
                                    logging.info(self)
                                    logging.info('using key')
                                    logging.info(convertedValue)
                                    ## TODO: make this accomodate whoe objects anew
                                    continue
                                convertedValue, created = _get_or_create(thrumodel, pk=convertedValue)
                                if type(v) == 'dict':
                                    # if its a dictionary, we can make a new one.  if not, we just skip it and relationship is not added
                                    try:
                                        convertedValue.update_fields(v)
                                    except IntegrityError:
                                        logging.info('Integrity error updating fields')
                                        logging.info(convertedValue)
                                    if not convertedValue.pk:
                                        convertedValue.save()
                                    convertedValue.update_m2m(v)
                                    convertedValue.save()
                        setattr(self, k, convertedValue)

                    else:
                        setattr(self, k, v)

        self.save()

    def get_current_week(self):
        """ Returns start and end datetime objects of current week, with week starting on Monday """
        return _get_current_week()

    ### Remove the need for serializers ###
    def notFound(self):
        raise Http404()

    def jsonResponse(self, jsReady, code=200):
        return HttpResponse(cxe.encode(jsReady), content_type='application/json', status=code)
    
    def deny(self, msg='You do not have permission'):
        return self.jsonResponse({'status': 'error', 'message': msg}, code=403)

    def toJSON(self, request=None):
        return cxe.encode(self.serialize(request=request))

    def serialize(self, nested=False, request=None):
        """ Serializes an object, leaving off many to many if it is nested in another to speed up queries. """
        exclude = []
        if hasattr(self, 'get_exclude_fields'):
            exclude.extend(self.get_exclude_fields(request))
        if nested is True:
            exclude.extend([x.name for x in self.__class__._meta.many_to_many])
        a = model_to_dict(self, exclude=exclude)
        # Don't know why this is necessary
        if hasattr(self, 'created'):
            if hasattr(self.created, 'isoformat'):
                a['created'] = self.created.isoformat()
        a['unicode'] = self.__unicode__()
        return a


