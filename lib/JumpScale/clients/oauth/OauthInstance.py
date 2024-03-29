import datetime
import urllib.request, urllib.parse, urllib.error
import os
import string
import random


from JumpScale import j


class OauthInstance():
    def __init__(self, addr, accesstokenaddr, id, secret, scope, redirect_url, user_info_url, logout_url, instance):
        if not addr:
            hrd = j.application.getAppInstanceHRD('oauth_client', instance)
            self.addr = hrd.get('instance.oauth.client.url')
            self.accesstokenaddress = hrd.get('instance.oauth.client.url2')
            self.id = hrd.get('instance.oauth.client.id')
            self.scope = hrd.get('instance.oauth.client.scope')
            self.redirect_url = hrd.get('instance.oauth.client.redirect_url')
            self.secret = hrd.get('instance.oauth.client.secret')
            self.user_info_url = hrd.get('instance.oauth.client.user_info_url')
            self.logout_url = hrd.get('instance.oauth.client.logout_url') 
        else:
            self.addr = addr
            self.id = id
            self.scope = scope
            self.redirect_url = redirect_url
            self.accesstokenaddress = accesstokenaddr
            self.secret = secret
            self.user_info_url = user_info_url
            self.logout_url = logout_url
        self.state = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(30))

    @property
    def url(self):
        params = {'client_id' : self.id, 'redirect_uri' : self.redirect_url, 'state' : self.state, 'response_type':'code'}
        if self.scope:
            params.update({'scope' : self.scope})
        return '%s?%s' % (self.addr, urllib.parse.urlencode(params))