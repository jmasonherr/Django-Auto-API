import logging
import random
import json
import inspect
from django.conf import settings
from django.template import RequestContext
from django.db.models.query import QuerySet
from django.forms.models import model_to_dict
from django.shortcuts import render_to_response
from django.http import Http404, HttpResponse, HttpResponseForbidden

from users.models import SGUser

from filter import build_filters
from inspector import build_routes
from permission import _superadmin, _permission
from serialization import RESTRequest, serializeInstanceLikeQry, qryToJSResponse

from conversion.modelconversion import DataEncoder
from django.views.decorators.csrf import csrf_exempt
from django.core.context_processors import csrf
from django.middleware.csrf import get_token

from django.contrib.auth.models import User, check_password
from django.contrib.auth import authenticate, login
cxe = DataEncoder()


def _slicepassword(p):
    i1 = random.randint(0, len(p) - 6)
    i2 = random.randint(i1, len(p) -1)
    return p[i1:i2][:6]

def get_exclude_fields(obj, request=None):
    if inspect.isclass(obj):
        return obj.cls_exclude_fields(request)
    return obj.get_exclude_fields(request)

def build_login_response(request, user):
    resp = {
            'csrf': str(get_token(request)),
            'session_key': _slicepassword(user.password),
            'user_id': user.sg_user.id,
    }
    return HttpResponse(cxe.encode(resp), content_type='application/json', status=200)

@csrf_exempt
def error_report(request):
    """ Log an error sent from another application"""
    logging.error('ERROR LOGGED FROM REMOTE API CLIENT')
    logging.error(request.GET.get('error'))
    return HttpResponse('ok');


@csrf_exempt
def api_login(request):
    data = json.loads(request.body)
    # Add user check?
    username = data['username']
    password = data['password']
    user = authenticate(username=username, password=password)
    if user:
        request.user = user
        return build_login_response(request, user)
    else:
        raise Http404()

@csrf_exempt
def api_signup(request):
    data = json.loads(request.body)
    # Add user check?
    username = data['username']
    password = data['password']
    from users.models import SGUser
    sgu = SGUser.check_against_email(username, username)
    if sgu.id:
        user = authenticate(username=username, password=password)
        if(user):
            return build_login_response(request, user)
        else:
            return HttpResponseForbidden('Email already in use')
    else:
        sgu.name = username.split('@')[0]
        sgu.temp_email = username
        sgu.app_user = User.objects.create_user(username=username, email=username, password=password)
        sgu.app_user.first_name = sgu.name
        sgu.app_user.save()
        sgu.save()
        
        # Make them a stripe user
        from payment_platform.models import PPCustomer
        PPCustomer.get_for_user(sgu)
        request.user = sgu.app_user
        return build_login_response(request, sgu.app_user)


    
    

def api_home(request):
    """ Simple home page that lists the possible endpoints for the API"""
    d = {
        'api_prefix': settings.URL_PREFIX,
    }
    d['routes'], _ = build_routes()
    return render_to_response(
        "auto_api/home.html",
        d, context_instance=RequestContext(request))
        
