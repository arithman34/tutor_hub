"""Describes CookieJWTAuthentication in the OpenAPI schema.

drf-spectacular finds this extension by its target class once the module is
imported (see AccountsConfig.ready).
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension

from .cookies import ACCESS_COOKIE


class CookieJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.CookieJWTAuthentication"
    name = ["jwtAuth", "cookieAuth"]

    def get_security_definition(self, auto_schema):
        return [
            {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
            {
                "type": "apiKey",
                "in": "cookie",
                "name": ACCESS_COOKIE,
                "description": "Set by POST /api/v1/auth/cookie/login. Unsafe methods also need the X-CSRFToken header.",
            },
        ]
