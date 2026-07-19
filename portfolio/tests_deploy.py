import os
import pathlib
import subprocess
import sys

from django.conf import settings
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, TestCase, override_settings

# Strong, obviously-fake key used only to isolate this test run from the
# operator's real SECRET_KEY strength. Injecting a strong key here proves
# Phase 1's settings.py logic is correct independent of the real .env value.
# Must be 50+ chars with 5+ unique characters and no 'django-insecure-'
# prefix, or Django's own check --deploy flags it as weak (security.W009).
TEST_SECRET_KEY = 'a1B2c3D4e5F6g7H8i9J0k-L_m+N=o!P#q$R%s&T*u(V)w1X2y3Z4'


def _dummy_get_response(request):
    return HttpResponse('ok')


class SettingsHardeningTests(TestCase):
    """Deterministic proof of the production settings hardening (Phase 1)."""

    @override_settings(
        DEBUG=False,
        SECURE_SSL_REDIRECT=True,
        ALLOWED_HOSTS=['testserver'],
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_forwarded_https_request_is_not_redirected(self):
        middleware = SecurityMiddleware(_dummy_get_response)
        request = RequestFactory().get('/', HTTP_X_FORWARDED_PROTO='https')

        response = middleware(request)

        self.assertEqual(response.status_code, 200)

    @override_settings(
        DEBUG=False,
        SECURE_SSL_REDIRECT=True,
        ALLOWED_HOSTS=['testserver'],
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_plain_http_request_without_header_is_redirected_to_https(self):
        middleware = SecurityMiddleware(_dummy_get_response)
        request = RequestFactory().get('/')

        response = middleware(request)

        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].startswith('https://'))

    @override_settings(
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_is_secure_true_with_forwarded_proto_header(self):
        request = RequestFactory().get('/', HTTP_X_FORWARDED_PROTO='https')

        self.assertTrue(request.is_secure())

    @override_settings(
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_is_secure_false_without_forwarded_proto_header(self):
        request = RequestFactory().get('/')

        self.assertFalse(request.is_secure())

    def test_check_deploy_exits_clean_with_debug_false(self):
        env = {
            **os.environ,
            'DEBUG': 'False',
            'SECRET_KEY': TEST_SECRET_KEY,
        }
        result = subprocess.run(
            [sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode, 0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_settings_source_is_env_driven_and_fail_closed(self):
        source = pathlib.Path(settings.BASE_DIR, 'config', 'settings.py').read_text()

        self.assertIn("config('CSRF_TRUSTED_ORIGINS'", source)
        self.assertIn("config('ALLOWED_HOSTS'", source)
        self.assertIn("config('DEBUG', default=False", source)
        # The removed hardcoded CSRF origin literal must not reappear.
        # (Framework doc-reference comments such as docs.djangoproject.com
        # legitimately contain '.com' and are not domain literals.)
        self.assertNotIn('placeholder.example.com', source)
