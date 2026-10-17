"""
Server-side verification of Google reCAPTCHA v2 tokens.
"""

import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


def verify(token, remote_ip=None):
    """Return True only if Google confirms `token` (the g-recaptcha-response value).

    Fails closed: a missing token, missing secret key, network error or bad
    reply all count as a failed check.
    """
    if not token or not settings.RECAPTCHA_SECRET_KEY:
        return False
    payload = {'secret': settings.RECAPTCHA_SECRET_KEY, 'response': token}
    if remote_ip:
        payload['remoteip'] = remote_ip
    try:
        request = urllib.request.Request(VERIFY_URL, data=urllib.parse.urlencode(payload).encode())
        with urllib.request.urlopen(request, timeout=5) as response:
            return bool(json.load(response).get('success'))
    except Exception:
        logger.exception("reCAPTCHA verification request failed")
        return False
