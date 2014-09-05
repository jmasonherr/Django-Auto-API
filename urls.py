from django.conf.urls import patterns, url

#(?P<variable_a>(\d+))

urlpatterns = patterns('',
    url(r'^login/?$', 'auto_api.views.api_login'),
    url(r'^signup/?$', 'auto_api.views.api_signup'),
    url(r'^error/?$', 'auto_api.views.error_report'),


    url(r'^(\w+)/?$', 'auto_api.views.route_api'),
    url(r'^(\w+)/(\w+)/?$', 'auto_api.views.route_api'),
    url(r'^(\w+)/(\w+)/(\w+)/?$', 'auto_api.views.route_api'),
    url(r'^/?$', 'auto_api.views.api_home'),
)