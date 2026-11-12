import tempfile
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings

from . import spa

INDEX = '<!doctype html><div id="root"></div><script type="module" src="/static/spa/assets/index-Ab12.js"></script>'


class SpaIndexTests(TestCase):
    def setUp(self):
        spa._cached_index.cache_clear()
        build = tempfile.TemporaryDirectory()
        self.addCleanup(build.cleanup)
        (Path(build.name) / "spa").mkdir()
        (Path(build.name) / "spa" / "index.html").write_text(INDEX, encoding="utf-8")
        self.build_dirs = override_settings(STATICFILES_DIRS=[build.name])
        self.build_dirs.enable()
        self.addCleanup(self.build_dirs.disable)
        self.addCleanup(spa._cached_index.cache_clear)

    def test_serves_index_for_the_app_root_and_deep_links(self):
        for url in ("/app", "/app/", "/app/students/6b3f1c1e/edit"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '<div id="root"></div>')

    def test_is_never_cached_and_sets_a_csrf_cookie(self):
        response = self.client.get("/app/")
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertIn("csrftoken", response.cookies)

    def test_needs_no_login(self):
        # The app shows its own login page; the API enforces auth.
        self.assertEqual(self.client.get("/app/login").status_code, 200)

    def test_only_answers_safe_methods(self):
        self.assertEqual(self.client.post("/app/").status_code, 405)

    def test_explains_a_missing_build(self):
        with override_settings(STATICFILES_DIRS=[tempfile.gettempdir() + "/no-such-build"]):
            spa._cached_index.cache_clear()
            response = self.client.get("/app/")
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "npm run build", status_code=503)

    def test_does_not_capture_other_paths(self):
        self.assertNotEqual(self.client.get("/application").status_code, 200)


class ImmutableStaticFileTests(TestCase):
    def test_hashed_files_are_immutable_but_index_is_not(self):
        immutable = settings.WHITENOISE_IMMUTABLE_FILE_TEST
        self.assertTrue(immutable("", "/static/css/app.2bb0a3640c85.css"))
        self.assertTrue(immutable("", "/static/spa/assets/index-B1x9fQzA.js"))
        self.assertFalse(immutable("", "/static/spa/index.html"))
        self.assertFalse(immutable("", "/static/css/app.css"))