@csrf_exempt
def route_api(request, modelname, id=None, nested=None):
    """ 
    Most of the API is contained here.  Nested can be a relationship or a method name that will be transformed into METHOD_nested.
    
        ex: GET /api/book/1/get_publisher_revenue/ will call GET_get_publisher_revenue on the 'Book' object
    
    Takes a request, /(modelname)/(id)/(nested)/
    
    
    """
    # Optimistic with the status code in the beginning
    code = 200
    

    
    # Convert the request into a form that contains DATA for convenience later
    request = RESTRequest(request)

    # Add in resave feature to update search indexes
    resave = request.GET.get('_resave_', False)

    # Check the user status, if its API logged in, use that
    if request.META.get('HTTP_X_APIUSER') and request.META.get('HTTP_X_SESSION_KEY'):
        try:
            sguser = SGUser.objects.get(pk=request.META.get('HTTP_X_APIUSER'))

        except SGUser.DoesNotExist:

            sguser = None
            logging.info('Error logging in  SGUser through API with ID %s' % request.META.get('HTTP_X_APIUSER'))

        if sguser and request.META.get('HTTP_X_SESSION_KEY'):
            if request.META.get('HTTP_X_SESSION_KEY') in sguser.app_user.password:
                request.user = sguser.app_user
            else:
                return HttpResponseForbidden('Incorrect password')

    # Check if the user has permission to execute that method
    permission_method = 'has_%s_permission' % request.method
    
    # Set number of items returned
    queryEnd = request.DATA.get('limit', settings.API_REQUEST_LIMIT)
    if 'limit' in request.DATA:
        del request.DATA['limit']
    
    # Create any query filters or sort order
    filters = {}
    sort = None
    if 'sort' in request.DATA:
        sort = request.DATA.get('sort', None)
        del request.DATA['sort']

    # Pagination
    queryStart = int(request.DATA.get('page', 0)) * settings.API_PAGE_COUNT
    #queryEnd = 100
    if 'page' in request.DATA:
        del request.DATA['page']
        queryEnd = queryStart + settings.API_PAGE_COUNT
    


    # Get all info on routes, so we know what to do with this request
    #if not routes:
    routes, _ = build_routes()

    if modelname not in routes:
        logging.error(' model name  %s not in routes' % modelname)
        raise Http404()

    # Get the appropriate model
    model = routes[modelname]['model']

    # Are we looking at a specific model or its relations?
    if id:
        try:
            model = model.objects.get(pk=id)
        except model.DoesNotExist:
            logging.error(' model name  %s with id %s not in routes' % (modelname, str(id)))
            raise Http404()

    # Not a specific model, probably GET list or POST to create
    else:
        if request.method == 'GET':
            if _permission(request, model, 'has_GET_permission_list') is False:
                return HttpResponseForbidden()
            qry = model.objects.filter(**build_filters(model, request.DATA))
            if sort:
                qry = qry.order_by(sort)
            return qryToJSResponse(qry[queryStart:queryEnd], resave, request=request)

        elif request.method == 'POST':
            if not _superadmin(request) and not model.has_POST_create_permission(request):
                return HttpResponseForbidden()
            # If ther's an id, use classmethod, otherwise look further
        else:
            if _permission(request, model, permission_method) is False:
                return HttpResponseForbidden()

    # Do we want a nested attribute/collection or method on the object?
    if nested:

        # Check to see if whatthey want is not allowed by the api
        if hasattr(model, 'get_exclude_fields') and nested in get_exclude_fields(model, request): # and not model.has_excluded_permission():
            return HttpResponseForbidden()

        ## Look first at the model's methods, this way a collection can be overloaded by some more important subset of the relationship.  We may only want active memberships for example
        if hasattr(model, '%s_%s' % (request.method.upper(), nested)):

            # Its calling a method on the model that is POST_purchase or GET_names
            fn = getattr(model, '%s_%s' % (request.method.upper(), nested))
            result = fn(request)
            # Check to see if its a Query.  If it is, we can continue filtering and
            # sort it
            if isinstance(result, QuerySet):
                filters = build_filters(result.model, request.DATA)
                if filters:
                    result = result.filter(**filters)
                if sort:
                    result = result.order_by(sort)
                return qryToJSResponse(result[queryStart:queryEnd], resave, request=request)

            # Not a query, just a response
            else:
                return result

        # Look in foreign keys
        elif nested in routes[modelname]['fks']:
            # Its a foreign key, return a single model
            model = getattr(model, nested)
            if not model:
                logging.error('%s is not a foreign key to %s' % (nested, model))
                raise Http404()

            # Make sure there's permission on that model
            if _permission(request, model, permission_method) is False:
                return HttpResponseForbidden()
            ## TODO: handle put
            if model:
                if resave:
                    model.save()
                return HttpResponse(cxe.encode(serializeInstanceLikeQry(model)), content_type='application/json')
            logging.error('%s is not a foreign key to %s unspecifiec error' % (nested, model))
            raise Http404()

        # Look in many to many relations
        else: #elif nested in routes[modelname]['m2m'] or nested in routes[modelname]['reverse_fks']:
            # Many to many, model is going to become a list of items
            if request.method != 'GET':
                return HttpResponseForbidden()
            model = getattr(model, nested)
            filters = build_filters(model, request.DATA)

            #TODO: check for get permissions
            qry = model.filter(**filters)
            if sort:
                qry = qry.order_by(sort)[queryStart:queryEnd]
            return qryToJSResponse(qry, resave, request=request)

#        else:
#            logging.error(routes[modelname]['reverse_fks'])
#            logging.error('%s goes to default 404 from %s' % (nested, model))
#
#            raise Http404()

    # Just want to act on a specific model
    else:
        # Make sure they have access to this model

        if request.method == 'POST':
            if not _superadmin(request) and not model.has_POST_create_permission(request):
                return HttpResponseForbidden()
            # If ther's an id, use classmethod, otherwise look further
        else:
            if _permission(request, model, permission_method) is False:
                return HttpResponseForbidden()
        creating = False
        if request.method == 'POST':
            # make an instance of the class
            creating = True
            code = 201
            ## The pre create hook returns a model or none.   if None, a new blank one is made

            if hasattr(model, 'api_pre_create_hook'):
                # The pre create hook can return an instance, if it does not, make a new one
                instnce = model.api_pre_create_hook(request)
                if instnce:
                    model = instnce
                else:
                    model = model()
            else:
                model = model()

        # We should have an instance of a model at this point, if its creating or updating
        if request.method in ['PUT','PATCH','POST']:
            if creating is False:
                if hasattr(model, 'api_pre_update_hook'):
                    model.api_pre_update_hook(request)
    
            # Update model, return
            model.update_fields(request.DATA, request=request)
            model.update_m2m(request.DATA, request=request)
            model.save()
            
            # Choose appropriate hook
            if creating:
                if hasattr(model, 'api_post_create_hook'):
                    model.api_post_create_hook(request)
            else:
                if hasattr(model, 'api_post_update_hook'):
                    model.api_post_update_hook(request)
        resp = {}
        
        # They want to delete the object
        if request.method == 'DELETE':
            code = 204
            model.delete()
        else:
            #resp = model.serialize(request=request)
            # Serialization is more consistent if done from a query
            resp = serializeInstanceLikeQry(model)
            if resave:
                model.save()
        return HttpResponse(cxe.encode(resp), content_type='application/json', status=code)





